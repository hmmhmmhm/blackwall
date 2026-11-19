# IOM4 Nonblocking Initialization Path

This is a static investigation from bw-0118. Original main is stopped at the IOM4 power request; this document itself is not evidence of IOM4 execution, CQ behavior, or physical-device behavior.

Pinned stock 2.4 main SHA and DFP SVD/header were checked and decoded with `analyze_iom4_path.py`. SVD IOM4 inherits the IOM0 layout, with base 0x40054000 and IRQ 10; its power mask is header PWRENIOM4=0x20. Existing IOM2 polling model addresses/state can be reused as a separate instance, but this does not mean the NB path is supported.

The existing SRAM snapshot showed IOM4 configuration intent as I2C 1 MHz, NB pointer 0x203366e0, length 0x800. The actual configure callee confirmed pointer+length<<2 and (length-8)<<2. Thus **length is used in four-byte units in this address/capacity arithmetic**. 0x800 is 8192 bytes and the calculated end address is 0x203386e0. Actual allocation, buffer lifetime, and DMA accessibility remain unconfirmed. The earlier `call-path-report-v2.json` units-unverified record remains historical. Public HAL and actual G2 config ABI differ, so structures are not substituted.

In the confirmed NB enable branch, if the state's NB pointer is nonzero, PC 0x581848 writes literal 0x800040 to CQSETCLEAR (offset 0x238). In the SVD this sets SWFLAG6 and clears 7; it is not CQ enable itself. Code then calls CQInit-family helper 0x581598 and requests DMATRIGEN=2. Public HAL NB enable performs similar kinds of work, but whole-function identity is not claimed. Nor is this called the first CQ access across all other global paths.

Existing engine DMA/CQ are unexecuted placeholders. Next, optionally connect IOM4 power/MMIO and observe the first unsupported request in actual original main. Continue blocking nonzero CQ/DMA. Merely storing request numbers or returning ready does not substitute for functional implementation.

Evidence: `private:simulator/iom4-path-research-02/report.json`. The 01 key first_cq_request was clarified as predicted_nb_enable_cq_request in 02. Independent reading review in the same GPT-6 family found no additional significant issue. Other families and archived transcript comparison were not performed. Original ARM, physical-device, and full boot/display verification scope remains at the existing baseline.
