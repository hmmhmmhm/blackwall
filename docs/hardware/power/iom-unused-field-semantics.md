# IOM2 Configuration Field Semantics and Execution Path

bw-0117 corrects MI2CRST interpretation and identifies the next original-main initialization path. bw-0115's earlier description as an actual software reset request was inaccurate; historical logs remain preserved.

## Evidence and model distinction

The same pinned Apollo510 SVD and C header describe bit 6 MI2CRST:

> Not used. To reset the module, toggle the SMOD_EN for the module

Public HAL writes this bit as 1 for all three 100k/400k/1MHz configurations. Rechecked pinned SVD/header/HAL SHA results are preserved in `private:simulator/iom-unused-field-research-01/report.json`. The problem was interpreting the field name alone as an actual reset, not forcibly bypassing an instruction.

The current wrapper stores defined MI2CCFG fields explicitly. It forwards only address-width bit 0 to the functional engine. Bit 6 is stored but causes no reset. Timing, sample count, delay, and unused-bit stored readback are virtual-model assumptions, not physical readback/timing verification. I2CLSB is rejected. ARBEN may be stored only; transfers with it enabled are rejected.

During an active transfer, MI2CCFG changes other than unused bits and SMOD_EN changes are blocked. Actual submodule reset, multi-master arbitration, and physical clock are unimplemented. Address width is rechecked at CMD; DEVADDR changes during an active transfer allow only the same address. Because the existing engine looks up current address for each chunk, this prevents remaining data from going to another peer.

## Findings and corrections

- First unit test failed due to an unsupported assumption that unused-bit readback is 0. That assumption was removed; no-effect reset and preservation of in-progress commands were tested. No physical value is claimed.
- First original stock24 run passed IOM2 configuration/off and reached IOM4 power request, but host failed it due to an unhandled SMPCNT tag warning from the existing engine. Warning filtering was not relaxed. It was rerun after modeling timing fields in explicit wrapper storage.
- Independent review identified stale ten-bit addresses after narrowing address width and address changes during active transfer. Command-time range checks and blocking active address changes were added.
- Unit04's 98 conditions include range failure/normal transfer with a registered ten-bit peer, remaining RX bytes after address-change rejection, streaming TX boundary of FIFO changes, unsupported behavior, and power blocking.
- Shared02's 18 conditions test the shared bank and actual mapped guard boundaries.
- First main comparison01 uses source before address-boundary strengthening. Comparison02 was run separately afterward and not mixed as results from the same source. Rerun reason was boundary-code change.

## Original main results and remaining work

In comparison01 before address strengthening, all three original images stopped strictly at next DEVPWREN=0x20 (IOM4 request) after IOM2 configuration 6 writes/20 reads and power-off. Final MI2CCFG is 0x3f270. PC was 0x494d78 for stock 2.4 and 0x488e90 for stock 2.3/Faceclaw38. Final-source comparison02 reproduced the same result. Unhandled engine warnings: 0.

`private:simulator/iom-unused-field-verification-01/report.json` preserves comparisons of raw native logs/reports, 17 current sources and C#/host source at execution, original main hash/vector, stock 2.3↔CFW scripts, and 36 register masks. Existing unchanged UART core 117/shared 28 regression evidence was reused after confirming source identity. This is not generalized to separate real-device or full-boot verification. Independent same-GPT-6-family review found no additional significant issues. Other model families and archived transcript comparison were not performed.

Commands are 0 and actual main has no peer. This is not I²C sensor discovery or successful bus transfer. Under stuck-off, a FIFOTHR write was attempted despite status 0 and blocked; this is not safe-fallback evidence. Full boot, integrated display, and real-device installation remain incomplete; product progress remains 13/29.

Next investigate actual configuration, DMA/CQ use, and peer contracts for IOM4 and subsequent IOM5/7. Existing engine DMA/CQ tags are not treated as actual transfer implementations.
