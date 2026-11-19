# Power trim sequence after GPU disable

Status: exact main, first store, function decode, and public-source comparison completed for three inputs. Behavior model is verified separately. Actual voltage, delay, retention, and full boot were not verified.

Public HAL 61b293a `am_hal_spotmgr_pcm2_0_gpu_off_sequence` was compared to stock 2.4 function 0x5c2080–0x5c2226. Current virtual buck ACT path:

1. Increase core active trim by 12, up to 1023.
2. Set memory active trim to 5.
3. Set PWRSW1 bits 29, 28, 31, 30 in order.
4. Set TON2 low/high=6, TON4 low/high=5, TON7 low=7, TON6 high=10.
5. Restore core active trim to starting value and memory active trim to 1.
6. Clear those four PWRSW1 bits in order.

PCM2 candidate has 18 writes. It differs from GPU-on preparation TON7=13/TON6=19, and on preparation clears switches before restoring trim. Therefore existing preparation model is not simply called again. PCM1 extra trim restore, B0 memory=0, and LDO branches are excluded. Wrong branches must block new access, not be skipped with virtual success.

Private `gpu-post-off-research-01/report.json` checked stock 2.3/2.4 and CFW main hashes and compared continuous M-class/V8 function decode, first core store, and PC-relative address 40020080. First store PC is 2.4=5c20e8, 2.3/CFW=5bab40. This does not mean all branches executed. Public HAL source hash and candidate decode are preserved; exact ABI equivalence is not claimed.

## Virtual storage transition

`--gpu-off-sequence-storage` requires explicit off response. It permits only the above 18 writes in exact order, with values preserving bits outside fields. Starting core trim and actual boost delta are recorded; starting trim is restored at index 12. Readiness requires power=powered-off, first GPU preparation complete, virtual buck=active. Storage transition does not start while disable is requested or stuck-on.

After off lifecycle starts, wrong values/order/repetition for model-owned registers are blocked rather than bypassed to another storage model. GPU reactivation and command execution remain unsupported. Current trim 973→985→973 is synthetic input, not physical calibration or actual voltage. Saturation calculation is source-supported, but saturation boundary runtime tests were not separately performed.

## Small virtual test

14 conditions passed in `gpu-off-sequence-native-01/report.json`. Ten new cases include complete sequence, wrong first value/order, misuse of GPU-on TON values, wrong restoration order, partial width, repetition, option unselected, awaiting response, and stuck-on. Four existing conditions including default power block and ring phase comparison passed. These are 14 CPU-written tests; actual main execution of the source-supported transition is separate.

## Main execution and verification

Three current-source runs of stock 2.3, 2.4, and CFW confirmed completion of 18 writes and final core/memory/PWRSW/TON values across seven registers. All then stopped attempting to write 0x73 to 0x40010400. Stock 2.4 control without post-off model stopped at prior 0x40020080. This observes initialization advancing to the next peripheral boundary, not boot success.

Native 14 and main four source snapshots match current source. CLI without required off response was rejected before file/Docker access. Aggregate is private `gpu-off-sequence-verification-01/final-verification.json`. Reactivation, subsequent command submission, GPU execution, integrated screen, and physical verification remain incomplete.

Next address 40010400 was compiled as pinned public header GPIO_BASE 40010000 + PADKEY offset 400. Initial PINCFG0 offset 400 hypothesis failed an assert because actual offset is 0 and was rejected; failed source/log and final PADKEY/PINCFG0 asserts are preserved. Do not describe PINCFG0 as this address. `next-boundary-layout.json` establishes layout, not protection-key behavior. Next analyze PADKEY protection, unlock, and pin-configuration conditions.
