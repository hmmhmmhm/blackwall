# Stock main MRAM writing and error returns

2026-11-17 · bw-0569. On Renode M55, **original stock 2.4 main adapter and buffer functions executed to check 4 KB write, failure, and readback differences**. This is unit evidence for a restoration candidate independent of existing boot's resident receive code. Upper OTA callback remains incomplete; **BV11 partial, overall 7/12=58.3%** remain. This is not physical access, new CFW functionality, or external publication.

## Execution scope

Full MRAM restored by the earlier actual ARM writer and SRAM from subsequent natural boot→screen execution were pinned. Main SHA is df8cfddf…. A synthetic SRAM caller invokes original adapter `4f5864` or buffer `488d34` and compares with original `memcmp480dc8`. This isolated function test starts in Thread/MSP/PRIMASK 0, not natural boot, RTOS, or BLE OTA.

Target is 434000..435000, including resident callback region that previously caused boot self-restoration failure. Payload is that page from retained **synthetic virtual pre-modification MRAM**, not a physical backup. Original main alignment check, IRQ entry/restoration, ROM power helper, and nonzero callback execute unchanged. SRAM ROM-auto flag and callback table remain from initial snapshot. Adapter/buffer tests completed under a guard disallowing boot code fetch.

Actual Boot ROM is absent. At `0200ff20`, after validating key 12344321, operation 1, source 20240000, offset d000, 1024 words, and PRIMASK 1, a functional model writes MRAM. Only this 4 KB range is allowed; direct CPU MRAM stores are blocked by existing protected memory. Power ready/stuck uses verified `BlackwallMemoryStartup` contract. Model ROM return settings and PC=LR at ROM boundary are explicit ROM substitution, not forced original-main success branches. Physical MRAM, permissions, electrical interruption, and cache precision are unverified. Observer neutrality is not generalized to all functions.

## Actual results

| Entry/condition | Completion/write | Original API return | Original comparison |
| --- | --- | --- | --- |
| Adapter normal | Normal return, 4096 bytes | 0 | 0, match |
| Adapter ROM status 7 | Normal return, 0 bytes | 08000107 | ffffffff, mismatch |
| Adapter first-bit readback corruption | Normal return, 4096 bytes then one-bit error | 0 | 1, mismatch |
| Adapter destination 434004 | Alignment rejection, 0 bytes/ROM calls 0 | 08000140 | Mismatch |
| Adapter ROM power stuck | Original power helper returns 4, then attempts ROM entry; guard stop/0 bytes | Function did not return | Comparison not run |
| Buffer normal | Normal return, 4096 bytes | 0 | 0, match |
| Buffer ROM status 7 | Normal return, 0 bytes | **0** | ffffffff, mismatch |

Normal/ROM-error/readback-corruption had one original power enable and disable each, two existing nonzero callbacks, and one ROM call. IRQ was masked at ROM entry and restored to PRIMASK 0 after normal return. Full 4 MiB before/after comparison confirmed boot/main/metadata outside allowed page unchanged. Alignment/ROM-error/power-not-ready left full MRAM unchanged.

**Buffer return 0 is not evidence of successful writing.** It swallows the actual ROM error. Original memcmp detected mismatch, but was invoked by the synthetic caller here. Whether the actual OTA verifier is correctly connected and handles failure requires separate verification. API/comparison register values during stuck power are intermediate execution state, not returns.

## Unsupported boundary in upper callback

Original `5c69f8`→device-info getter `5c6994` was also executed, but all three records stopped before writing. They are not added to successful tests.

1. Existing minimal fixture stopped unsupported at JEDEC address e00fefe0 read.
2. Connecting existing board's `BlackwallChipIdentity(23,0,0)` functional profile produced NOCP at VMOV 495e8a. This is missing FPU initialization in isolated caller, not evidence of actual firmware defect.
3. Retrying with FPU/CPACR=f00000 initialized as in existing initialized-main profile stopped without fault on 40021000 MCU clock-mode read. CONTROL became 4 after original float instructions from 0; FPCA was not forced.

Getter cached capacity was not filled and callback not deleted to bypass the boundary. Next first verify existing clock behavior contract and actual asset/hash and call contract of **ITCM delay code copied by original boot**. Do not replace delay at address 40 with NOP/immediate return and count success. Then check actual callback error return and original OTA readback verifier before determining natural ATT/OTA connection. This dependency is a gap in isolated diagnostic environment, not generalized to full original-board boot failure.

## Audit, preservation, and cleanup

Outside Git, `simulator/stock-main-mram-bw569-01` freezes seven adapter/buffer contracts and JEDEC boundary, `-02` missing FPU initialization, and `-03` clock boundary. Each folder retains source, assembly, link script, caller binary, manifest, native log, and raw result. An independent audit not importing current model then compared original inputs, component hashes, raw/report agreement, full MRAM, returns/IRQ/power/callback, and expected unsupported boundaries.

- `stock-main-mram-audit-bw569-01`: 179 conditions before cleanup.
- `-02`: same 179 confirmed, then remaining duplicate dumps/ELFs totaling 8,520,816 bytes cleaned.
- `-03`: saved independent audit-source run outside repo in `/tmp`; 181 conditions passed after cleanup.
- Ten owned native jobs/containers confirmed terminated. Total duplicate/reproducible builds cleaned across the task: 42,604,100 bytes. Each final 4 MiB image and SHA can be reconstructed from initial MRAM and retained 4 KB page.
- Two input-validation units passed. These counts do not increase overall acceptance completion.

**Audit pass also means unsupported records were accurately retained and classified.** It does not mean three callbacks or full-stock restoration succeeded.

## Reproduction

Existing private pinned inputs, pinned Renode image, and LLVM 21 are required. Use new output names. Model/runner changes are recorded as new runs.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/run_stock_main_mram_probe.py "$bw_assets/simulator/main-mram-new-01" --entry adapter --fault success
python3 -B tools/run_stock_main_mram_probe.py "$bw_assets/simulator/main-mram-new-02" --entry buffer --fault rom-error
```

The ten frozen runs can be audited again without current runner. Read only, without `--cleanup`:

```sh
python3 -B "$bw_assets/simulator/stock-main-mram-audit-bw569-03/audit-source.py" "$bw_assets/simulator/main-mram-audit-new-01"
```

Apply existing [boot self-restoration failure](boot-self-restore-results.md), [upstream restoration-gate difference](../research/upstream-independent-restore-review.md), and [all 12 conditions](../data/bootloader-validation-progress.json) together. Pending original ROM, factory INFO1, same-board authentication/recovery, full-stock complete hash/reboot, and version-combination gaps remain.
