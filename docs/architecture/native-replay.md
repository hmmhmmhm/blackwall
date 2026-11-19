# Pinned Native Execution Profile

bw-0126. This is the first follow-up to the Astra review. Without regenerating models, it copies, checks, and sequentially executes the Renode inputs for the three originals frozen in bw122. It does not include the bw124 RTC storage model.

```sh
python3 tools/native_replay.py \
  tests/profiles/bw122-iom-startup-mock0.json \
  "$HOME/Library/Application Support/Blackwall/simulator/iom-startup-main-comparison-01" \
  "$HOME/Library/Application Support/Blackwall/simulator/native-replay-new"
```

The output directory must be a new path. `--check-only` checks hashes, original identity, Python syntax, existing logs/reports, and comparison conditions for every case without running Docker or creating output files. The manifest contains hashes of eight execution inputs and existing reports/logs, original profiles, synthetic assumptions, and endpoint expectations. Do not commit proprietary main.bin or private execution material to Git. This command requires those local assets and is not a distribution tool runnable from a clean checkout alone.

The eight inputs are board.repl, strict.cs, run.py, result.py, probe.resc, main.bin, and ITCM/SRAM fill. Main is checked against existing pinned_main raw hashes/sizes for stock 2.3, Faceclaw 38, and stock 2.4. Stock 2.3 and CFW board/model/result/probe are identical; run.py differs only in main length. After prechecking all cases, they run sequentially on the pinned Linux ARM64 image ID. Input hashes are checked again afterward. Original source, PC, and return values are not modified.

The profile is a reviewed local execution instruction, not a security validator for safely executing arbitrary externally supplied profiles or an OTA package parser. Docker uses network none, restricted memory/CPU, and a read-only execution-directory mount; the existing helper confirms termination of individual containers.

Common checks cover original inputs, no execution-memory/system-control violations, one strict MMIO stop, actual pause before the host timeout, and no unexpected engine errors. Per-profile checks cover PC, active guards, UART/IOM counters, and CQ pair counts. Future profiles allowing different behavior must not force previous UART counts as a shared invariant. Full instruction-trace identity and patch coverage are not checked.

Results separate preparation, per-case copy, native, and audit time. Native time includes C# compilation, pinned host sleep, execution, and container cleanup. This is operational cost for a single run, not guest performance, device latency, or acceleration. A timeout alone does not pass before actual target behavior is observed. This profile ends at an intentional unsupported OCTRL read, not successful boot.

Host checks: `python3 tools/test_native_replay.py`. Integrated verification of the current RTC change, bounded patch/MMIO trace, app loop, and integrated display remain separately incomplete.

## bw126 verification results

Replays of stock 2.3, Faceclaw 38, and stock 2.4 in `private:simulator/native-replay-01/report.json` all passed. PCs were 0x4e8394, 0x4e8394, and 0x506c20 respectively; all stopped strictly on an OCTRL read. Selected UART/IOM counters, CQ pair counts, and input hashes matched the frozen baseline.

Seven host tests include rejection of duplicate/missing reports, memory/system-policy violations, host timeout, incorrect guard count, and unexpected engine errors. They filled a log-assessment test gap identified by Astra; native execution was not repeated because of this change. Separate full-trace, RAM-equivalence, and physical-device verification were not performed.
