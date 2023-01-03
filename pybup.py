#! /usr/bin/python3
# a very simple incremental backup utility

import os
import sys
import hashlib # for sha1sum
import subprocess # for calling shell command
import shutil # for copy file
import errno
import datetime
import functools
import natsort # natural sort folder name

# copy folder recursively
def copy_folder(src, dst):
    try:
        shutil.copytree(src, dst)
    except OSError as exc: # python >2.5
        if exc.errno in (errno.ENOTDIR, errno.EINVAL):
            shutil.copy(src, dst)
        else:
            # raise
            print('copy_folder() failed! you might not have permission!')
            exit(1)

# utility for sorting pybup.txt (accordig to '[size] [hash] [path]')
def pybup_line_cmp(line, line1):
    str = line[:beg_time] + line[end_time:]
    str1 = line1[:beg_time] + line1[end_time:]
    if str < str1: return -1
    if str1 < str: return 1
    return 0

# generate pybup.txt
# write to file if fname provided, otherwise return list of lines
# lazy mode: input the `pybup` (list of line) from `pybup.txt`
def size_time_sha1_cwd(fname=None, pybup=None):
    lazy_mode = pybup != None
    flist = file_list_r('./')
    lines = []
    Nf = len(flist)
    my_exclude = set(exclude)
    if fname != None:
        my_exclude.add(fname)

    # create dict from '[size] [time] [path]' to [sha1]
    if lazy_mode:
        hash_dict = {}
        for line in pybup:
            key = line[:end_time] + line[beg_path-1:]
            hash_dict[key] = line[beg_hash:end_hash]

    for i in range(Nf):
        f = flist[i][2:]
        if not os.path.exists(f): # deleted just now
            continue
        # get size and time
        size_str = '%014d' % os.stat(f).st_size
        time_str = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y%m%d.%H%M%S')
        # get hash
        if not lazy_mode:
            sha1str = sha1file(f)
        else: # lazy mode
            key = size_str + ' ' + time_str + ' ' + f
            try:
                sha1str = hash_dict[key]
            except:
                sha1str = sha1file(f)
                print('(not lazy) ', end="")
        line = size_str + ' ' + time_str + ' ' + sha1str + ' ' + f
        str = '[{}/{}] {}'.format(i+1, Nf, f)
        if len(str) > path_max_sz: str = str[:path_max_sz-3] + '...'
        elif len(str) < path_max_sz: str = str + ' '*(path_max_sz-len(str))
        print(str+'\r', end="", flush=True) # \r moves the cursur the start of line
        if os.path.split(f)[1] in my_exclude:
            continue
        lines.append(line)
    # sort accordig to '[size] [hash] [path]'
    lines.sort(key=functools.cmp_to_key(pybup_line_cmp))
    print('', flush=True)
    if fname != None:
        f = open(fname, 'w')
        f.write('\n'.join(lines) + '\n'); f.close()
    return lines

# return True if review is needed, otherwise directory will be clean after return
def check_cwd(lazy_mode):
    if os.path.exists('pybup-new.txt'):
        print('pending review, replace pybup.txt with pybup-new.txt when done.')
        print('', flush=True)
        return True
    if not os.path.exists('pybup.txt'):
        print('pybup.txt not found, please don\'t delete it next time!')
        cwd = os.path.split(os.getcwd())[1]
        os.chdir('..')
        # in a backup version folder ?
        if os.path.split(os.getcwd())[1][-6:] == '.pybup':
            print('rename to [{}]'.format(cwd + '.broken'), flush=True)
            os.rename(cwd, cwd + '.broken')
            os.chdir(cwd + '.broken')
            print('hashing...', flush=True)
            size_time_sha1_cwd('pybup-new.txt')
            print('pending review, if everything ok, delete ".broken" from folder name and rename pybup-new.txt to pybup.txt.')
            print('', flush=True)
            return True
        else:
            os.chdir(cwd)
            print('hashing...', flush=True)
            size_time_sha1_cwd('pybup.txt')
            return False
    elif os.stat('pybup.txt').st_size == 0:
        # pybup.txt is empty
        print('hashing...', flush=True)
        size_time_sha1_cwd('pybup.txt')
        return False
    elif os.path.exists('pybup-norehash'):
        # pybup.txt not empty, norehash
        print("pybup-norehash exist, assuming no change or corruption!", flush=True)
        if not debug_mode:
            os.remove('pybup-norehash')
        return False
    else: # pybup.txt non-empty, rehash
        f = open('pybup.txt', 'r')
        pybup = f.read().splitlines(); f.close()
        if lazy_mode:
            print('pybup.txt not empty, rehashing (lazy mode)...', flush=True)
            pybup_new = size_time_sha1_cwd(None, pybup)
        else:
            print('pybup.txt not empty, rehashing...', flush=True)
            pybup_new = size_time_sha1_cwd(None)
        
        if pybup_changed(pybup, pybup_new): # has change
            f = open('pybup-new.txt', 'w')
            f.write('\n'.join(pybup_new) + '\n'); f.close()
            f = open('pybup-diff.txt', 'w')
            f.write(diff_cwd()); f.close()
            print('folder has change, review pybup-diff.txt, if everything ok, replace pybup.txt with pybup-new.txt, delete pybup-diff.txt, and add pybup-norehash')
            print('', flush=True)
            return True
        else:
            print('no change or corruption!', flush=True)
            f = open('pybup.txt', 'w')
            f.write('\n'.join(pybup_new) + '\n'); f.close()
            return False

