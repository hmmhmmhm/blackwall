# Faceclaw and stock comparison: existing evidence and next experiment

2026-11-18 · bw-0584. Existing execution and comparison evidence was reviewed with user approval. An independent review by GPT-6.2 Sol was checked against the documentation. This work examines saved evidence; it is not a new firmware run.

## Scope already executed

The original Faceclaw/38 ARM main ran on Renode M55 from main reset through actual patch hooks and stock fallback to the 576×288 first screen. The first screen is the stock dashboard, not the Faceclaw custom HUD. Original task wait/resume, virtual reset, touch/ring scenarios, and six- and 60-second runs after the screen are separately recorded. These depend on sensor/GPU functional models and are not boot from the actual Boot ROM or physical performance certification. [First screen](../bootloader/boot-family-first-screen.md) · [main boot](../firmware/native-main-boot-acceptance.md) · [sustained scope](../hardware/display-gpu/sustained-goal-completion.md).

The fixed Faceclaw main SHA is `4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f`; its exact stock base is 2.3.0.24 SHA `fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5`. Comparison with stock 2.4 would mix in vendor version changes. Proprietary images and captures remain outside Git. [Original identification](../firmware/raw-firmware-execution-audit.md).

The existing six E15 pairs are API display and communication diagnostics comparing each firmware family's original against a mutated candidate under identical conditions. They are not a cross-comparison of Faceclaw-specific features against stock or evidence of a custom HUD in natural main. [Comparison acceptance](../firmware/firmware-comparison-acceptance.md).

## Confirmed differences and gaps

With the same F0 input, stock 2.3 entered the normal SendDataToBoth path and Faceclaw reached the custom handler entry boundary. This evidence is at isolated original ARM function level; the custom command body, app consumption, and display changes were not confirmed. The AN prefix was also confirmed only up to the branch boundary of the Faceclaw EUS wrapper. [TPL boundary](../hardware/display-gpu/display-request-root-contract.md) · [EUS boundary](../hardware/communication/eus-att-device-ingress-contract.md).

The leading candidate for the next experiment is to identify custom HUD entry, update, and exit inputs and required state in the pinned upstream source, then send identical virtual stimuli to Faceclaw and exact stock 2.3 under the same model and initial state. Observe the actual original hooks, input handling, display changes, and fallback/exit separately. If protocol or initial state is unconfirmed, record the first unsupported boundary. Host-specified PC or direct custom-state injection must not be treated as successful natural execution.

This is an experiment proposal, not a claim that the custom UI has already run. Natural integration of recovery-patched boot with Faceclaw and actual glasses compatibility are also separately unverified. No physical access, write, or new native run occurred.

There is also a smaller nondestructive comparison candidate before visual comparison. Settings protobuf field 100 in the pinned Faceclaw source reports the firmware revision ([upstream research](../research/upstream-research.md)). Comparing Faceclaw's actual transmission with stock 2.3's response to the same virtual phone settings query could first verify patch-specific behavior without assuming custom display behavior. At this stage this is a source-based candidate, not a new natural integrated run with identical stimuli. A 640×480 virtual framebuffer and a 576×288 guest capture are not automatically treated as the same format.
