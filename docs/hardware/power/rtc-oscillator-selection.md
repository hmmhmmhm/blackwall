# RTC Oscillator Selection Storage Model

bw-0124. Extends the next strict boundary of the authorized stock-based simulator. Existing original ARM instructions and branches remain unchanged; there is no hardware access.

Pinned Apollo510 SVD CLKGEN.OCTRL is base 0x40004000+0xc, OSEL bit 7, reset 0/mask 0x80. Zero requests XT 512 Hz; one requests LFRC/2. The SVD says selection and XT use are inoperable on A/B0 silicon. Pinned HAL's control function writes the bit but status_get returns LFRC as a constant. Thus status_get is not used as actual oscillator confirmation. Exact correspondence between model chip revision 0x23 and that silicon designation, and actual device oscillator state, are unknown.

Alternatives are a full oscillator/RTC model, unconditional reset-value return, and explicit configuration storage. A full model lacks clock/power/revision information; unconditional 0 hides initial state. This work uses `--rtc-osel-storage xt|lfrc` to specify the initial bit. xt is the source-reset value, not necessarily actual state at main entry. Default remains unsupported strict.

It stores 32-bit OCTRL reads and writes containing only bit 7. Reserved bits, adjacent addresses, and other access widths are blocked. Reports record initial/current requests and read/write counts, leaving effective source unknown. This is an assumed request latch, not physical proof even of A/B0 readback. Actual clock, frequency, time, oscillator ready, and revision behavior are unimplemented.

Verification covers read/write/reset and blocking atomicity for both initial values, default strict, and three original runs with the same model. No success state or function bypass is added to pass the new stop.

## bw124 integrated verification results

Work resumed after direction review and common replay/patch observation. Existing unit 38 strict.cs was confirmed byte-identical to current core, so standalone tests were not repeated. Five original runs in `private:simulator/rtc-osel-main-comparison-01/report.json` passed.

| Run | Initial request | OCTRL reads/writes | Final request | Strict stop PC |
| --- | --- | --- | --- | --- |
| Stock 2.4, xt assumption | 0 | 2/2 | 0 | 0x507004 |
| Stock 2.3, xt assumption | 0 | 2/2 | 0 | 0x4e8778 |
| Faceclaw38, xt assumption | 0 | 2/2 | 0 | 0x4e8778 |
| Stock 2.4, lfrc assumption | 128 | 2/2 | 0 | 0x507004 |
| Stock 2.4, model unused | Unsupported | Unsupported | Unsupported | Existing 0x506c20 |

The first four stop on RTC.RTCCTL (0x40004800) read. The register was confirmed in pinned SVD and original disassembly/r0 snapshot compared. The next original instructions clear RSTOP bit 4 and store it, but BIC/STR did not execute because the current read did not return. Guard value 0 is not a read result. RTC time, oscillation, and silicon effects remain unknown. This is not a test recording the complete order of both writes.

Without the model, the existing bw122 strict endpoint and selected counter remain. Stock 2.3/CFW board/model/result/probe match; run.py differs only in main length. Actual main UART TX/ISR and I2C commands/CQ pairs are all 0; full boot/display and device verification remain incomplete.

Independent review found startup-fixture connection was missing when only the RTC option was specified. RTC option was added to fixture selection and bare guard reports protected with hasattr. `rtc-osel-runner-regression-01` passed three native regression runs: bare, RTC-only, and full-xt. Bare/RTC-only stopped at earlier 0x495e9c with zero RTC accesses; full-xt retained OCTRL 2/2 and the new endpoint above. Five original runs before correction and three regressions after correction are preserved as separate runner snapshots. Generated run.py/result.py now receive host syntax compilation before native startup.

Final `private:simulator/rtc-osel-final-verification-01/report.json` compares original hashes, actual logs, reports, core source, and unit 38 reuse for eight runs. `next-boundary.json` preserves the unreturned RTCCTL read; `runner-fix.diff` preserves limited changes between two runner snapshots. Same GPT-6-family read-only independent review found no additional significant issue after the boundary fix. Astra was not used and no separate transcript archive comparison occurred. Product conditions remain 13/29.

Next investigate RTC clock/control/counter contracts and reusable models instead of filling RTCCTL with a success value. Separate execution and time-progression evidence is required before claiming counter or time implementation.
