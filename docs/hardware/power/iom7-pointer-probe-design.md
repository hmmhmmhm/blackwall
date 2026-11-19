# IOM7 Address-Pointer Experiment

bw-0134. This is a diagnostic experiment within the previously authorized peripheral implementation stage, not a product architecture expansion or authorization for physical writes. No physical device or Astra is used.

Alternatives are retaining static analysis only, connecting a full PMIC model, or an experiment accepting only an explicit address pointer. The third is selected because actual PMIC state and part remain unknown. A full model and generic ACK/0 responses could obscure information and select original branches inaccurately. Static analysis and original decoding continue.

The virtual I2C peer is explicitly connected only at IOM7 address 6b. It accepts only the observed two bytes 05 09 as address-pointer setup. This is an experimental condition, not implementation of nPM silicon behavior. Other bytes, lengths, and writes, and all reads stop with CpuAbortException; no read value is generated. FinishTransmission preserves the pointer and records a separate completion count. Reset clears pointer and counts. Rejected requests do not change pointer state beyond diagnostics. Only one two-byte pointer request is handled at a time; resetting the same pointer after Finish is allowed.

Independent direct-call tests check correct pointer/finish/reset and rejection of other addresses, widths, fragments, and reads. Then pinned existing main/model files are copied and only peer, explicit board connection, and diagnostic output added to sequentially run stock 2.4/2.3/Faceclaw. Original main/fill/policy remain unchanged. The experiment does not read new values or replace main functions with bridges. Base and derived file hashes are preserved. The default runner does not automatically install this peer.

Success means accepting the original pointer write and observing its next actual requirement. If read is not reached, report the first strict boundary unchanged. Full boot, display, physical ACK, and actual part identification are not completion conditions.
