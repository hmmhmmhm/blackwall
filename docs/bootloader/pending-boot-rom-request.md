# Actual ROM request in pending boot and next boundary

2026-11-17 · bw-0572. At the stop in the original pending path, the **actual ROM request to write 16 FF bytes to 7fe000** was confirmed. Subsequent original code requests software POR without using the write return value. That subsequent reset itself was not executed. BV02 remains partial, overall 8/12=66.7%.

## Request confirmed in actual ARM execution

Existing pending ready/stuck boards, original boot/main, and strict model were reused unchanged. New opt-in `--capture-rom-request` reads CPU registers and bounded 16-byte SRAM only after pausing the existing machine. It neither maps ROM nor supplies a success return.

| Item | Actual ready / stuck value |
| --- | --- |
| Stop PC | 0200ff20, original ROM bytes absent |
| Key / operation | 12344321 / 1 |
| Source | 20022d68 |
| Destination offset / address | ff800 word / 7fe000 |
| Length / actual source | 4 words / FF×16 |
| LR | 42ec11, instruction after BLX in original ROM trampoline |
| PRIMASK | 1 |
| ROM power status | ready cf / stuck 4f |

Both runs reached original reset→manager→pending decision→original MRAM wrapper→ROM entry. Main/handoff 0, CPU fault 0, memory-policy/peripheral guard 0, boot/main SHAs unchanged. **This is not successful ROM execution, write, or reset.** Original code attempted the ROM call even when stuck; this is not generalized to actual ROM's not-ready handling.

The two raw `exports/result.json` files from bw556 and complete JSON from new runs were exact before observation. Original collection scope including GPR, SP, instruction count, virtual time, event/context, and fault/guard matched. The new observation additionally reads power status after pause, so no claim is made that all peripheral read counters are unaffected.

## Original clear and reset code

The following instructions in original boot SHA ecb91896… were directly decoded:

- The literal at 42e180 is 7fe000; source-template literal at 42e18a is 434320. Original template's 16 bytes are all FF, matching actual request source.
- Original alignment-check wrapper 42e84c is called at 42e19a.
- Immediately after return, 42e19e overwrites R0 with saved PRIMASK, and 42e1a0 restores IRQ state. There is no branch checking write result.
- After setting R0/R1 to 0, it calls 42e86c at 42e1a8. That function's 0 branch writes D4 to 40000008 and waits.

Pinned SHA b6ca35dc… of the preserved public Apollo510 header was also compared. The request corresponds to RSTGEN.SWPOR software POR key. Actual POR propagation or retention was not confirmed in this run. Decode, opcode, literals, and original/public-header hashes are retained in the private audit.

Thus this ROM request differs from programming the complete main image: it clears pending metadata and resets. Since the original does not use write status, a **virtual failure control must check whether reset with the marker still present re-enters pending**. Currently this is a source-supported expectation, not execution verification of a retry loop or physical observation.

## Contract for next implementation

Existing `BlackwallOtaMarkerRead` supplies one immutable word to specified original read consumers. Simply returning ROM success in that state would make persistent state and CPU branch disagree; BV02 is not completed that way.

Next connect explicit virtual 16-byte state and a ROM program functional contract limited to this actual request. Record initial 16 bytes, modification range, per-word changes, and post-reset preservation while retaining key/op/address/length/source/IRQ/power validation. Distinguish ready-success, ready-ROM-error, and interruption/partial writes; do not unconditionally succeed stuck. Connect original SWPOR request and new boot pending/cleared selection without describing it as execution inside original ROM. Existing readonly profile and physical-access restrictions remain.

## Evidence, verification, and cleanup

Outside-Git `simulator/pending-rom-request-bw572-01/{ready,stuck}` retains frozen source/board/runtime, manifest, native logs, raw results, and rom-request.json. `pending-rom-request-audit-bw572-01..02` passed 25 conditions for request/full-run exactness, original clear/reset instructions, public header, classification, permissions, and termination. Saved audit source was rerun outside the repo in `/tmp` using the existing Capstone environment. Eleven runner units also confirmed RED→GREEN.

Termination and container absence for two owned natives were confirmed. Runner verified and immediately cleaned up duplicate main inputs/guest image dumps totaling 15,099,818 bytes. No new host build/cache was created; original inputs, key analysis/logs/hashes, and 16-byte observation remain. No glasses/BLE/serial/external posting/subagent execution occurred.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/run_boot_validation.py pending-rom-ready "$bw_assets/simulator/pending-request-new-01" --capture-rom-request
"$bw_assets/simulator/venv-02/bin/python" -B "$bw_assets/simulator/pending-rom-request-audit-bw572-02/audit-source.py" "$bw_assets/simulator/pending-rom-request-bw572-01" "$bw_assets/simulator/pending-request-audit-new-01"
```

BV02/BV05/BV06/BV12 in the current [overall progress table](../data/bootloader-validation-progress.json) remain incomplete. Earlier [virtual full-stock restoration completion](main-driven-boot-restore-results.md) remains unchanged.
