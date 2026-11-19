# IMU expected by the firmware

The strongest current candidate is **TDK InvenSense ICM-45608**. This identification is source-supported, not a physical device reading.

The verified paths in original stock 2.4, stock 2.3, and Faceclaw read one byte from WHO_AM_I register 72 at IOM4 I²C address 69 and compare it to 81. When all byte candidates were compared in independent ARM execution, only 81 selected the next reset entry.

bw329 correction: The lowercase driver-path filename `imu_icm45608.c` was found in all three original images. The earlier uppercase model-name-focused search missed it, so the statement that no model-name string was found is withdrawn. The binary's driver filename supports the expected device in addition to register/ID evidence. It does not establish physical chip markings or silicon revision.

The pinned [official header](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu.h) defines `INV_IMU_STRING_ID` as ICM45608 and `INV_IMU_WHOAMI` as 81. The same commit's register map defines WHO_AM_I as 72. Files were checked against canonical Git blobs. This combines address, ID, initialization, and indirect-register behavior; it does not prove the ID is globally unique.

[TDK product material](https://www.invensense.tdk.com/en-us/products/inertial-sensors/icm-45608-ict-15318) describes ICM-45608 as a six-axis IMU with three accelerometer and three gyroscope axes. It does not establish that the separate ICT magnetometer on that page is installed in G2.

Some legacy EDMP bit use in the G2 binary differs from reserved markings in the pinned latest TDK map. Therefore the entire SDK ABI and register defaults are not assumed identical. Physical chip marking, actual WHO_AM_I, and silicon revision remain unknown; no physical reading or disassembly was performed.

Execution evidence: [IOM4 identification contract](../power/iom4-polling-imu-contract.md), [virtual IMU reset](imu-timed-reset-peer.md), [indirect lookup](imu-indirect-endianness-peer.md). Without physical confirmation, the current emulator models limited source-backed behavior of this expected device.

## Expected auxiliary magnetometer

In bw329, separate original MAG initialization was confirmed across three images to accept only ID 45 in register 01. The first internal I²C master configuration's payload 1e also matches the pinned SDK's `MAG_I2C_ADDR`. The [official SDK wrapper](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/invn_mag.c) connects the Ict1531x driver, and its [header](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/Ict1531x/Ict1531x.h) defines the same register/ID. Seven newly acquired sources/headers were checked against canonical Git blobs; the existing source snapshot was preserved.

[TDK DS-000548 revision 1.1](https://d17t6iyxenbwp1.cloudfront.net/s3fs-public/2026-08/ds-000548-ict-15312-ict-15318-datasheet-v1.1.pdf) describes chip_id 45 and the same unlock/reset register sequence for both ICT-15312 and 15318. This supports the auxiliary device family expected by firmware. ID alone does not distinguish the two variants. It does not imply nine axes are integrated into one IMU chip.

bw330 follow-up: With [virtual I²C master transactions](imu-i2cm-magnetometer-bootstrap.md) connected, native main received ID 45 from a declared virtual MAG and stored ID/ready 45/1 in SRAM using original code. With ID 44 as control, both values remained 0/0, but upper initialization continued to the next ODR lookup. This verifies virtual-profile consumption and ID gating, not physical installation, ID, or revision.
