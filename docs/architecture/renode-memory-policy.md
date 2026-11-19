# Renode Main Write and ITCM Execution Protection

Status: Applied by default in the main runner. It stops main CPU writes, reads/execution beyond the main file, ITCM instructions not written by the guest, and SRAM code execution. This does not reproduce the actual device's MRAM controller or security configuration.

The bw419 [post-reset protection-lifetime test](../hardware/power/reset-memory-protection-lifecycle.md) found and fixed a defect where CPU reset cleared page-I/O routing and allowed out-of-range reads. Distinguish initial execution protection from post-reset protection; do not retroactively apply the corrected policy to past successful evidence.

## Implementation and source evidence

`tools/renode-memory-policy.cs` attaches after loading the image and A5-initialized memory and before execution. Host-initialized ITCM bytes are not considered guest-written. The main runner has no option to disable protection.

Initially tested bus-write hooks and page-I/O routing alone could not block main writes. [Renode documentation](https://renode.readthedocs.io/en/latest/advanced/writing-peripherals.html) explains that MappedMemory accesses are handled in the C layer. The tlib gitlink of pinned Infrastructure commit `042a58285ee91453f99d31f19e8aa140102ec540` is `antmicro/tlib` `9251d7e8d5b6bab6d4a6d5299e4832f98b75c6cc`. Its [exec.c](https://github.com/antmicro/tlib/blob/9251d7e8d5b6bab6d4a6d5299e4832f98b75c6cc/exec.c) and `include/softmmu_template.h` show a path where NOTDIRTY writes to clean code pages can bypass bus calls. Actual independent tests also changed main.

Main writes are therefore prohibited using Renode external permission windows. Three identity windows covering the entire 32-bit address space are placed BeforeInternal: only main mapping is Read|Execute; the rest is All. This is a virtual policy added before internal CPU permission checks, not validation of actual MPU configuration accuracy. Permission errors record address and PC and abort. The callback supplies no width, so report width=0 means **unknown**. Test code labels byte/halfword/dword writes separately, but does not claim the callback measured width.

Reads after the end of the main file are detected through bus read hooks and page-I/O routing. The hook runs after the background-memory read itself, but aborts before the guest executes the next instruction using its result. This is not a model returning zero from empty space as normal data.

ITCM writes are tracked per byte in a CPU memory-access callback. That callback runs after the write and is not used to block main writes. Before executing a code block, Thumb instruction length and whether each byte was written are checked; code execution outside main/ITCM is also rejected. Verified ITCM blocks are cached but invalidated on every ITCM write. A rewritten guest instruction that becomes longer and extends into unwritten bytes is checked again.

## Verification and regression runs

Two controls in `verify_renode_memory_policy.py --unguarded-control` first confirmed that main writes and execution of host-prefilled ITCM were allowed. Failed results are retained in `renode-memory-red-01/`.

Eleven checks in final `renode-memory-verification-09/report.json` passed.

| Test | Confirmed result |
| --- | --- |
| Three main byte/halfword/dword writes | Original word preserved; subsequent RAM completion write not executed |
| Host-initialized ITCM execution | Not recognized as guest-written; stops |
| Guest-copied ITCM code | Return value 7; four written bytes |
| Only first halfword of 32-bit instruction written | Stops before execution; two written bytes |
| Main padding read and execution | Stops at exact out-of-range address |
| ITCM code rewrite | Changed return value 9 confirmed |
| Instruction length extended by rewrite | Cache rechecked and unwritten-byte execution blocked |
| SRAM code execution | Stops before execution |

Blocked address, PC, width where provided by callbacks, written-byte count, RAM sentinel, return value, and unexpected engine warnings were checked too. Intermediate executions failing compilation/object generation are not success evidence. Shared execution tooling was improved to preserve logs on timeout.

With protection enabled by default, stock 2.3, 2.4, and Faceclaw under revision 0x23 + SPOT storage stopped at the same 0x40021018 read as before. PC was 0x488a7c for 2.3/Faceclaw and 0x494964 for 2.4. Raw main hash and previously observed state excluding memory policy and instruction count matched prior reports. Default-option stock 2.4 also retained 0x40021000, PC 0x495e9c. All four runs had 24 guest-written ITCM bytes, zero protection violations, and zero unverified engine messages. boot_verified, hardware_validated, and installable remain false.

Results are outside Git in `Blackwall/simulator/renode-memory-*/`. The comparison is retained in `renode-memory-regression-comparison-01/report.json`.

```sh
python3 tools/verify_renode_memory_policy.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-memory-policy-tests"
```

## Remaining limitations

Instruction blocks are checked before execution. This does not mean native decoders are prevented from pre-reading unwritten bytes. Code generated later in the same block by its earlier instructions may cause a conservative stop. Do not conceal this with automatic retry or check bypass.

This policy is for the current single-main startup test. Full reset, retention, multiple CPUs, DMA writes, actual MRAM write controller, hardware aliases, and cache/security state have not been validated. Peripheral models, full boot, firmware display, web installation, and physical recovery validation also remain incomplete. Actual glasses were not accessed.
