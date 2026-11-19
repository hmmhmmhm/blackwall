# Official GAF Evaluation Package and Public State Map

bw-0451. bw450 confirmed that waiting for GAF execution is an actual dependency of the natural render path. Instead of repeating bw381's audit of 48 setter traces or bw396's search of three repositories, this work investigated an official MCU driver and SensorStage distribution not previously checked. This is static analysis: no new ARM/native run or model change. Overall progress remains 10/16=62.5%.

## New public distribution path

The [TDK SensorStage product page](https://www.invensense.tdk.com/en-us/sensorstage) describes sensor updates via public GitHub and on-device GAF evaluation. The [pinned pkg.json](https://github.com/tdk-invn-oss/tdk-sensorstage/blob/4f2f7ba632ff8564b93402d638989c2468f1a2a2/pkg.json) in official `tdk-invn-oss/tdk-sensorstage` identifies ICM45608 SensorStageApp 2.0.0, release date 2026-06-26.

The pinned commit is `4f2f7ba632ff8564b93402d638989c2468f1a2a2`. The archive's LFS pointer Git blob is `8ce10e5f6b7bb23a3f20cf334df8761da35bb9a4`, LFS SHA256 is `a72b8e70deadec0172c5d75235634815e51c1b20e9d7a53639a6d2861b677fc8`, and size is 3,158,324 bytes. Both length and SHA256 of the archive received from the public media path were checked. There was no login, registration, or bypass of download permissions.

This is a public **SensorStage evaluation package**. It is not established as the same complete SDK as the SmartMotion eMD download whose metadata required login in bw439. The historical login-required item is not generalized to a claim that no public material exists.

## Actual contents

The archive's 1,066 entries were inspected. Only 582 static documentation, Python source, XML, and UI configuration files were preserved in a separate copy; path escapes and symlinks were not extracted. Package Python/JS/firmware was not executed. Two .bin/.elf files in `Release/bin` were not extracted, analyzed, or installed.

- Driver API PDF, HTML documentation, and eight Doxygen header source documents.
- Nineteen UI Python scripts and ICM45608 register XML.
- Of 673 register entries in the XML, 68 fields named GAF/on-demand were separately indexed. This does not mean 68 calculation algorithms or EDMP opcodes.
- This archive inventory contains no .c/.h implementation files, .s/.asm, .a, or numerical fixtures in .csv/.npy/.npz/.json form. It does not prove absence of every expected value hidden in arbitrary document formats.

In particular, `inv_imu_edmp_set_gaf_parameters` and similar Doxygen entries are declarations/API descriptions, not ROM-internal implementations. The package name or existence of an .elf does not establish that EDMP ROM execution code was obtained.

The [repository LICENSE](https://github.com/tdk-invn-oss/tdk-sensorstage/blob/4f2f7ba632ff8564b93402d638989c2468f1a2a2/LICENSE) is TDK InvenSense 5Clause. It specifies sensor use conditions and restrictions on reverse engineering distributed binaries and was preserved as a separate source. Only public source, documentation, and metadata were read; no binary disassembly or incorporation into project code occurred. It is not treated as the same license as existing BSD/ISC-family material.

## Scope confirmed by the state map

New `gaf-schema-index.json` indexes names, banks, addresses, and descriptions; it does not apply POR values as emulator initial values. Addresses and byte widths matched for all 64 fields whose names correspond to the existing pinned public memmap header. This does not verify identical defaults, calculations, or lifecycles. The following addresses/descriptions were cross-checked as independent material:

| Item | Address | Confirmed scope |
| --- | --- | --- |
| Dynamic service request | SRAM 0004 | bit 1=GAF parameter request, bit 2=bias request |
| GAF init status | SRAM 0924 | State set to 1 when eDMP completes GAF initialization |
| Saved gyro accuracy | SRAM 05bc | Name/scope of the four-byte value the original setter later reads |
| Read gyro bias | SRAM 096c..0971 | Field range exposed as six bytes |

The 0924 completion flag description does not establish all internal calculation effects or which request timing owns it. It is not grounds to automatically set it to 1 immediately after requests 2/4. The read gyro bias XML description says s32q12, but its address range and public API int16[3] are six bytes. It is not expanded to 12 bytes based on the format wording alone; the inconsistency is recorded.

This material did not supply the complete internal calculation of requests 2/4, exact sensor ROM/ISA, or an independent input/numerical output oracle. `CalculationSupported=false` and rejection of unsupported effect access remain.

## Separate MCU driver investigation

The newly identified official [ICM45686 MCU driver](https://github.com/tdk-invn-oss/motion.mcu.icm45686.driver/tree/0a5bed6975b5cdeecb98f95db420f3058dd88547) was pinned to commit `0a5bed6975b5cdeecb98f95db420f3058dd88547`; eight source files were checked by Git blob/SHA256. EDMP/APEX initialization and ROM entries 0x4000/+4/+8 were confirmed.

Its `EDMP_ROM_DATA_SIZE` is used as the SRAM clear length. The name is not interpreted as the size of a ROM code image. The files read and CMake source list did not provide ICM45608 GAF request 2/4 execution implementation; another part's APEX code is not substituted for G2 sensor ROM.

## Resumption conditions and preservation

The new evaluation material can support target-specific state-map and API input verification. Resuming normal GAF execution still requires an implementation/execution contract or independent effects oracle. Do not run more identical busy/time variants or promote E05/E09 with arbitrary ready. This material alone does not complete natural pixels, sensor samples, or full initialization.

Thirty-one final static checks covered source Git blob/SHA, LFS archive, safe extraction, actual XML bit fields/index, direct comparison of 64 pinned memmap fields, preservation of the format inconsistency, and unchanged scope. New native runs and reruns of the existing 48 setter tests: 0.

To avoid mixing with proprietary assets, source responses, commit/license, archive/LFS pins, inventory, document/XML indexes, and verification reports are preserved in private `simulator/gaf-observable-review-01`. Evaluation firmware is not attached to public documentation. Existing emulator code, default profile, and all 16 completion conditions were unchanged. No physical access, subagents, or external publication occurred.
