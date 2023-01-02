#! /usr/bin/python3
# a very simple incremental backup utility

# === params ===========================
src = '/mnt/d/'
dest = '/mnt/q/'
ver = '0'
select = [] # only backup these sub-dirs
start = '' # skip until this folder
ignore = []
debug_mode = True # don't delete pybup-nohash, check incremental backup
# =====================================

import os
import sys
import hashlib # for sha1sum
import subprocess # for calling shell command
import shutil # for copy file
import errno
import natsort # natural sort folder name

# exclude these files in pybup.txt
exclude=('pybup.txt', 'pybup-new.txt', 'pybup-diff.txt', 'pybup-norehash')

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

# get a list of files and modified date and size of current directory
def size_time_cwd():
    flist = file_list_r('./'); Nf = len(flist)
    ftime = []
    fsize = []
    for i in range(Nf):
        f = flist[i]
        if not os.path.exists(f): # deleted just now
            continue
        print('[{}/{}] ||||||||||||||\r'.format(i+1, Nf), end="", flush=True)
        if os.path.split(f)[1] in exclude:
            continue
        ftime.append(round(os.path.getmtime(f)))
        fsize.append(os.stat(f).st_size)
    return ftime, fsize

# hash every file in current directory and sort hash to a list
# sha1_cwd('pybup.txt') should be the same with `find . -type f -exec sha1sum {} \; | sort > pybup.txt`
# write to file if fname provided
# doesn't include `fname` itself
def sha1_cwd(fname=None):
    flist = file_list_r('./')
    sha1 = []
    Nf = len(flist)
    if fname != None:
        exclude.add(fname)

    for i in range(Nf):
        f = flist[i]
        if not os.path.exists(f): # deleted just now
            continue
        # new pybup.txt format
        # line = '%12d'.format(os.stat(f).st_size) + '  ' + round(os.path.getmtime(f)) + '  ' + sha1file(f) + '  ' + f
        line = sha1file(f) + '  ' + f
        print('[{}/{}] {}    ||||||||||||||\r'.format(i+1, Nf, line[44:]), end="", flush=True)
        if os.path.split(f)[1] in exclude:
            continue
        sha1.append(line)
        sha1.sort()

    if fname != None:
        f = open(fname, 'w')
        f.write('\n'.join(sha1) + '\n')
        f.close()
    else: # fname == None
        print('', flush=True)
    return sha1

# return True if review is needed, otherwise directory will be clean after return
def check_cwd():
    if os.path.exists('pybup-new.txt'):
        print('pending review, replace pybup.txt with pybup-new.txt when done.')
        return True
    if not os.path.exists('pybup.txt'):
        print('pybup.txt not found in', old_dir, 'please don\'t delete it!')
        old_dir = os.path.split(os.getcwd())[1]
        os.chdir('..')
        # in a backup version folder ?
        if os.path.split(os.getcwd())[1][-6:] == '.pybup':
            print('rename to {}'.format(old_dir + '.broken'), flush=True)
            os.rename(old_dir, old_dir + '.broken')
            os.chdir(old_dir + '.broken')
            print('hasing...', flush=True)
            sha1_cwd('pybup-new.txt')
            return True
        else:
            os.chdir(old_dir)
            print('hasing...', flush=True)
            sha1_cwd()
            return False
    elif os.stat('pybup.txt').st_size == 0:
        # pybup.txt is empty
        os.remove('pybup.txt')
        print('hasing...', flush=True)
        sha1_cwd()
        return False
    elif os.path.exists('pybup-norehash'):
        # pybup.txt not empty, norehash
        print("pybup-norehash exist, assuming no change or corruption!", flush=True)
        if not debug_mode:
            os.remove('pybup-norehash')
        return False
    else: # pybup.txt non-empty
        print('pybup.txt not empty, rehashing...', flush=True)
        sha1_new = sha1_cwd()
        sha1_new = '\n'.join(sha1_new) + '\n'
        f = open('pybup.txt', 'r')
        sha1 = f.read(); f.close()
        if sha1_new != sha1: # hash change
            f = open('pybup-new.txt', 'w')
            f.write(sha1_new); f.close()
            print('folder has change, review pybup-diff.txt, if everything ok, replace pybup.txt with pybup-new.txt, delete pybup-diff.txt, and add pybup-norehash', flush=True)
            f = open('pybup-diff.txt', 'w')
            f.write(diff_cwd()); f.close()
            return True
        else:
            print('no change or corruption!', flush=True)
            return False

