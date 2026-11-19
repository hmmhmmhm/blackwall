# Six- and 60-second post-screen execution plan

Status: all 10 conditions verified on 2026-11-16. This is separate from existing v3 16/16 and is not completion of a fully precise emulator.

- [x] Bounded observation, semantic contracts, and rejection tests
- [x] New 100 ms observation pilot to check originals, initial path, actual work/cost
- [x] Two cold reset → six seconds after first screen runs for each of three originals on previously pinned profile
- [x] Two cold reset → six seconds after first screen runs for each of three originals on final integrated profile
- [x] Two cold reset → 60 seconds after first screen runs for each of three originals
- [x] Record actual wall/virtual time, CPU/memory, observation cost, run counts/scope
- [x] Determine required ROM/GPU/GAF assets, missing items, and acquisition paths
- [x] Frozen-material reaudits, intentional-failure rejection, and full completion audit

New condition denominator 10: three per-original six-second conditions, three per-original 60-second conditions, one measurement, and one each for ROM/GPU/GAF gaps. Each time condition requires two actual runs with identical cold inputs and semantic checks. Existing 100 ms material does not complete these. Two six-second and two 60-second runs per original on the final integrated profile and full audit were completed. Progress is 10/10; scope and evidence are managed in dashboard/machine record. Follow machine record/dashboard for latest status.

Implementation is divided among frozen first-screen derivation/additional observation/audit/measurement in `tools/run_sustained_screen.py`, bounded signal accumulation and sampling in `tools/renode-sustained-observer.cs`, and time/resource/error rejection in `tests/test_sustained_screen.py`. Existing device/ARM/boot prefix is unchanged. New schema2 profile separates execution and semantics. Only first/periodic/final actual frame samples are preserved; full frame capture is not claimed. Distinguish task/IRQ/clock progress, original faults, GPU rejection, normal idle, and stuck state. Observation changes are not assumed noninterfering.

After virtual 100 ms pilot, six seconds then 60 seconds sequentially. Host guard is not a performance result and timeout is failure. For a live process verify the same handle and do not restart solely due to observation timeout. ROM/GPU/GAF work establishes possession or absence of exact required material; it does not implement full precision in this Goal. No physical device, Astra, or external publication.

## Initial measurements and failure

New-observation 100 ms pilot: virtual 100.702 ms / actual 3.807 seconds / 6,463,355 instructions, frame +4, fault 0. Total Docker 98.36 seconds includes compile and cold boot. One ballpark run does not establish 60-second cost. Initial audit's missing `selected_observation` was corrected and saved data alone reaudited.

First six-second run stopped strictly 1.558034 seconds after screen at MSPI0 0x40060000/PC4e8a46. Broad guard name `guard_iom7_tail` was not interpreted as device name. Frozen first-screen's old MSPI model lacked JBD status read. The functional profile was extended by reusing the same source/module already verified in bw366 and explicit virtual 5a01 only. Existing strict failure was preserved and is not claimed to represent physical normal status.

Existing startup PC trace is a bounded sample and can be truncated over long runs. This is disclosed in all reports and not claimed as full execution history. Long-run judgment uses separate accumulated signal counters, bounded samples, checkpoints, original faults/guards, and progress. No claim of exhaustive IRQ/all-frame capture or observer noninterference.

Follow-up stock24 explicit JBD 5a01 profile verified virtual 6.000787 seconds, wall 98.538 seconds/total Docker 194.115 seconds, instructions +130,395,983, screen 3→13, fault/guard/GPU error 0, and cumulative accounting of 31,338 signals. One run did not yet meet stock24's two-run six-second requirement. Final guest frame was preserved as raw/gain16 and clock/text/icons visually confirmed to remain.
