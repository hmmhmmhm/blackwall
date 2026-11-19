# Upstream changes rechecked

2026-11-10. Checked with `git ls-remote ... HEAD` and a commit diff after fetching. The candidate build and dependency pins were not changed.

| Repository | Checked HEAD | Compared with the previous review |
| --- | --- | --- |
| g2-bootloader-patch | 6198d70e18293caebf8314d2e40bd3b1d0a5ee16 | Unchanged |
| g2flash | 845f665e0dfdcfd06b7d3a294388de6f17a5bd59 | Unchanged |
| Faceclaw | 8b70585da8f8ad529b73647a589e6852bbb441c7 | One commit after the previously reviewed 70ec2a0d |

The Faceclaw changes concern Play Store distribution metadata, Android SDK 36, APK/AAB release procedures, and privacy information. The changed-file list and build/release diff were reviewed. There were no changes to firmware patches, BLE probing, or recovery integration. Do not conflate the previously reviewed commit with the latest HEAD.

These changes did not resolve the unknown boot/hardware/case identification for the user's device, booting mixed configurations, or full recovery. Repeating file/mock validation without hardware cannot satisfy those items. An [upstream inquiry draft](upstream-compatibility-question.md) was prepared; external publication had not been approved.
