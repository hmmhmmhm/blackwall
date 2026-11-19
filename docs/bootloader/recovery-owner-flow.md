# Recovery reception and write ownership with damaged main

bw-0244. The pinned 2.4 boot research candidate's flow was investigated and a compiled UART2 worker test added without executing damaged main. **This is not integrated evidence of RAM writer execution, MRAM writing, scheduler, case, or physical recovery.**

## Owners and connections

| Stage | Source-level owner | Current evidence and remaining boundary |
| --- | --- | --- |
| Normal main web OTA | Main BLE/OTA service | Not assumed alive with damaged main. VirtualTemple retransmission is a host fixture |
| Recovery entry | Patched boot_task_then_flag manager | Creates worker thread after UART handle/pin table, awake/callback, and wake/power checks. Scheduler/entry window not integration-verified |
| USB→one temple | Host CaseLink and case RAM relay | Case ROM loader, identity/firmware checks, SRAM upload/readback, single route and boot beacon/hold. Depends on case 1.2.57 source; compatibility of owned case unconfirmed |
| UART2 authentication and RAM-program reception | Compiled uart2_worker | HELO/HOLD/OKAY HMAC, LOAD length/entry/CRC32, DATA then READY. ARM executed in this test |
| RAM-program invocation | boot_ram_invoke and RAM API3 | Compiled send_output/recv_input and held-session context configuration confirmed. Stopped before actual call entry |
| Main-byte writing | RAM recover.bin | Up to 256-byte recv→stock MRAM function 0x42e84d→cache invalidate→readback→progress. Supported by source and prior standalone writer tests; not yet connected to new worker fixture execution |
| Full recovery sequence | Host Recovery.recover/install | Boot-prefix preflight/API checks/backup/CRC→body write/CRC→vector 16-byte final write/final CRC→optional CONTINUE. Not atomic rollback |

The worker does not depend on main BLE stack or main function calls. But **being able to execute the worker function** differs from **a damaged device actually executing the worker during boot**. Global initialization, thread scheduling, watchdog/interrupts, and case reset require separate evidence. Existing initialization/registration results from [boot analysis](bootloader-2-4-analysis.md) are reused without elevating them to full boot success.

## New execution tool and verification

`tools/emulate_recovery_worker.py` verifies pinned full boot SHA, append blob/metadata, and byte correspondence, then starts uart2_worker in a synthetic thread-entry context. Main vector is 0 in virtual MRAM; main fetch and MRAM writes are rejected.

UART MMIO connects to byte queues and upstream Client exchanges actual packets. Unlike previous upstream Worker tests replacing receive/transmit functions, the new fixture executes their ARM instructions. The previous 118 tests were not rerun.

Stock tick/delay/GPIO callees, immediately ready UART, and cache-maintenance storage are explicit models. The three callees' results/return PCs are mocked, so this is not natural main reset or physical timing. HMAC, CRC, LOAD/DATA, and session configuration are compiled code. It stops before the first boot_ram_invoke instruction and does not synthesize payload success return.

```sh
blackwall_sim="$HOME/Library/Application Support/Blackwall/simulator"
"$blackwall_sim/venv-02/bin/python" tools/emulate_recovery_worker.py \
  "$HOME/Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01" \
  --output "$blackwall_sim/my-new-worker-run/report.json"
```

Output is a new file outside Git, saved 0600. Key is used only for in-process HMAC; raw handshake/key are not recorded in the report. No serial/BLE tools or upstream CLI are executed.

Private `simulator/recovery-owner-01/report.json`: UART 20 frames, API 3/held 1, writer 264-byte SHA match, compiled callback/session correspondence confirmed. Stop PC 0x434910 is actual boot_ram_invoke entry. Main instructions 0, MRAM writes 0, payload executed=false, recovery_verified=false. Passed=true means this limited contract passed.

Three tests passed: normal authentication/upload→RAM invocation boundary; BAD_CRC rejection of an upload with correct frame checksum but wrong code CRC and blocking host's subsequent RUN; and claim rejection of HOLD with one bit changed from correct HMAC. The last stops waiting at an instruction budget, not an actual authentication timeout test. Results remain in `tests.log`.

## Newly clarified safety differences

- Upstream recover() can warn about pending flag 0x55555555 and continue writing. The writer itself also does not reject the pending flag. Blackwall must stop on pending/unknown, so raw CLI is not treated as a safe execution wrapper. A separate hard gate is needed before actual writer connection.
- preflight() checks stock boot-prefix SHA with hook restored. Local full patched-boot/key pairing cannot substitute for full-hash identification of an actual device.
- Direct MRAM main recovery does not restore NOR resources, codec, or full boot. Body/vector restoration is not labeled full stock.
- VirtualTemple stock retransmission after damage remains a host write. The new fixture did not replace that transport or integrate complete W5 recovery.

## Next unit

Follow-up bw245 [M55 resident writer](recovery-m55-resident-writer.md) connected actual context wrapper, writer/callback, stock MRAM adapter, and virtual ROM writing. It checked normal 512 bytes and four error/short-range conditions; full recovery, manager/case, and physical boundaries below remain.

Connect RAM call entry through writer→callback→stock MRAM wrapper in the same state. Do not omit M55 context save/restore or synthesize success returns. Reuse existing Renode M55 and standalone writer/PMIC evidence, distinguishing ROM programming mock from hardware. Then connect the segment where manager/relay actually enters with main unavailable. If blocked by external evidence, switch to D3 resolved_font→buffer lifetime→renderer caller research.

Product 13/29=44.8%, scope v2, and physical-device authorization boundary remain.
