# Original MSPI0 CQFLAGS and Retention Power Contract

bw-0309. Verified bw308's three original main/SRAM/GPR states and saved audits, then analyzed the original ARM code. There was no new natural M55 main execution or peripheral-model change. Overall completion criteria remained **13/29 = 44.8%, scope v2**.

## Observed behavior

| Item | Verified scope |
| --- | --- |
| CQFLAGS save | Execution from the original LDR where natural main stopped saves the complete word to an SRAM shadow. The public register mask is 16 bits. |
| CQFLAGS restore | The original restore block reads only the shadow byte and writes the lower 8 bits to CQSETCLEAR. It does not use the upper hardware-state byte in this restore write. |
| Upper-byte control | Tested every upper byte from 0 to 255 with native software flags fixed at `0x80`. All three binaries had the same save/restore PC path and the same order and values for 25 restore writes. The full input word remains in the shadow, so this does not mean all RAM is identical. |
| Active queue | If the saved CQCFG execution bit is 1, the experiment distinguishes the path before the original CQ disable call and stops before the CQ enable call during restore. It does not absorb that case into the inactive path. |
| Pending work | Separate calls setting each of the original instance's two pending counters to 1 returned status 3 without MMIO, rejecting suspend. |
| HAL power-off | The original HAL function for enum 16 clears only enable bit 14 and succeeds with an explicit immediate-response fixture. An already-off input succeeds without a write. |
| Integrated suspend tail | All three binaries executed original power, clock, and release calls and reached the successful return point in 668 observed instructions. The power response is explicit virtual input. |

## Experiment inputs and execution level

`tools/inspect_mspi0_retention.py` executes original ARM on Unicorn M7. The first save section and integrated suspend tail start from saved native GPR, stack, and full SRAM, with Thumb state and MMIO responses supplied. The restore block, HAL, and busy checks use separate synthetic entries and stacks. Original instructions, branches, and return values were unchanged.

Twenty register values already saved to the shadow by natural execution are read from actual SRAM. CQCFG=2, software flags=`0x80`, and IRQ enable=`0x1a80` are verified values from the existing natural execution. The three values DMABCOUNT, DMATHRESH, and THRESHOLD, which had not yet been read after CQFLAGS, explicitly use public reset fixtures. They are not claimed as actual reads by natural main.

The restore experiment separately executes **only the block after** the original power and clock recovery calls. It does not prove successful actual wake calls, a complete power cycle, or physical state retention. Bounded source tests must be distinguished from progress in natural Renode boot.

## Details of subsequent power and clock handling

The original HAL release function's synthetic input uses aggregate enable `0x4e00` and the same status, with status declared to respond immediately as `0x0e00` after clearing bit 14. Other enable bits are preserved. An already-`0x0e00` input succeeds without a write. Physical response time and recovery from stuck-on errors were not verified.

The integrated suspend tail performs the following:

1. Saves required shadows and sets the valid marker.
2. Clears MSPI interrupt enable.
3. Uses the original HAL to clear MSPI0 power request bit 14 and checks the declared off response.
4. Changes the shared MSPI clock word from `0xa4215` to `0xa4214`, clearing only the MSPI0 gate.
5. Original clock-release code also clears CLKGEN misc's HFRC2 force bit (`0xfbbfe1` → `0xfbbfc1`). Modeling only the clock gate would miss this subsequent action.
6. Reaches the original upper caller's return point with result 0.

The restore block first saves CQCFG with its execution bit off. If the queue had previously been active, a separate enable function is called afterward. The 25 restore register writes for an inactive queue match the shadow and clear the valid marker.

Compared this with `regCQFLAGS & 0xFF` restoration and final CQCFG restoration in the pinned [Ambiq MSPI source](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_mspi.c). This does not guarantee the entire current source ABI or actual G2 power-domain behavior.

## Conditions for the next model integration

Do not supply upper CQFLAGS bits as a generic idle/complete response. The next candidate should combine a virtual response restricted to the exact verified retention-read PC and input state with the inactive MSPI0 power-off/reset/IRQ/clock lifecycle. Continue blocking other CQFLAGS readers and active CQ, DMA, and PIO. Then identify the next panel transfer and framebuffer boundary in original natural main.

Full wake restoration, power failure/interruption scenarios, retention of panel state itself, a new natural M55 main run, and integrated display remained unverified. No physical glasses or case were accessed.

## Reproduction assets

The reports and inspectors in final original analysis `simulator/mspi0-retention-source-03/` and frozen reproduction `mspi0-retention-source-05/` match byte for byte. One analysis comprises 1,557 original ARM sections and separate calls; do not describe this as a count of natural boot tests. Eighty-four Python dependencies were frozen, and the SHA values of nine existing models remained unchanged. Pins for the SDK, SVD/header, three original main/SRAM images, and results are recorded in `mspi0-retention-verification-01/manifest.json`.

Initial source01/02 were preserved as results before expanding scope and strengthening checks. After confirming that source04's execution handle had disappeared and that its process and output files were absent, a new source05 reproduced the analysis. The existing run was not duplicated merely because observation timed out. Details are in `interrupted-attempt.json`; source04 is not used as a completed result.
