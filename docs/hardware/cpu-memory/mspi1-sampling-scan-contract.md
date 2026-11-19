# Original MSPI sampling scan contract and observations

Task bw-0173 did not change the production peripheral model or the original firmware's execution endpoint. It produced a development diagnostic tool that confirms the tuning procedure, actual RAM input and ID classification, and resolves missing events at selected observation points. Overall product completion remains 13/29 (44.8%).

## Execution observed

`probe_mspi1_sampling_context.py` reused the fixed model, board, main, fill, and execution policy from `mspi1-rdid-main-01`. It added only read-only runtime observation points and increased the existing observer capacity from 128 to 4096. The observation points are checked against actual instruction boundaries decoded from function entries.

Each of the three original images in `mspi1-sampling-context-01` produced 1,165 selected events with no omissions. These are records at registered observation points, not a complete trace of every ARM instruction or bus transfer. Execution stopped at the same strict boundary as before: a request to start RX3 after changing RXCAP bit 22.

The following sequence was confirmed 288 times in each of the three originals:

1. The original FIFO helper returns.
2. Input R0 to the original ID classifier is C22539.
3. The same classifier returns with R0=0.

The initial RAM copy snapshot remains 403925C2. Thus, within this observation, the 288 repetitions do not establish that the ID was rejected or that the same value should be changed arbitrarily. They correspond to the first 9 settings × 32 fine steps of the original scan loop.

## RAM table and code boundaries

An initial static search assumed the table literal was a flash address and returned an empty slice. The actual pointer is in RAM. The empty result was not used as a table; instead, 216 bytes of RAM initialized by the original firmware were read in four bounded snapshots.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| Scan function entry | 47AB18 | 475E00 |
| Actual RAM address of table | 200025D0 | 2000092C |
| ID classifier | 47A846 | 475B2E |

The table has 36 rows × 6 bytes, and its content SHA256 is `a26d40aacdbb0889ec7da60e94af64373ba35610ca63a92b0555b718cdeae182` in all three images. Each row follows `[1, a, b, c, 1, 32]`, where a/b are 0 or 1 and c is 1..9. These are values from the original RAM, not evidence that the entire HAL ABI matches.

Static analysis also exposed a case where decoding from the second halfword of a 32-bit Thumb instruction made the stride appear to be 33. Re-decoding from the function entry showed the actual stride is 6; the erroneous interpretation was discarded. The tool checks the entry and hook address boundaries and the stride-6 instruction to prevent recurrence. Actual RXCAP source byte observations also matched the table prefix: nine 0s followed by 1.

## Source evidence for classification and selection

The public SVD/header defines DEV0CFG RXCAP=bit 22, RXNEG=bit 23, and TXNEG=bit 24. TIMING_SCAN_SET in the fixed HAL sets these three fields and TX/RX DQS delay and turnaround. This supports the functional names and storage contract; it is not a measurement of actual edges or setup/hold times.

The original scan function iterates through 36 coarse settings and 32 fine steps. It marks a fine bit when the read function returns 0 and the ID classifier result is not 2. It then calls the longest-run helper and a subsequent selection helper. The relevant code, branches, and function returns were checked from function entries. Completion of the full scan and its selection result have not yet been confirmed by execution.

Twelve separate isolated Thumb/M-class function tests (4 inputs × 3 images) executed the actual original classifier code: C22539→0, 123456→2, 3925C2→2, and 253900→0. The little-endian RAM word is distinct from the aligned ID received by the classifier. In particular, because 253900 is also accepted, this classifier cannot be treated as strict JEDEC authentication or confirmation of the installed chip. This isolated harness did not change the PC, input, or return value of the main execution.

The final 71 checks in `verify_mspi1_sampling_context.py` verified fixed source, original bytes, the same strict boundary before and after observation, the RAM table, actual classifier sequence, zero missing selected events, observation-only runtime, and comparison of the three images. Version 02, which strengthened function boundary/stride and classification/selection call checks after audit 01, also passed 68 checks. In response to review, version 03 added an entry-based check that the classifier result hook is an actual BX LR, and checked all 20 instruction bytes of the longest-run helper and nine synthetic mask runs (0→0, FFFFFFFF→32, 00FF0000→8 across 3 images); all 71 checks passed. These mask tests are not physical signal measurements either. The original reports were retained.

## Boundaries for the next implementation

A functional ideal SDR sampling profile must state its assumption of error-free digital byte delivery and must not suggest that a physical timing window was created or measured. Retain the comparison between the default fixed configuration and the selected profile. Do not infer signal margins to make only particular settings succeed, or alter the ID, original branch, or scan return value to force success.

The next step is to observe the full scan and selection result using a profile that states this assumption and leaves those decisions to the original code. Actual signal quality, installed chip, complete boot, NOR contents, integrated display, and physical device recovery remain incomplete. No glasses connection, flashing, or persistent write was performed in this task.

The checks and wording above incorporate the inherited parent-model review's request for stronger evidence of the return hook and helper meaning. Astra, another model family, and a full transcript audit were not used.
