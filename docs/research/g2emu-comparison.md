# g2emu and Blackwall Comparison

bw-0551 · 2026-11-17. At the user's request, the full project was cloned and investigated. The comparison considers G2 hardware emulation for CFW testing. **Blackwall has deeper boot, device-path, and regression-validation foundations, while g2emu has a more developed integrated desktop UI and recording/replay tools.** This judgment is based on the pinned sources and retained Blackwall evidence below; it is not an overall performance score or ranking of physical accuracy.

## Investigation basis

- Upstream: https://github.com/ithinkthisiscool/g2emu
- Clone HEAD: `dcbce06c25869dcb3b6a7221609b08e174423bb6`, author date `2026-10-23T11:57:27-04:00`, subject `upload codebase`.
- Clone: private `simulator/g2emu-clone-review-01`, including the MIT LICENSE. Investigation and tests did not modify upstream files.
- For g2emu, source analysis and Python tests were performed. Renode native boot, a live GTK screen, and a speed comparison under identical conditions were not run.
- For Blackwall, retained evidence was reused from the [final original boot audit](../bootloader/original-boot-completion-audit.md), [capability catalog](../architecture/emulator-capability-catalog.md), [CFW comparison acceptance](../firmware/firmware-comparison-acceptance.md), and [sustained execution](../hardware/display-gpu/sustained-screen-dashboard.md). Native execution was not rerun for this comparison.

## Assessment by area

| Area | Pinned g2emu source | Blackwall verified scope | Assessment |
| --- | --- | --- | --- |
| Original ARM execution | Executes an actual main binary on Renode M55 | Actual stock 2.4/2.3 and Faceclaw main; stock 2.4 through its original bootloader | Both execute actual ARM. Blackwall also validated the bootloader connection |
| Default boot path | Starts directly at 2.3.2.14 main reset, with code patches and PC/register intervention | Stock 2.4 boot reset → original handoff → main → UI, with unchanged boot/main bytes and no forced branch | Blackwall has stronger natural-path validation |
| GPU results | Command capture → external Python raster → GUI; completion/IRQ stubbed | Reference raster writes to guest SRAM before completion/IRQ; raw frames compared at the same point | Blackwall has a stronger foundation for CFW tests involving guest readback |
| Input | Original debug-shell commands, with some experimental/pending | Virtual GPIO/IOM/IRQ touch and UART relay → original parser/app/display validation | Blackwall tests the physical device path more deeply |
| Sensors, failures, storage | Permissive functional models including I2C responses, EDMP success, and constant ADC | Pinned contracts and evidence for natural FIFO/IRQ consumption, reset, storage and peer failures, and candidate comparison | Blackwall covers more checks. Sensor fusion accuracy is unverified in both |
| Desktop usability | GTK4/libadwaita, live/console, recording, replay/seek/scrub, settings/shortcuts, screenshots | Primarily CLI, viewer, pinned manifests, and audit/comparison tools | g2emu has the more complete integrated UI |
| Speed | README claims real-time and accelerated operation; provides C# model and pacer | Execution costs recorded for separate existing profiles | No ranking without common measurements |

## Important source differences

### Default boot executes real firmware but intervenes in execution

The default C# recipe [boot-fast.resc](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/boot-fast.resc) includes [boot-stream.resc](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/boot-stream.resc). Lines 40–76 of the latter do the following:

1. Set VTOR/SP/PC to the main reset entry. The recipe does not execute the original bootloader.
2. Replace the delay function at `0x48ac24` in emulator memory with immediate-return code.
3. Force UART2 case-manager startup to return via LR.
4. Skip BLE WSF task startup release by changing PC.
5. Change R0/R1/R2/LR/PC to call the original UI event poster.

The description that the original firmware file is preserved is correct, but execution memory and the execution path are changed. Calling this a mock screen would also be inaccurate: it executes the original UI/renderer while bypassing unimplemented initialization. Blackwall's latest stock 2.4 evidence checks unchanged boot/main memory bytes and the original handoff/input paths, but does not establish that functional sensor, GPU, ADC, or cadence model assumptions match physical hardware.

