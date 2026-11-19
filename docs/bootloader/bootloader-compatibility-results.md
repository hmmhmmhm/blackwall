# Boot/main/recovery combinations and repeat verification

2026-11-17 · bw-0574. Ten pinned assets and nine explicit combinations were mapped to operation-specific evidence. Across 24 boot/main pairs × seven operations, 168 decisions confirmed **only eight evidence-backed operations allowed and 160 rejected**. Supported virtual 2.4 full-stock restoration was also repeated with a new writer and fresh boot/frame. BV12's current pinned-asset matrix, repeat, and unsupported-rejection conditions were completed, reaching 10/12=83.3%. This is not recovery compatibility for all versions or physical installability.

## Decisions differ by operation

`bootloader-validation-matrix.json` is queried by exact boot/main SHA and synthetic-chip23-trim0 profile. Status is verified-compatible / source-supported-untested / unknown / incompatible. Verified applies only to recorded virtual operations. Original manager fallback to main is not treated as UART2 authentication success.

| Boot / main | Scope confirmed | Restoration/authentication decision |
| --- | --- | --- |
| Stock 2.4 / stock 2.4 | Original boot→main/frame, virtual pending-metadata lifetime | Final stock boot verified; arbitrary recovery operations not automatically allowed |
| Research patch 2.4 / stock 2.4 | Guarded fallback, post-restoration main/frame | Virtual main/full-stock restoration verified; same-board authentication/recovery unverified |
| Upstream 42e27e9 current 2.3.2.14 / same-bundle main 2.3.2.14 | Original reset→guarded fallback→main reset | Worker 0, UART2 TX 0. Full main/frame/restoration unverified |
| Upstream previous 2.3.2.14 / same-bundle main 2.3.2.14 | Same fallback | Not promoted to authentication/restoration support |
| Custom-key research patch 2.3 / same-bundle main 2.3 | Local artifact pairing confirmed | Natural execution/restoration of this boot/main unconfirmed |
| Stock boot 2.3.2.14 / same-bundle main 2.3 | Limited analysis including original adapter comparison | Natural full boot/frame/restoration unconfirmed |
| Upstream current 2.3 boot / stock main 2.4 | Upstream documentation claim; source-supported-untested | This virtual combination not executed; request rejected |
| Research patch 2.4 / Faceclaw38 | Only isolated specified-handoff entry confirmed | Natural boot/frame/restoration unconfirmed; rejected |
| Research patch 2.4 / legacy main 2.3.0.24 | Combination not executed | Unknown; rejected |

Distinguish main 2.3.2.14 SHA 69f9ef63… from legacy main 2.3.0.24 SHA fffbf74b…. Faceclaw38 is fixed research-bundle SHA 4118af85…, not presented as upstream's latest product state. Public current/previous boot SHAs are also distinguished as 7010d103…/06f8a8d5…. Previous reused existing upstream test_storage_deferral.py reconstruction procedure in memory and verified exact SHA. No new firmware file or installation artifact was made.

Physical hardware revision, each side's boot, and actual case version are unknown. User main 2.4.0.24 is the official app's combined display, not independent verification of both temples. Case 1.2.57 is only a source fixture. Synthetic MCU revision 23 is not equated with actual hardware revision 5.

## Read-only decision tool

`check_bootloader_compatibility.py` hashes actual boot/main bytes and returns virtual_planning_match only when the requested operation was verified for that combination. Unknown, source-only, incompatible, truncated/unknown images, physical context, and arbitrary operations such as flash/install are rejected. Results always retain installable=false / hardware_validated=false / execution_performed=false.

**It is neither a security boundary automatically approving runners nor a flasher.** Actual runners still must check their frozen model, initial state, and component SHAs. Version strings or local artifact pairing alone do not authorize execution/installation.

Existing `check_recovery_set.py` was reused unchanged. Two correct 2.3/2.4 file/key combinations were checked, and cross-mixing 264-byte recover.bin of equal length and mixing keys were rejected in both directions. This static pairing result differs from operation-specific virtual verification. The 2.3 writer MRAM entry 42e83d cannot be mixed with 2.4's 42e84d. Proprietary images/keys remain outside Git.

## Full-stock repeat result

`full-stock-repeat-bw574-01` confirmed a new original-main writer processing 39 pages/159744 bytes, 39 original verifier calls, and full MRAM. Model/caller/board/runtime/input bytes matched previous bw571; final 4 MiB SHA 8e0e4761… and new stock boot→main→576×288 frame SHA 81200ab1… matched. Original images, neighboring regions, IRQ/original callback/readback were independently audited.

Bitwise exactness of full execution SRAM is not claimed. Cadence SRAM hashes differ, previous 871f3029…/new c6d0fa39…, but each run passed pre/post-pause identity and correlation with actual guest frame. This repeat reproduces restored bytes, original path, and completed frame, not physical timing or complete runtime determinism.

## Audit and cleanup

Outside Git, `bootloader-matrix-audit-bw574-01..05` retains 168 decisions, actual ten-artifact hashes, normal/error pairing, actual upstream current/previous fallback evidence, and repeat audit. After cleanup, rerunning from saved source/registry/nine support modules only in `/tmp` passed matrix 11 and restoration 41+regression 49 conditions. Five unknown/truncated/physical negatives and three checker units also passed. Remaining unregistered combinations are rejected as unknown; not all version combinations are claimed restoration-verified.

A path error occurred when follow-up cleanup recording/rerun was attempted before audit 02 completed. The audit process was not restarted; normal termination of the same handle was confirmed. First audit and actual deletion-hash receipt remained, and post-completion cleanup record/independent re-audit 03 was performed. Two natives terminated with container absence and duplicate dumps/ELFs totaling 19,546,373 bytes cleaned. Canonical inputs, frozen source/hash/logs, actual 39-page readback, unique frame/SRAM, and analysis remain.

## Reproduction

Existing pinned private inputs and Renode image/LLVM 21 are required. Use new output names.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/check_bootloader_compatibility.py --boot "$bw_assets/recovery/private-boot-24-candidate-01/source/build/bootloader.bin" --main "$bw_assets/simulator/sustained-render-guard-native-01/stock24/main.bin" --operation virtual-full-stock-restore
python3 -B "$bw_assets/simulator/bootloader-matrix-audit-bw574-05/audit-source.py" "$bw_assets/simulator/full-stock-repeat-bw574-01" "$bw_assets/simulator/version-matrix-audit-new-01"
```

Remaining overall conditions were BV05/06 same-board UART2 authentication/recovery. Current trim 0 takes guarded fallback through original power callbacks, while trim 1/2 factory INFO1 gaps remained unresolved. They are not deleted or filled with arbitrary values to manufacture recovery success.

The procedure was strengthened to check seven current-source SHAs before manipulating reconstruction offsets and previous SHA immediately afterward. Actual inputs already matched exactly in prior checks. The same 101 conditions/168 decisions passed new frozen 04→outside-repo 05 re-audit. No native rerun was added.
