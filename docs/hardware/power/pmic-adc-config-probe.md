# Original PMIC ADC Configuration Restore Path

bw-0135. The meaning of ADC configuration read by original initialization was analyzed, and an experiment responding only with explicit virtual state identified the next initialization boundary. This does not implement an actual PMIC or full G2. No physical device, Astra, or external publication was used.

## Contract established from original code

Stock 2.4 backend candidate 0x4fec4e splits a 16-bit address into high/low bytes and passes them to IOM7/0x6b. At the call site of initialization candidate 0x4fed72, R3=1 corresponds to a restore flag. Subsequent ADC getter candidate 0x58098e reads one byte at 0x0509 and separates bits 0 and 1. Bit 1 is also an operand of an instruction recording internal instance burst state.

This is consistent with the restore_values path and ADC config getter shape in pinned [Nordic source](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_core.c). It does not prove identical original symbols or full library version. Initialization is not interpreted as necessarily expecting reset 0. Static addresses, instructions, and main hash are preserved in `private:simulator/pmic-adc-source-01/report.json`.

The stock 2.3/Faceclaw getter is 0x57d956. Instead of applying address differences from another IOM function, unique prefixes and actual PUSH/STRB/POP were checked per original. All runs proceed from original main reset without function bridges, forced branches, or return overrides.

## Explicit virtual state

Existing pointer probe optional `adcConfig` defaults to −1 (unknown), or explicitly accepts 0–3. Only when selected does it respond with that value to a one-byte read at pointer 0x0509. Data is fixed virtual state, not read from an actual device. Reset preserves the selected virtual initial value but resets pointer and counters. This experiment allows read/Finish after pointer write/Finish; it does not verify physical STOP.

Other read lengths, unselected pointers, other registers, and value writes are blocked. This model does not implement actual ADCCONFIG RW behavior, ADC measurement, automatic timer, IRQ, power, or charging. Nordic ADK was not copied into executable code. The default main runner does not automatically connect a peer or response.

## Actual results

The 43 checks in `i2c-adc-config-unit-02/report.json` cover 20 existing unknown behaviors, four virtual values, invalid read length, read Finish/reset, and invalid constructor values. After unit01's 39 checks, diagnostic request pointer and additional wrong-length checks were added as new material.

`pmic-adc-main-01/report.json` records seven original runs:

| Input | Virtual configuration | R0 before bit 0 / bit 1 stores | Getter return point | Next request |
| --- | --- | --- | --- | --- |
| Stock 2.4 | 0 | 0 / 0 | Reached | 0x050a pointer |
| Stock 2.4 | 1 | 1 / 0 | Reached | Same |
| Stock 2.4 | 2 | 0 / 1 | Reached | Same |
| Stock 2.4 | 3 | 1 / 1 | Reached | Same |
| Stock 2.3 | 0 | 0 / 0 | Reached | Same |
| Faceclaw38 | 0 | 0 / 0 | Reached | Same |
| Stock 2.4 | unknown | Not reached | Not reached | Existing 0x0509 read stop |

In the first six, entry, two output stores, cache store, and the point before POP were observed once each in order. Original success status literal 0x2bad0000 also matches R0 before POP. The next original request then executed, but no separate hook was installed at caller continuation itself. The hook is before STRB, so this is not generalized to direct verification of RAM after storage.

No response is supplied at next address 0x050a. Rejected pointer request value is guard.value=0x050a and previous pointer is guard.address=0x0509. These are logical peer addresses, distinct from CPU MMIO addresses. CPU stops at IOM7 CMD write (stock 2.4 PC 0x58236c, 2.3/CFW 0x57b014). Even though it returns to the same PC, request content and execution path progressed beyond the earlier first 0x0509 pointer stage.

## Audit and next work

The 120 checks in `pmic-adc-verification-01/report.json` compared unit/raw markers, pinned originals/images, base/derived hashes and unchanged main/fill/probe/result, exact peer replacement and explicit board arguments, observation order/operands/status, unknown control, and stock 2.3/CFW model/runtime agreement. Existing parse_log also checks policy violations and unexpected warnings/errors. UART TX, ISR, and CQ pairs are 0; full boot/display remain incomplete. Product conditions remain 13/29.

Next, investigate ADC NTC configuration and remaining PMIC state needed by restore initialization together. Expand using explicit, sourced virtual profiles while preserving that actual inherited state is unknown. Do not switch to a generic response model adding arbitrary 0 for every read. Independent GPT-6-family reading review identified the limit of pre-store observation; the scope above reflects it. The parent separately audited final seven native results. No separate transcript archive review occurred.