# show difference between pybup-new.txt and pybup.txt of current folder
def diff_cwd():
    f = open('pybup.txt', 'r')
    pybup = f.read().splitlines(); f.close()
    f = open('pybup-new.txt', 'r')
    pybup_new = f.read().splitlines(); f.close()
    i = 0; j = 0
    output = []
    while 1:
        if i == len(pybup):
            for j in range(j, len(pybup_new)):
                output.append(pybup_new[j] + ' [new]')
            break
        elif j == len(pybup_new):
            for i in range(i, len(pybup)):
                output.append(pybup[i] + ' [deleted]')
            break
        hash = pybup[i][beg_hash:end_hash]; hash_new = pybup_new[j][beg_hash:end_hash]
        if hash == hash_new:
            i += 1; j += 1
        elif hash < hash_new:
            output.append(pybup[i] + ' [deleted]')
            i += 1
        else: # hash_new < hash
            output.append(pybup_new[j] + ' [new]')
            j += 1
    output.sort()
    return '\n'.join(output) + '\n'

# sha1sum of a file
# use 1MiB buffer size fot big file
def sha1file(fname, buff_sz=1024*1024):
    if os.path.getsize(fname) <= buff_sz:
        f = open(fname, 'rb')
        data = f.read()
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

# check if `pybup1` is different from `pybup` (ignore time)
def pybup_changed(pybup, pybup1):
    if len(pybup) != len(pybup1):
        return True
    for i in range(len(pybup)):
        line = pybup[i]; line1 = pybup1[i]
        str = line[:end_size] + ' ' + line[beg_hash:]
        str1 = line1[:end_size] + ' ' + line1[beg_hash:]
        if str != str1:
            return True
    return False

# check if `pybup1` has only added files to `pybup` but not deleted or modified [return 1]
# if nothing changed (ignore time), [return 0]
# otherwise (more complicated change) [return -1]
def pybup_add_only(pybup, pybup1):
    i = 0; j = 0
    N = len(pybup); N1 = len(pybup1)
    if N > N1: return -1
    while i < N and j < N1:
        line = pybup[i]; line1 = pybup1[j]
        str = line[:end_size] + ' ' + line[beg_hash:]
        str1 = line1[:end_size] + ' ' + line1[beg_hash:]
        if str == str1:
            i += 1; j += 1; continue
        elif str > str1:
            j += 1; continue
        else: # str < str1
            return -1
    if i == N: return 1
    else: return -1