# show difference between pybup-new.txt and pybup.txt of current folder
def diff_cwd():
    f = open('pybup.txt', 'r')
    sha1 = f.read().splitlines(); f.close()
    f = open('pybup-new.txt', 'r')
    sha1_new = f.read().splitlines(); f.close()
    i = 0; j = 0
    output = []
    while 1:
        if i == len(sha1):
            for j in range(j, len(sha1_new)):
                output.append(sha1_new[j][44:] + ' [new]')
            break
        elif j == len(sha1_new):
            for i in range(i, len(sha1)):
                output.append(sha1[i][44:] + ' [deleted]')
            break
        hash = int(sha1[i][:40], 16)
        hash_new = int(sha1_new[j][:40], 16)
        if hash == hash_new:
            i += 1; j += 1
        elif hash < hash_new:
            output.append(sha1[i][44:] + ' [deleted]')
            i += 1
        else: # hash_new < hash
            output.append(sha1_new[j][44:] + ' [new]')
            j += 1
    output.sort()
    return ('\n'.join(output))

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

# recycled code
'''
# sha1_cwd() using bash command
def sha1_cwd_bash(fname=None):
    print('deprecated! use sha1_cwd instead!'); sys.exit(1)
    lines = shell_cmd('find', '.', '-type', 'f', '-exec', 'sha1sum', '{}', ';').splitlines()
    lines.sort()
    if fname != None:
        exclude.add(fname)
    i = 0
    while i < len(lines):
        if os.path.split(lines)[1] in exclude:
            del lines[i]
            i -= 1
        i += 1
    if fname != None:
        f = open('pybup.txt', 'w')
        f.write('\n'.join(lines))
        f.close()
    return lines
'''

## =========== main() program ==============
os.chdir(src)
need_rerun = False

if select:
    folders = select
else:
    folders = next(os.walk('.'))[1]
    folders.sort()

