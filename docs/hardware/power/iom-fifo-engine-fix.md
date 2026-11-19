# IOM FIFO Transfer Ordering Fix

bw-0116 fixes transmission of zeros in the latter part of an eight-byte partial TX reproduced in bw-0115. This is a virtual peripheral-engine defect, not firmware. Original guest code and branches were not changed.

`iom_engine_source.py` verifies Apollo4 IOM source SHA `164bf8a85ca189d2a64a71723564f0e5ab122be995a6924819e9ee1d9fb0bfad` from Renode infrastructure commit `066a7f13c052215632d469c995c89aea37c573b1`. FIFO Push memory storage is moved before the Count-increment callback. Type name and using locations change for combined C# compilation; remaining engine code is retained. Generation stops if input changes. Original MIT copyright/license header is preserved. The whole project is not copied and firmware functions are not replaced.

The executing engine is now `BlackwallPollingIomEngine` generated and compiled from pinned source, not the Apollo4 type itself in the installed runtime assembly. Full equivalence of both engines was not established. Apollo510 clock/FIFO/type differences and strict MMIO checks remain in the wrapper.

In 86 conditions in `private:simulator/iom-fifo-fixed-unit-01`, the previously failing input sent correct bytes. Tests cover partial words, FIFO boundaries, repeated wrap for TX lengths 1/3/4/5/31/32/33/65/257, and long RX 36. Empty TX, active CMD overlap, and busy power-off blocks remain. The temporary TX length limit was removed. Eighteen shared-power/guard boundary conditions in `iom-fifo-fixed-shared-01` also passed.

`iom-fifo-fixed-verification-01` preserves generated source/hash, diff, current source copy, and independent review. Rejection of tampered upstream was confirmed. Actual main was not rerun at this stage. Original main will be reverified after combining with subsequent MI2CRST interpretation correction to avoid duplicate runs. Physical bus timing, full boot, display, and installability remain incomplete; product progress is 13/29.

## MI2CRST interpretation correction

Subsequent investigation found the same pinned Apollo510 header and SVD describe MI2CRST as “Not used. To reset the module, toggle the SMOD_EN for the module”. Public HAL also includes this bit as 1 in I2C configuration values. The earlier bw-0115 document's interpretation as an “actual software reset request” was inaccurate. That stop resulted from the model rejecting bit 6. The inactive meaning of this bit and actual SMOD_EN reset behavior are distinguished in subsequent bw-0117.
