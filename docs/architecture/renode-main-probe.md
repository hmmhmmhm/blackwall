# Executing Actual G2 Main Startup Code in Renode

Status: Initial code was executed from the reset vector of two pinned stock versions and Faceclaw main, stopping at the first external power-register access. This is not full boot or installation compatibility validation.

## Runner and boundary

`tools/run_renode_main_probe.py` checks exact SHA-256 and component CRC for the existing three bundles, then extracts only main. It does not execute original bootloader, case, BLE, or codec. It validates initial SP and reset vector and points the Renode M55 vector table to main.

Virtual memory comprises 0x3c0000 bytes of main from 0x438000, 512 KiB SRAM, 3 MiB System SRAM, and 256 KiB ITCM. SRAM/ITCM are filled with A5. Initial tests lacked main write protection and ITCM guest-written-byte execution restrictions. Subsequent implementation applies the [memory policy](renode-memory-policy.md) by default. Do not claim all protections and peripheral models from the existing Unicorn runner were ported.

M55/NVIC are existing Renode models. Virtual MIPS and SysTick frequency are virtual settings, not actual Apollo510B timing. This does not establish correctness of every intrinsic core register. Pre-boot hardware and bootloader state were not supplied.

`tools/renode-strict-mmio.cs` was registered for peripheral space 0x40000000..0x5fffffff and separate PPB space 0xe0010000..0xe010ffff. Instead of returning zero on reads or ignoring writes, the model records address, width, kind, and value of the first access and aborts the CPU. The guard does not check internal registers already owned by Renode core models. Warnings in those internal paths are treated as separately unverified messages in the report.

CPU abort stops virtual time, so RunFor is not used to wait for completion. After a bounded host execution interval, the CPU is paused and state read. The default is two seconds, allowed range 0.01–15 seconds, and whole-process timeout 45 seconds. If time ends before the first stop, report host-window-ended. The first 0.5-second stock 2.4 test reached this limit while processing data and was not interpreted as failure or boot completion. The first RunFor attempt waited after abort until hitting the container memory limit and was replaced with the host-time approach.

Execution uses a container with network none, 512 MiB, one CPU, 128 PIDs, removed capabilities, and no-new-privileges; only relevant input/output folders are mounted read-only. Actual glasses and Docker socket are not passed in. Original main and generated files are retained only in new output folders outside Git.

## Actual firmware results

| Input | First read address | Width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | 0x40021000 | 4 | 0x489fb4 |
| Stock 2.4.0.24 | 0x40021000 | 4 | 0x495e9c |
| Faceclaw 38 | 0x40021000 | 4 | 0x489fb4 |

Each guard access count was exactly one, with no PPB guard accesses or unverified engine messages. The existing Unicorn runner was also run with identical images, A5 memory, and only the core-register storage hypothesis. Main SHA, bundle SHA, first external address, width, and PC matched Renode for all three inputs. This cross-checks an initial execution boundary, not full execution equivalence or accuracy of all core behavior. Instruction counts and host time are not used to compare hardware performance.

Execution JSON/logs are retained in `Blackwall/simulator/renode-main-stock23-01/`, `renode-main-stock24-02/`, and `renode-main-faceclaw-01/`; cross-comparison is retained in `unicorn-renode-startup-comparison-01/comparison.json`.

## Verification of actual guard behavior

`tools/verify_renode_mmio_guard.py` builds seven independent M55 ELFs and runs them on actual Renode. It tested six 1-, 2-, and 4-byte read/write cases and a PPB read. Each program first writes RAM sentinel 0x11112222 and is arranged to overwrite it with 0x33334444 after the unsupported access. In all seven cases address, width, kind, and write value were correct, access count was one, and the sentinel remained 0x11112222. This is evidence that the guard does not return zero and allow subsequent code to execute. Results are in `renode-mmio-guard-verification-01/report.json`.

Reproduction example:

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-renode-main"
python3 tools/verify_renode_mmio_guard.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-renode-guard-check"
```

[M55 environment setup](renode-m55-probe.md) is a prerequisite. Next was connecting Apollo510 power-register behavior to Renode and comparing with the existing runner's virtual power conditions. Execution of initial code alone does not validate Faceclaw's subsequent hooks, display, BLE functions, or recovery.

Later, [LP/HP power and reset-shadow fixtures](renode-startup-fixtures.md) were connected as explicit options. Three images × two modes advanced to the next watchdog access, with the same boundary confirmed in Unicorn. Default no-model execution still stops at the locations in the table above.
