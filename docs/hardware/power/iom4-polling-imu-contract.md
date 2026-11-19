# First IOM4 Polling Transfer and IMU Identity Contract

bw-0320. Saved main/SRAM/GPR for three originals were analyzed. No new native main run, peripheral-model change, or physical access occurred. The important correction is that **the current boundary is an I²C CMD write, not CQ activation**.

## Address interpretation correction

In pinned Apollo510 SVD, IOM CMD offset is `120` and CQCFG offset is `228`. Thus `40054120=101` is IOM4 CMD. Interpreted as CMD fields, it is WRITE, TSIZE one byte, CONT 0, offset byte 0. Current CQ configuration is 2, disabled, and pair count is 0.

CQ terminology in bw317/bw319 documents was wrong. Addresses, values, PCs, raw captures, and receive/DMA results are unchanged. Existing documents were corrected and earlier copies preserved as private research assets. Historical append-only wording remains, with this correction applied in a later record. Existing saved-audit numerical checks remain unchanged.

The current strict adapter checks for a registered I²C peer before executing CMD. It blocked before transfer because IOM4 had no peer. A separate new CQ/DMA engine is not required for this request.

## Actual register-select and read preparation

Original stack, HAL calls, and caller field stores were connected. First target address is `69`; the transfer byte prepared in FIFO is `72`. The 72 previously seen in native r1 must not be interpreted as an I²C address.

1. IOM4 attempts to write register-select byte 72 to address 69 (CMD 101).
2. Under a declared completed state, original HAL checks STATUS.IDLE and errors, then clears IRQ/restores previous enable.
3. Original wrapper prepares the next descriptor for address 69, length 1, direction read, and the actual WHOAMI caller stack buffer.
4. The blocking HAL writes CMD 102, reads a receive FIFO word, and stores one byte in the actual buffer.

Both operations use polling. This is not described as checking CQCFG writes, CQ fetches, or DMA execution. First-completion status fixtures 0/1 and error NAK fixture 10 were distinguished. NAK ran until immediately before error cleanup entry; pending state ran until immediately before original 1 µs delay entry. Full error cleanup and actual clock delay were not verified.

## One byte and one word in FIFO

Logical read length is one byte, but original HAL immediately reads a word with a FIFO1SIZ-at-least-4 fixture. FIFO1SIZ 0/1 first proceeded to the original delay boundary. These results are not generalized to physical FIFO measurements.

The source-derived Renode core in the current capture has word backing with `BytesCount = Count * 4`. This supports reuse of the existing backend structure that places a one-byte I²C response in one word. It does not mean the peer payload must be arbitrarily expanded to four bytes or count overwritten with a success value. Actual inherited backend behavior must be checked in subsequent native peer connection.

## ICM45608 source evidence

The actual call chain is sensor transport callback → register-read helper → WHOAMI getter → initialization byte comparison. Getter requests register 72, length 1, and initialization compares response `81`. Of 256 response values, only 81 reached the next reset-function entry; others returned failure. The reset function itself was not executed.

This matches name/WHOAMI 81 in [TDK's ICM45608 header](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu.h) and WHO_AM_I 72 in the [register map](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_regmap_le.h). Interface configuration → ID check → reset order in [advanced init](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_driver_advanced.c) was also compared with the original path.

Official repository live main was checked and pinned to commit `646f55a6ec119b59d9ebce47af660842b53e5506`. Material is BSD-3-Clause; LICENSE, C/H, Git tree/blob, and SHA were verified. IDs from other ICM models are not copied. This match is **source evidence for the IMU expected by firmware**, not physical BOM/chip revision confirmation or evidence of complete TDK/G2 ABI identity.

Additional synthetic combinations selected the reset-entry branch when byte was 81 even with nonzero read status. Therefore a matching ID alone does not guarantee preceding error handling or safe recovery. Reset/resumption after actual failure requires separate verification.

## Verification and next implementation

`tools/inspect_iom4_command.py` executes 804 ARM scenarios across three originals: per image, four select-write conditions, one subsequent read preparation, six read conditions, and 257 WHOAMI gate conditions. These are saved frames/separate branch fixtures in Unicorn M7, not natural M55 run counts. No SRAM memory-write hook or firmware instruction, branch, or return patch was used.

Final analysis `iom4-command-source-04` and frozen `iom4-command-frozen-01` report/inspector are compared byte-for-byte. All nine models are unchanged. Source, 106 frozen Python files, upstream license/commit/blob, failures, and results are recorded in private `simulator/iom4-command-verification-01/manifest.json`.

Initial fixture omissions of DMACFG/unused configuration fields and an unmapped power read caused by entering delay at FIFO1SIZ 1 were preserved. Registers and word counts requested by the actual original were compared; delay was not forced to return. The initial reset-call offset misidentification and failed check mistaking GitHub's commit-alias tree response for canonical tree SHA were also preserved; the canonical tree was separately obtained and verified.

Next connect a limited virtual ICM45608 peer at IOM4 address 69 to the existing I²C backend. First verify register-select/WHOAMI response and stop at unsupported reset/config accesses, expanding only behavior supported by source and original functions. Simulated success is not reported as real-device recovery or physical IMU measurement. Then continue connecting nonzero main draw/input and pixel viewer.

Overall is 13/29=44.8%, scope v2. Goals of web installation, Faceclaw CFW, recovery boot, integrated simulator, and display remain in progress; full boot/UI and physical installation are incomplete.
