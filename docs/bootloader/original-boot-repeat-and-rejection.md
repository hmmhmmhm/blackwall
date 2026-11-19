# Reproduction and rejection for the original boot/main display

The subsequent bw550 [final audit of all eight conditions](original-boot-completion-audit.md) is complete. Progress and remaining work below record the state at this task.

bw-0549. Two cold runs were checked with identical final `stock24-original-boot-screen-v1` manifest contents, all native component bytes, initial assets, and host runner source. `original-boot-cli-native-bw548-02` and `original-boot-cold-repeat-native-bw549-01` each passed 30-condition audits before and after cleanup and recorded first boot_count 1. These did not resume one virtual board; each started at bootloader reset in a new owned container.

Both completed 576×288 raw frames are byte-identical with SHA `81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2`, and each matches guest SRAM at the same point. Instruction counts 203,575,386/203,502,831 and virtual times 20.739792/20.648957 seconds differ. This is bounded invariant verification allowing timing differences from initial host polling, not a claim of full CPU/time identity or cycle accuracy.

## Unsupported boundary in actual original code

`unknown-boot-marker` changed only one OTA marker profile item on the board to unknown. It stopped at original boot PC 0x42e582's 0x7fe000 four-byte read with one guard_mram_tail. Handoff/main/UI/render entries 0, frame 0, external touch/UART responses 0. Original boot/main images were unchanged. Normal native process termination, 29 conditions for expected strict rejection, and separate --audit-existing passed. This is emulator rejection of unsupported input, not successful vendor firmware recovery/error handling or boot.

## Host rejection of corrupt inputs

A one-byte-corrupted input preserving the original boot's 149,773-byte length and vector, and a truncated 100-byte main input, were supplied to the actual CLI. Both were rejected by exact-image preflight with exit 1 before output directory or owned native job creation. Canonical originals still match. These are host preflight size/hash rejections, not bootloader cryptographic validation. Corrupt copies totaling 149,873 bytes were immediately removed after retaining hashes, commands, and error logs.

Cleanup totaled 15,189,587 bytes: second normal run 11,189,873, unsupported native 3,849,841, and corrupt copies 149,873. Owned containers were removed; canonical assets, model, original logs, final RAM/frame, and audits retained. First normal-run cleanup was recorded in bw548.

OB07 complete, overall 7/8=87.5%. OB08 final all-condition audit and entry-document cleanup remained. See private simulator/original-boot-repeat-verification-bw549-01/{cold-repeat-proof,preflight-rejection-proof,verification}.json and manifests/audits/cleanup for three native captures.
