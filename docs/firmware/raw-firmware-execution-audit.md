# Audit of Original Firmware Execution and Comparison Conditions

> bw-0117 interpretation correction: MI2CRST bit 6 is explicitly “Not used” in pinned Apollo510 header/SVD. The historical software-reset-request interpretation below was inaccurate; the stop at the time was the model rejecting bit 6. It is distinct from actual SMOD_EN reset.

In bw-0107, current source and frozen execution artifacts were compared for the user's three questions. Material: private raw-main-audit-02/report.json, runtime-script-comparison.json.

## Code actually executed

Renode Cortex-M55 directly executes main ARM/Thumb instructions. Main from type 0 of pinned OTA bundles, excluding the 32-byte component header, was compared byte-for-byte with each run folder's main.bin. Stock 2.4 (3700068 bytes), stock 2.3 (3758688 bytes), and Faceclaw38 (3829832 bytes) all matched. Faceclaw is an original artifact containing upstream CFW modifications and is not called stock. Load address is 438000; vector SP/reset are read from each image. Starting at main reset is not full-device boot through ROM, original bootloader, recovery bootloader, or other processors. Separately authored small synthetic M55 IRQ guest and independent renderer are distinguished from actual main results.

## Execution path and synthetic hardware

Review of current runner and combined memory/system-control/model sources found no code overwriting PC or return registers to force a successful branch. IRQ vector hooks also only count/query ICSR. CPU writes to main are blocked by an external virtual MMU; code outside main is allowed only in guest-written ITCM ranges. This audit reviewed loaded inputs and source; it did not obtain a full post-execution main RAM digest.

This cannot be claimed as the same natural path as actual hardware. Assumptions include:

- INFO1 metadata zero selects original invalid-info fallback.
- Synthetic chip revision 0x23, power/reset state, GPU ID/status, and other responses are supplied.
- Power ready responds on first status read without reproducing physical stabilization delay.
- ADC channel 3 is constant 2048, not actual sensor, temperature, or calibration data.
- Cache is a coherent functional model, not actual cache timing or coherence defects.
- RAM uses a prior A5 pattern, not physical residual state or full secure boot.

Check instructions execute as original code, but returned virtual values determine success/failure/fallback branches. Thus the current result is “execution from original main reset through UART on a partial board model with explicit assumptions,” not proof of an identical stock-device boot path. Unsupported MMIO strictly stops.

## Stock and Faceclaw comparison

The baseline pair is stock 2.3.0.24 and Faceclaw38 based on it. Both runs have the same options, assumptions, and combined C# source. Frozen run.py differs only in mainLength 3758688→3829832. Interpreting all differences between stock 2.4 and CFW 2.3 as Faceclaw effects would mix vendor-version changes. Stock 2.4 execution also has an additional post-capture option.

The same-address prefix has 111 changed bytes and length increased 71144 bytes. These are static byte differences, not counts of features or executed patches. All three actual mains currently stop strictly at UART power-off request with TX 0/ISR exception entries 0. Same endpoint alone does not establish identical full instruction traces. Patch-point coverage and meaningful per-function traces have not yet been collected, so dynamic verification of Faceclaw functional differences remains incomplete. The comparison baseline is established; later difference analysis should use this pair under identical assumptions.

Independent source/artifact review was from the same GPT-6 family. No separate transcript archive was provided. Physical verification, full boot, integrated display, and installability assessment remain incomplete.

## After multi-UART connection — bw-0112

Frozen follow-up `private:simulator/multi-uart-verification-01/final-verification.json` was compared. Stock 2.3/2.4 and Faceclaw38 all pass 26 register writes and power-off responses for each UART1/2/3, then strictly stop at IOM2 power request (write 8 to DEVPWREN 0x40021004). The earlier UART power-off stop describes bw-0107 and is not the latest endpoint. Actual main UART TX and UART ISR exception entries remain 0. Full boot and integrated display remain incomplete. In-progress bw-0115 IOM2 implementation is not yet included in verified execution results.

The conclusions about original ARM main execution, no forced branches, virtual-hardware assumptions, and uncollected dynamic patch coverage remain. This check reused frozen evidence; no firmware rerun or physical-device test occurred.

## After IOM2 connection — bw-0115

The latest stop is MI2CCFG reset request after IOM2 power request. Under active conditions stock 2.4 at 0x582062 and stock 2.3/Faceclaw38 at 0x57ad0a requested `0x400522c0=0x3f270`. Original-requested MI2CRST behavior was unsupported, so execution strictly stopped. Transfer commands: 0. Under stuck-off, a FIFOTHR write was attempted despite power status 0 and blocked; this is not safe-fallback evidence.

UART IRQ-hook setup reused a loop variable, causing some historical report reset_vector values to show the final UART IRQ vector. Report variables were separated without changing execution setup, and original vectors and reports of final four mains directly compared. Detailed results and incompleteness are recorded in `iom-strict-integration.md`.

## After FIFO fix and field interpretation correction — bw-0116/0117

