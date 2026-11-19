# uLED MSPI0 Queue, Interrupt, and Retention Power Contract

bw-0307. Analyzed bw306's saved state and original ARM without accessing physical glasses/case or running a new Renode main. Overall completion criteria remained **13/29, 44.8%, scope v2**.

## Boundaries checked

| Item | Evidence and limits |
| --- | --- |
| Natural M55 starting point | Reverified the CQCURIDX write boundary, full SRAM, GPR, main SHA, and saved audit for all three bw306 inputs. |
| Follow-up queue configuration | Continued original ARM in Unicorn M7 to the point where controller enable returned success 0. Each input had 58 observed instructions; CQEN remained 0. |
| Observation-method control | Executed the same section with MMIO callbacks and ordinary memory separately. Full PC path, SRAM, WORK, general registers, XPSR, and PRIMASK matched for all three inputs. Do not treat final-memory comparison as observation of every transient write. |
| IRQ | A separate function call confirmed clear/enable mask `0x1a80`, preservation of existing enable bits, IRQ20 priority 4, and NVIC enable write. This matches public SVD MSPI0 IRQ20. Actual interrupt generation/service is unverified. |
| Retention power | A separate power-control call with state 2/retain 1 stopped at the CQFLAGS read after 20 reads of known registers. This does not prove completion of power-off/restoration. |

The runner executes the original binary but is M7, with Thumb state and MMIO/SCS fixtures explicitly supplied. The first section uses saved GPR and actual stack/RAM; IRQ and power tests use synthetic call arguments and stack. Distinguish these from natural M55 boot progress. Firmware instructions, branches, and return values were not modified.

## Queue configuration is not execution start

The actual CMDQ tables in all three binaries identically contain addresses for CQCFG/CQADDR/CQCURIDX/CQENDIDX/CQPAUSE/CQSTAT. Initial CQ address is the actual saved TCB pointer and length is 1,024 bytes.

The original subsequent sequence is:

1. Store 0 in CQCURIDX and CQENDIDX.
2. Set index-equality pause mask `0x4000` in CQPAUSE.
3. Store the TCB address in CQADDR.
4. Store priority value 2 in CQCFG. Execution bit 0 is off.
5. The MSPI enable function writes `0x400080` to CQSETCLEAR. Under explicit set/clear interpretation, software flags become `0x80`.
6. Set the enabled bit in the MSPI handle and return success. Distinguish this from CMDQ's own enabled bit.

CQPAUSE and CQSETCLEAR are different registers. Keeping the execution bit off in initial CMDQ configuration is consistent with init/enable separation in the pinned [Ambiq CMDQ source](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_cmdq.c). This does not guarantee the full SDK and firmware ABIs match.

## Intermediate call that must not be omitted

Immediately after MSPI enable succeeds, the upper uLED function calls a separate configuration function with arguments `(0,0)`, then clears/enables IRQ. Initial exploration stopped at an unmapped write inside this configuration function. The checker deliberately ends immediately after the success return; it does not skip this call. Therefore **we cannot yet conclude that natural execution reached IRQ configuration**. The next M55 candidate must check whether the existing GPIO model handles this section and analyze any new boundary using actual original operations.

## Remaining issue in retention power

A separate call using an explicit config-reset fixture and the previously observed disabled CQ configuration reads device/config/pad, CQ address/pause/index, and INTEN, then stops at `CQFLAGS(0x2b0)`. The fixture's config values are not claimed to be the final values of natural device_configure.

The original stores the entire CQFLAGS word in an SRAM shadow. Unknown input/complete/idle bits were not arbitrarily synthesized as 0 or success. DMA, PIO, CQ execution/completion, panel transfer, and framebuffer were not implemented. Next analyze bits actually used in CQFLAGS save/restore together with the power off/on contract. Do not copy the MSPI1 NOR/XIP model unchanged into the MSPI0 panel model.

## Reproduction and preservation

- Tool: `tools/inspect_mspi0_queue_contract.py`.
- Private final analysis: `simulator/mspi0-queue-source-03/`; frozen reproduction: `mspi0-queue-source-04/`. Report and inspector each match byte for byte.
- `mspi0-queue-verification-01/manifest.json`: 79 Python checks frozen, nine existing model SHA values unchanged, source/results pinned. One analysis contains 27 original ARM sections/independent calls. Do not report this as a number of natural boot tests.
- `mspi0-queue-sdk-01/`: verified SHA-256, Git blobs, and complete tree for commit-pinned CMDQ C/H. Existing SVD/header were also compared with existing pinned SHA values.
- Initial exploration's unmapped GPIO failure and the checker's incorrect wrapper BL offset interpretation were preserved in `mspi0-queue-research-01/`. The latter was corrected to actual `+0x26`. Initial source01/02 were not overwritten.

The next goal is to connect this nonexecuting CQ configuration to an optional MSPI0 model and advance natural main by combining the intermediate GPIO, independent IRQ, and CQFLAGS retention boundaries. Do not report it as integrated display or full boot success.
