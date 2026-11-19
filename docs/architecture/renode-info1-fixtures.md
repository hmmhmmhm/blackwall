# Renode Info1 Provenance and Invalid Metadata Tests

Status: Actual main instructions from two stock versions and Faceclaw were executed to compare Info1 provenance branches. Actual device calibration values and OTP contents are not provided. Full boot remains incomplete.

## Explicit inputs and evidence

In pinned Apollo510 CMSIS definitions, MCUCTRL SHADOWVALID (0x400201bc) bit 0 is VALID and bit 3 is INFO1SELOTP. Bit 6 OTPREADY is separate. `--shadow-info1 mram|otp` supplies virtual conditions reading 1 or 9 respectively. VALID=1 and all other bits=0 are input assumptions, not observed device state. Selecting OTP does not fabricate OTPREADY or actual OTP contents. This option requires explicit `--startup-controls`.

`--info1-metadata-fixture zero|erased` is allowed only when MRAM provenance is explicit. It does not fill all Info1 memory; it handles only aligned four-byte reads at the three addresses below. All three words are 0 or 0xffffffff, and valid calibration is always false.

| Address | Information |
| --- | --- |
| 0x42003240 | PATCH_TRACKER0 |
| 0x42003310 | TRIM_REV |
| 0x42003314 | FT1_GDR1 |

Address definitions and existing binary-analysis evidence follow the Info1 section of the [runner analysis record](simulator-runner-status.md). Pinned material is hal_ambiq commit `61b293a49db34030c545f99101f7ebf6a3050314`. This fixture is for research into initial error-input paths; it does not claim erased values are always rejected by firmware as invalid. Successful reads and validity of calibration data are separate. Writes to SHADOWVALID or information regions, partial-width accesses, and other information addresses stop at the strict guard.

## Verification

Two tests expecting successful reads first failed on the existing model (`renode-info1-red-01/`). After adding the model, source and metadata type, actual readback, per-word read counts, valid_calibration=false, and subsequent guest writes were checked. Forty-eight checks in `renode-info1-verification-01/report.json` passed: 31 existing strict/initial-control checks and 17 new Info1 checks.

Actual main was tested with four inputs per image under LP, reset shadow=2, watchdog, reset-controller, and startup-control conditions. The next unimplemented boundaries across 12 runs were:

| Condition | Next access | Stock 2.3 / Faceclaw PC | Stock 2.4 PC |
| --- | --- | --- | --- |
| MRAM, metadata not supplied | 0x42003310 read, 4 bytes | 0x48 | 0x48 |
| OTP, contents not supplied | 0x40021004 write 0x08000000, 4 bytes | 0x488e90 | 0x494d78 |
| MRAM, zero metadata | 0x4002000c read, 4 bytes | 0x489c4c | 0x495b34 |
| MRAM, erased metadata | 0x4002000c read, 4 bytes | 0x489c4c | 0x495b34 |

MRAM PC=0x48 is the location of code copied by the guest to ITCM. OTP-path power-on was unsupported and stopped; it is not an OTP read success. The next boundary under invalid metadata is CHIPREV, and no actual chip revision was assumed.

Unicorn runs with the same inputs matched all 12 in raw main hash, stop address, width, PC, source-state read count, and read count for each supplied metadata word. This compares code paths under shared assumptions, not actual hardware or timing. All runs have boot_verified, hardware_validated, and installable false. Results are outside Git in `Blackwall/simulator/renode-info1-*-*-01/` and `unicorn-renode-info1-comparison-01/`.

```sh
python3 tools/verify_renode_mmio_guard.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-info1-tests" \
  --with-startup-fixtures --with-startup-controls --with-info1-fixtures
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-invalid-info1" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller \
  --startup-controls --shadow-info1 mram --info1-metadata-fixture zero \
  --wall-run-seconds 5
```

The scope of subsequent implementation and verification of main memory protection and ITCM execution restrictions follows the [memory policy](renode-memory-policy.md). No physical-device operation, firmware installation, or GitHub publication was performed.
