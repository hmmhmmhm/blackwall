# Read-Only Virtual Slots and Original Record Loading

Task bw-0280. Added optional `readOnlySlots` mode to the [inspection-only key DB model](keydb-slot-read-profiles.md). **Original main advanced past virtual record reads to a separate update-marker read at `0x7fe000`.** No value was supplied at that address. Actual glasses, keys, and MRAM were not accessed.

## Model change and scope

The optional mode allows byte/two-byte/four-byte/eight-byte reads only in `0x7ff000–0x7ff9ff` for explicit `zero`/`uninit-ff` profiles. It provides previously declared synthetic slot contents as memory, rather than adding caller-PC exceptions for the copy function and each record field. All values are uniform 0 or ff, not device originals or actual pairing state.

Existing scanner-only mode remains the default. Unknown cannot enable backing. Adjacent tail and all writes remain rejected; peripheral API reads crossing the range are rejected before data counters change. In optional mode, the host may also read declared virtual slots; distinguish this from scanner-only host rejection. Persistent storage, MRAM programming, and actual key restoration were not implemented.

DataReads/DataBytes count backing reads/bytes separately from the existing scanner's 2,570-byte reads. DataWordReads counts four-byte reads. Do not interpret diagnostic counts as actual record counts or hardware throughput.

## Original contract checked first

`inspect_keydb_record_load.py` verified original main hashes and existing audit material, then executed actual ARM fragments in M7.

- Actual 200-byte memcpy: checked zero/ff/0..199 data and preservation of 16 bytes around the destination and the stack.
- Record first word 0 or `ffffffff` exits as empty; two other values enter nonempty-record handling. It was not assumed that zero always copies 200 bytes × 10.
- A cache-control fragment preparing MRAM writes moves immediately to the next state if register bit 7 is synthetically ready; if not ready, it reaches error-4 preparation after software poll counter 10,000. Control values were `1f` → `3f`. Actual cache response/time was not measured.

There are nine conditions per image, 27 original ARM scenarios total. They use synthetic entry, stack, registers, and plain MMIO memory input. Source memcpy/memset was not reimplemented or replaced with success stubs, forced branches, or memory-write observers. Since the original cache caller has no local branch immediately afterward checking this return, do not treat timeout as safe write cancellation. The actual MRAM program callee was not executed.

## Original M55 execution results

| Profile | Observed path | Next block |
| --- | --- | --- |
| Backing zero, stock 2.4/2.3/Faceclaw 38 | After ten scanner slots: 3,160 backing reads/3,680 bytes; last address `7ff9c3` | Four-byte read of separate OTA marker `7fe000` |
| Backing uninit-ff, stock 2.4 | First-slot 257-byte check followed by original write preparation; zero backing reads | Cache `40021014=3f` write |
| Unknown, stock 2.4 | Backing forbidden, zero data supplied | First slot byte read |
| Backing off, stock 2.4 | Existing scanner-only retained | First four-byte read of 200-byte copy |

Backing-zero reads comprised 70 four-byte, 2,780 byte, and 310 two-byte reads. The 2,000-byte DB RAM identified in source was 0 in the final snapshot. Since it was also 0 in the earlier snapshot, this comparison alone does not prove all initialization writes or completed key DB API. Evidence is the combination of actual data consumption, original empty branch, and subsequent execution boundary; it is not full main boot completion.

The initial stock 2.4 plan expected the next HCI write boundary, but actual execution read `0x7fe000` at `0x44ac6c`. The original report retains PC/address expectation failure; after checking source, a separate saved audit judged the result. The same native execution was not restarted and the original failure was not changed to true. Other two images' load PC is `0x44a962`.

Immediately after that load is comparison with `0x55555555`. This address matches the OTA marker in the existing [web verifier boundary](../../archive/web-protocol-verification.md) and [recovery owner investigation](../../bootloader/recovery-owner-flow.md). **Marker value is unknown**; key-DB zero was not extended into this area. The existing Blackwall installation principle of not merely warning on pending/unknown and then continuing actual writes also remains.

## Verification and preservation

- Preserved RED for a constructor without the new argument; then 148 component conditions passed. These include existing 119 plus optional-mode values, widths, end boundary, overrun, write rejection, reset, and unknown rejection.
- Six native runs and six separate saved audits. The first stock 2.4 raw semantic failure remains; the other five passed their initial semantic contracts too. Unknown/off exactly matched source CPU, instruction count, events, and boundary. The uninit path was not canceled or bypassed in backing mode.
- Private `keydb-record-source-01` has 27 original conditions; `keydb-record-profiles-contract-01` has six saved native analyses. Model, originals, failure, audits, and 23 analyzer dependencies are pinned in `keydb-record-verification-01/manifest.json`. Separate reanalysis of the pinned copy and identical reports were confirmed. Proprietary main/SRAM remain outside Git.

## Next units

1. Analyze original read/write/reset flow for marker `0x7fe000` and related state together with existing updater/recovery contracts. Distinguish virtual normal/update-pending states from default unknown.
2. MRAM cache preparation, ROM program, and completion/failure/interruption handling remain separate unfinished work. Do not assume physical readiness or convert cache timeout to success.
3. Then connect to actual app loop/display boundaries. Separate EM9305 NVM, both sides/case compatibility, and physical recovery also remain incomplete.

Overall completion was 13/29 = 44.8%. Do not report successful integrated main or 576×288 display.
