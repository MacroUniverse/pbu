#! /usr/bin/python3
# a very simple incremental backup utility

import os, platform, sys, shutil, datetime, time, errno, functools
import hashlib # for sha1sum
import subprocess # for calling shell command
import natsort # natural sort folder name

if platform.system() == 'Linux':
    # Check if the script is run as root (UID 0)
    if os.geteuid() != 0:
        print('must run as root!')
        exit(1)

# globle variables (with default values)
# should only be set once at most
class gvars:
    def __init__(self):
        # ================== user params ========================
        self.base_path = '/mnt/z/' # directory to backup
        self.folders = ['abc', 'def'] # folder(s) in base_path to backup (use [] to detect sub-folders with .pbu)

        # /mnt/c/Users/addis/  /mnt/e/
        self.dest = '/mnt/y/pbu/' # backup directory for [folder.pbu] folders
        self.ver = '' # version number (use yyyymmdd.hhmmss if empty)

        self.start = '' # skip until this folder.
        self.ignore_folders = {'@eaDir'} # ignore these folders.
        self.ignore = {'Thumbs.db', 'desktop.ini'} # ignored file names
        self.ignore_ext = {'.baiduyun.uploading.cfg'} # ignored file extensions

        self.lazy_mode = True # hash a file only when size or time changed [should change this option to the partial checksum algo in rm_repeat]
        self.lazy_check = True # if nothing is deleted or changed, skip manual check
        self.debug_mode = False # won't delete `pbu-norehash`, check incremental backup
        self.hash_name = False # replace folder and file names with hash (first make sure tree is clean)
        
        self.path_max_sz = 100 # max length for file path display
        self.auto_save_period = 120 # time (seconds) period of auto-save to .pbu-new-asv
        self.print_period = 30 # time (seconds) period of printing a line of report, use -1 to print every file before using '\r' to erase it
        
        # ================ internal constants ===================
        # .pbu line forma
        self.beg_size = 0; self.end_size = 14 # size string (14)
        self.beg_time = 15; self.end_time = 30 # time string (15)
        self.beg_hash = 31; self.end_hash = 71 # sha1 string (40)
        self.beg_path = 72 # path string

g = gvars()

# copy folder recursively
def copy_folder(src, dst):
    try:
        # will preserve metadata
        shutil.copytree(src, dst, symlinks=True) # don't follow symlinks
    except OSError as exc: # python >2.5
        if exc.errno in (errno.ENOTDIR, errno.EINVAL):
            shutil.copy2(src, dst) # will preserve metadata
        else:
            # raise
            print('copy_folder() failed! you might not have permission!')
            exit(1)

# utility for sorting .pbu (accordig to '[size] [hash] [path]')
def pbu_line_cmp(line, line1):
    str = line[:g.beg_time] + line[g.end_time:]
    str1 = line1[:g.beg_time] + line1[g.end_time:]
    if str < str1: return -1
    if str1 < str: return 1
    return 0

def pbu_path_p10_cmp(line, line1):
    str = line[g.beg_path+10:]
    str1 = line1[g.beg_path+10:]
    if str < str1: return -1
    if str1 < str: return 1
    return 0

# print a line then move cursor to the front
last_print_time = 0

def print_tmp_line(str):
    global last_print_time
    if len(str) > g.path_max_sz:
        str = str[:g.path_max_sz-3] + '...'
    elif len(str) < g.path_max_sz:
        str = str + ' '*round((g.path_max_sz-len(str))*1.5)
    
    if g.print_period < 0:
        print(str+'\r', end="", flush=True) # \r moves the cursur the start of line
    else:
        # print current status at least every `current_time` seconds
        current_time = time.time()
        if current_time - last_print_time > g.print_period:
            print(str, flush=True)
            last_print_time = current_time

