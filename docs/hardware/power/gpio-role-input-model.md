# GPIO156 Input Adapter Limited to the Original Consumer

Work bw-0214. Low/high were explicitly supplied under the [GPIO role contract](gpio-role-input-contract.md). In stock 2.4, 2.3, and Faceclaw38, original GPIO helper and role function processed five samples and returned low→1, high→2. The next block is `0x40008200` read. This does not complete general GPIO hardware or the synchronization module.

## Model boundary

`BlackwallGpioRoleInput` is a **limited input adapter coupled to the original HAL consumer's ABI**. It is not described as a model reproducing all general GPIO bank inputs.

At actual bus read it checks:

- Address is RD4 `0x40010414`.
- Current CPU is CortexM and PC is the original read instruction in the pinned main.
- CPU r0 target pin is 156.
- PINCFG156 recorded in root is actual observed value `0x93`.
- An explicit low/high profile and finite read budget (1..64, default 5).

Only then does it return a word with level in bit 28. Zero in the other 31 bits is **padding discarded by the original's immediate shift/mask**, not a claim that other pins are physically low or their input values. This padding is not supplied to other pins/consumer PCs. Default is component disconnected/unknown. Writes, byte reads, and other banks retain existing strict boundaries.

`TrySample` is the model API directly testing the same pin/PC/config/budget judgments. In actual main, `TryRead` reads CPU context and calls it. Direct unit calls alone were not claimed as CPU-context integration; native runs below confirmed it.

Rejected accesses do not change Reads, budget consumption, or level. However, if an actual CPU attempted access, last-attempt diagnostics `LastContextPc/Pin` update even before rejection. Not every diagnostic field is described as completely invariant. Reset clears sample count and last context.

This adapter is a static logical-level experiment. Electrical wiring, pull behavior, edge/IRQ, physical debounce, and left/right temple correspondence were not verified. Extending it to a general GPIO input model independent of CPU context requires separate evidence for each pin's external signal and known scope.

## Run options and observations

Added `--gpio-role-level unknown|low|high` (default unknown) and `--gpio-role-read-budget` (default 5). Selection requires explicit existing writable synthetic LittleFS preparation. The helper takes per-image GPIO read PC and role-function location from source contract 49 and rechecks actual GPIO BL and return locations.

Observations were added only immediately after original GPIO calls and at role-function epilogue. An SRAM snapshot of the first GPIO output variable was also read. Role, PC, and return values were not written, and original delay/sample loop was not skipped.

Outside Git in `simulator/gpio-role-main-01/`:

| Run | GPIO samples | Original role return | Next PC |
| --- | ---: | --- | --- |
| stock24-low / high | 5 each | 1 / 2 | `0x47d3f0` |
| stock23-low / high | 5 each | 1 / 2 | `0x4786c4` |
| cfw-low / high | 5 each | 1 / 2 | `0x4786c4` |
| stock24-budget1 | 1 | Not reached | Existing GPIO read `0x49668c` |
| stock24-default | 0 | Not reached | Existing GPIO read `0x49668c` |

All six normal runs had five original HAL sample returns of 0; first output snapshot was low 0/high 1. Actual CPU's last PC and pin also matched source read PC/156. Original role function returned low 1/high 2. This can be connected to source contract Master/Slave labels, but lower transport initialization or whole role-module success was not confirmed.

Budget 1 supplied only the first sample and blocked the second read. Default unknown matched earlier board bytes, full CPU state, and selected observed events. Normal runs also retained the previous full event prefix with drop 0. Event counts are stock 2.4 3039, stock 2.3 2909, Faceclaw 3001.

The next `0x40008200` is **TIMER CTRL0** in the pinned SVD. Its timer module, mode, clock, and IRQ contract require subsequent source analysis; reset 0 was not yet supplied.

Follow-up bw-0215 [TIMER0 contract](timer0-sync-start-contract.md) confirmed UPCOUNT/HFRC-div16/CMP0=6000, stopped configuration and IRQ67 preparation, and shared state with TIMER14. TIMER0 execution model and actual IRQ remained unverified at that point.

## Verification

- Missing type before change preserved in `gpio-role-input-red-01/renode.log`.
- 38 unit items: low/high, unknown pin/PC/config, budget, reset, invalid constructor arguments, host read, and root rejection of input writes/byte/other bank. Direct sample logic and connected root rejection were distinguished.
- Eight actual mains: six low/high, budget 1, and default unknown.
- Three prerequisite CLI cases rejected before output creation.
- `verify_gpio_role_evidence.py` 124 items compared logs/reports, current model, pinned main/derived assets, previous full event prefix, actual CPU context, original output/return, budget, and default boundary.
- Python compilation passed.

Results are `gpio-role-verification-01/report.json`. A review agent inheriting the parent model read the current change and identified no significant functional/default/scope defects. Its recommendation to clarify updating last-attempt diagnostic fields on rejection is reflected above. Actual context integration was confirmed by six native runs. Astra was not used.

## Overall state

Next is investigation of the original call/configuration contract for TIMER CTRL0 access. Full main boot, BLE, display, and real-device installation/recovery remain incomplete; product fulfillment remains 13/29 (44.8%). No glasses access, permanent writes, or external publication occurred.
