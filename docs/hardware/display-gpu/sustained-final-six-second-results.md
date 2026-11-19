# Six-second reverification of final integrated profile

Complete: two cold runs per original, six total. Each original used the same main/model/board/runtime/activation as the 60-second test.

| Original | Actual virtual seconds (two runs) | Post-screen wall seconds (two runs) | Four-run 6/60-second integration |
| --- | --- | --- | --- |
| Stock 2.4 | 6.017903 / 6.011489 | 140.833 / 158.196 | Passed |
| Stock 2.3 | 6.005872 / 6.003891 | 171.241 / 101.486 | Passed |
| Faceclaw 38 | 6.001175 / 6.002039 | 94.130 / 86.317 | Passed |

Each pair independently verified matching configuration/final frame, original UI receive wait/TCB, actual DMA source bytes/FNV, fault/guard 0, and instruction/virtual-time progress. Stock24 had 47 DMA/1232 bytes; stock23/Faceclaw 46 DMA/1203 bytes. The previous stock24 second attempt's host 90-second failure was preserved separately; input/model/runtime/budget were not changed on resumption.

Canonical private: `simulator/sustained-final-audit-01/report.json`; all 12 runs, six pairs, and three-original integration passed. Overall 10/10 covers post-screen six/60-second execution and determination of material gaps, not physical accuracy, ROM boot, or one-hour long-run completion.

[Full costs](sustained-execution-costs.md) · [Final report](sustained-goal-completion.md). No new build/cache after work (`-B`/bytecode disabled); verification inputs and results are preserved.
