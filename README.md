# pybup
simple generic backup script

* each subfolder `folder` in `src` with `pybup.txt` (initially empty) will be backed up to `dest/folder.pybup/folder.v*`, where `*` is version number `ver`
* `pybup.txt` keeps the info for every file inside, format: `[size] [time] [sha1] [path]`.
* incremental backup will just move identical files from previous version, if any exist
* `lazy_mode`: hash a file only when size or time changed. This will not protect against bit rot, turn off once in a while and rerun.
* \[deprecated\] create an empty file `pybup-norehash` in the same folder with `pybup.txt` to let the script assume folder is up to date and do nochecking at all.

![flowchart](pybup.png)

# TODO
* make `pybup` more like git! (without staging area)
* `pybup status` to check source folder
* `pybup commit` to commit to a new version (15-digit backup time)
* `pybup fsck` to check backup folder (all versions)
* use `.pybupignore` file similar to `.gitignore`