# backup or check a single folder
def backup1(folder, dest, ver):
    os.chdir(src)

    folder_ver = folder + '.v' + ver
    dest1 = dest + folder + '.pybup/'
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
        else: # no previous packup(s)
            print('previous backup not found!')
        print('', flush=True)

    # === check source folder ===
    print('checking', '['+folder+']'); print('-'*40, flush=True)
    os.chdir(src + folder)
    if (check_cwd(lazy_mode)):
        # `folder` has change or corruption
        need_rerun = True
        return
    elif os.path.exists(dest2):
        # backup folder already exist, check
        print(''); os.chdir(dest2)
        print('checking ['+folder_ver+']'); print('-'*40, flush=True)
        if (check_cwd(lazy_mode)):
            need_rerun = True
            return
        # compare 2 pybup.txt
        f = open(dest2 + 'pybup.txt', 'r')
        pybup_dest = f.read().splitlines(); f.close()
        f = open(src + folder + '/pybup.txt', 'r')
        pybup = f.read().splitlines(); f.close()
        if (pybup_changed(pybup, pybup_dest)):
            print('pybup.txt differs from source! please use a new version number and run again.')
            print('', flush=True)
            need_rerun = True
            return
        else:
            print('pybup.txt identical from ['+folder+'].'); print('everything ok!', flush=True)
            print('', flush=True)
            return
    elif not dest2_last:
        # no previous backup, direct copy
        if dest2_last == '':
            print('no previous backup, copying...', flush=True)
            os.chdir(src)
            copy_folder(folder, dest2)
            print('', flush=True)
            return

    # last version backup exist
    os.chdir(dest2_last); print('')
    print('checking ['+folder_ver_last+']'); print('-'*40, flush=True)
    if (check_cwd(lazy_mode)):
        need_rerun = True
        return
    # compare 2 pybup.txt
    f = open(dest2_last + 'pybup.txt', 'r')
    pybup_dest = f.read().splitlines(); f.close()
    f = open(src + folder + '/pybup.txt', 'r')
    pybup = f.read().splitlines(); f.close()
    if pybup_add_only(pybup, pybup_dest) >= 0:
        # no change or only added file(s)
        # can rename version directly
        print('rename [{}] to [{}]'.format(folder_ver_last, folder_ver))
        os.rename(dest2_last, dest2); print('', flush=True)
        return
    else:
        print('cannot rename.'.format(folder)); print('', flush=True)

    # --- incremental backup ---
    # pybup must be sorted accordig to '[size] [hash]'
    print('---- starting incremental backup ----', flush=True)
    f = open(dest2_last + 'pybup.txt', 'r')
    pybup_last = f.read().splitlines(); f.close()
    os.chdir(src + folder)
    f = open('pybup.txt', 'r')
    pybup = f.read().splitlines(); f.close()
    rename_count = 0; i = j = 0
    
    Nf = len(pybup)
    for i in range(Nf):
        size_hash = pybup[i][beg_size:end_size+1] + pybup[i][beg_hash:end_hash]
        path = pybup[i][beg_path:]
        print('[{}/{}]          \r'.format(i+1, Nf), end="", flush=True)
        # ensure dest path exist
        dir = os.path.split(dest2+path)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        # try to match a previous backup file
        match = False
        while j < len(pybup_last):
            size_hash_last = pybup_last[j][beg_size:end_size+1] + pybup_last[j][beg_hash:end_hash]
            if size_hash_last > size_hash:
                break
            elif size_hash_last == size_hash:
                path_last = pybup_last[j][beg_path:]
                os.rename(dest2_last + path_last, dest2+path)
                rename_count += 1; match = True
                del pybup_last[j]
                break
            j += 1
        if not match: # no match, just copy
            shutil.copyfile(path, dest2+path)
    
    # update previous pybup.txt
    print('update previous pybup.txt')
    shutil.copyfile('pybup.txt', dest2 + 'pybup.txt')
    delta_remainder_warning = False
    if pybup_last:
        f = open(dest2_last + 'pybup.txt', 'w')
        f.write('\n'.join(pybup_last) + '\n')
        f.close()
    else:
        print('internal warning: incremental backup should not happen, the backup folder should have been renamed to new version.')
        print('this is only an optimization warning, your backup is ok!')
        delta_remainder_warning = True
    
    # delete empty folders
    print('remove empty folders')
    # shell_cmd('find', dest2_last, '-empty', '-type', 'd', '-delete')
    rm_empty_folders(dest2_last, True)
    
    # summary
    print('total files:', len(pybup))
    print('files moved from previous version:', rename_count)
    print('', flush=True)
    
    if debug_mode:
        print('------- DEBUG: rehash backup folder ------')
        os.chdir(dest2)
        if (check_cwd(lazy_mode)):
            print('internal error: incremental backup failed!')
            need_rerun = True
        if not delta_remainder_warning:
            os.chdir(dest2_last)
            if (check_cwd(lazy_mode)):
                print('internal error: incremental backup failed!')
                need_rerun = True
        print('everything ok!')
        print('', flush=True)


## =========== main() program ==============

# === params ===========================
src = '/mnt/d/' # directory to backup
dest = '/mnt/q/' # backup directory
ver = '1' # version number
select = ['比心'] # select folders to backup (even without pybup.txt)
ignore = [] # ignore these folders
start = '' # skip until this folder
lazy_mode = True # hash a file only when size or time changed
debug_mode = True # won't pybup-nohash & check incremental backup
path_max_sz = 130
# =====================================

# exclude these files in pybup.txt
# add anything you want to ignore
exclude=('pybup.txt', 'pybup-new.txt', 'pybup-diff.txt', 'pybup-norehash', 'Thumbs.db')

if src[-1] != '/': src += '/'
if dest[-1] != '/': dest += '/'


os.chdir(src)
need_rerun = False

# pybup.txt line format
beg_size = 0; end_size = 14
beg_time = 15; end_time = 30
beg_hash = 31; end_hash = 71
beg_path = 72

if select:
    folders = select
else:
    folders = next(os.walk('.'))[1]
    folders.sort()

# get folders with pybup.txt inside (or use `select` if not empty)
print('folders to backup:'); print(''); i = 0
if select:
    folders = select

while i < len(folders):
    folder = folders[i]
    if os.path.exists(folder + '/pybup.txt'):
        print('[{}] {}'.format(i+1, folder))
        i += 1
    elif select:
        open(folder + '/pybup.txt', 'w').close()
        print('[{}] {}'.format(i+1, folder))
        i += 1
    else:
        del folders[i]
print(''); print('')
Nfolder = len(folders)

# skip until folder = start
ind0 = 0
if start:
    for ind0 in range(Nfolder):
        if folders[ind0] == start:
            break

#  ==== loop through all sub folders =====
for ind in range(ind0, Nfolder):
    folder = folders[ind]
    print(''); print('#'*40)
    print('[{}/{}] {}'.format(ind+1, Nfolder, folder))
    print('#'*40); print('', flush=True)
    if folder in ignore:
        print('folder ignored by `ignore` param.')
        continue
    backup1(folder, dest, ver)

if need_rerun:
    print('--------- review & rerun needed ----------')
else:
    print('---------------- all done ----------------')
