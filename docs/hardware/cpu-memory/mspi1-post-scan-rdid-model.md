# MSPI1 Post-Scan RDID Model and Original Execution

Task bw-0176. Added turnaround-0 RDID only under the explicit `ideal-sdr` profile. Original stock 2.4, 2.3, and Faceclaw main completed the post-scan ID read and original classification, then stopped at the next status-read request. Full boot and integrated display remained incomplete; product progress remained 13/29, 44.8%.

## Scope of changes

`renode-mspi1-pio.cs` allows ideal SDR RDID only when DEV0CFG with RXCAP, RXNEG, and TXNEG removed equals the existing 02010861 or the new 02010061. The difference is turnaround 8 versus 0. The existing allowed configuration for `fixed-capture` was unchanged.

Command 9F, CTRL30441, explicit MX25U25643G identity, and power, clock, idle, and empty-FIFO conditions remain unchanged. Other turnaround values, commands, lengths, and configurations still stop at strict guards. No actual flash backing or write commands were added. This is a signal-error-free digital model of idle SPI NOR, not verification of the installed chip, waveforms, or physical timing.

## Tests and execution

First ran `verify_mspi1_zero_turnaround.py` against the previous model. `mspi1-zero-unit-01/renode.log` rejected the initial zero-turnaround CTRL write during setup as unsupported and contains no success marker. The subsequent production change consisted of only two lines in the allowed-CFG decision.

| Verification | Simulator path outside Git | Result |
| --- | --- | --- |
| New RX, eight sampling combinations, FIFO, clock abort, reset | mspi1-zero-unit-02 | 36 checks |
| Reject new request under default profile | mspi1-zero-fixed-01 | 4 checks |
| Prevent response generation without identity | mspi1-zero-none-01 | 4 checks |
| Reuse existing ideal/fixed sampling and RDID fixtures | mspi1-zero-regressions-01 | 51 + 33 + 30 checks |
| Three original mains and fixed control | mspi1-zero-main-01 | 4 combinations |
| Raw evidence, source, inputs, and run comparison | mspi1-zero-verification-01 | 119 checks |

Used the existing `probe_mspi1_sampling_main.py` runner unchanged. Original main was not modified and branches, returns, and delays were not forced. Runs start from main reset under the previously specified virtual memory, power, clock, and other assumptions. This does not establish a complete ROM boot or successful physical hardware checks.

Each of the three ideal runs completed 1,155 transfers including two resets, with 1,153 RDID/FIFO operations: 36×32=1,152 scan operations plus one additional ID read on the normal path. The 36-word scan matrix and selection 010000010e20 matched the previous run, and the original scan return R0=0 was preserved. Subsequent selected events were, in order:

1. Original scan return, R0=0.
2. Original FIFO helper return for the additional RDID, R0=0.
3. Original classifier input, R0=C22539.
4. Original classifier return, R0=0.

There were 3,790 selected observation events per image with zero drops. These are registered observation points, not a complete trace of all ARM instructions. The default fixed run stopped at the RXCAP change boundary after 288 RDID operations, as before.

## Next boundary

The subsequent request in all three originals was INSTR05, CTRL10441, RX1 byte, with DEV0CFG03010061. The length, instruction, and no-address condition in the actual stack descriptor were compared with saved logs. No status byte was returned yet. The next step was to analyze the manufacturer status register and original polling path to define required idle state, busy transitions, and unsupported-bit contracts. Returning zero for every status simply to make boot succeed is not acceptable.

Audit tool `verify_mspi1_zero_evidence.py` compared the two-line difference from the previous model, identical red/green fixtures, current model and original main hashes, actual logs and reports, read-only runtime, raw matrix snapshot, original post-scan event order, and next request. Stock 2.3 and Faceclaw use the same model, board, and runtime apart from original image length.

No glasses connection, scan, installation, RAM execution, or persistent write occurred. Astra, another model-family review, and a complete transcript-file audit were not used.

An agent inheriting the parent model performed a read review of production, tests, and the 119-check audit and reported no additional material defects. Physical validation and saved original-execution evidence remain limited as described above.
