# Original erase errors, alignment, length, and FAL returns

bw390. The existing ARM inspector was extended to erase and ran 11 scenarios each for original stock 2.4, stock 2.3, and Faceclaw, 33 in total. **Erase also loses errors through nonzero NOR error → adapter 0 → partition 0 → FlashDB success 0.** Actual erase, interruption, and restart of physical or virtual backing remain unverified. E08 remains incomplete; overall progress is 6/16 = 37.5%.

## Function connections

The program callback and addresses were not reused. The connection followed the DB, partition, and device descriptors in successful native SRAM and the actual erase callback at +0x30. The FlashDB erase wrapper's unique signature, NOR sector command, and original ready/poll relationship were also checked.

| Layer | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| FlashDB erase wrapper | 0x5b4286 | 0x5a3bbe |
| FAL partition erase | 0x5bedec | 0x5b4c28 |
| device erase adapter | 0x5776ee | 0x55dfc6 |
| NOR sector erase | 0x47bca0 | 0x476f88 |
| ready helper | 0x47b832 | 0x476b1a |
| bounded poll | 0x47b7e0 | 0x476ac8 |

Actual ARM instructions ran continuously from the FlashDB wrapper through partition lookup, device callback, NOR function, and ready/poll. These are isolated Unicorn M7 calls, not an M55 main reset or a test in the original RTOS context. ABI leaves for peripheral transfer, WEL, controller lifecycle, logging, error notification, and status/delay/context are synthetic. The original poll and loop branches execute directly, but neither time nor NOR bytes change. Stub addresses, transfer arguments, returns, and trace SHA are recorded in the report.

## Actual returns and command counts

| Input | NOR return | adapter/partition | FlashDB | sector commands |
| --- | --- | --- | --- | --- |
| Normal 4096 bytes | 0 | 4096 | 0 | 1 |
| Length 1 byte | 0 | 4096 | 0 | 1 |
| Normal 8192 bytes | 0,0 | 4096 | 0 | 2 |
| Busy timeout after command | 4 | 0 | 0 | 1 |
| Busy timeout before command | 3 | 0 | 0 | 0 |
| Second-sector timeout | 0,4 | 0 | 0 | 2 |
| Transfer ABI error 7 | 7 | 0 | 0 | 1 |
| Unaligned start address | Not called | 0 | 0 | 0 |
| Length 0 | Not called | 0 | 0 | 0 |
| Partition out of range | Not called | -1 | 1 | 0 |
| Read-only DB | Not called | Not called | 1 | 0 |

All three images showed the same return policy. The erase adapter checks 4 KB address alignment and rounds length up to 4 KB. The return value 4096 for a successful 8192-byte request is the actual original remaining-sector length value. It is not evidence that all 8192 bytes were erased on actual storage.

A timeout after the command made 1201 status calls: one preliminary ready read plus 1200 original timeout polls. A timeout before the command made 1200, and a second-sector timeout made 1203. These are counts of executed commands and branches, not physical delay durations. Actual error notification arguments (operation 3, error 3/4/7) were recorded. Success inside the notification API and handling by the higher-level application were not verified.

An unaligned start address and length 0 also remain success 0 at FlashDB. Out-of-range and read-only controls return error 1, confirming that the inspector does not fix every result at 0. The program FlashDB error 3 and erase error 1 were not forced to the same number. The normal two-sector command addresses were also checked to increase from 0x1fc0000 to 0x1fc1000.

## Verification scope

Seven conditions for each of the 33 cases checked layer returns, all NOR calls, original poll counts, exact commands and addresses, error notifications, stack return, and SRAM invariance. The new erase report is byte-exact against the frozen source. The inspector's existing 21 program cases were rerun and confirmed byte-exact against the old report. No erase-only copy of the inspector was added. There were no new Renode runs this time.

```sh
<private-python> tools/inspect_nor_error_propagation.py <simulator> <new-output> --operation erase
```

Results and original/source hashes are preserved in private `nor-erase-propagation-01/report.json`, `nor-erase-propagation-frozen-01/report.json`, `nor-program-propagation-regression-01/report.json`, and `nor-erase-propagation-research-01/manifest.json`. The dataless package reused the existing pinned local dependency wrapper.

## Next integrated test boundary

Existing erase-stuck main evidence stopped strictly on the next sector read from busy NOR after three poll failures, but did not connect the erase callback, FAL and FlashDB returns, backing before and after, and a new reset in the same capture. It is not counted as new full-recovery evidence, and the same input will not simply be rerun.

Next, hold the original initial formatter's first sector erase using the existing `completeSectorErase:false` model and observe the original return PCs above. A declared nonzero initial virtual NOR pattern is needed to judge data preservation, unlike a test in which a sector already at FF stays FF. Pin a normal control and failure capture with the same initial pattern, then pass only completed backing to a new process to inspect the original firmware's actual response with faults off. Do not force original branches or stub the erase callback to success.

This model assumes the entire sector changes to FF at completion and therefore does not guarantee physical power-loss or partial-erase behavior. In the isolated second-sector failure test, the first NOR function returning 0 alone does not establish physical commit of the first sector. E08 erase interruption, actual recovery, stored-version mismatch, and integrated verification per original image, as well as E05/E06 natural application/reset tests, remain outstanding. The 16 criteria and API 3/6 were unchanged. No physical device, flash/OTA, Astra/subagent, or external publication was involved.
