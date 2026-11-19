# Boot self-restoration and resident recovery-code lifetime

2026-11-17 · bw-0567. Existing ARM RAM writer completed stock boot-body restoration, and a new reset→stock main→screen was confirmed. However, while clearing the patch extension, it overwrote receive code it uses and full-stock restoration failed. **BV11 remains partial, overall 7/12=58.3%.** No physical access, firmware installation, or external posting occurred.

## Execution-code cache defect fixed first

Existing protected MRAM is executable `ArrayMemory` that blocks direct CPU stores before changes. A control used a synthetic M55 caller in RAM invoking an MRAM callee twice. The first call executed `movs r0,#0x12`; a host write like the ROM model changed it to `#0x34` between calls. Actual MRAM bytes changed, but both default execution and a control calling only `InvalidateTranslationBlocks()` returned 12 on the second call: previously translated code executed.

Infrastructure corresponding to pinned Renode 1.17.0 build f1dd1b4af was fully cloned/checked out at commit cd4b002aac2398994c4a61a34a8b31b5700facf2, license licenses/MIT.txt. [TranslationCPU](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Peripherals/Peripherals/CPU/TranslationCPU.cs) processes only already queued ranges in `InvalidateTranslationBlocks`; calling it without first registering an address had no effect in this test. A control applying the `OrderTranslationBlocksInvalidation(start,end)` path used by [MappedMemory](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Peripherals/Memory/MappedMemory.cs) to the same range produced actual second ARM result 34.

Virtual ROM program was changed to register the actual destination range after completing a write block. This is a coherent emulator execution-code model, **not reproduction of physical M55 I-cache**. PC, branches, and security conditions were not fixed, and original ROM was not represented as executed. Four existing M55 regressions—normal, ROM failure, readback mismatch, and 68-word interruption—also passed.

This defect matters when overwriting boot code the same CPU executed. Prior full-main restoration did not execute main from the RAM writer and verified actual final MRAM by booting a new machine, so that evidence is not withdrawn. Initial IronPython register-binding failure and incorrectly selected invalidation-call control remain in logs/source.

## Virtual original and permission scope

Initial input is `full-main-restore-bw564-02/vector/exports/final-mram.bin`, whose main was restored by actual ARM writer. Main SHA is stock 2.4 df8cfddf… and marker FFFFFFFF. Based on that full MRAM, a **synthetic virtual pre-modification snapshot** was first retained with boot changed to stock 149773 bytes and subsequent 9971 bytes defined as 0. This tail 0 is not inferred as a physical device's original or official-bundle bytes.

Virtual backup and experimental initial input are exact outside boot footprint 410000..437000. Original 16 instruction bytes at seven stock helper stubs also match the target, preventing host stubs from continuing to execute overwritten code.

Existing main/default permissions remain. Only explicit boot experiment options allow these fixed ranges, which cannot be mixed with main/full options:

- Prefix: 410000 / 149776 bytes (stock 149773 + three virtual-backup padding bytes).
- Whole: 410000 / 159744 bytes.
- Tail: 434910 / 9968 bytes.

These are virtual fixture permissions, not silicon ROM ranges or authorization for device writes. Direct CPU MRAM stores remain blocked. An option to collect incomplete-run results is also limited to boot experiments and does not relax normal writer completion checks.

## Actual ARM writer results

| Test | Actual program / request | Result | Remaining actual mismatched bytes |
| --- | ---: | --- | ---: |
| Boot prefix | 149776 / 149776 | UART RESULT and context return completed; boot raw has stock SHA ecb91896… | 9488 |
| Complete boot footprint | 150528 / 159744 | Receive function overwritten, then guest fault; no response/return. Stopped at 120-second observation limit | 8790 |
| Tail after completed prefix | 768 / 9968 | Receive function overwritten, then guest fault and unsupported read 3e; no response/return | 8775 |

Each final 4 MiB MRAM was independently reconstructed from original input and actual programmed-byte prefix and matched. Main/metadata/neighbors were unchanged. Last column is actual byte comparison against the complete synthetic original, distinct from restore checker leaving the entire mismatching 9971-byte tail component unverified.

In both failures first changed-code entry was `block_receive` 434be4. Its original first halfword e92d had actually changed to 0000 in MRAM. Observation recorded this and continued; the original ARM path executed overwritten code and left CFSR 20000/HFSR 40000000. The whole-footprint test stayed at 434c06 with fault recorded until observation limit. This isolated RAM-call fixture did not verify full actual boot/RTOS fault-handler/watchdog lifetime. It does not verify physical watchdog/power-loss time or permanent bricking. Old code cache was not retained to manufacture success.

