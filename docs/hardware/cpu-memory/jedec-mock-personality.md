# Explicit Mock JEDEC Identity and Original Query Return

bw-0132. Actual JEDEC values remain unknown; the original query path is tested under deliberately injected mocks. This experiment combines `source-reset-zero-ids` with existing GPU/clock assumptions; it does not verify an accurate actual G2 hardware personality or an installable combination.

## Sources reviewed and unknown values

Pinned HAL `am_reg_jedec.h` defines base `0xe00fef00`, PID0–3 offsets `0xe0..0xec`, CID0–3 offsets `0xf0..0xfc`, and manufacturer JEPID `0x9b` field positions. Actual Apollo510B part-number and CID values were not established. Do not transfer HAL comments about Apollo/Apollo2 CID as facts about Apollo510.

Checked SDK source, web searches, and extracted text from the existing official datasheet. macOS PDFKit extracted text from 302 pages, but CoreGraphics warnings occurred and not all visual content was reviewed. Failure to find values in extracted text is not proof that the entire document lacks them.

Eight virtual JEDEC registers are provided only when both values are explicitly specified:

```text
--jedec-mock-part 0x000 --jedec-mock-cid 0x00000000
```

Part is 12-bit and CID 32-bit; the chip-info profile and existing explicit revision are required. Manufacturer bits use source `0x9b`; revision bits are shared with virtual CHIPREV. PID4–7, reserved regions, writes, and other access widths are unsupported. Omitting options keeps PID0 read as a strict stop. Low MCUCTRL and PPB share model ownership, and delegate reset does not clear root values.

## Tool for observing original execution

Reused the existing PC observer and centralized runtime-generation code in `execution_observer.py`. Existing points and the new main runner use the same generator. Optional features:

- `--observe-pc LABEL:ADDRESS`: up to 128 aligned points within original main.
- `--observe-sram LABEL:ADDRESS:WORDS`: copy 1–16 words from G2-mapped SRAM on the first hit of a declared point. One snapshot per point; no guest writes.

The caller must confirm instruction boundaries from source and original decoding. API checks of alignment and image range do not prove an arbitrary data address is a valid instruction. This is bounded debug observation for the current SRAM map and single-CPU model, not a physical device API.

Compared original BL/PUSH/POP with saved Thumb LR/stack at the prior stop and selected six points: API entry, internal information-query entry, internal return POP, wrapper continuation, API return POP, and caller continuation. There are no original symbols, so function names are inferred from the HAL shape. PC, return values, and instructions are not overwritten. A 64-byte snapshot just before return preserves fields written by the original before the caller reuses the stack.

## Verification results

The 35 checks in `jedec-unit-01` verified eight registers, shared ownership, read-only behavior, value reconstruction, default unknown, invalid constructors, and reset. `execution-observer-snapshot-unit-02` confirmed an actual synthetic ARM guest store of 42 in the first-hit snapshot, point order, R0/R2, ring bound, rejection of eight invalid captures, and preservation of guest results. Three existing observation checks and three new request checks also passed.

Results in `private:simulator/jedec-main-comparison-01/report.json`:

| Run | Mock part/CID | Natural API return | Next stop |
| --- | --- | --- | --- |
| Stock 2.4 | 0 / 0 | Returned to caller, R0=0 | IOM7 CMD write `0x201` |
| Stock 2.3 | 0 / 0 | Returned to caller, R0=0 | Same request |
| Faceclaw 38 | 0 / 0 | Returned to caller, R0=0 | Same request |
| Stock 2.4 control assumption | `0xfff` / `0xb105100d` | Returned to caller, R0=0 | Same request |
| Stock 2.4 unsupported | Unspecified | Return point not reached | Existing JEDEC.PID0 read |

In the first four runs all six points were observed once in order. R0 at internal entry matched the actual structure destination; in the pre-return snapshot original ARM assembled JEDEC fields as part/JEPID `0x9b`/revision `0x23`/CID respectively. Existing MCU/SKU memory calculation was preserved. Legacy FlashSize remains excluded from verification. API return 0 and Qualified 1 are original constant paths, not physical verification or qualification of the mock identity.

The new stop address is `0x40057120`, requested value `0x201`. PCs are stock 2.4 `0x58236c`, stock 2.3/CFW `0x57b014`. IOM7 was reenabled, but there is no target peer and zero commands are allowed. Reaching a request differs from actual bus transmission and a target response. UART TX/ISR and CQ pairs also remain 0; full boot/display is incomplete.

## Remaining model-consistency limitation

Selected source-reset SKU `0x002d480f` has SKUGFX bit 8 = 0, which HAL interprets as no GPU support. This may conflict with the independently selected GPU identity/power assumptions. The collection is not a reviewed actual G2 personality; do not silently change the bit to advance UI. Actual SKU confirmation or separate verification of an explicit virtual feature personality is required.

Next investigate IOM7's destination address, original request, and connected-device protocol. Do not pass initialization with a generic peer that unconditionally returns ACK/0 for a device of unknown provenance.

A read-only review within the same GPT-6 family found no additional material defects. The parent independently compares results from five original runs. Astra, physical device work, and separate transcript-archive comparison were not used. Product criteria remain 13/29.

Reproduce using `tools/verify_jedec_main.py SIMULATOR_ROOT NEW_OUTPUT` in the existing Capstone venv. Without mock and observation options, the existing execution path and unsupported boundary remain.

Final saved-evidence audit: 107 checks in `private:simulator/jedec-verification-01/report.json` compared raw markers/reports, current source, pinned main/image, return observations, default strict behavior, and five unsupported CLI conditions. `host-tests.log` in the same folder records rerunning six common-generator and existing-validator checks. The existing native batch was not rerun, and the audit itself is not counted as new hardware verification.
