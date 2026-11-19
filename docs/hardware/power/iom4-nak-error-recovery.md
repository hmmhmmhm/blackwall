# IOM4 NAK Error and Original Recovery Transactions

bw-0360. The goal is to determine the relationship between actual IOM error → original HAL → upper initializer/app producer. WHOAMI mismatch means a device responded normally with a different value; NAK is a bus error. Existing missing-peer strict rejection/IllegalCommand does not substitute for NAK.

## Pinned contract

Full NAK cleanup in the original polling HAL and caller error-branch checks were added to existing `inspect_iom4_command.py --nak-cleanup`. Original main/SRAM/GPR provenance is verified by existing saved audits. There are 12 combinations per image of initial debug 0/4, FIFOCTRL 2/3, and previous interrupt enable 0/10/20: 36 total.

When original HAL reads NAK bit 4 it returns status `08000002`. It saves/blocks IRQ enable, lowers I2C enable, and resets FIFO. It temporarily enables then restores `IOMDBG.IOCLKON`, re-enables FIFO/I2C, clears IRQ, and restores previous enable. Final clear/enable restoration in the original polling function also executes separately. The caller of failed register-select branches to an error-release helper instead of data read.

IOMDBG offset 388/IOCLKON bit 1 in pinned Apollo510 SVD forces IO clock on, not a device reset or arbitrary success flag. FIFOCTRL.FIFORSTN bit 1 is active-low FIFO reset. Actual cleanup order was confirmed with original ARM. Only the delay function in isolated M7 testing is replaced by an ABI leaf; argument `6 × original handle configuration value` is checked. This is not relabeled as physical timing or natural M55 execution evidence.

## Optional error model

Default `BlackwallStrictIom` is unchanged. Only IOM4 can select these profiles:

- `i2cNakCommand`: deliver address-phase NAK once at a specified CMD ordinal. Default −1 disables it. Requires a positive ordinal and IOM4 recovery profile.
- `i2cRecoveryClock`: default false. Supports only IOMDBG IOCLKON storage needed by actual cleanup. Allows 0/2 with I2C/SPI disabled, FIFO reset, and command idle. Other debug functions are not considered implemented.

NAK is delivered after CMD validity/registered-peer checks. Peer Write/Read/FinishTransmission are not called and queued FIFO words remain; original code must reset FIFO to clean them. Only NAK interrupt bit rises, with no successful command-complete. Existing engine handles IRQ enable/clear. Subsequent normal transactions use the existing backend unchanged. This is declared untimed address-phase error injection, not actual bus waveform/NAK timing certification. Partial-payload ACK or mid-byte NAK is unsupported.

CMD1504 is the first GAF request 2 transaction in the current pinned profile, not a fixed position in all new CFW. If a candidate changes transaction order, it must be rebound to the original profile; a fault at another position is not judged a firmware regression. Unsupported peers remain strictly rejected.

## Natural runs and limits

NAK was injected only at CMD1504 in stock 2.4/2.3/Faceclaw38 main-reset runs. After not delivering the first GAF request 2 payload to the peer, original execution progressed to next IPREG select `7ca272`, the new strict boundary. Bias/GAF 225 bytes were stored earlier; IOM4 has CMD1505, FIFOCTRL2, I2C enable48, IRQ false. Final clock 0 alone is not claimed as evidence of all transient writes; specific order of complete original cleanup is distinguished from the isolated-function contract above.

EDMP GAF calculation/ready was not automatically implemented. Attempting subsequent transactions after a lower error does not mean normal GAF completed. Initializer/wrapper returns and app events were not reached, so E05/E12 remain incomplete and overall is 4/16=25%. Do not expand identity/initial-ready/NAK-position variants after this to manufacture upper-level success. Unsupported behavior needed for the current question was identified as subsequent IPREG/calculation contract after GAF service; next independent work is a legitimate device/transport app-producer contract.

## Reproduction and verification

Original images remain outside Git. Isolated function checks:

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/inspect_iom4_command.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-output-directory> --nak-cleanup
```

Direct MMIO model checks use `python3 tools/verify_iom_adapter.py <new-private-output-directory> --nak-profile`. They check first normal transfer → specified NAK → peer no-side-effect/remaining FIFO/IRQ → FIFO reset/clock restoration → next normal transfer and invalid clock-write rejection. Default regression omits the option in the same tool.

Natural execution passes private `simulator/iom4-gaf-request-nak-plan-03.json` to existing `run_native_candidate.py`, specifying selected case and new output path. Control uses `--control` and adds no error option to the board. Saved captures are rechecked with the same plan and `--audit-existing --audit-output <new-private-audit-directory>`. Only one IOM component changes; original main, other peripherals, and initial memory remain unchanged.

The first observer test failed caller-branch checks because a previous stop hook remained in the same Unicorn instance. Returned state was cloned into a new machine to isolate it from the old hook. The next failure was a fixture rejecting restoration of nonzero interrupt enable; explicit fixture support was corrected. Both copies remain in private research folders and are not reported as original-code errors. A red test without the new model failed from missing constructor profile before implementation. plan01 was rejected before execution for missing control semantic checks, fixed in plan02.

Final evidence of verification and remaining image/default controls is recorded in private `simulator/iom4-nak-cleanup-research-01/manifest.json`. No physical access, permanent writes, or CFW feature implementation occurred.

Additional observation failure: the first control's new post-stop diagnostic called `ReadDoubleWord(388)`, increasing IOM reads by 1. CPU/existing events matched but exact check failed; capture was preserved. The final model diagnoses with read-only `RecoveryClockValue`, without MMIO side effects. The three fault-capture models differ from final model only in this one property line. plan02 is preserved for auditing historical fault captures; plan03 is the final diagnostic path. Historical captures are not retroactively modified.

Final verification: three natural original fault captures passed; default control02 CPU/all events/full SRAM exact; four saved audits passed. Final model direct 17, default regression 82, and runner 13 passed. Thirty-six isolated original cases and frozen report are byte-identical; the existing 804-case report is also byte-identical to its prior baseline. The only final-model addition after the three fault captures is one read-only property without MMIO side effects; final model was used in control02 and 17 direct checks. This is not reported as three fault reruns on the final model. Because the overall question of upper initialization return remains unanswered, bw360 ends deferred with partial results.
