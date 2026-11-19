# Original EN4B and Configuration Register Contract

Task bw-0181. Analyzed the next B7 request from bw180 using manufacturer documentation and original ARM code. No new main execution or model changes were made.

Macronix MX25U25643G v1.1 pages 21, 33, and 43 describe EN4B=B7, RDCR=15, and Configuration Register bit 5=4BYTE. After B7 completes, the address length becomes 32 bits; reset, power-off, or EX4B returns it to 24 bits. The EN4B procedure on page 43 does not specify a WREN/WEL prerequisite. Do not use it as grounds for adding one. Undocumented behavior of the physical chip was not verified.

## Distinguishing reset states

In the Configuration Register on page 37, only TB (bit 3) is nonvolatile OTP; ODS, PBE, 4BYTE, and DC are volatile. Do not confuse these with QE, BP, and other Status Register fields. Text and the rendered image of page 38 tables 9 and 10 were compared to confirm ODS000=30Ω default and DC00 default. Volatile bits of an arbitrary configuration byte must not simply be preserved across reset.

The subsequent model was planned to accept only explicit reset fixtures 0 or 8 (TB OTP 1), without guessing the entire configuration. Because WRSR changes to other volatile settings were not yet supported, it would cover only the bit 5 transition caused by B7 and restoration of reset defaults. The TB fixture is not a physical observation either.

## Confirmed original path

The actual request in the three original images is CFG03010061, CTRL C1, instruction B7, data 0 TX. After successful transmission the caller invokes the existing WIP polling and calls a verification function through a function pointer. If that function returns nonzero, execution advances to the next path.

A function in the originals issuing RDCR15 and RX1 and checking bit 5 was also identified. Its entry is 47B83E in stock 2.4 and 476B26 in stock 2.3/Faceclaw. Following successful transfer, it reads the actual byte and uses `LSLS #26` followed by a sign branch to return 1 when bit 5 is 1. **Native execution had not yet confirmed whether this function was the actual target of that function pointer.** Subsequent execution would connect this entry, byte, return value, and caller as read-only observation points.

The report produced by `tools/inspect_mspi1_address_mode.py` at `simulator/mspi1-address-mode-contract-02/report.json` outside Git checked 24 items covering source pins, manufacturer descriptions, requests and descriptors in all three originals, the caller, and the candidate helper. The rendered page 38 is `datasheet-page-38.png` in the same directory. The first 01 inspection stopped because handwritten relative offsets 112/116 did not match actual Thumb instruction boundaries. Expectations were corrected to 114 LDR, 116 LDR, and 118 BLX after decoding from the function entry; the incorrect addresses were not used for execution observation.

This research supports the bit contract and a static candidate. It did not yet prove address switching, RDCR reception, the actual callback target, memory address handling, full boot, display, or physical-device validation. Overall completion remained 13/29 (44.8%). No glasses access, installation, RAM execution, or persistent write occurred.

A read review by an agent inheriting the parent model reported no additional material errors. Subsequent bw182 results confirming the actual callback target, byte, and decision are recorded in [address-mode model execution](mspi1-address-mode-model.md). The unverified status above describes the scope at the time of the bw181 static analysis. Astra, another model-family review, and a complete transcript-file audit were not used.