### Showing a screen differs from reproducing the guest framebuffer

[G2NemaStream.cs](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/cs/G2NemaStream.cs) sets the completion ID and GPU IRQ at kick and captures commands and sources. A separate `Raster` in [engine.py](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/engine.py) creates the screen. This path has no connection to write raster pixels back into the Renode guest framebuffer. It is useful for screen observation, but CFW validation depending on GPU result readback needs additional work.

Blackwall's `tools/renode-nema-ring-device.cs` connects the `NemaRingConsumer` output callback to SystemBus.WriteBytes. For the latest screen, guest SRAM after actual packing was compared against 165,888 bytes of 576×288 A8 raw data. Both use reference/functional rasters; neither guarantees complete Nema GPU shader ISA coverage or physical pixel/timing accuracy.

### Meaning of successful input and peripheral tests

Swipes in [actions.toml](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/actions.toml) use the original debug-shell `sinput` path. Some general event-router inputs are experimental and some content transfer is pending. Keep-awake writes a guest RAM global. UI cross-fade is host interpolation and must be distinguished from the original firmware generating additional animation frames.

The [fast platform](https://github.com/ithinkthisiscool/g2emu/blob/dcbce06c25869dcb3b6a7221609b08e174423bb6/g2emu/apollo510-m1-fast.repl) supplies broad unimplemented MMIO as MappedMemory. G2Iom returns ACK/zero for unregistered I2C addresses and successful completion without computation for EDMP commands. PWRCTRL couples enable/status, and ADC returns a constant board sample. This is a pragmatic functional model for reaching the UI, but does not automatically validate how device failures affect CFW. Blackwall also has explicit functional models, constants, and unsupported boundaries; it has not solved real sensor fusion.

## Tests performed and limitations

The following ran in an isolated Python 3.12 venv with Pillow 13.0.0 without modifying upstream. The private review JSON/install log is authoritative for the actual installed version.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v \
  test_nema_raster g2emu.tests.test_g2emu g2emu.tests.test_gtk_ui
```

Result: **103 = 81 passed + 21 skipped + 1 error**, 7.680 seconds, exit 1. The error was FileNotFoundError on macOS because `tree_rss_mb` requires Linux `/proc`. Skips required display/GTK or undistributed firmware/captures. These were not counted as GTK or actual boot success. Passing tests cover the software raster, configuration, panel model, FakeMonitor, and related components; they do not prove complete hardware reproduction.

The initial Python 3.9 run had two module import failures due to missing tomllib. A subsequent Python 3.12 run with the wrong working directory also failed imports; both are retained in separate diagnostic logs. The 103 tests above are the final result run from the clone root. Upstream code was not patched to make them pass.

## References and next choice

The recommendation is to retain Blackwall's validation core and refer to g2emu's **live screen, recording/replay, seek, and real/experimental/pending input labels**. This comparison does not authorize a UI port or new implementation. Bringing delay removal, startup skips, or immediate completion returns into Blackwall's validation path could weaken the meaning of existing tests.

Neither project has completed full Boot ROM, cycle-accurate Apollo510B, GPU ISA, RF/analog, or precise sensor-fusion reproduction. Blackwall's latest bootloader validation covers one stock 2.4 combination; do not extend earlier stock 2.3/Faceclaw main tests into claims of successful bootloader-mediated execution. Do not convert numbers of completion criteria, code, or tests into a percentage of overall advancement.

## Assets and cleanup

Retain the clone, commit/license/source SHA, and test/install/failure logs. Remove the isolated venv and duplicate partial snapshot from the initial connector after investigation. Final cleanup size and status are recorded in private `simulator/g2emu-tests-bw551-01/review.json`. No physical glasses, Renode native execution, GUI, external publication, or subagent execution occurred.
