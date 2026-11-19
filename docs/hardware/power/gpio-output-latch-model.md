# Limited GPIO Output Latch Model

Status: pinned source, layout, and output-enable condition analysis complete. The behavioral model is verified separately. Full boot, display, actual pin voltages, and connected-device behavior remain incomplete or unverified.

Public Apollo510 GPIO header and metadata describe WT value read/write, WTS one-bit set, and WTC one-bit clear. Zero bits in alias writes preserve existing values. The condition that GPIO output is enabled is not omitted. Status reads use WT; WTS/WTC reads are blocked. Twenty-one addresses were compiled against GPIO_Type. They are not confused with identically named FPIO registers.

`tools/analyze_gpio_output_sources.py` checks pinned header/metadata hashes, 21 offsets, zero in 32-bit field diagrams, and per-pin FNCSEL/OUTCFG enums. Initial analysis missed whole-word diagrams due to a colspan 1 filter and was corrected after confirming actual colspan 32. The subsequent assumption that all 224 pins are GPIO3 failed at pin 135. Examination of all enums found 190 GPIO3 pins and 34 with all FNCSEL reserved. The list is recorded in source results, not interpreted as the number of GPIO pins exposed on actual G2. Failure/correction is preserved in private `gpio-output-research-01/parser-correction.json`.

## Model contract

`--gpio-output-latch` is explicitly selected with GPIO config storage. It uses zero from the public diagram as an initial latch hypothesis, not a value read from a real device. Seven 32-bit words are modeled; input RD, external signals, voltage, load, open-drain, tristate, and EN/ENS/ENC are unsupported.

For each set mask bit in WTS/WTC, the model checks guest-configured GPIO function 3, push-pull OUTCFG 1, and FIEN/FOEN forced enables disabled. Reserved-only pins, unwritten pins, and other mux/output modes first-stop. Direct WT writes are allowed only when all 32 pins in that word meet conditions. Alias mask 0 changes no bits. WT read is the virtual latch word, not actual pad observation. PADKEY lock protects PINCFG and is not reused as permission for this output operation.

Three original inputs stopped attempting WTC0=0x80 after pin7 config=0x183. Candidate instructions and main hashes are preserved in `gpio-output-research-01/main-input-and-write-candidates.json`. The model does not promise physical value retention after subsequent output configuration changes and blocks states outside scope.

## Record correction and virtual tests

The static candidate inspector accepted only store mnemonic `str` and rejected actual `str.w`. A record error in which a later shell finish command continued after that failure was corrected with an append-only note. After confirming the wide store at the exact observed PC, the candidate file was generated and `candidate-correction.json` preserved. Subsequent verification batches stop on failure and check evidence files and passing values before finish. Evidence is not backdated to the original completion time.

Twenty native conditions and one separate mux-strengthening condition passed. Checks cover preservation of other bits in normal set/clear, repeats, zero masks, full-word direct writes, last pin 223, and blocking unknown pins, unsuitable mode, other mux, reserved-only pins, forced enables, mixed masks, partial widths, alias reads, input reads, and unselected option. Two existing config/IRQ behavior conditions are included. The diagnostic policy atomically changes no output word if any bit in a mixed mask is unsuitable; it is not claimed as actual silicon error response. Original native 20 preserves source snapshot; mux strengthening is separately recorded using the same runtime source.

## Main runs and read-only diagnostics

Stock 2.3/2.4 and CFW executed 11 clears and three sets. Latch words are `[0x600,0,0,0,0x40,0,0]`; direct WT writes/reads are 0. Execution then blocked on 0x42003300 DWORD read. Stock 2.4 without the option blocked at prior WTC0=0x80 write.

All three stopped at PC 0x48. Without asserting cause, a read-only 256-byte virtual ITCM diagnostic `--capture-itcm-prefix` was added and stock 2.4 run separately. Code/model were unchanged and the same guard/output result reproduced. Changed prefix range 40..57 is 24 bytes, matching guest-written tracking 24 and execute-unwritten violations 0. At PC 48 is a loop reading a word from r0, writing it to r1, and decrementing r2. The original address of that read is 42003300. There was no result matching the entire first 24 bytes to a contiguous main array, and the copy loop caller's purpose is unknown.

First four runs preceded the diagnostic option; one separate run followed it. All C# model snapshots match and host snapshot reads do not change guest state. Source, native 21 conditions, main 4 and diagnostic 1 results are in private `gpio-output-verification-01/final-verification.json` and `itcm-diagnostic.json`. Full boot, subsequent GPU submission, integrated display, and real-device verification remain incomplete. Next identify the 42003300 information region and ITCM copy call purpose from source and images.

Independent review identified terminology incorrectly calling FIEN/FOEN fast-I/O. Public header describes forced input/output enable. The 0x0c000000 mask restriction remains a conservative unsupported condition. The fast-io name in existing native reports means FIEN=1; those originals remain preserved. Corrected name is force-input, and FOEN=1 force-output is separately verified. Actual FPIO path is outside this model and is not confused with these bits' meanings.

Two FIEN/FOEN strengthening conditions passed on the same runtime. There are 22 unique conditions and 23 executions total; one FIEN condition was rerun after renaming. Final tally is `final-verification-02.json`; previous verification files/reports were not overwritten.