## Booting the same MRAM from a new reset

Each MRAM hash actually output by writer was verified; a new machine loaded its boot/main windows and actual marker. Only stock boot-body bytes were allowed as executable code; tail was classified as separate persistent area. Writer failures remained recorded and were not changed to success by new reset.

- Completed prefix: stock boot reset→stock handoff→main/UI→actual 576×288 guest framebuffer, fault/guard 0.
- Failed full-footprint write: likewise succeeded through main/UI and screen, fault/guard 0. Writer completion remains false.
- Failed tail write: new boot reset→stock handoff→main reset entry, fault/guard 0. This third control was checked only through main entry, not UI/screen completion.

The first two screen raw 165888-byte SHAs are `81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2`, matching previous stock result and each actual guest SRAM source. New reset is cold reset of a separate virtual machine, not certification of automatic rollback, same-board UART2 authentication/recovery integration, or physical power-cycle recovery.

**Rebooting with stock main and boot body differs from full stock.** All three final states differ from original virtual bytes in the extension region, so full-stock=false. A physical device still needs an original backup of that region. A recovery tool independent of main is not necessarily independent of callback/return paths in boot.

## Verification and preservation

- 30 host tests: capture/options 8, existing full-main scope 3, boot scope 2, reboot input/branch 7, restore checker 10.
- 60 C# component conditions: existing policy 23, full-main 11, boot 18, actual Program rejection 8. These are not added to original ARM execution counts.
- Three synthetic M55 cache controls, four existing actual compiled-writer regressions, three new boot writers, and three new boot resets are distinguished. Initial failures/configuration errors remain separately.
- Independent 80-condition audit recalculated actual MRAM, original logs/faults/overwritten instructions, pinned payload/model, cold boot/frame, and range decisions. Source and three support modules were frozen. Saved audit reran outside repo in /tmp after cleanup and all passed.

Private simulator evidence:

- `mram-code-cache-inventory-bw567-01/source-review.json`: build→exact submodule commit, MIT/source SHA, API inventory.
- `mram-code-coherency-bw567-03`: same-model default/drain-only/ordered-range controls. 01/02 are configuration failures and initial-control history.
- `coherent-mram-regression-bw567-01/audit-and-cleanup.json`, `boot-restore-policy-bw567-02`.
- `boot-self-restore-bw567-01`: virtual-original snapshot, three writer sources/logs/states, each actual final MRAM and cold-boot evidence.
- `boot-self-restore-audit-bw567-02`: saved post-cleanup independent 80-condition audit, audit-source.py, and frozen support modules.

Duplicate inputs and temporary dumps were removed after execution. Originals/final MRAM, SRAM context, original code/hashes, and key source/logs needed for independent audit remain. Cleanup totals and owned-job termination are in cleanup-summary.json in the same audit folder. Public upstream checkout is retained as pinned source directly used in analysis.

## Reproduction

Repository root, existing private inputs, and pinned Renode image are required. Use new output names. There is no serial/BLE/physical installation.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
"$bw_assets/simulator/venv-02/bin/python" -B tools/run_boot_self_restore.py "$bw_assets/simulator/boot-self-new-01"
python3 -B tools/run_restored_boot.py "$bw_assets/simulator/boot-self-new-01/prefix/native" "$bw_assets/simulator/boot-self-new-01/prefix/cold-boot" --mode restored --boot-state stock-prefix --screen
python3 -B tools/run_restored_boot.py "$bw_assets/simulator/boot-self-new-01/whole/native" "$bw_assets/simulator/boot-self-new-01/whole/cold-boot" --mode restored --boot-state stock-prefix --screen
python3 -B tools/run_restored_boot.py "$bw_assets/simulator/boot-self-new-01/tail-after-prefix/native" "$bw_assets/simulator/boot-self-new-01/tail-after-prefix/cold-boot" --mode restored --boot-state stock-prefix
```

Run repo-independent audit of existing evidence to a new output using saved audit-source.py and frozen modules. Do not make it retroactively depend on current candidate builder or later repo source.

```sh
python3 -B "$bw_assets/simulator/boot-self-restore-audit-bw567-02/audit-source.py" "$bw_assets/simulator/boot-self-restore-bw567-01" "$bw_assets/simulator/boot-self-audit-new-01"
```

Next investigate whether an existing upstream restoration path independent of boot resident code exists, while retaining gaps in original ROM/factory INFO1, same-board authentication integration, and version combinations. Do not arbitrarily develop a new recovery firmware payload as a substitute for full-stock success.
