# pybup
simple generic backup script

* each subfolder `folder` in `src` with `pybup.txt` (initially empty) will be backed up to `dest/folder.pybup/folder.v*`, where `*` is version number `ver`
* `pybup.txt` keeps the info for every file inside, format: `[size] [time] [sha1] [path]`.
* incremental backup will just move identical files from previous version, if any exist
* `lazy_mode`: hash a file only when size or time changed. This will not protect against bit rot, turn off once in a while and rerun.

![flowchart](pybup.png)
