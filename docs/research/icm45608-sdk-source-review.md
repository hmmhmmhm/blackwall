# User-Supplied ICM45608 SDK 2.0.0 Review

bw478. The user supplied `emd-icm45608_examples-atmel-cm4-fpu-2.0.0.zip` after signing in and downloading it. The actual sources and examples were reviewed and compared with the existing public driver. **The core sensor driver is the same as before; no new complete GAF calculation implementation was found.** The official MCU examples and initial-state definitions can inform functional model design. No new ARM execution, device connection, or SDK executable execution occurred.

## Preservation and inspection scope

The original Downloads file was retained and an identical copy preserved at `icm45608-sdk-review-01/sdk-original.zip` in the private simulator workspace. Its SHA-256 is `57b68bb9d7cae0d749f8127fe4dd194dba2821a17b85d841eba707e9facde13c`. This checks identity between the supplied file and copy and subsequent integrity; it is not verification of a manufacturer's ZIP signature.

The archive index contains 3,186 entries totaling 70,896,195 uncompressed bytes. Excluding macOS metadata and directories, there are 1,463 files. Checks rejected absolute paths, parent-path escapes, symlinks, and encrypted entries. Only 368 text files, including C/H, example README/project XML, and linker scripts, were extracted to a separate copy. Installation and flashing instructions in the ZIP README were read as reference material only. Microchip Studio, sensorcli, and SDK firmware were not executed.

The root LICENSE describes source use for internal development/testing and includes object-code reverse-engineering restrictions and precedence for different file-specific licenses. Separate permissions appear in the actual driver C and ICT1531x C/H files. This review compared source, documentation, and integrity; it did not disassemble object code. Do not copy or publish the entire SDK or restricted material in Git. Before reusing code, check the pinned public upstream and the license of the particular file.

## Direct comparison with the public driver

The actual Git tree of the previously preserved `tdk-invn-oss/motion.arduino.ICM45608` commit `646f55a6ec119b59d9ebce47af660842b53e5506` was compared against 46 files in SDK `sources/drivers/icm45608/imu`. The tree SHA-256 was rechecked from the previous manifest and each file's Git blob SHA-1 calculated.

| Result | Files | Meaning |
| --- | ---: | --- |
| Original bytes identical | 0 | SDK CRLF differs byte-for-byte from public LF files |
| Identical after CRLF → LF | 45 | Includes GAF host driver, memmap, and patch definitions |
| Actual difference | 1 | Only `inv_imu_version.h` changes `2.0.0-rc1` to `2.0.0` |
| Drivers absent from public tree | 0 | Limited to these 46 compared files |

The public version header was fetched again from its pinned raw URL and its Git blob checked. Replacing only the version string made it identical to the SDK header. **This does not claim all 1,463 SDK files match existing material.** The official Atmel examples, board HAL, host tools, and documentation are separate material.

The same GAF setter follows request 2 → request 4 → mask/disable → calmag patch. The service helper writes a request to sensor SRAM → triggers on-demand processing → waits 200 µs on the host → checks idle. ROM IRQ entry configuration remains present. The 200 µs is an initial host wait, not the actual calculation completion time. This source comparison did not newly reveal the sensor's internal calculations.

## Evidence actually added by this SDK

1. **Explicit initial state in runnable initialization examples:** The GAF example distinguishes cases with and without saved calibration and prepares bias, accuracy, and temperature. This allows a cold-calibration scenario to be designed separately from an arbitrary all-zero RAM state. It is evidence of MCU host input preparation, not an oracle for the complete internal SRAM results of requests 2/4.
2. **Input/output consumption examples:** The GAF, wearable, all-quaternion, and dynamic protocol examples show raw/calibrated values, frames, timestamps, and output consumption order. The presence of examples is distinct from obtaining the sensor fusion formula source.
3. **Magnetometer source:** The `Ict1531x` driver specifies ID 0x45/register 01, modes 04/05, status 06, frame counter 07, temperature 08/09, XYZ 0a..0f, and the DRDY-clear rule on the last data read. ID and control registers correspond to expectations in the [existing G2 original bootstrap](../hardware/sensors-input/imu-i2cm-magnetometer-bootstrap.md). This is not a measurement of the exact physical chip variant, wiring, or latency.

The archive filename/extension index found no standalone `.csv/.npy/.npz/.json` numeric fixtures, `.s/.asm` ISA sources, or `.a/.lib/.so` libraries. This was a limited file-format search, not proof that every binary lacks information or that the entire SDK lacks such material. The contents of supplied BIN/EXE/DLL files were not examined.

## Conclusion for the next design

The conclusion of the [premise review](../hardware/sensors-input/gaf-functional-model-options.md) stands. Identical execution down to sensor ROM is not the only way to test the original M55 firmware. The recommended next design is to **preserve the existing strict profile and create a separate, explicit cold/stationary sensor functional profile**.

That profile should consistently handle bus configuration → requests 2/4 → busy/completion → state actually read by the host → FIFO/IRQ without modifying the original ARM, branches, or TCB. Use the SDK's host initial values, types, and input/output contracts, but label inferred internal sensor effects as assumptions. Do not count zero-filling all unknown SRAM or merely returning ready as validation of normal GAF accuracy. Unsupported accesses must remain visible.

Having the SDK does not mean the functional model has already been implemented or original boot has completed. This work only reviewed design evidence; implementation follows discussion of model choice, assumption boundaries, and validation claims. The 16 overall v3 acceptance criteria and 10/16 = 62.5% remain unchanged.

## Browser Skills and verification record

At the user's request, the browser-skill instructions were read and `bsk browsers --json` confirmed the Chrome extension was connected and responsive with zero active sessions. Since the SDK was already supplied, no new browser session was opened and no page or login was manipulated. Login completion was reported by the user; no separate authentication-state check is claimed. For future browser work, use Browser Skills' Agent Window and a fresh browser inventory.

The private `icm45608-sdk-review-01/` retains the original ZIP, acquisition information, archive listing, selected source hashes, public-driver comparison, and verification tool. The 429 checks are mostly file-integrity and comparison judgments, not 429 GAF numerical tests. No new VM, physical device, subagent, or external publication was used.
