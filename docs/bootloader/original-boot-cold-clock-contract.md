# Oscillator control during original boot

Status: bw527 in progress. Main and display integration remain incomplete.

After ADC power response, original boot function 0x426fb0 enabled MISC.FRCHFRC bit 0 and wrote 1 to 0x40004044 at PC 0x426fc4. The previous clock model rejected it because it required buck active for every write.

Pinned SDK `am_hal_clkgen.c` functions `am_hal_clkgen_private_hfrc_force_on` and `am_hal_clkgen_private_hfrc2_force_on` control oscillator force without a buck condition. This is separate from selecting MCU high-performance mode. The model's buck guard was moved from before oscillator control to before MCU mode request, retaining it only for the latter. Reserved bits, partial writes, and status writes remain blocked. This explicit zero-delay response model does not verify actual oscillator voltage, stabilization, or frequency precision.

## Material checked

- `private:simulator/boot-clock-source-bw527-01/source-proof.json`: pinned HAL/original SHAs and function locations.
- `private:simulator/boot-clock-cold-red-bw527-02/report.json`: reproduced rejection of the existing cold request on a normal board.
- `private:simulator/boot-clock-cold-green-bw527-01/report.json`: 12 C# contract checks passed, including HFRC/2 enable/disable, MCU-mode protection, and reserved-bit/partial/status blocking.

First test `boot-clock-cold-red-bw527-01` observed rejection of the first request, then an abnormal clock profile on a second board conflicted with existing GPU-ready constructor conditions and the process exited 133. It is not treated as firmware fault or a normal RED report. A GPU-connected board is checked with the normal clock profile, and existing isolated MCU no-ack guest regression checks the failure-response policy.

ADC and clock cold tests were combined in `tools/verify_boot_cold_power.py --contract adc|clock`. The verifier copy from the earlier ADC run is retained in its RED/GREEN folders.

## Original execution and cleanup

All ten conditions passed: seven existing HFRC and three MCU nominal/no-ack/repeat. Original boot stopped after 13,791,447 instructions writing 0x400 to shared power 0x40021004 (PC 0x41c05c). Memory protection, system control, and CFSR/HFSR errors were 0. HFRC boundary was passed but main/frame not reached. Authoritative record: `private:simulator/original-boot-clock-cold-native-bw527-01/frontier-proof.json`.

Ten regression ELFs totaling 335692 bytes and an identical 149773-byte boot dump were cleaned up. Actual logs, source, SHAs, inputs, and rebuild commands remain; owned container removal was confirmed.
