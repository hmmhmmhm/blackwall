# Capturing original RTOS state for GPU completion IRQ

Follow-up bw265 obtained [full SRAM/ITCM and linked task structures](../../firmware/original-main-full-memory.md). Below records the earlier partial RTOS capture; it is still not a complete machine checkpoint.

Work `bw-0262`, following the [completion IRQ contract](nema-irq-completion-wait-contract.md). Kernel globals, current TCB, and stack were collected from original main. This is not evidence of actual IRQ delivery, PendSV execution, or full boot.

## Execution and capture scope

`tools/nema-rtos-context-candidate.json` uses the same pinned Renode M55, board, original ARM, and peripheral models as existing `em9305-reset-main-01`. It runs from original reset and emits diagnostics only after stopping at existing SPI DCXCTRL boundary. No CPU register writes, guest branch changes, or IRQ injection.

CPU observations and all events matched existing runs exactly across three images. Each capture includes 32-bit registers actually enumerated by the executable, three source-identified kernel globals, 512 bytes from TCB pointer, and 512 bytes each from current SP, OtherSP, and address pointed to by TCB first word. Addresses are limited to aligned board SRAM ranges. This does not mean actual TCB size is 512 bytes; later bytes may contain neighboring objects. A5 fill or zeros are not interpreted as initialized fields.

## State confirmed

| Item | Stock 2.4.0.24 | Stock 2.3.0.24 | Faceclaw 38 |
| --- | --- | --- | --- |
| Two scheduler-query inputs | `1 / 0` | `1 / 0` | `1 / 0` |
| Original query return | `2` | `2` | `2` |
| Current TCB | `0x200743c0` | `0x20074f2c` | `0x20074f2c` |
| Current SP | `0x2004ac20` | `0x200488c8` | `0x200488c8` |
| Saved SP in TCB first word | `0x2004ad00` | `0x200489a8` | `0x200489a8` |
| OtherSP raw | `0x2007fa90` | `0x2007fa90` | `0x2007fa90` |
| CONTROL / xPSR | `6 / 0x01000000` | Same | Same |
| BASEPRI / PRIMASK / FAULTMASK | `0 / 0 / 0` | Same | Same |

Original query function itself ran in a separate Unicorn M7 fixture. Only ROM and two globals were supplied, SRAM writes forbidden, and original `bx lr` returned within 32 instructions. Return 2 is this contract's result, not identification of exact G2 FreeRTOS version.

With xPSR IPSR=0 and CONTROL.SPSEL=1, current SP is interpreted as Thread-mode PSP under [Arm CMSIS SP-selection rules](https://arm-software.github.io/CMSIS_6/latest/Core/group__Core__Register__gr.html). OtherSP is preserved by execution API name and raw value, not marked as separately verified MSP.

Current SP and TCB saved SP differ by 224 bytes in all three. A running task's TCB saved pointer cannot substitute for current CPU context. Meaning of TCB first word was confirmed from original PendSV store instructions, but the complete saved frame was not verified as currently restorable context. TCB name candidates or neighboring words were not arbitrarily established as required execution structures.

## Execution API limits

Pinned runtime reflection inventory confirmed `SP=13`, `OtherSP=22`. There was no PSPLIM/MSPLIM-specific enum or property. `IsUsingProcessSP` property exists but was not read in this main capture, so its value is not reported.

Downloaded Renode infrastructure `042a58285ee91453f99d31f19e8aa140102ec540` `CortexMRegisters.cs` has `MSPCURR=107`, `PSPCURR=108`. They are absent from the actual pinned executable's enum and were not used. This specifically shows source head and binary API agreement is unconfirmed. Do not substitute 0 for PSPLIM or infer it from one TCB word.

Next establish a verified way to read stack-limit state on pinned M55, then test actual IRQ entry and original PendSV save/restore in a limited test. Existing live-draw fixture's synthetic stack and partial SRAM must not be treated unchanged as kernel-ready context. Full task selection also needs more scheduler state and other task stacks.

## Preservation and verification

Under `simulator/` outside Git:

- `nema-rtos-context-main-01/stock24`: report creation failed due to wrong CPU variable name in observation code; failure input/log preserved.
- `nema-rtos-context-main-02/{stock24,stock23,cfw}`: three runs correcting only variable name; schema2 semantic checks passed.
- `nema-rtos-runtime-api-01`: CPU enum/property inventory from same Docker image; separate API query without starting guest program.
- `nema-rtos-api-research-01`: comparison source and URL/SHA, marked runtime match unconfirmed.
- `nema-rtos-context-verification-01`: initial 63-check audit.
- `nema-rtos-context-verification-02`: final **72 checks passed**, adding plan match, pinned main SHA, and runtime identity except diagnostic insertion. Saved material was audited without native rerun.

Inspector: `tools/inspect_nema_rtos_context.py`. Three original main runs and three original leaf-query runs are distinct. No physical-device access; overall goal remains **13/29=44.8%**. D3 original-main display path and integrated 576×288 screen remain incomplete.