# get folders with pybup.txt inside
print('folders to backup:'); print(''); i = 0
while i < len(folders):
    folder = folders[i]
    if os.path.exists(folder + '/pybup.txt'):
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
    os.chdir(src)
    folder = folders[ind]

    print(''); print('='*40)
    print('[{}/{}] {}'.format(ind+1, Nfolder, folder))
    print('='*40); print('', flush=True)

    if folder in ignore:
        print('folder ignored by `ignore` param.')
        continue

    folder_ver = folder + '.v' + ver
    dest1 = dest + '/' + folder + '.pybup'
    dest2 = dest1 + '/' + folder_ver
    
    # === search latest backup ===
    print('current backup [{}]'.format(folder_ver), flush=True)
    dest2_last = ''
    if os.path.exists(dest1):
        backups = next(os.walk(dest1))[1]
        if backups: # found previous packup(s)
            backups = natsort.natsorted(backups)
            folder_ver_last = backups[-1]
            dest2_last = dest1 + '/' + folder_ver_last
            print('previous backup [{}]'.format(folder_ver_last))
        else: # no previous packup(s)
            print('previous backup not found!')
        print('', flush=True)

    # === check source folder ===
    print('checking', '['+folder+']'); print('-'*40, flush=True)
    os.chdir(src + '/' + folder)
    if (check_cwd()):
        # `folder` has change or corruption
        need_rerun = True
        continue
    elif os.path.exists(dest2):
        # backup folder already exist, check
        print(''); os.chdir(dest2)
        print('checking ['+folder_ver+']'); print('-'*40, flush=True)
        if (check_cwd()):
            need_rerun = True
            continue
        # compare 2 pybup.txt
        f = open(dest2 + '/pybup.txt', 'r')
        sha1_dest = f.read(); f.close()
        f = open(src + '/' + folder + '/pybup.txt', 'r')
        sha1 = f.read(); f.close()
        if (sha1_dest != sha1):
            print('pybup.txt differs from source! please use a new version number and run again.')
            print('', flush=True)
            continue
        else:
            print('pybup.txt identical, everything ok!'); print('')
            continue
    elif not dest2_last:
        # no previous backup, direct copy
        if dest2_last == '':
            print('---- no previous backup, copying... ----', flush=True)
            os.chdir(src)
            # os.makedirs(dest2)
            # shell_cmd('cp', '-a', folder + '/.', dest2)
            copy_folder(folder, dest2)
            print('', flush=True)
            continue

    # last version backup exist
    os.chdir(dest2_last)
    print('checking ['+folder_ver_last+']'); print('-'*40, flush=True)
    if (check_cwd()):
        need_rerun = True
        continue
    # compare 2 pybup.txt
    f = open(dest2_last + '/pybup.txt', 'r')
    sha1_dest = f.read(); f.close()
    f = open(src + '/' + folder + '/pybup.txt', 'r')
    sha1 = f.read(); f.close()
    if (sha1_dest == sha1):
        # can rename version
        print('rename {} to {}'.format(dest2_last, dest2))
        os.rename(dest2_last, dest2)
        print('', flush=True)
        continue

    # --- incremental backup ---
    print('---- checking previous backup [' + os.path.split(dest2_last)[1] + '] ----', flush=True)    
    os.chdir(dest2_last)
    if (check_cwd()):
        need_rerun = True
        print('================> backup corrupted! should not happen!')
        continue
    print('')

    print('---- starting incremental backup ----', flush=True)
    f = open('pybup.txt', 'r')
    sha1_last = f.read().splitlines()
    f.close()
    os.chdir(src + '/' + folder)
    f = open('pybup.txt', 'r')
    sha1 = f.read().splitlines()
    f.close()
    rename_count = 0; i = j = 0
    # assuming both sha1_last and sha1 and sorted
    for i in range(len(sha1)):
        hash = sha1[i][:40]
        path = sha1[i][43:]
        # ensure dest path exist
        tmp = os.path.split(dest2+path)[0]
        if not os.path.exists(tmp):
            os.makedirs(tmp)
        # try to match a previous backup file
        match = False
        while j < len(sha1_last):
            hash_last = sha1_last[j][:40]
            if hash_last > hash:
                break
            elif hash_last == hash:
                path_last = sha1_last[j][43:]
                os.rename(dest2_last+path_last, dest2+path)
                rename_count += 1; match = True
                del sha1_last[j]
                break
            j += 1
        if not match: # no match, just copy
            shutil.copyfile(path[1:], dest2+path)
    
    # update previous pybup.txt
    print('update previous pybup.txt')
    shutil.copyfile('pybup.txt', dest2 + '/' + 'pybup.txt')
    f = open(dest2_last+'/pybup.txt', 'w')
    f.write('\n'.join(sha1_last))
    f.close()
    
    # delete empty folders
    print('remove empty folders')
    # shell_cmd('find', dest2_last, '-empty', '-type', 'd', '-delete')
    rm_empty_folders(dest2_last, False)
    
    # summary
    print('total files:', len(sha1))
    print('moved from previous version:', rename_count)
    print('', flush=True)
    
    if debug_mode:
        print('------- DEBUG: rehash backup folder ------')
        os.chdir(dest2)
        if (check_cwd()):
            print('internal error: incremental backup failed!')
            need_rerun = True
        os.chdir(dest2_last)
        if (check_cwd()):
            print('internal error: incremental backup failed!')
            need_rerun = True
        print('everything ok!')
        print('', flush=True)

if need_rerun:
    print('============ review & rerun needed =============')
else:
    print('=============== ALL DONE ===============')
