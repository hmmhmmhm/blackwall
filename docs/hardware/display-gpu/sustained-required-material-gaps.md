# ROM, GPU, and GAF required-material gaps for sustained goal

bw493. This active Goal determines possession/absence, evidence, and acquisition paths of required material. It does not complete precise implementation of the three internal functions or physical investigation. Fifteen actual assets were read and SHA/size and key source contents pinned. Private `simulator/sustained-required-gaps-01/report.json` is the canonical judgment.

| Area | Material possessed and reviewed | Still needed for precise reproduction |
| --- | --- | --- |
| ROM/boot | Original stock boot 2.3.2.14 and 2.4.0.24, data initialization/handoff/MRAM wrapper analysis | Exact Apollo510B revision Boot ROM image/reset entry, corresponding Info1/trim and security initial state, ROM/verification-engine effects |
| GPU | Pinned Apollo Nema header/SDK, original ARM-generated commands, actual guest framebuffer from current reference model | Independent Apollo510B/G2 output/specification distinguishing half-pixel, coverage, sampling, nibble/AL44, rounding, and command meanings for the IP used |
| GAF | User SDK 2.0.0, GAF host driver/examples, request 2/4, FIFO/IRQ, original ARM decoding/axis conversion | Sensor EDMP ROM/ISA or sufficient computation specification; independent motion/calibration time series → quat/bias/accuracy outputs and precision information |

ROM wrapper call `0x0200FF21` is a concrete boundary requiring distinction between held boot binary and actual ROM. ROM status in prior isolated tests was mocked. Obtaining SDK/ROM ABI descriptions alone does not execute actual ROM bytes. Among named project assets/profiles reviewed here, no item proved full ROM cold boot. This is not global proof that no ROM file exists anywhere on the Mac or in all external material.

GPU source explicitly requires `packingReference`/`textureReference` and states packing policy is not physical GPU verification. Half-pixel naming difference between other Nema generation documentation and Apollo header remains. Do not reuse current model-generated PNG as physical ground truth for that same model. First pin inputs distinguishing asymmetric nibbles, nonzero destination, boundary clip, half-pixel, and quantization, then find exact-IP specification or independent hardware output.

User ZIP matched existing preserved SHA `57b68bb9…`. Actual `inv_imu_edmp.c` uses ROM entry and dynamic GAF requests 2/4. Existence of host quaternion-read functions or public RAM patch alone does not establish preceding ROM computation or full fusion. Nor is it claimed every SDK binary lacks the algorithm. Define example corpus of stationary/rotation/magnetic disturbance/recalibration/drop/reset inputs and outputs, then obtain permitted implementations/test vectors or independent observation.

Acquisition order: compare exact ROM ABI/IP revision/sensor version in existing materials → inspect exact contents of manufacturer-public/account-accessible materials → if insufficient, propose separate hardware observation. Buying development boards, physical reads/dumps, security/persistent writes are not included in this research approval. Current functional model's sustained verification continues independently even without these materials.

Independent evidence: [boot analysis](../../bootloader/bootloader-2-4-analysis.md), [GPU sampling](gpu-sampling-source-boundaries.md), [SDK source review](../../research/icm45608-sdk-source-review.md), [GAF public-material refresh](../sensors-input/gaf-execution-source-refresh.md). Physical access, SDK binary execution, new ARM execution, Astra, external publication: 0.
