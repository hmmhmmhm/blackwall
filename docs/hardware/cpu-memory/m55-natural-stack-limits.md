# Observing Original PendSV and Stack Limits

Task `bw-0263` follows [RTOS state collection](../display-gpu/nema-rtos-context-readiness.md). Stack-limit instructions were verified on the pinned Renode M55, and 120 PendSV executions naturally performed by the stock 2.4 original main were observed. This did not connect a new GPU completion IRQ or complete full boot.

## Query method and independent core test

The actual runtime exposed `GetSystemRegisterValue(string)`, but `PSPLIM`, `MSPLIM`, lowercase names, `PSP`, `MSP`, and `CONTROL` all returned `No such register`. An invalid-name negative control did the same. The existence of the method was not mistaken for a supported Arm-M register API.

`tests/fixtures/m55-stack-limits.c` and `tools/probe_m55_stack_limits.py` tested an independent M55 core without G2 code. Actual ARM `MSR/MRS` wrote and read these values, then restored the originals.

| Register | Explicit test value | Read and restore |
| --- | --- | --- |
| PSPLIM | `0x20002000` | Passed |
| MSPLIM | `0x20001000` | Passed |
| PSP | `0x20008000` | Passed |

Eight conditions passed, including the completion mailbox and absence of faults. This shows that the implementation does not always return 0 for PSPLIM. The test does not verify stack overflow exception accuracy or actual Apollo510B behavior.

## Natural path through original code

The stock 2.4 raw main SHA is `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a`. The original ARM was unchanged. Execution began at reset on the existing board model and stopped at the existing unsupported SPI DCXCTRL boundary. Guest PC, branches, returns, registers, vectors, and SRAM were not forced.

`tools/renode-stack-limit-observer.cs` collects the following using separate read-only PC hooks:

- Immediately after `MRS r0, PSP` in original PendSV: `0x60bb74`.
- Immediately after `MRS r2, PSPLIM` in original PendSV: `0x60bb82`.
- Immediately after `MSR` at three PSPLIM settings found in the raw image: reset, first task entry, and PendSV restoration.

Original PendSV PSP reads, PSPLIM reads, and PSPLIM restorations were observed **120 times each**. All were actual Handler mode with IPSR=14 and handler SP `0x2007fa90`, matching the value previously preserved under API name OtherSP. CPU `IsUsingProcessSP` was false during these handler observations and true in the final Thread state.

All 362 samples were preserved without loss. PSPLIM reads had 29 distinct values, all nonzero SRAM addresses. The last original PSPLIM setting was `0x20046dc8`, matching the stack-base candidate in the current TCB from an earlier independent main capture. This is the **last observed setting**, not a direct API read of PSPLIM at the stop. MSPLIM during original execution was not directly collected here.

This is evidence that the RTOS's actual PendSV path works in the existing main. It does not establish a new GPU IRQ, GPU semaphore release, or full RTOS context readiness for the draw fixture. Runs adding the same new observation to stock 2.3 and Faceclaw have not yet been performed.

## Execution effects of the observation points

The exact comparison with the existing no-observer baseline **failed**. All original events, general registers, and the final boundary matched, but six leaves differed.

| Item | Existing baseline | PC hooks added |
| --- | ---: | ---: |
| Executed instruction count | 65,991,868 | 65,991,958 |
| startup power reads | 9,683 | 9,684 |
| MCU mode reads | 9,683 | 9,684 |
| device reads | 9,201 | 9,200 |
| GPU enable reads | 5,039 | 5,038 |
| Byte 4 of first stack window | 50 | 49 |

A separate control installed only **empty callbacks** at the same five addresses. Empty and recording hooks produced exactly the same complete CPU observations and existing events; the empty hook collected 0 samples. The difference is therefore narrowed to the installation of hooks rather than register or property reads. Translation-block splitting and timing changes are hypotheses, not proof of the precise internal engine mechanism.

Both native results' original `passed=false` and `comparison:exact` failures were preserved. The checks were not weakened to make the original execution appear to pass. Subsequent candidates and controls must use the same pinned hook layout and continue to disclose differences from earlier runs without it.

## Evidence and follow-up

The following are preserved under `simulator/` outside Git:

- `m55-stack-limit-api-01`, `m55-stack-limit-api-02`: actual API queries and unsupported errors.
- `m55-stack-limit-core-01`: independent core source, ELF, disassembly, mailbox, and hashes.
- `m55-natural-stack-limits-main-01/stock24`: original PendSV samples, `strict.cs` containing the first observer source, failed exact contract and logs.
- `m55-stack-empty-hooks-main-01/stock24`: empty-hook control at the same addresses and failed exact contract.
- `m55-stack-limit-verification-01`: saved-evidence audit by `tools/audit_m55_stack_limits.py`, **67 checks passed**. It distinguishes `audit_passed=true` from `native_exact_comparison_passed=false`. No native rerun was required.

The current project observer also includes an empty control method and control diagnostics. Differences from the first capture's source and plan are audited against the frozen capture. The live plan records the latest component SHA and retains the original no-observer exact contract, so the same differences will still fail.

Next, use controls with the same hook layout to define the full context collection and restoration scope needed for GPU IRQ. Do not substitute a TCB's previously saved SP for the current PSP or fill uncollected SRAM and stack limits with 0 to pass the IRQ. The existing rendering fixture and main context are not yet connected.

There was no physical glasses or case access, firmware write, or external publication. Overall product conditions remain **13/29=44.8%**.
