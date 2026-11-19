# Evidence for Resuming Normal GAF and the Public User Guide

Follow-up bw478: the user supplied the downloaded SDK and actual source review is complete. The unconfirmed SDK contents below describe the state at the time; current findings are in the [SDK source review](../../research/icm45608-sdk-source-review.md).

Follow-up bw477 premise correction: sensor ROM/ISA is not a prerequisite for every functional emulator. The earlier block is a verification gap in the current strict GAF profile, and a separate functional model is a design alternative. Read [SDK usefulness and functional model alternatives](gaf-functional-model-options.md) alongside this. That proposal does not mean implementation is complete or physical GAF agreement established.

bw476. The remaining normal GAF dependency was reviewed after [FIFO/IRQ integration](imu-fifo-gpio-irq-integration.md). Previous busy/trim/NAK variants and host correction tests were not repeated. Official guide AN-000478 rev 1.0, 54 pages, was newly obtained, but **the G2 GAF request 2/4 calculation implementation, execution ISA, and independent numerical results were not obtained.** Model changes and new original ARM runs were 0; overall progress remains 10/16=62.5%.

## Newly obtained material

The current [official ICM-45608 product page](https://www.invensense.tdk.com/en-us/products/inertial-sensors/icm-45608-ict-15312) exposes AN-000478. The cached search listing for AN-000365 differed from actual HTML. A cached title alone is not treated as obtaining the document.

AN-000478's direct PDF URL returned 404 in bw459; this time it was obtained through the ordinary public process on the actual [official download page](https://www.invensense.tdk.com/en-us/download-resource/000478-icm-45605icm-45686-user-guide). The frontend's anonymous app-token flow and public metadata were checked, and only documents with `field_requires_login=false` were downloaded. No account login, device connection, or publication occurred, and the token was not stored. The initial 403 from a direct backend GET without a token was preserved as a preparation failure.

The document covers ICM-45605/45686. Page 14 describes those products' ROM/SRAM and APEX features. That page was rendered and directly inspected, and relevant pages 11/14/25/27 were read in full. Extraction, table of contents, and exact-word index for all 54 pages were preserved. Memory sizes for other products are not substituted for an actual ICM-45608 ROM image or instruction execution specification.

The document did not provide a GAF-specific input/output or request 2/4 calculation contract. No GAF/ISA/opcode hits in the word index are limited search results, not proof that implementation is absent from all possible public material. FIFO configuration order and APEX configuration procedures may be references, but this guide does not complete normal GAF busy.

Current official ICM-45608 SmartMotion eMD metadata still has `field_requires_login=true` and null version. The SDK was not downloaded and its contents were not read at this stage. The [bw451](gaf-public-evaluation-package.md) boundary remains: the public SensorStage evaluation package and this SDK are not treated as identical.

## Common gap across overall completion conditions

E05 requires passing required initialization on three originals and handling RTOS app events. Normal GAF is currently a gap in that initialization. Natural rendering/continuous frames for E09/10, screen after input for E11, and natural sensor task consumption after initialization for E12 share the dependency. Original reset → service/new ATT handling for E06 was already verified, but its condition of **restart during E05 execution** was not yet met. Therefore the same idle-reset variant is not rerun to mark E06 complete.

When new material is received, first classify which execution evidence it provides:

| Required evidence | What to check | Material insufficient alone |
| --- | --- | --- |
| Actual calculation source/specification | Target ICM-45608 and ROM/patch version; request 2/4 inputs, formulas, write scope, lifetime, errors | Host FIFO decoder, another chip's correction function |
| EDMP execution basis | Program/ROM and ISA, registers, memory, call/return rules | ROM entry addresses or RAM patch array alone |
| Independent observations | Before/after state, changed regions, and actual subsequent consumption for the same version and inputs | Existing ARM tests with synthetic ready and accuracy |

Preserve provenance of source/license, version, hashes, inputs, and results, and limit supported effects. One matching fixture does not support all GAF inputs or unknown RAM. Inspecting the full SmartMotion SDK inventory is the next unconfirmed path, but the SDK is not promised to contain sensor ROM/ISA.

This evidence collection is not authorization for physical access. Current glasses I²C/SRAM/ROM were not read, boot was not induced, and no tool was run to probe ROM addresses on an unversioned device. If an inquiry, upload, or physical data collection becomes necessary, present the specific work first.

## Verification and preservation

Private `simulator/gaf-unreviewed-execution-01/` preserves actual product HTML, evidence of public JS/metadata paths, anonymous public document metadata, PDF/text/renders, limited search index, SDK access metadata, and verification. Bundled Poppler pdftotext extracted the PDF and pdftoppm rendered it. After confirming pypdf was absent from the initially selected development venv, existing tools were reused; no new package was installed.

Ten static checks verify only acquisition source, public flag, PDF hash/54 pages, target difference, index, render, and SDK login requirement. They are not counted as calculation accuracy or emulator integration successes. New VM/physical access/subagents/external publication: 0.

## Goal blocked assessment

The same required gap persisted across recent consecutive goal work bw474, 475, and 476. bw474 made independent progress on the original FIFO API and bw475 on pulse/IRQ connection, but neither obtained execution evidence for normal GAF initialization. The new official material in bw476 did not close the gap either.

| Remaining condition | Current verification and final resumption condition |
| --- | --- |
| E05 | Required GAF requests 2/4 and subsequent initialization/app lifecycle incomplete |
| E06 | Three originals have reset/service/new ATT; restart during E05 execution in the condition's wording is unmet |
| E09 | Original draw task is ready but blocked by higher-priority sensor GAF wait; no natural frame generated |
| E10 | Continuous frames over time/events after E09 natural frame must be verified |
| E11 | Input → task → app/UI entry exists; final integration of natural UI/screen effect retains the dependency above |
| E12 | FIFO configuration, IRQ, and separate API consumption exist; natural sensor task consumption after initialization incomplete |

This is not a state where more standalone diagnostics alone can satisfy final acceptance. Current material cannot verify normal calculation, so the blocked assessment applies without reducing goal scope or declaring completion. Direct evidence for resumption is one of calculation source, execution specification, or independent input/output in the table above. SDK access alone is not a resolution before actually inspecting calculation material.

The goal is neither cancelled nor complete. When new material is provided, review that evidence first and resume in order: normal GAF → E05 → natural frame/input/sensor integration. Do not automatically initiate account access, external publication, or physical access to obtain it.
