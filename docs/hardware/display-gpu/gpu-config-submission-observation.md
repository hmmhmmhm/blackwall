# GPU CONFIG response and pre-submission boundary observations

Status: observation-model verification in progress. Full boot, GPU execution, screen, and physical verification remain incomplete.

## Value evidence and hypotheses

Pinned GPU metadata gives LOADCTRL 0x1f0 reset value 0xf4030105. Official SDK defines both NEMA_CONFIG and NEMA_LOADCTRL at the same offset. SDK read name CONFIG and metadata name LOADCTRL are not interpreted as different addresses.

Official SDK NEMA_CONFIGH is 0x1f4, but pinned public metadata has no reset value and GPU_Type marks this location reserved. Do not arbitrarily fill 0 as an actual device value. `tools/verify_gpu_config_sources.py` compiles comparisons of source hashes, low value, macro/type offsets and explicitly records high reset value=null.

`--gpu-config-low-response` requires raster trace storage. It supplies low word only; CONFIGH defaults unsupported. Separate `--gpu-config-high-hypothesis zero|bit9` represents two scenarios, not actual device values. SDK branches on high bit 9, so 0 and 512 are compared. This response does not advertise implemented GPU features: implemented_gpu_features=false.

## Boundary before STATUS

First observation with low-only blocked at CONFIGH 0x1f4. High=0 hypothesis stopped at STATUS 0xfc read. Stock 2.4 static call candidate compares whole read word to 0 and proceeds on a different path. Callee parameter 0x14 is not mapped directly to another SDK enum to establish a name.

`--gpu-initial-status-hypothesis zero|nonzero` is permitted only with explicit CONFIGH hypothesis. It supplies raw STATUS 0 or 1 in initial trace state. 1 does not mean actual busy bit; input observes code branching on word zero/nonzero. Default remains blocked. This is not a model accepting/completing GPU work and responds only with initial ring 3, reset 2, stored mode, and on state. Subsequent submission remains blocked by existing guard.

Separate public, virtual, and unknown:

- Low 0xf4030105: public initial word, source-supported, not G2 measurement.
- High 0/512 and initial STATUS 0/1: explicit unverified hypotheses, not hardware evidence.
- Raster effect, post-reset ring validity, GPU ISA/decoder, full boot: unimplemented/unverified.

Writes, partial reads, early access, and out-of-range registers unsupported. No automatic success when CONFIGH or STATUS unspecified. Actual glasses, OTA, and persistent storage unchanged.

Initial GPU-config-native-01 (15 conditions) and two main observations use source before STATUS hypothesis. Additional observations have separate source snapshot; initial results not overwritten.

## Final observations and remaining goals

Current source snapshot passed 23 guard conditions and preserves eight main runs. Each native snapshot core source and main combined source matched current files. Verification: private `simulator/gpu-config-verification-01/final-verification.json`.

| Input/hypothesis | First blocked access |
| --- | --- |
| stock 2.4 low only | CONFIGH 0x400901f4 read |
| stock 2.4 high=0, STATUS unspecified | STATUS 0x400900fc read |
| stock 2.4 high=0, STATUS=0 | Write 0 to peripheral enable 0x40021004 |
| stock 2.4 high=0, STATUS=1 | Write 0x73 to 0x40010400 |
| stock 2.4 high=512 | Write 0 to 0x40090374 |
| stock 2.3 / CFW high=0, STATUS=0 | Each writes 0 to 0x40021004 |
| stock 2.4 power stuck-off | Write 0 to 0x400900f8, no CONFIG read |

STATUS=0 CPU path stops at GPU power-off request; current power model does not support off after on. Progress to another peripheral with STATUS=1 is not evidence of normal boot or safe fallback. New register on high-bit9 path is also unsupported.

**Subsequent CMDRINGSTOP submission request was not yet captured.** Existing initial ring configuration is not completed submission. CPU RAM preparation, submit request, GPU execution, framebuffer, and screen display each require separate evidence. Next identify exact power-off call and preservation conditions in source. No claim of passing full boot with arbitrary STATUS or power-success values.

Catalog count correction: 106 macro names, 104 unique offsets. 1f0 and 20c each have two aliases. Previous 107 compile assertions cover 106 register macros and one command constant. Registered values did not change; wording that counted names as unique addresses was corrected.
