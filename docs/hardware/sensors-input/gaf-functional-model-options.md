# Need for GAF Evidence and Functional Model Alternatives

Follow-up bw478: the user provided the downloaded SDK and actual source review is complete. The unconfirmed SDK contents below describe the state at the time; current findings are in the [SDK source review](../../research/icm45608-sdk-source-review.md).

bw477. The user asked whether GAF material was essential and whether searching, simulation, or a workaround was possible, so the assumptions behind the blocked assessment were reconsidered. Questions about SDK login and usefulness were later included in the same investigation. No new model implementation, original ARM execution, or physical access occurred.

## Correction to prerequisites

Running original ARM firmware and identically executing the sensor's internal ROM are different requirements. Project v3 does not require chipset cycle, analog, RF, or full GPU ISA accuracy; it uses the necessary peripheral functional contracts. Therefore, **the conclusion that obtaining sensor ROM/ISA is essential to all functional emulator development was too strong.** The earlier blocked assessment treated the accuracy and verification requirements of the current strict GAF profile as the only implementation path for the whole project.

Renode's [peripheral modeling guide](https://renode.readthedocs.io/en/latest/advanced/writing-peripherals.html) describes a C# model handling CPU bus accesses and implementing register reads, writes, reset, and side effects. A structure that preserves original M55 instructions while replacing only the sensor with a functional model is possible. That fact alone does not prove any GAF result matches a physical device or that the current original will run to completion.

## Practical options

1. Obtain evidence of exact device behavior: extend the existing strict profile using SDK, source/documentation, and independent observations. This favors sensor accuracy verification, but the SDK is not guaranteed to contain ROM/ISA.
2. Explicit functional model: consistently model I²C, configuration, trigger, busy, completion, FIFO, IRQ, and host-consumed state, declaring inputs, assumptions, and unverified scope for calibration and sensor output. This alternative can execute the original ARM, branches, and scheduler unchanged. Preserve the current strict model and distinguish model-based UI/CFW tests from verification of agreement with physical GAF.
3. Patch original code or force PC, TCB, or ready: this may advance execution but is a different experiment from verifying the original natural path. It is not recommended as an alternative to the default original verification path.

The recommendation is to obtain the SDK and inspect its actual contents first, then design option 2 as a separate profile if gaps remain. Setting all unknown RAM to 0 or merely clearing busy and declaring success does not establish functional model consistency. SDK investigation and functional model design can proceed in parallel. Major model changes, verification claims, and how completion criteria apply should be decided after discussion with the user; this record proposes them only.

## SDK access and expected value

Official metadata `field_requires_login=true` and the public frontend's login-check → download handling were confirmed. This supports that download is configured after login; it does not confirm download completion on an actual account or whether additional account restrictions exist.

The advertised filename is `emd-icm45608_examples-atmel-cm4-fpu-2.0.0.zip`. It suggests an example package for Atmel CM4-FPU; it does not mean its contents were read. Official metadata version is null, recorded separately from 2.0.0 in the filename. SDK contents, additional terms, and license had not yet been checked.

After obtaining it, first inspect target sensor driver/initialization examples, state/RAM structures and calculation code after GAF requests 2/4, supported ROM/patch versions, and tests/logs and expected results. This may narrow the functional model's scope. A gap may remain if it duplicates the public driver already held or the essential behavior exists only inside sensor ROM. Thus **it is worth obtaining, but login alone is not assumed to solve the problem.**

Access: [official SDK download](https://www.invensense.tdk.com/en-us/download-resource/icm-45608-smartmotion-emd). Do not request passwords or login tokens or bypass account/download permissions. Before placing downloaded material in public Git, first check provenance, hashes, and license; the downloaded material is not placed there.