# generate .pbu
# return list of lines of in `.pbu` format
# write to file if fname provided
# lazy mode: input the `pbu` (list of line) from `.pbu`
def size_time_sha1_cwd(fname=None, pbu=None, pbu_asv=None):
    flist = file_list_r('./')
    lines = []
    Nf = len(flist)
    ignore = set(g.ignore)
    if fname != None:
        ignore.add(fname)

    # create dict from '[size] [time] [path]' to [sha1]
    if g.lazy_mode:
        hash_dict = {}
        for line in pbu:
            key = line[:g.end_time] + line[g.beg_path-1:]
            hash_dict[key] = line[g.beg_hash:g.end_hash]
        for line in pbu_asv:
            key = line[:g.end_time] + line[g.beg_path-1:]
            hash_dict[key] = line[g.beg_hash:g.end_hash]
    warn_link = True
    auto_save_time = time.time()
    for i in range(Nf):
        f = flist[i][2:]
        if not os.path.exists(f): # deleted just now
            continue
        name = os.path.split(f)[1]
        if name in ignore:
            continue
        if os.path.islink(f):
            if warn_link:
                print('### warning: symlink is currently not supported! ignored!')
                warn_link = False
            continue
        f_ignored = False
        for ext in g.ignore_ext:
            if name[-len(ext):] == ext:
                f_ignored = True; break
        if f_ignored:
            continue
        # get size and time
        size_str = '%014d' % os.stat(f).st_size
        time_str = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y%m%d.%H%M%S')
        # get hash
        if not g.lazy_mode:
            print_tmp_line('[{}/{}] {}'.format(i+1, Nf, f))
            sha1str = sha1file(f)
        else: # lazy mode
            key = size_str + ' ' + time_str + ' ' + f
            if key in hash_dict:
                print_tmp_line('[{}/{}] {}'.format(i+1, Nf, f))
                sha1str = hash_dict[key]
            else:
                print_tmp_line('[{}/{}] (hash) {}'.format(i+1, Nf, f))
                sha1str = sha1file(f)
        lines.append(size_str + ' ' + time_str + ' ' + sha1str + ' ' + f)
        # auto-save
        current_time = time.time()
        if current_time - auto_save_time >= g.auto_save_period:
            with open('.pbu-new-asv-writing', 'w') as f:
                f.write('\n'.join(lines) + '\n')
            os.rename('.pbu-new-asv-writing', '.pbu-new-asv')
            auto_save_time = current_time
    # sort accordig to '[size] [hash] [path]'
    lines.sort(key=functools.cmp_to_key(pbu_line_cmp))
    print('', flush=True)
    if fname != None:
        with open(fname, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    return lines

# return True if review is needed, otherwise directory will be clean after return
def check_cwd():
    if os.path.exists('.pbu-new'):
        print('pending review, replace .pbu with .pbu-new when done.\n', flush=True)
        return True
    if not os.path.exists('.pbu'):
        print('.pbu not found, please don\'t delete it next time!')
        cwd = os.path.split(os.getcwd())[1]
        os.chdir('..')
        # in a backup version folder ?
        if os.path.split(os.getcwd())[1][-6:] == '.pbu':
            print('rename to [{}]'.format(cwd + '.broken'), flush=True)
            os.rename(cwd, cwd + '.broken')
            os.chdir(cwd + '.broken')
            print('hashing...', flush=True)
            size_time_sha1_cwd('.pbu-new')
            print('pending review, if everything ok, delete ".broken" from folder name and rename .pbu-new to .pbu.\n', flush=True)
            return True
        else:
            os.chdir(cwd)
            print('hashing...', flush=True)
            size_time_sha1_cwd('.pbu')
            return False
    elif os.stat('.pbu').st_size == 0:
        # .pbu is empty
        print('hashing...', flush=True)
        size_time_sha1_cwd('.pbu')
        return False
    elif os.path.exists('pbu-norehash'):
        # .pbu not empty, norehash
        print("pbu-norehash exist, assuming no change or corruption!", flush=True)
        if not g.debug_mode:
            os.remove('pbu-norehash')
        return False
    else: # .pbu non-empty, rehash
        with open('.pbu', 'r') as f:
            pbu = f.read().splitlines()
        if g.lazy_mode:
            pbu_asv = []
            if os.path.exists('.pbu-new-asv'):
                with open('.pbu-new-asv', 'r') as f:
                    pbu_asv = f.read().splitlines()
                os.remove('.pbu-new-asv')
            if os.path.exists('.pbu-new-asv-writing'):
                os.remove('.pbu-new-asv-writing')
            print('lazy mode (size and time)...', flush=True)
            pbu_new = size_time_sha1_cwd(None, pbu, pbu_asv)
        else:
            print('rehashing...', flush=True)
            pbu_new = size_time_sha1_cwd()

        if pbu_changed(pbu, pbu_new): # has change
            with open('.pbu-new', 'w') as f:
                f.write('\n'.join(pbu_new) + '\n')
            output,Ndelete,Nchange,Nnew,Nmove = diff_cwd()
            print('[deleted]', Ndelete, '\n[changed]', Nchange, '\n[new]', Nnew, '\n[moved]', Nmove)
            with open('.pbu-diff', 'w') as f:
                f.write(output)
            print('folder has change, review .pbu-diff, if everything ok, replace .pbu with .pbu-new, delete .pbu-diff, and add pbu-norehash')
            print('for a more human readable form of .pbu-diff, you can also use:')
            print('`git diff --no-index --word-diff .pbu .pbu-new`\n', flush=True)
            if g.lazy_check and Ndelete == 0 and Nchange == 0:
                print('-- skiping human review due to `lazy_check` option. --')
                os.rename('.pbu', '.pbu-old'); os.rename('.pbu-new', '.pbu')
            return True
        else:
            print('no change or corruption!', flush=True)
            with open('.pbu', 'w') as f: # time might change, update.
                f.write('\n'.join(pbu_new) + '\n')
            return False

# show difference between .pbu-new and .pbu of current folder
def diff_cwd():
    with open('.pbu', 'r') as f:
        pbu = f.read().splitlines()
    with open('.pbu-new', 'r') as f:
        pbu_new = f.read().splitlines()
    i = 0; j = 0
    output = []
    Ndelete = Nchange = Nnew = Nmove = 0
    while 1:
        if i == len(pbu):
            for j in range(j, len(pbu_new)):
                output.append('[new]     ' + pbu_new[j]); Nnew += 1
            break
        elif j == len(pbu_new):
            for i in range(i, len(pbu)):
                output.append('[deleted] ' + pbu[i]); Ndelete += 1
            break
        line = pbu[i]; line_new = pbu_new[j]
        str = line[:g.end_size] + ' ' + line[g.beg_hash:]
        str_new = line_new[:g.end_size] + ' ' + line_new[g.beg_hash:]
        if str == str_new:
            i += 1; j += 1
        elif line[g.beg_hash:g.end_hash] == line_new[g.beg_hash:g.end_hash]:
            # same hash, different path
            output.append('[moved]   ' + line + ' -> ' + line_new[g.beg_path:])
            Nmove += 1; i += 1; j += 1
        elif str < str_new:
            output.append('[deleted] ' + line)
            Ndelete += 1; i += 1
        else: # str_new < str
            output.append('[new]     ' + line_new)
            Nnew += 1; j += 1
    # find out hash change for files with same paths
    output.sort(key=functools.cmp_to_key(pbu_path_p10_cmp))
    i = 0
    while i < len(output)-1:
        if output[i][g.beg_path+10:] == output[i+1][g.beg_path+10:]:
            output[i] = '[changed] ' + output[i][10:]
            del output[i+1]
        i += 1
    return '\n'.join(output) + '\n', Ndelete, Nchange, Nnew, Nmove

# sha1sum of a file
# use 1MiB buffer size fot big file
def sha1file(fname, buff_sz=1024*1024):
    # if os.path.islink(fname):
    #     target = os.readlink(fname)
    #     print(fname, '->', target)
    #     sha1 = hashlib.sha1(target.encode('utf-8'))
    #     return sha1.hexdigest()
        
    if os.path.getsize(fname) <= buff_sz:
        try:
            with open(fname, 'rb') as f:
                data = f.read()
        except PermissionError:
            print('no permission to read file:', fname); exit(1)
        sha1 = hashlib.sha1(data)
    else:
        sha1 = hashlib.sha1()
        with open(fname, 'rb') as f:
            while True:
                data = f.read(buff_sz)
                if not data:
                    break
                sha1.update(data)
    return sha1.hexdigest()

# retur a list all file paths recursively
# paths start with `path` (relative or absolute)
def file_list_r(path):
    files = []
    # r=root, d=directories, f = files
    for r, d, f in os.walk(path):
        for file in f:
            files.append(os.path.join(r, file))
    return files

# remove empty folders recursively
def rm_empty_folders(path, removeRoot=True):
    'Function to remove empty folders'
    if not os.path.isdir(path):
        return
    # remove empty subfolders
    files = os.listdir(path)
    if len(files):
        for f in files:
            fullpath = os.path.join(path, f)
            if os.path.isdir(fullpath):
                rm_empty_folders(fullpath)
    # if folder empty, delete it
    files = os.listdir(path)
    if len(files) == 0 and removeRoot:
        # print("Removing empty folder:", path)
        os.rmdir(path)

# pipe won't work!
def shell_cmd(*cmd):
    process = subprocess.Popen(list(cmd), stdout=subprocess.PIPE)
    output, error = process.communicate()
    if error != None:
        print(error)
        sys.exit(1)
    return output.decode()

# check if `pbu1` is different from `pbu` (ignore time)
def pbu_changed(pbu, pbu1):
    if len(pbu) != len(pbu1):
        return True
    for i in range(len(pbu)):
        line = pbu[i]; line1 = pbu1[i]
        str = line[:g.end_size] + ' ' + line[g.beg_hash:]
        str1 = line1[:g.end_size] + ' ' + line1[g.beg_hash:]
        if str != str1:
            return True
    return False

# check if `pbu1` has only added files to `pbu` but not deleted or modified
# [return list of added file paths] if only added files
# [return empty list] if nothing changed (ignore time)
# [return -1] otherwise (more complicated change)
def pbu_add_only(pbu, pbu1):
    i = 0; j = 0
    N = len(pbu); N1 = len(pbu1)
    if N > N1: return -1
    new_file_list = []
    while i < N and j < N1:
        line = pbu[i]; line1 = pbu1[j]
        str = line[:g.end_size] + ' ' + line[g.beg_hash:]
        str1 = line1[:g.end_size] + ' ' + line1[g.beg_hash:]
        if str == str1:
            i += 1; j += 1; continue
        elif str > str1:
            new_file_list.append(j)
            j += 1; continue
        else: # str < str1
            return -1
    if i == N:
        for j in range(j, N1):
            new_file_list.append(j)
        return new_file_list
    return -1

# for g.hash_name mode
# read .pbu and rename every file with it's hash
def hash_name_cwd():
    if os.path.exists('.pbu-hashname'):
        return
    with open('.pbu', 'r') as f:
        pbu = f.read().splitlines()
    for i in range(len(pbu)):
        line = pbu[i]
        hash = line[g.beg_hash:g.end_hash]; path = line[g.beg_path:]
        dir, fname = os.path.split(path)
        os.rename(path, dir + '/' + hash)
    open('.pbu-hashname', 'w').close()
    print('TODO: hash folder names as well!')
    # note: renaming will not change modification time

# reverse from hash_name_cwd()
def unhash_name_cwd():
    if not os.path.exists('.pbu-hashname'):
        return
    with open('.pbu', 'r') as f:
        pbu = f.read().splitlines()
    for i in range(len(pbu)):
        line = pbu[i]
        hash = line[g.beg_hash:g.end_hash]; path = line[g.beg_path:]
        dir, fname = os.path.split(path)
        os.rename(dir + '/' + hash, path)
    os.remove('.pbu-hashname')

# backup or check a single folder
def backup1(folder):
    os.chdir(g.base_path)

    folder_ver = folder + '.v' + g.ver
    dest1 = g.dest + folder + '.pbu/'
    dest2 = dest1 + folder_ver + '/'
    
    # === search latest backup ===
    print('current backup [{}]'.format(folder_ver), flush=True)
    dest2_last = ''
    if os.path.exists(dest1):
        backups = next(os.walk(dest1))[1]
        if backups: # found previous packup(s)
            backups = natsort.natsorted(backups)
            folder_ver_last = backups[-1]
            dest2_last = dest1 + folder_ver_last + '/'
            print('previous backup [{}]'.format(folder_ver_last))
            if folder_ver < folder_ver_last:
                print('version seems to be decreasing, please check! exiting...')
                exit(1)
        else: # no previous packup(s)
            print('previous backup not found!')
        print('', flush=True)

    # === check source folder ===
    print('checking', '['+folder+']'); print('-'*40, flush=True)
    os.chdir(g.base_path + folder)
    if check_cwd():
        # `folder` has change or corruption
        return True
    elif os.path.exists(dest2):
        # backup folder already exist, check
        print(''); os.chdir(dest2)
        print('checking ['+folder_ver+']'); print('-'*40, flush=True)
        if check_cwd():
            return True
        # compare 2 .pbu
        with open(dest2 + '.pbu', 'r') as f:
            pbu_dest = f.read().splitlines()
        with open(g.base_path + folder + '/.pbu', 'r') as f:
            pbu = f.read().splitlines()
        if (pbu_changed(pbu, pbu_dest)):
            print('.pbu differs from source! please use a new version number and run again.')
            print('', flush=True)
            return True
        else:
            print('.pbu identical from ['+folder+'].\n');
            print('everything ok!\n', flush=True)
            return False
    elif not dest2_last:
        # no previous backup, direct copy
        if dest2_last == '':
            print('no previous backup, copying...', flush=True)
            os.chdir(g.base_path)
            copy_folder(folder, dest2)
            print('', flush=True)
            return False

    # last version backup exist
    os.chdir(dest2_last); print('')
    print('checking ['+folder_ver_last+']'); print('-'*40, flush=True)
    if check_cwd():
        return True
    # compare 2 .pbu
    with open(dest2_last + '.pbu', 'r') as f:
        pbu_dest = f.read().splitlines()
    with open(g.base_path + folder + '/.pbu', 'r') as f:
        pbu = f.read().splitlines()
    cp_inds = pbu_add_only(pbu_dest, pbu)
    if isinstance(cp_inds, list):
        # no change or only added file(s)
        # can rename version directly
        print('rename [{}] to [{}]'.format(folder_ver_last, folder_ver))
        os.rename(dest2_last, dest2)
        if not cp_inds:
            print('done.', flush=True)
            return False
        print('', flush=True)

        # cp_inds not empty
        print('copying new files to [{}]...'.format(folder_ver))
        os.chdir(g.base_path + folder)
        Ncp = len(cp_inds)
        for i in range(Ncp):
            ind = cp_inds[i]
            path = pbu[ind][g.beg_path:]
            print_tmp_line('[{}/{}] {}'.format(i+1, Ncp, path))
            # ensure dest path exist
            dir = os.path.split(dest2+path)[0]
            if not os.path.exists(dir):
                os.makedirs(dir)
            shutil.copy2(path, dest2+path)
            pbu_dest.append(pbu[ind])
        print(''); print('update .pbu')
        pbu_dest.sort(key=functools.cmp_to_key(pbu_line_cmp))
        with open(dest2 + '.pbu', 'w') as f:
            f.write('\n'.join(pbu_dest) + '\n')
        print('')
        print('done.', flush=True)
        return False
    else:
        print('cannot rename.\n'.format(folder), flush=True)

    # --- incremental backup ---
    # pbu must be sorted accordig to '[size] [hash]'
    print('---- starting incremental backup ----', flush=True)
    with open(dest2_last + '.pbu', 'r') as f:
        pbu_last = f.read().splitlines()
    os.chdir(g.base_path + folder)
    with open('.pbu', 'r') as f:
        pbu = f.read().splitlines()
    rename_count = 0; i = j = 0
    
    Nf = len(pbu)
    for i in range(Nf):
        size_hash = pbu[i][g.beg_size:g.end_size+1] + pbu[i][g.beg_hash:g.end_hash]
        path = pbu[i][g.beg_path:]
        print_tmp_line('[{}/{}] {}'.format(i+1, Nf, path))
        # ensure dest path exist
        dir = os.path.split(dest2+path)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        # try to match a previous backup file
        match = False
        while j < len(pbu_last):
            size_hash_last = pbu_last[j][g.beg_size:g.end_size+1] + pbu_last[j][g.beg_hash:g.end_hash]
            if size_hash_last > size_hash:
                break
            elif size_hash_last == size_hash:
                path_last = pbu_last[j][g.beg_path:]
                os.rename(dest2_last + path_last, dest2+path)
                pbu[i] = pbu[i][:g.beg_time] + pbu_last[j][g.beg_time:g.end_time] + pbu[i][g.end_time:]
                rename_count += 1; match = True
                del pbu_last[j]
                break
            j += 1
        if not match: # no match, just copy
            shutil.copy2(path, dest2+path)
    with open(dest2 + '.pbu', 'w') as f:
        f.write('\n'.join(pbu) + '\n')
    
    # update previous .pbu
    print('update .pbu in previous version, rename the original to .pbu-old')    
    os.rename(dest2_last + '.pbu', dest2_last + '.pbu-old')
    delta_remainder_warning = False
    if pbu_last:
        with open(dest2_last + '.pbu', 'w') as f:
            f.write('\n'.join(pbu_last) + '\n')
    else:
        print('internal warning: incremental backup should not happen, the backup folder should have been renamed to new version.')
        print('this is only an optimization warning, your backup is ok!')
        delta_remainder_warning = True
    
    # delete empty folders
    print('remove empty folders')
    # shell_cmd('find', dest2_last, '-empty', '-type', 'd', '-delete')
    rm_empty_folders(dest2_last, True)
    
    # summary
    print('total files:', len(pbu))
    print('files moved from previous version:', rename_count, '\n', flush=True)
    
    need_rerun = False
    if g.debug_mode:
        print('------- DEBUG: rehash last backup folder ------')
        if not delta_remainder_warning:
            os.chdir(dest2_last)
            if check_cwd():
                print('internal error: incremental backup failed!')
                need_rerun = True
    print('done.', flush=True)
    return need_rerun


## =========== main() program ==============

def main():
    if g.base_path[-1] != '/': g.base_path += '/'
    if g.dest[-1] != '/': g.dest += '/'
    g.ignore.update({'.pbu', '.pbu-old', '.pbu-new', '.pbu-diff',
                    'pbu-norehash', '.pbu-new-asv', '.pbu-new-asv-writing'})
    if not g.ver:
        g.ver = datetime.datetime.now().strftime('%Y%m%d.%H%M%S')

    os.chdir(g.base_path)
    need_rerun = False

    if g.folders:
        folders = g.folders
    else:
        folders = next(os.walk('.'))[1]
        folders.sort()

    # get folders with .pbu inside (or use `folders` if not empty)
    print('folders to backup:\n'); i = 0
    if g.folders:
        folders = g.folders

    while i < len(folders):
        folder = folders[i]
        if os.path.exists(folder + '/.pbu'):
            print('[{}] {}'.format(i+1, folder))
            i += 1
        elif g.folders:
            open(folder + '/.pbu', 'w').close()
            print('[{}] {}'.format(i+1, folder))
            i += 1
        else:
            del folders[i]
    print('\n', flush=True)
    Nfolder = len(folders)

    # skip until folder = start
    ind0 = 0
    if g.start:
        for ind0 in range(Nfolder):
            if folders[ind0] == g.start:
                break

    #  ==== loop through all sub folders =====
    need_rerun = False
    for ind in range(ind0, Nfolder):
        folder = folders[ind]
        print('\n' + '#'*40)
        print('[{}/{}] {}'.format(ind+1, Nfolder, folder))
        print('#'*40 + '\n', flush=True)
        if folder in g.ignore_folders:
            print('folder ignored by `ignore_folders` param.')
            continue
        if backup1(folder):
            need_rerun = True

    if need_rerun:
        print('--------- review & rerun needed ----------')
    else:
        print('---------------- all done ----------------')

main()