With latest source, three original mains completed IOM2 configuration 6 writes/20 reads and power-off, then stopped at next IOM4 power request (DEVPWREN=0x20). PC is 0x494d78 for stock 2.4 and 0x488e90 for stock 2.3/CFW38. Actual main I²C commands are 0; no synthetic peer was connected.

The IOM engine is a type compiled from pinned upstream source with corrected FIFO storage order, distinct from replacing original main functions. MI2CRST metadata says Not used, correcting the prior reset interpretation. Timing/config readback is explicit virtual storage, not physical verification. See `iom-unused-field-semantics.md` and `iom-fifo-engine-fix.md` for evidence and incompleteness.

## After IOM4 connection — bw-0119

Latest three original mains request CQSETCLEAR=0x800040 in IOM4 NB enable branch and strictly stop. PC is 0x581848 for stock 2.4 and 0x57a4f0 for stock 2.3/CFW38. Actual I2C commands are 0; CQ/DMA remain unimplemented. Stock24 handle module 4/mode 1/NBptr/length were compared in a bounded snapshot. IRQ10 pending is synthetic testing, not evidence of actual-main CPU ISR execution. Final source/log/hash comparison for three originals plus two independent power failures is recorded in `iom4-strict-integration.md`.

## After bounded CQ addition — bw-0121

Source-defined CQ was separately verified with synthetic SRAM pairs. Actual main CQ pairs are 0. Default unknown CQinputs strictly stop at IOM2 CQFLAGS save. Under explicit mock pin 0 profile, three originals complete IOM4 initialization/off and reach IOM5 power request 0x40. This pin value is a virtual assumption, not physical input confirmation. Details, controls, and incompleteness are in `iom-command-queue-engine.md`.

## After IOM startup instance expansion — bw-0122

With explicit CQ mock input 0, three originals passed IOM2/4/5/7 configuration/off and reached CLKGEN.OCTRL read. UART1 reactivation was observed, but TX/ISR are 0. Actual CQ pairs/I2C commands are also 0; this is not full boot. Default unknown blocking and four per-module power-failure conditions were separated. See `iom-startup-instance-set.md` for source/log/hash, initial handle 0, later allocation, and correction of historical auditor count assumptions.

## Rechecking user questions — bw-0123

Frozen latest three original runs were rechecked byte-for-byte against pinned bundle components for main.bin, confirming SHA256 and actual Renode log/report agreement. Original ARM/Thumb main executes without replacement by reimplemented functions. CPU/peripheral models and synthetic test guests are distinct from original main.

Stock 2.3 and Faceclaw38 board.repl/strict.cs are identical; run.py differs only in mainLength argument. Current runner/memory/system/reset source review found no forced PC/return changes or function bypasses. However, synthetic INFO1/ADC/power/CQ inputs determine original check branches, so an identical natural physical boot path is not established. Execution begins at main reset, not ROM/bootloader.

Dynamic patch coverage and per-function comparison traces remain absent. Same stop alone does not establish identical paths or Faceclaw feature behavior. UART initialization register writes were observed, but TX/ISR are 0 and full boot/integrated display remain incomplete. This check reused existing evidence, with no native rerun or device access. Evidence: `private:simulator/raw-execution-question-recheck-01/report.json`. Product progress remains 13/29.

## After RTC selection storage — bw-0124 resumed

With explicit xt/lfrc request latch, three originals strictly stopped at RTC.RTCCTL 40004800 read after two OCTRL reads/writes. PC is stock24 507004, stock23/CFW 4e8778. Without the model, the existing OCTRL stop remains. Actual oscillator/time/revision effects are unknown and subsequent RSTOP clear/store has not executed. UART TX/ISR/I2C/CQ are 0 and full boot/display remain incomplete. See `rtc-oscillator-selection.md` for separate snapshots/evidence of five originals and three regressions after runner-boundary correction.

## After virtual RTC adapter connection — bw-0130

Under explicit epoch2000/100Hz profile, three originals progressed after one RTCCTL read/store to MCUCTRL.CHIPPN 40020000 read. PC is stock24 495f64, stock23/CFW 48a07c. Counter commits 0; this is not evidence of original RTC counter/alarm execution. Unsupported counter writes reach the same endpoint; no RTC model retains existing RTCCTL stop. See `rtc-strict-adapter.md` for 44 independent virtual checks and separation of five originals/failed captures. Full boot/display and physical device remain incomplete; Astra unused.

## After partial chip information and SKU calculation — bw-0131

Under explicit PN/SKU reset, synthetic zero ID, and shared revision profile, three originals wrote confirmed fields and memory size of a partial 64-byte structure with ARM, then strictly stopped at JEDEC.PID 0xe00fefe0 read. PC is stock24 495fe2, stock23/CFW 48a0fa. This is not evidence of getter return, physical identity, or boot/display. Controls distinguishing Qualified constant 1 and unwritten FlashSize/JEDEC fields are in `chip-identity-contract.md`.
