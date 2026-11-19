# M55 resident writer and virtual MRAM writing

bw-0245. The actual RAM-call state from the [previous worker test](recovery-owner-flow.md) was moved to Renode M55, connecting pinned ARM context wrapper → uploaded recover.bin → compiled recv/send callbacks → stock MRAM wrapper → virtual ROM write → worker RESULT. **This is not completion of physical device recovery, full main recovery, or web UI integration.**

## Code executed and explicit models

Pinned 2.4 research boot and writer bytes were unchanged. First the Unicorn worker completes authentication, upload, and CRC check and stops at the first boot_ram_invoke instruction. MRAM 4 MiB, SRAM 512 KiB, and general/control registers are saved and hash-pinned. Main vector is 0 and execution of main instructions rejected. Existing capture was reused; authentication/upload were not repeated for each debugging attempt.

M55 distinguishes:

- R0–R12, SP, LR, APSR/XPSR, BASEPRI, PRIMASK, and FAULTMASK are compared with saved state.
- M55 extensions not observed in Unicorn are separate fixtures: FPU on, CONTROL.FPCA=1, VPR=0xffff, distinct S0–S31 patterns, and stack limits 0. CONTROL adds bit 2 to saved value, so complete CPU state is not claimed identical to the original.
- Tick, delay, GPIO, stock IRQ/power helpers, and ROM programming entry 0x0200ff20 are explicit models. Calls to these bindings return modeled results. Scheduler, physical UART/baud, and ROM internals do not execute.
- Only the ROM model writes virtual bytes within the permitted main-body range. Direct guest MRAM stores are rejected. Stock MRAM adapter 0x42e84c executes actual original instructions.
- UART input is prequeued transcript replay. Actual bytes/CRC of ARM output request/progress/RESULT are compared with expected frames. Dynamic host stop-and-wait or case relay was not verified.
- Cache memory is a coherent fixture. DCacheInvalidateByMVA writes validate range, alignment, and address sequence in an NVIC register action. Actual stale cache and cache timing are not implemented.

Vpush/vpop, VPR, FP/control, and general register save/restore in boot_ram_invoke 0x434910–0x434986 were not bypassed. At return to original LR, R0–LR, S0–S31, and control state matched the initial M55 fixture. Return result is stored in the original call struct and compiled worker sends the actual RESULT frame.

## Results

| Condition | ROM model calls | Virtual write | Actual ARM result |
| --- | ---: | ---: | --- |
| Normal 512 bytes | 2 | 512 bytes | Block progress 256/512, RESULT 0, readback matches |
| ROM status 7 | 1 | 0 bytes | Stock adapter returns 0x08000107, no retry |
| First-block readback mismatch | 1 | 256 bytes including injected corruption | Writer RESULT 3, second block not written |
| Minimum 16-byte readback mismatch | 1 | 16 bytes including injected corruption | Writer RESULT 3, context restored |

All four confirmed one context entry/return, preservation of 16-byte main vector, zero guard violations/CFSR/HFSR, and general/FP/VPR/control restoration. Cache addresses: normal 18, ROM failure 0, 256-byte mismatch 9, 16-byte mismatch 1. Original behavior processing the same line twice at block boundaries is preserved.

Final three conditions are retained in private `simulator/recovery-m55-writer-12/`, and 16-byte condition in `recovery-m55-writer-edge-01/`. `recovery-m55-verification-01/audit.py` passed 144 checks for saved source/model/input/log SHAs, GPR transfer, explicit FPCA difference, context return/frame/cache addresses/write ranges, 0600 permissions, and more. Five new host capture/output boundary tests and three existing worker tests also passed. Native was not rerun for audit.

## Tool use

```sh
blackwall_sim="$HOME/Library/Application Support/Blackwall/simulator"
"$blackwall_sim/venv-02/bin/python" tools/run_recovery_m55_writer.py \
  "$HOME/Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01" \
  "$blackwall_sim/my-new-resident-writer-run"
```

Use a new output. MRAM/SRAM copies potentially containing proprietary material or private keys are 0600, folders 0700. Outputs inside any Git/worktree, not just Blackwall, are rejected before reading firmware. No device/BLE/serial access occurs. Docker uses a pinned image and network none, with runs sequential.

## Execution conditions learned from failures

Initial binding/execution failures are retained in separate folders. Python int→RegisterValue conversion, PC setter initialization indication, standalone process protocol dependency, and FPU enable/FPCA seed were corrected. A run setting only CPACR produced NOCP UsageFault 0x80000 at vpush and was not counted as passing. The same instruction ran in a native profile with FpuEnabled on.

RunFor could fail to reach target virtual time on an aborted machine. Thereafter StartAll and bounded host wait/pause were used like the common main runner, retaining cleanup of an external 45-second timeout. Termination and absence of corresponding containers for initial manual stop and timeout were confirmed.

An unhandled cache-invalidate warning was not ignored. An attempt to register a separate peripheral overlapping the NVIC address was rejected; as with existing system-control pattern, NVIC register action/hook was connected after board registration. Native crash from a pre-registration hook attempt was also retained. Final four runs have no warnings/errors except translation-cache clamp.

API references: [Renode hook documentation](https://renode.readthedocs.io/en/latest/basic/using-python.html), [CortexM FpuEnabled implementation](https://github.com/renode/renode-infrastructure/blob/master/src/Emulator/Cores/Arm-M/CortexM.cs). Live documentation was not substituted for pinned-image behavior evidence; actual APIs used were confirmed in native runs above.

## Remaining integration

This is a limited body experiment on a recovery path independent of damaged main. Full image backup/CRC, vector-last, pending OTA hard gate, actual host stop-and-wait, manager scheduling/PMIC/case relay, physical ROM programming, and physical restoration are not yet integrated. Main-body writing is not judged full stock. The next product axis is D3 font-wrapper buffer lifetime and actual renderer-caller integration, while remaining W5 recovery integration stays open.

Product 13/29=44.8%, scope v2, and glasses installation/write authorization boundary remain.
