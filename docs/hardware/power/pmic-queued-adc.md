# PMIC Measurement Queue and Original Result Handling

bw-0148. Six single-measurement channels and result transfer were extended without changing actual original main bytes.

## Source contract and selected policy

The [official System Monitor](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html?contentId=tITzAAb8obCIYU3HrAc0SQ) specifies priority VBAT → NTC → IBAT → die → VSYS → VBUS and non-preemption of an ongoing conversion. One pending request per channel and duplicate drop are finite policies of this selected model, not proof of physical queue depth. Manual tasks 500/501/502/503/507 and automatic IBAT after VBAT are supported. Burst, automatic periodic operation, delay 508, and direct 506 are unsupported. Nominal 250 µs per conversion is an existing declaration, not measured G2 time.

The explicit profile is queued-six-channel-fixture with raw array `[778,512,5,466,611,0]`, ordered VBAT/NTC/IBAT/die/VSYS/VBUS. These are not physical sensor readings. Without resultResetProfile, results are unknown. Explicit source-reset supplies ADK-defined 0510..051a reset 00 as known register contents while leaving Completed at 0. Known reset values are distinct from actual completed measurements; this does not verify identical values in actual warm state or physical reset. Existing source-reset ADC configuration, scratch0 mock 0, and INFO1/revision/power/cache assumptions remain.

## Result transfer and trace

The root typed backend checks supported task addresses and rejects configuration changes during an active conversion before writing. On the first result-read chunk it snapshots the known range and handles subsequent 4+4+2. Unknown ranges and overruns are rejected; after STOP the internal pointer advances by the consumed length. Transaction snapshot and pointer policies are contracts of the selected model, not verification of atomic result reads on physical PMIC.

Only the queue profile uses trace ring 64. Normal communication is not blocked when the trace fills, and aggregate counters and a separate ADC result-payload trace are preserved. The existing bounded probe profile is unchanged. Original execution still stops at actual unsupported registers/behavior.

## Unit tests

The 401 checks in private pmic-queued-unit-03 include existing 369 plus 32 new. They check VBAT → NTC → automatic IBAT → die → VBUS after an ongoing VSYS completes. Completion order `[4,0,1,2,3,5]`, one completion each, and event cf were confirmed. This is a synthetic unit scenario. It also checks active non-preemption, duplicate drop, atomic configuration changes, unknown state, 4+4+2, overrun, pointer, continued ring operation, and Reset cancellation. Even if a conversion completes after the first chunk, the rest of the transaction uses the old snapshot and the next transaction sees the new result. unit01 had 395 checks for five channels; 02 had 396 including VBUS; 03 had 401 adding snapshot/counters.

## Original ARM results

Private pmic-queued-main-01 contains three originals and two controls, five cases total. Stock 2.4, 2.3, and Faceclaw all showed completions `[1,1,1,0,0,0]`, order `[0,2,1]`, from two guest requests and one automatic IBAT. Actual original code has not yet requested die/VSYS/VBUS tasks.

Returned payload is `C2-80-00-00 / 02-00-00-01 / 00-10 / 04`. The first 4+4+2 are ten result bytes; final 04 is one IBAT status byte. Die/VSYS/VBUS zeros here are explicit reset-register contents, not completed measurements. Execution then stopped at the next unsupported request, 0334 (BCHGCHARGESTATUS) pointer read, width 2. Original watchdog remains Start 0.

The previous two-channel model control retained the existing 501 boundary. With queue enabled but result reset omitted, the control rejected the first four-byte read at 511 due to unmeasured die/VSYS and returned zero result bytes. This preserves the fact that removing the assumption changes the path.

## Input sensitivity of RAM results

At `2007fa84` in existing read-only snapshots, all three originals showed float32 `[3.798,0.004,25.009]`. Exact structure and units were not named. In a single stock 2.4 sensitivity run, changing only VBAT/IBAT raw to 819/10 produced `[3.999,0.008,25.009]`. Seven execution inputs including firmware, runtime, model, and fill are byte-identical; only two board raw fields differ. This shows input changes reflected in original RAM results. Since two inputs changed together, it does not independently establish correspondence or units for each sensor and field. Nor is it evidence of physical measurement or accuracy. The report states that no stock/CFW comparison was performed for the single sensitivity run.

## Tools and final verification

The replay builder was corrected where VBAT/IBAT depended on previous board values so all six raw arguments are reflected. The current helper byte-reproduces four existing queued boards and reflects six changed fields. Raw 778/5 in these original runs matched inherited values, so prior inputs/results were not changed. After correction, sensitivity 819/10 was actually run to confirm application of different raw arguments.

Scalar conversion unit06 408, watchdog unit11 240, and recovery-pmic-feed-12 five ARM cases were also reverified. The latter retains explicit power/pins/frozenDWT/status-hole mocks. The 129 checks in pmic-queued-verification-01 compared source/unit/main 5/sensitivity 1 raw results, exact counters/payload, known-versus-measured distinction, next guard, default boundary, input byte invariance, source pins, builder reproduction, raw variation, RAM response, and single-case comparison scope. Independent GPT-6-family review's interpretation of snapshots, unmeasured values, and grouped input changes was incorporated. No transcript archive comparison occurred.

Next is 0334 status meaning and source/reset conditions. Full ADC modes, full main loop, display, and physical installation/recovery remain unverified; product completion remains 13/29.
