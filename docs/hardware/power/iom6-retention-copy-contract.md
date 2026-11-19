# IOM6 Startup Retention Copy Contract

A follow-up checkpoint to bw-0242. Without assuming the entire external CQ input, this work allowed one specific original retention save in a limited manner. All three original inputs reached GPIO117 reset/ready wait after state save and power-down. Initialization completion, first SPI communication, and full boot remain incomplete.

## Original code behavior

Stock 2.4 save block is 0x581e32–0x581eec, restore block 0x581cf8–0x581dee. Corresponding stock 2.3/CFW blocks are each 0x7358 lower. CQFLAGS is copied to handle+0x884 and written back to the same register on restore. The pinned HAL C source's private registerState.regCQFLAGS references are also these two save/restore locations. The original instructions were directly checked without assuming the public SDK and original share the full ABI.

The SVD describes lower CQFLAGS fields as current status/read-only and [15:8] as hardware status. Its generic access tag says read-write, leaving a metadata inconsistency. The current model follows the status description and existing CQSETCLEAR contract. This is not verification of physical register write behavior.

Original ARM save/restore blocks were directly executed in separate Unicorn unit tests. After checking 32 combinations of five-bit inputs, the test expanded to **all 128 patterns** of seven unknown status bits to avoid assuming selector relationships. Three images executed 768 save/restore runs total, passing 2,696 checks.

Saved RAM values differ by pattern. But excluding only unknown hardware status mask 0x7f00, other saved fields and restore writes were identical. IRQ mask, software flags, and remaining register values were not excluded. This is limited evidence of independence for effective restore writes in the tested retention blocks, not equivalence of the full function, entire program SRAM, or physical pin values. Unit tests began at explicit basic blocks rather than full function or main entry; internal opcodes/branches were not changed.

## Limited mode

`BlackwallStrictIom.cqStartupRetentionPc` defaults to −1. Even when enabled it returns 0x8c40 only once under these conditions:

- Module 6, SPI configuration latch selected, global cqInputLevels=-1.
- Clock 0x1201, SPI config 0, DMA trigger 2, known SUBMOD low 8 bits 0x20.
- CQ disabled/config 2, software flags 64, IRQ mask/pause/index 0.
- Pinned original PC and CPU R1 IOM6 base match; R4 is a virtual handle checked for range, alignment, and module 6.
- Zero previous snapshot reads.

0x8c40 is a consistent representative value corresponding to input vector 0 under the existing selector definition. It does not establish actual device input 0. It is used on limited source evidence that the corresponding pattern does not affect effective writes in the current retention restore. This value generates neither actual GPIO input nor EM9305 response.

Global InputLevels/AvailableFlagsMask remain unknown. Guards for general CQFLAGS reads, other PC/context, second snapshots, and peer commands were not lifted. Power-down does not reopen the one-read budget; only full peripheral reset initializes it.

The first application trial rejected the same boundary because it compared SMOD2 type bits outside the backend mask. This was corrected to compare masked SubmoduleControl supplied to Apollo510. The failure was preserved; original guest code was not changed and failure values were not tailored.

## Original main results

| Input | Limited mode | Next boundary |
| --- | --- | --- |
| Stock 2.4 | One snapshot, one IOM6 save/power-off | PC 0x501bf2, GPIO word 0x40010410 read |
| Stock 2.3 / CFW | Same limited copy/power-off | PC 0x54a54a, same GPIO word read |
| Stock 2.4 mode-off control | Zero snapshots | Existing CQFLAGS PC 0x581e82; CPU, instruction count, observations, boundary exact |

All three active inputs have global input=-1, no peer, and 0 IOM6 commands/CQ pairs. UART0 bytes, IRQ 8, and prior event prefix were preserved. Main ran as pinned original from reset, with no observer hook, PC, branch, or return changed during execution. GPIO judgment at the new PC remains blocked.

The initial description called it GPIO149 due to incorrectly calculating input word base as 0x40010400. Actual base is 0x40010404, so 0x40010410 bit 21 is **GPIO117**. PAD117 address 0x400101d4 and original config 0x2093 were also checked. Execution/check addresses and opcodes were unchanged; the description was corrected. Historical raw reports remain preserved.

The original lowers and raises reset output GPIO93, then polls GPIO117. Next investigate EM9305 reset/ready state and timing contracts needed for this actual branch. No specific input was returned to force passage through the loop.

## Verification and reproduction material

- After confirming a native constructor red for the new option, 66 unit checks passed. Host context cannot use the limited read and global input remains unknown.
- With the final build, existing IOM 82, CQ 79, and 43 checks for seven explicit inputs exactly matched previous frozen reports. Historical models were not regenerated with the new builder.
- Three original mains, one control, and 193 saved audits passed. A stock 2.4 exploratory report was preserved as a semantic failure expecting the previous boundary, then separately re-audited after source confirmation of the new boundary.
- Inputs, raw logs, and source/audits are preserved privately in `iom6-retention-source-04`, `iom6-retention-unit-02`, `iom6-retention-regression-02`, `iom6-retention-discovery-02/stock24`, `iom6-retention-main-01`, `iom6-retention-current-audit-02`, and `iom6-retention-verification-02`.
- An initial regression parser used the wrong CQ marker name; it was corrected by reinterpreting saved logs without rerunning native. The final regression rerun was a separate input to verify a later context-mask code change.

The manufacturer [EM9305 datasheet URL](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) was checked, but the current request redirected to another company information page and did not obtain reset/RDY text. Search-cache summaries were not adopted as conclusive chip-protocol evidence.

bw-0242 remains in progress because it precedes first transfer. No physical glasses access, installation, or permanent write occurred; product progress remains 13/29=44.8%, and normal font-bank, full boot, integrated display, and physical recovery remain incomplete.

Follow-up bw273: [virtual active event delivery](../communication/em9305-active-event-transport.md) connected CS/RDY phase and RX-only, confirming initial event acceptance and wrong-event rejection across three originals. Optional budget 2 was added for the same retention cleanup, retaining default 1 and unknown global inputs. Full main/BLE/display/physical device remain incomplete.
