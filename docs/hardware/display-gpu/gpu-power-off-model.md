# GPU power-off response model

Status: opt-in virtual response implemented; limited verification completed for 19 native and five main cases. Full boot, GPU execution, and integrated screen remain incomplete. Only enable/status bits are modeled based on [static evidence](gpu-power-off-research.md).

## Explicit hypothesis

Main runner `--gpu-power-off-response off|stuck-on` requires active power profile and explicit initial STATUS=zero. This is not a measurement of actual device initial STATUS. With option omitted, disable writes while on remain blocked as before.

Writing enable=0 while on clears the requested word and transitions to off-requested. At next status read, off clears the status bit and becomes powered-off; stuck-on retains the bit and becomes stuck-on. Response delay is assumed zero at the first read. This is not a model of actual voltage, delay, or GPU idle judgment.

At disable request, epoch_retired=true. Saved initialization records remain diagnostic, but GPU CONFIG/STATUS/ID reads, IRQ clear, and ring writes are blocked by phase gate. GPU power reactivation is blocked in both profiles. No claim that physical registers/RAM are retained or initialized after power-off; reactivation modeling needs separate evidence. CPU RAM itself remains in current emulator memory, not interpreted as GPU being able to reuse it.

The model covers only the first on→off lifecycle. Full reset propagation, GPU DMA, command completion, IRQ generation, and output are unimplemented. First-stop guards for unsupported access and hardware authorization boundaries remain.

## Small virtual tests

Private `simulator/gpu-power-off-native-01/report.json` passed 15 conditions: three existing stuck-off/default active-disable block/initial STATUS=zero conditions and 12 new. New cases cover off/stuck-on responses, separation of request and response, repeated status reads, reactivation block, post-disable CONFIG/STATUS/IRQ clear/ring write blocks, and partial-width write rejection. These verify the model contract, not chip behavior or full firmware boot.

## Five main runs

Stock 2.4 off/stuck-on/default, stock 2.3 off, and CFW off ran with the same source. Private `gpu-power-off-verification-01/final-verification.json` compares 15 native core snapshots and five main combined sources against current files and confirms:

| Scenario | Power phase | First block |
| --- | --- | --- |
| stock 2.4, stock 2.3, CFW / off | powered-off | write 0x6d3d9 to 0x40020080 |
| stock 2.4 / stuck-on | stuck-on | write 0x73 to 0x40010400 |
| stock 2.4 / option omitted | on | write 0 to 0x40021004 |

CPU progress to subsequent power configuration after off response was observed. Movement to other peripheral initialization when stuck-on is not proof of successful fallback or correct error handling. No corresponding physical device input or timeout verification occurred.

Subsequent CMDRINGSTOP submission, GPU execution, full boot, and integrated screen remain incomplete. Next analyze power-state transition conditions for post-disable VRCTRL 0x40020080 write and connect necessary subsequent model. Do not unconditionally permit the boundary or skip the CPU. Negative CLI tests confirmed off option without required hypothesis is rejected before input-file/Docker access.

## Test strengthening after independent review

Review noted that existing ring-off OR4 submission is blocked even when on, insufficient evidence for the power phase gate. It is interpreted only as submission-block regression. Four separate conditions were added writing valid initial OR6 with ring 0/ID initialized. On returned step 1 normally; off-requested/powered-off/stuck-on each stopped first at step 0. Four conditions in `gpu-power-off-native-ring-02/report.json` passed.

Native total is 19 conditions (15 existing + four added); five main cases and runtime source were unchanged. Final aggregate is `gpu-power-off-verification-01/final-verification-02.json`. First verification file is preserved with verifier hash and 15 conditions from that time; strengthened file updates it.
