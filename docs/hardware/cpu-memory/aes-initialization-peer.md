# Natural M55 Execution of 32 AES-CMAC Transactions

bw-0297. Connected the 32 requests and responses in the [verified original AES-CMAC contract](aes-initialization-contract.md) to an optional virtual HCI peer. No glasses or charging case were accessed.

## Results

| Original main | AES scenario | Cumulative command / response events | Actual next request |
| --- | --- | --- | --- |
| Stock 2.4 | Enabled | 54 / 55 | `01052006`, 10 bytes |
| Stock 2.3 | Enabled | 54 / 55 | `01052006`, 10 bytes |
| Faceclaw | Enabled | 54 / 55 | `01052006`, 10 bytes |
| Stock 2.4 | Disabled control | Previous 22 / 23 | Previous `01172020`, 36 bytes |

Each of the three enabled runs recorded 211 CS frames, 422 IOM commands, and 52 application reply drains. Renode M55 executed from the original main reset without changing main bytes, the PC, or return registers. The existing virtual peripheral, initial memory, and response assumptions still apply. This does not prove a complete ROM boot or equivalence to physical hardware.

The previous isolated Unicorn test stopped at an FR read in an environment without UART1. This natural run passed that path through the existing UART1 model. Each image retained its earlier UART1 transmit prefix, added 30 bytes, and entered the UART1 exception 12 more times. This is evidence of virtual UART transmission and M55 IRQ execution, not validation of physical UART timing, peers, responses, or the complete lifecycle. The additional transmitted content was not identified conclusively as the CMAC tag itself.

The next request was confirmed by correlating R8=10, R9=0, R10, and the original ring record in actual SRAM. `2005` is LE Set Random Address with a six-byte argument, cross-checked against the searchable [SIG specification §7.8.4 distribution copy](https://community.renesas.com/cfs-file/__key/communityserver-discussions-components-files/297/Core_5F00_v5.2.pdf). The request stopped at the original write-ready GPIO check and was not transmitted. The PC was `0x501676` for stock 2.4 and `0x549fce` for the older image and Faceclaw.

## Model and Safety Boundaries

`BlackwallEm9305EventPeer.aesInitializationHex` is disabled by default and requires the fixed public P-256 point scenario. A set contains exactly 32 transactions, each with a 36-byte request and a 23-byte response. Sets derived from proprietary firmware are retained only as private assets outside Git.

The constructor checks framing, opcode, status, and length, then independently recomputes each cryptographic result with .NET AES-128 ECB. It applies HCI byte order and rejects mismatches before execution. The source analysis also checked the results with CommonCrypto and public AES/CMAC test vectors, giving two independent providers for response verification. Initialization was not advanced using arbitrary success bytes or zero results.

At runtime, the model compares the exact request bytes and order sent by the original firmware. Partial transfers follow the existing capacity and CS commit rules. It blocks the next command before a response, incorrect bytes, short reads, extra requests after the transactions are exhausted, and automatic rearming after reset. GPIO and idle checks also account for one extra P-256 event in the expected response count for the subsequent AES stage.

This is not execution of real EM9305 firmware or an implementation of secure random numbers or device keys. No cryptographic policy or persistent region of installable CFW was modified.

## Verification and Reproduction

- First confirmed a red constructor failure requiring the unimplemented `aesInitializationHex`.
- Passed 1,138 checks at default capacity 9, 3,131 at capacity 2, 364 with the new scenario disabled, and 58 for the existing two-command scenario.
- Confirmed successful construction and rejection of incorrect lengths, headers, cryptographic results, and a missing prerequisite public point.
- Passed four final natural runs and four separate saved-run audits. The audits did not rerun the CPU.
- The disabled control exactly matched the preceding P-256 baseline in CPU state, command count, registers, and all existing observation events.
- Reanalyzed saved results with 50 frozen Python dependencies and confirmed byte-identical reports.
- Changed only `renode-em9305-reset.cs`. Hashes of the three IOM, keyDB, and OTA-marker models remained identical; the compiled changes and the original main and complete SRAM hashes were checked.

The preparation tool `tools/prepare_aes_candidate.py` checks the fixture hash, original main, and initial SRAM hash used in analysis. It also recomputes responses with CommonCrypto and writes a private plan. The audit tool is `tools/inspect_aes_profiles.py`; the existing candidate runner was used. The preparation tool's initial SRAM verification was also cross-checked against existing execution assets.

Private simulator assets:

- `aes-peer-main-01/{stock24,stock23,cfw}`: successful natural runs.
- `aes-peer-control-01/stock24`: default-preservation control.
- `aes-peer-saved-audit-01`: audits of the four saved runs.
- `aes-peer-verification-01/manifest.json`: model, dependency, unit, native, audit, and fixture pins.

The next step is to use the original code to establish the source and validity of the `2005` address, response consumption, and whether advertising initialization follows, then continue toward natural app and display operation. These results do not establish BLE connection, advertising startup, the app loop, or a completed 576×288 display. The web installer, recovery boot, and installable CFW were not modified, and readiness for installation on physical hardware remains incomplete. Overall product progress remains at scope v2, 13/29 = 44.8%.
