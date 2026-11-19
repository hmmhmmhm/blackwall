# MSPI1 Zero-Turnaround RDID Contract After Scan

Task bw-0175. Analyzed bw174 original execution logs and pinned source without changing the peripheral model. Stock 2.4, 2.3, and Faceclaw all stop at the same three-byte RDID request after scan ends. The next model extension targets this request; receive completion has not yet been verified.

## Confirmed request

`inspect_mspi1_post_scan_rdid.py` reads each image's saved log with a strict parser and compares it with the report. Main bytes match originals extracted from the pinned bundle. The next request appears after scan actually returns R0=0.

| Item | Existing RDID during scan | Request after scan |
| --- | --- | --- |
| DEV0CFG | `03010861` | `03010061` |
| TURNAROUND0 | 8 | 0 |
| INSTR | `9F` | `9F` |
| CTRL request | `30441` | `30441` |
| Receive length | 3 bytes | 3 bytes |
| Address transmission | None | None |

The DEV0CFG values XOR to `800`. In pinned Apollo510 SVD/header, TURNAROUND0 is bits 13:8, mask `3F00`; no other field differs. The post-scan value has TXNEG=1, RXNEG=0, RXCAP=0, CLKDIV=1, CPOL/CPHA=0. Saved logs also confirm DEV0XIP=`ED` and CTRL1=0. These are controller configuration interpretations, not measurements of actual electrical waveforms.

The actual R1 descriptor has the same first 20 bytes as the earlier RDID; its last word is a bounded SRAM receive buffer. This stock 2.4 buffer is `20329C98`. Original helper entry, transfer call, and stack return address were compared at instruction boundaries. Thus there is no need to treat arbitrary opcodes as successful or change the scan return value. Transfer completion and the path where original code uses the ID must be checked in the next execution.

## Manufacturer evidence and scope

Compared SHA-256 of the previously obtained Macronix MX25U25643G v1.1 PDF with the existing source manifest. Page 27 describes CS assertion, instruction, and 24-bit ID output in sequence for RDID, explicitly in SPI mode only. It does not describe a required dummy cycle between command and ID. Under the current idle SPI NOR model assumption, zero-turnaround RDID is therefore a reasonable extension candidate.

This does not identify the chip fitted to the actual glasses or confirm its current protocol mode or physical timing. Do not extend the existing eight-turnaround exploration model into physical calibration either. There is no basis to allow all turnaround values or other instructions and receive lengths indiscriminately. The next implementation must separately verify this confirmed request and compatibility with existing profiles while retaining unknown-transfer guards.

## Verification results

The 41 checks in `simulator/mspi1-post-scan-rdid-contract-01/report.json` outside Git verify pinned metadata, manufacturer documentation, three original mains, saved strict requests, descriptors, scan returns, and helper call positions. This work did not rerun native main or change peripheral source. It prepares follow-up model work based on source evidence and does not prove full boot, display, BLE, or recovery success. Overall progress remained 13/29, 44.8%.

There was no glasses connection, installation, RAM execution, or persistent write.

A read-only review by an agent inheriting the parent model found no material offset or interpretation errors. The new request's contract is distinct from successful reception. No Astra, other model-family review, or full transcript-file audit was performed.
