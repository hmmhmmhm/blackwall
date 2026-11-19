# Application HCI wait and original TX path

bw-0283. Source and virtual execution verification performed without glasses or case access. Overall completion is 13/29=44.8%; this does not mean full boot, integrated display, or installation readiness.

## Original behavior confirmed

After the earlier OTA-marker-cleared scenario, the GPIO117 consumer calls the same original SPI/HCI read/write functions as initial RF readiness code. If GPIO word bit 21 is high it takes the RX path; if low, the TX ring path. This loop's source limit is 1000. This is not a measurement of actual pin waveform or IRQ behavior.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| New GPIO read PC | `4dd1d4` | `4c9990` |
| Original read function | `5018d6` | `54a22e` |
| Original write function | `5017be` | `54a116` |
| Next write-ready boundary in this run | `501676` | `549fce` |
| TX ring | `20076304` | `20076cbc` |
| Pending packet pointer | `20067764` | `20067774` |

The ring's six words are write offset 260, read offset 0, used 260, capacity 2080, record stride 260, and buffer pointer. In bw284, executing the original producer/consumer corrected the names of the first and fifth fields. Both currently equal 260, so bw283's value comparison passed but could not by itself distinguish field meaning. **Used 260 does not mean packet length or 260 commands.** The record length is 4 and actual pending bytes are `01 03 0c 00`, an HCI_Reset command. The next command must not be sent before Command Complete, and this is distinct from a controller hardware reset. [Bluetooth Core 6.1 §7.3.2](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html).

The natural-execution callback matches dispatcher index 7. Current R5 had changed to 0 inside the callback and could not serve as the index. The table at SP+12 and saved index at SP+16 of the original push frame reconstructed it and were compared to R2's callback address. This corrected the initial failed analysis based on current R5 without forcing CPU branches.

## Model change and boundary

Optional `applicationIdlePc` was added to `renode-em9305-reset.cs`; default 0 disables it. Idle-low is returned only in an explicit scenario satisfying all of:

- Exact original PC, address `40010410`, config `93`, and actual R0 address match.
- Reset released, not held, and version scenario present with two responses.
- Peer `Complete`, CS known/high, and existing peer ready level 0.

No active RX high, third command, new response, or automatic rearm was added. The original write-ready consumer after CS low remains a strict stop. Existing initialization peer's two commands, two replies, and five frames remain unchanged.

All three mains continued from original reset, passing a four-byte packet to the original write function after one new GPIO idle read. R8=4, R9=0, R10=actual packet pointer and SRAM bytes were confirmed, and the ring descriptor was unchanged. **The pending packet has not yet been transmitted.** This is evidence of natural main progress, distinct from fragment execution with an arbitrary entry, but uses the existing explicit virtual hardware state. Full IRQ lifecycle, BLE initialization, and normal boot remain incomplete.

## Verification material

Retained outside Git in `~/Library/Application Support/Blackwall/simulator/`:

- `application-hci-source-01`, `-02`: 27 original ARM conditions. Four GPIO words, ring empty/occupied, and poll counter 0/999/1000 were tested in three images. Fragment tests use synthetic function entry/registers and verified main SRAM.
- `application-hci-idle-unit-02`: 58 conditions, including rejection of initial/intermediate states, acceptance of completed idle, rejection of incorrect PC/address/config and CS low, default off, and constructor constraints. Five constructor conditions were added after existing 53; initial red was missing constructor support.
- `application-hci-idle-main-01/{stock24,stock23,cfw}` and `application-hci-idle-control-01/stock24`: all four native runs passed semantic contracts. Off control exactly matched previous observed CPU and selected events.
- `application-hci-idle-saved-audit-01`: independent audit of four saved runs.
- `application-hci-idle-contract-01`, `-02`: identical results comparing packet, actual write context, and ring against saved SRAM, without CPU rerun.
- `application-hci-idle-verification-01/manifest.json`: pins 27 Python dependencies, four models, and input/capture/audit/unit/source SHAs. Existing IOM/keyDB/marker and web installation gate were unchanged.

The first verification-manifest attempt failed by reading the `__pycache__` directory as a file. Selection was fixed to `.py` files only; saved audits and native runs were not restarted.

## Next work

Analyze actual pending command write-ready/CS/SPI framing and Command Complete consumption together before extending the peer. Providing GPIO idle alone does not make the command succeed. Then connect through the natural application event loop and display initialization and check whether the already verified original glyph/GPU paths are called by natural UI.

Web installation and recovery remain separate goals. This virtual progress does not authorize unknown hardware combinations or actual OTA/bootloader/controller NVM writes.
