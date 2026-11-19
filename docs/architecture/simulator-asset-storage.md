# Recovering Storage Space for Simulator Evidence Assets

During the bw346 shape-stream run, available host space fell to about 120 MiB and CFW execution and Docker daemon connectivity stopped. That capture was retained as failure evidence. Other projects' data, Docker images/volumes, and original firmware were not deleted.

Recovery was limited to regular files of at least 1 MiB inside the Blackwall simulator folder outside Git. Files with identical size and SHA-256 were replaced with independent APFS `clonefile` clones. Byte hashes were compared before replacement, and original mode and access/modification times were preserved. Files with xattrs, special flags, hard links, or different owners were excluded. This did not guarantee identical inode or creation/change metadata.

This is not hard-linking. Separate small test files confirmed distinct inodes and link count 1, and confirmed that modifying a clone preserved the original. Paths and contents remain unchanged, so existing byte-hash audits continue to work. Saved audits of three later native runs and three baselines also passed.

Private `simulator/storage-maintenance-01` retains the reproduction script, per-file hash/original path/replacement inode journal, space report, and independence control. Of 3,230 files inspected, 2,839 were replaced. Available space increased from 136,450,048 bytes to 10,851,766,272 bytes. These are filesystem observations at that time, not a permanent project space guarantee.

OrbStack was restarted and Docker API responsiveness confirmed. No remaining container mounted the failed CFW capture path, and no other containers were removed. CFW02 was then executed as a new run and passed. No automatic cleanup or periodic task was installed.

A `ditto` compression test was ineffective and was not applied to originals; the first script's xattr API discovery error was also retained as a failure. Environment recovery is not added to product acceptance scores. Check available space before new large runs, and do not interpret a run affected by insufficient space as firmware failure or success.
