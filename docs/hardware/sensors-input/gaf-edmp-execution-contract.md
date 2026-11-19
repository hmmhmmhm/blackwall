# GAF Execution Contract and Target Sensor Datasheet

bw439. The official 275-page ICM-45608 datasheet DS-000595 revision 1.1 was obtained. The bw396 driver search and frozen-core failure loop were not repeated. There was no new ARM execution or model change.

## Findings from the target material

The datasheet linked from the [official ICM-45608 product page](https://www.invensense.tdk.com/en-us/products/inertial-sensors/icm-45608-ict-15312) was downloaded, and its SHA256, original URL, text, and relevant page renders were preserved privately. The search cache and actual product page document lists differed; the record uses the actual HTML.

- Page 48: EDMP uses a dedicated ISA for motion processing. Loading a RAM patch into the M55 engine does not execute sensor code. This also does not mean opcode/register execution rules were disclosed.
- Page 122, 18.1: SRAM address 4 bit 1 requests GAF parameter configuration (value 2), and bit 2 requests GAF bias configuration (value 4). This independent document cross-checks existing public driver constants and original ARM analysis.
- The same table describes the value after reset and before EDMP_INIT as arbitrary. The table's default 0 is not treated as a known 0 immediately after reset.
- Page 122, 18.2 also has a bit for use cases that do not need GAF. This is a host-specified input; there is no evidence that the current original G2 selects that mode. No boot bypass forcibly changes the bit on the host.

The hashes of three existing files from pinned TDK driver commit `646f55a6ec119b59d9ebce47af660842b53e5506` were rechecked. ROM entries are 0x4000/+4/+8, and the GAF setter follows request 2 → request 4 → calmag RAM patch loading. This order does not support assuming that the public calmag patch alone can execute preceding services. The existing limitation concerning the length difference between actual G2 and public calmag images remains.

## SDK and unavailable material

SmartMotion eMD metadata on the official page lists an Atmel CM4 FPU2.0.0 package, but `field_requires_login=1`. The package contents were not downloaded and the login path was not bypassed. Therefore no conclusion is drawn that the package lacks ROM, ISA, or an oracle.

The material obtained did not provide an EDMP opcode specification, the complete sensor ROM, request 2/4 calculation implementation, or independent numerical expected values. Datasheet service IDs and settings do not substitute for the calculation's complete side effects. `CalculationSupported=false` and rejection of unsupported RAM access remain. Normal GAF initialization (E05/E12) is incomplete.

## Next work

Do not repeat the same frozen timeout/ready variants or investigation of the same upstream files. Resuming normal GAF requires exact executable code/ISA contract, a calculation specification, or independent inputs/outputs and a supported effects scope. Do not automatically start a real-device dump or inquiry.

Switch to the independently outstanding E11 touch input. The existing [GPIO event request](touch-gpio-event-request.md) confirmed only the original attempt to read register 03, 16 bytes. Next, pin the original decoder that reads those 16 bytes, its validation/error branches, and consumer. Do not count this as complete input/UI first.

Evidence is private `simulator/gaf-edmp-execution-contract-01/{verification-report.json,source-pins.json,manifest.json}`. Original PDF/text/renders/SDK metadata are preserved only outside Git. Text was extracted with pypdf 7.0.1, and actual page 48/122 renders were directly reviewed. Overall progress remains 10/16=62.5% and API 3/6. No physical access, external publication, or subagent calls occurred.

Subsequent bw451 obtained a separate [public SensorStage evaluation package](gaf-public-evaluation-package.md). The login-required item above does not mean all public material is absent. Whether the evaluation package is identical to the full SmartMotion SDK and whether normal GAF calculation is implemented remain unconfirmed.
