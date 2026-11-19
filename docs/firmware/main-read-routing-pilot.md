# Preliminary comparison of main read routing optimization

bw-0421. **The candidate was not adopted.** A candidate to reduce I/O routing for normal main data reads was compared in one pair against fixed stock 2.4 in a 500 ms busy scenario, but the result did not support an improvement. No general performance conclusion that it is faster or slower is drawn.

The candidate enables I/O routing only from the 4 KiB page containing the first address where a read of up to 8 bytes can extend past the end of the file (end−7) through the end of the main mapping. MMU write protection, block execution protection, ITCM write tracking, and restoration after reset use the same source. The actual range/alignment and cross-boundary protection matrix was not run, so candidate safety is not approved either. Production policy SHA `29daafce…` and full-page routing were retained. Candidate SHA `312cdbff…` is retained privately for diagnosis only.

Both sides used the same fixed Renode image, CPU 10 MIPS, 512 MiB/CPU 1, original, input, 500 ms, and selected stop at three observations. The profiler was off. Initial load averages were 2.00/2.55/2.97 with 8 logical CPUs. Before comparison, `benchmark-checklist` and `principle-explain-the-number` were read and adoption criteria recorded in the private plan.

| Measurement | Existing policy | Candidate |
| --- | ---: | ---: |
| Host seconds for fixed 500 ms resumed interval | 1.646 | 1.897 |
| Total host seconds including initialization, execution, and result collection | 45.778 | 47.381 |
| Total ARM instructions | 85,808,849 | 85,808,849 |
| Busy polls after that interval | 362 | 362 |

These are preliminary results from one run each. They cannot support a speed comparison because neither a repeated distribution nor a new bottleneck profile was collected. With no indication of improvement, the five adoption pairs and protection matrix were not started. The existing bw399 distribution is not substituted for repeated results of this candidate.

Four actual complete SRAM snapshots (initial, ATT, and final), R0–R15, instruction count, virtual boundary, and two runtime JSON files were exact matches on both sides. Main, board, execution script, observation class, and initial memory inputs were also exact. Guard/fault/memory violations were 0, as was calculation count; this short run did not reach the original timeout.

Material is retained privately in `main-read-routing-research-01/{plan.json,pilot-audit.json}` and `main-read-routing-pilot-01`. `probe_main_read_routing.py` is a reproducibility tool using those fixed inputs and does not change production defaults. Runs are not repeated to select a desired number. Next, execute the original timeout path within a finite budget using the verified existing observation stops and protection policy. There was no physical device, subagent, or external posting. Overall progress remains 8/16=50.0%.
