# kvTime Corrupt Inputs and Original Reload Policy

Partial bw385, E08 investigation. Overall progress remains **6/16=37.5%**, and the API screen checklist remains 3/6. The full requirements for recovery after storage failure, interruption during writes, and version mismatch are not yet met.

## Three inputs at actual main reset

The existing normally saved stock 2.4 NOR image was replaced with independent copies, while original main, peripheral models, initial SRAM/ITCM, and execution order were retained. Only NOR was loaded at CPU instruction 0; prior guest SRAM was not imported. Results are RAM records at the existing unsupported CPDLPSTATE22 stop after original main reset.

| Synthetic NOR input | Actual original RAM result | Scope verified |
| --- | --- | --- |
| One timestamp bit changed, FlashDB CRC32 mismatch | Existing initial value rewritten as type 3: `030000002b2d376820007ac6` | Corrupt saved value not adopted. Full error handling and subsequent app recovery unconfirmed |
| Same change with only FlashDB CRC32 recomputed, internal CRC16 mismatch | Corrupt `0300000001f153651000fe58` loaded unchanged | With valid outer CRC, internal CRC corruption is not blocked at this checkpoint |
| First byte changed to 4 and both internal and external CRC recomputed | `0400000000f1536510000444` loaded unchanged | Type 4 adoption observed. Meaning of this byte and upper-app compatibility unconfirmed |

All three runs retained the subsequent PC `0x4956e2` and CPDLPSTATE `0x22` strict stop. Probe exit 1, full boot false, and CFSR/HFSR and memory-policy violations 0. The type 4 test is not evidence that actual firmware version mismatch handling is complete. Loading internally corrupt values into RAM is not described as normal app use, display update, or safe recovery.

The changed inputs are host-created static corruption fixtures. They do not reproduce an intermediate NOR program state or physical power loss. Original source NOR and main are unchanged. Differences between normal and corrupt results come from the specified storage inputs, not firmware patches.

## Isolated execution of original policy function

`inspect_kvtime_reload_policy.py` executed actual ARM instructions from stock 2.4 `0x57a270` and stock 2.3/Faceclaw `0x5a32d4`, including the original producer and CRC calculation. This isolated Unicorn M7 test is distinct from natural Renode M55 boot. Read/write APIs and log flags use an explicit synthetic ABI; FlashDB/NOR were not executed in this test.

The following were confirmed in 48 scenarios: three originals, eight inputs each × store return 0/7.

- A negative/0 read return triggers an attempt to resave type 3 using the current global record's values.
- A positive return compares the read CRC field with the current global record's CRC field. This function does not recompute the read payload's CRC.
- Resaving occurs only if CRC fields differ and the first byte is below 3. A mismatch with first byte 3/4 or a positive one-byte return is not rejected at this layer.
- This function does not copy the read stack payload into the global record. Global initialization/restoration belongs to another path.
- Even if the resave API returns 7, this function returns 0. The 7 is a synthetic nonzero ABI status, not identified as an actual NOR error code.

Therefore a return of 0 from this function cannot be used as the storage recovery acceptance criterion. RAM values, actual backing bytes, program/erase state, restart consumption, and original error branches must be judged separately.

## Verification and limitations

Frozen reports for the 48 isolated scenarios and frozen audit reports for the three actual resets are each byte exact. Sixteen checks per saved capture verified original main SHA, model/runner equivalence, corruption range/CRC, neighboring NOR input, initial SRAM, instruction-0 loading, and actual RAM/log/report agreement. The checks also rejected three semantic negatives: additional corruption consistently manipulating JSON/log/hash, reported values differing from RAM, and importing prior SRAM. Fourteen progress-management checks passed.

The first source fixture named equal-crc-current used the actual initial type 1 unchanged; it was corrected to specify type 3 and reverified in policy02/frozen02. Policy01 is preserved as history. The first audit's runner text comparison failed solely because addresses were formatted in hex versus decimal. Only the two record/state address literals were normalized to equivalent decimal values for comparison; the rest of original runtime is exact. The initial symlink negative was rejected earlier at the path boundary and is not counted as a semantic negative. Only reverification reaching all three failure causes in independent COW copies is valid.

Pinned evidence is under the private simulator: `kvtime-reload-policy-02`, `kvtime-reload-policy-frozen-02`, `kvtime-corrupt-native-01/stock24-*`, `kvtime-corrupt-audit-03`, `kvtime-corrupt-audit-frozen-01`, and `kvtime-corruption-research-01/manifest.json`.

```sh
<private-python> tools/inspect_kvtime_reload_policy.py <simulator> <new-output>
<private-python> tools/probe_kvtime_corrupt_restart.py <simulator> <writer-capture> <new-output> --mode bad-container-crc
<private-python> tools/verify_kvtime_corrupt_restart.py <simulator> <new-audit> <damage-capture>...
```

The probe retains exit 1 when the subsequent hold is not reached. The verifier's passed result means the observation/input contract matches, not that recovery succeeded. The dataless `blackwall_package.py` was run using the previously specified local pinned dependency wrapper; its source was not overwritten.

## Work needed for the full requirement

For E08, pin failure/interruption points and completed bytes in actual original program/erase execution, and connect storage operation returns, original error branches, corruption scope, and new reset results. Do not relabel this bit flip as an interrupted write. First investigate the NOR controller's pending program, reset, and commit order and FAL return/timeout contract. Original 2.3/Faceclaw are included in the 48 isolated policy cases, but the three corrupt NOR natural-reset inputs have not yet been run on them. Establish the controller failure/interruption contract before blindly duplicating the experiment.

There was no physical glasses access, flash, OTA, subagent, or external publication.
