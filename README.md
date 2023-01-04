# pbu
simple generic backup script

* each subfolder `folder` in `src` with `pbu.txt` (initially empty) will be backed up to `dest/folder.pbu/folder.v*`, where `*` is version number `ver`
* `pbu.txt` keeps the info for every file inside, format: `[size] [time] [sha1] [path]`.
* incremental backup will just move identical files from previous version, if any exist
* `lazy_mode`: hash a file only when size or time changed. This will not protect against bit rot, turn off once in a while and rerun.
* \[deprecated\] create an empty file `pbu-norehash` in the same folder with `pbu.txt` to let the script assume folder is up to date and do nochecking at all.

![flowchart](pbu.png)

# TODO
* `shutil.copystat` to preserve mata data as much as possible

## make `pbu` more like git! (without staging area)
* `pbu status` to check source folder
* `pbu commit` to commit to a new version (15-digit backup time)
* `pbu fsck` to check backup folder (all versions)
* use `.pbuignore` file similar to `.gitignore`
* `pub checkout` to checkout any version
* `pub checkout-pbu` to checkout any version in the `.pbu` folder
