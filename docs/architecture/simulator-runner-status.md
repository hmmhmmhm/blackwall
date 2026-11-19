# Development simulator runner status

Latest stage: six original-main combinations selecting the [explicit buck response](../hardware/power/buck-state-response-model.md) advanced to the next clock request for switching to high-performance mode. Full boot and integrated screen remain incomplete.

Earlier optional path: the [D-cache functional model](../hardware/cpu-memory/coherent-data-cache-model.md) advanced past original main cache initialization to the second buck status read. Full app loop and integrated screen remain incomplete. Initial runner results below are historical and distinct from each model's options and limits.

Following the user-approved development order, the first common runner was implemented. `tools/firmware_runner.py` validates pinned stock 2.3.0.24/2.4.0.24 and Faceclaw/38 bundles and extracts main. It executes in isolation from the main reset vector; full boot and screen display are not yet implemented.

## Model and stop conditions

- Unicorn 2.1.4, an explicit Cortex-M4 approximation. It does not reproduce all Apollo510B CPU functionality.
- Main area is read/execute-only; provisional SRAM is 512 KiB from 0x20000000, filled with 0xa5. This does not establish the full SoC memory map.
- No bootloader-configured peripheral state, MMIO, ROM, interrupt model, or function stubs.
- Stop on unmapped/protection violations, execution outside code, emulator errors, instruction/time limits; record reason, PC, SP, access width, and recent addresses.
- Do not declare successful boot. `boot_verified`, `hardware_validated`, and `installable` are false in all current reports.

## Test results

Seven synthetic Thumb code tests passed: unmapped read/write/execution, code write protection, instruction limit, identical run results, and invalid reset vector rejection. Actual images and synthetic tests are distinct.

Each of three actual bundles was run twice, yielding identical paired reports. Six JSON files are preserved in private `simulator-reset-01/`.

| Image | First unimplemented access PC | Access | Observed instruction boundary |
| --- | --- | --- | ---: |
| Stock 2.3.0.24 | 0x601a84 | 4-byte read at 0xe000ed88 | 14 |
| Stock 2.4.0.24 | 0x5fbe84 | 4-byte read at 0xe000ed88 | 14 |
| Faceclaw/38 | 0x601a84 | 4-byte read at 0xe000ed88 | 14 |

The access corresponds to the [CPACR location](https://documentation-service.arm.com/static/64c7832738511951cb7a246e) in Arm documentation. The [CMSIS SCB definition](https://arm-software.github.io/CMSIS_6/latest/Core/structSCB__Type.html) also identifies the coprocessor access control register. This register was not yet modeled or given an arbitrary return value. The stop indicates the runner lacks a model, not an actual firmware error.

## Usage

```sh
/tmp/blackwall-research-GJjXQFhx/offline-venv/bin/python tools/firmware_runner.py \
  /tmp/blackwall-research-GJjXQFhx/stock-2.4.0.24.bin \
  --output /tmp/blackwall-reset-new.json --instructions 10000
```

This example uses the then-current environment path; a permanent deployment environment was not yet set up. Existing output files are not overwritten. No hardware connection or installation option exists.

Next: check the relationship between the CPACR access instruction and CPU-internal FPU control and model only that scope. Do not simply allow a whole system register page as RAM. Then connect boot handoff initial state, necessary peripheral models, and actual display output. The full development hardware simulator goal remains incomplete.

## CPACR storage model

Added `tools/simulator_registers.py` and optional `--cpacr-storage`. Default execution still stops at CPACR. When enabled, only aligned 4-byte reads/writes at 0xe000ed88 are allowed, with initial 0 and written values 0 or 0x00f00000. Other values, widths, and adjacent addresses stop with `unsupported-register-access`. Initial 0 is an isolated-run assumption, not an observed boot handoff value.

Actual main reads CPACR, ORs 0x00f00000 and writes it, then executes DSB/ISB and FPSCR setup. [Unicorn 2.1.4 register code](https://github.com/unicorn-engine/unicorn/blob/2.1.4/qemu/target/arm/unicorn_arm.c) exposes C1_C0_2 as internal cp15.cpacr_el1, but automatic connection to M-profile MMIO control was not assumed. Separate one-instruction tests on Cortex-M4 and M33 executed VMSR FPSCR both before and after CPACR configuration. Thus this is a **storage/readback model**, not FPU permission enforcement, privilege, or exception modeling; the report states this.

Eleven synthetic tests passed in total. Added checks cover CPACR write/readback, adjacent register rejection, 1-byte rejection, and unsupported value writes leaving state unchanged. Execution rejected in an MMIO callback stops immediately; subsequent state is not treated as a normal resumption point.

Private `simulator-cpacr-01/` preserves two actual-image reports per image; each pair was identical.

| Image | Next stop PC | Unimplemented access | Instruction boundary |
| --- | --- | --- | ---: |
| Stock 2.3.0.24 | 0x601a38 | 4-byte write at 0xe000ed08 | 26 |
| Stock 2.4.0.24 | 0x5fbe38 | 4-byte write at 0xe000ed08 | 26 |
| Faceclaw/38 | 0x601a38 | 4-byte write at 0xe000ed08 | 26 |

0xe000ed08 corresponds to [CMSIS SCB VTOR](https://arm-software.github.io/CMSIS_6/latest/Core/structSCB__Type.html). The CPACR model did not automatically allow VTOR on the same page. 14→26 is an observation for this path, not performance or full-boot progress.

Actual reset code also configures MSPLIM/PSPLIM. The fact that the Cortex-M4 approximation did not stop there is not proof of instruction or stack-limit accuracy. Next expansion requires review of CPU v8-M state, separation of VTOR and interrupt scope, and boot handoff initial state.

## VTOR storage and longer initialization

Added VTOR storage with `--cpacr-storage --vtor-storage`: 4-byte access at 0xe000ed08 and write/readback of actual main base 0x438000. Other vector bases stop as unsupported. Interrupt dispatch, exception vector fetch, and privilege are not modeled. CPACR alone retains the existing VTOR stop.

Thirteen runner tests passed, including VTOR write/readback and unsupported vector base rejection. In `simulator-vtor-01/`, two 100000-instruction runs per image were identical and all stopped at the instruction limit. This is not a normal boot judgment.

Longer `simulator-vtor-02/` runs with a one-million instruction limit observed the following unmapped writes:

| Image | PC | Write address / width | Instruction boundary |
| --- | --- | --- | ---: |
| Stock 2.3.0.24 | 0x61ba2c | 0x2013519c / 4 | 471076 |
| Stock 2.4.0.24 | 0x60badc | 0x2010e6dc / 4 | 460124 |
| Faceclaw/38 | 0x61ba2c | 0x2013519c / 4 | 471076 |

Each long run occurred once; no two-run reproducibility is claimed. Addresses are outside provisional 512 KiB SRAM. Confirm actual full RAM range and initialization purpose before expansion. Arbitrary RAM pages were not added automatically just because access stopped. No hardware access occurred.

## System SRAM from the official memory map

Ambiq [Apollo510B datasheet 1.1.0](https://contentportal.ambiq.com/documents/20123/4530417/Apollo510B-SoC-Datasheet.pdf) p.34 Table 4 identifies DTCM 0x20000000–0x2007ffff and System SRAM 0x20080000–0x2037ffff, followed immediately by reserved space. The earlier 512 KiB model covered only DTCM. This does not verify the owned device's silicon revision or RAM power state.

Analysis around stock 2.3 stop PC 0x61ba2c shows a loop storing r5=0 to destination r2 and repeating while length remains. Binary evidence therefore identifies zero initialization. The same address 0x2013519c also appears in g2flash ABI material.

Optional `--system-sram` adds only the official System SRAM range, initially 0xa5; power, retention, security, and alias are not modeled. Reserved space remains unmapped. Fifteen tests passed including expanded RAM writes and out-of-range rejection.

In private `simulator-sram-01/`, each of three actual images ran once. They passed the earlier unmapped write and reached the one-million instruction boundary limit. Final PC was 0x61ba30 for stock 2.3/Faceclaw and 0x60bae0 for stock 2.4, still in the initialization loop. Neither normal boot nor full initialization is declared complete. Next check initialization descriptor length/range and whether the loop terminates normally with sufficient budget.

## Initialization loop exit and ITCM boundary

Explicit budgets up to 10 million instruction boundaries and wall timeout up to 30 seconds were enabled; defaults remain. Reports now include R0–R12 and DTCM/System SRAM SHA256 at exit. These hashes represent post-run virtual state, not an actual device dump.

In private `simulator-sram-02/`, each image ran once with a 10-million limit and 15-second timeout. All exited the zero-fill loop before the limit and stopped at PC 0x43a15a attempting a 1-byte write to 0x40. Stock 2.3/Faceclaw observed 2852817 instruction boundaries, stock 2.4 2890657. R5=0x40; the next initialization destination differs from the earlier System SRAM range. This is not evidence of full boot completion or equivalent peripheral state.

Official memory map places 0x40 in ITCM, which the runner did not yet map. Next determine whether this write is copy, decompression, or initialization and whether it leads to actual code execution. Existing CPU approximation, security, and power limits remain. A budget boundary test brought the total to 16 passing tests.

## First peripheral access after ITCM initialization

`--itcm` adds official ITCM 0x00000000–0x0003ffff to virtual memory. Actual byte changes before/after guest writes are checked at the next instruction boundary, and only instructions composed of proven changed bytes can execute there. A write hook alone does not establish executability. A write equal to initial 0xa5 cannot be proven and may conservatively stop. Alias, security, and power states are unimplemented.

Synthetic tests checked execution of a guest-written ITCM branch, stopping on uninitialized execution, and refusal to treat a store equal to the initial value as execution evidence. All 19 runner tests passed.

Private `simulator-itcm-01/` preserves one run per image. All proved 24 changed ITCM bytes and had the same final ITCM SHA256. Actual output stopped on these peripheral reads:

| Image | PC | Unimplemented read | Instruction boundary |
| --- | --- | --- | ---: |
| Stock 2.3.0.24 | 0x489fb4 | 0x40021000 / 4 bytes | 8343858 |
| Stock 2.4.0.24 | 0x495e9c | 0x40021000 / 4 bytes | 7326612 |
| Faceclaw/38 | 0x489fb4 | 0x40021000 / 4 bytes | 8343858 |

These stopped on unimplemented peripheral access, not the execution limit. They do not mean full initialization/boot completion. ITCM changed-byte count is not the number of instructions actually executed in ITCM. Next verify the official register definition at 0x40021000 and function control flow. No arbitrary success value or memory page was supplied.

## Power status query and ITCM delay loop

Official datasheet places 0x40021000 in Power Control. [Register definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/pwrctrl_regs.html#MCUPERFREQ) from Ambiq HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` preserved by Zephyr define MCUPERFREQ there: bits 4:3 MCUPERFSTATUS, bit 2 ACK, bits 1:0 requested mode. These materials concern Apollo510 and do not verify identical behavior on the owned G2 revision. In particular the documented HP frequency was not used as actual G2 frequency.

Stock 2.3 function 0x489fa0 reads bits 4:3, compares with 2, branches in delay calculation, and calls 0x40. Power control as a whole is not modeled merely because an address differs.

`--power-mode lp|hp` is a virtual stable-state scenario. LP=0x0d and HP=0x16 encode request/ACK/status with explicit assumption that other bits are 0. These are neither device reads nor reset values. Only 4-byte reads at that address are supported; other addresses/widths and all power-transition writes are rejected. New `PowerModeRead` model and tests brought runner total to 21 passing.

LP/HP results on all three actual images are preserved in private `simulator-power-01/`. Each run occurred once, not a repeatability test. Hitting a limit is not boot completion. Both scenarios entered repeated delay paths at ITCM 0x40/0x42. Next inspect actual delay instructions and inputs and proceed with longer execution or state-preserving virtual-time handling verified for equivalence.

## State-preserving delay-loop summary

Private `itcm-delay-inspection-01.json` identifies actual ITCM 0x40 instructions: `SUBS r0,#1; BNE 0x40; BX lr`. Input 0 causes 32-bit underflow, so it is not summarized. A later separate memory-copy loop is outside this handling.

Added `tools/simulator_delay.py` and optional `--fast-delay`. It applies only at address 0x40 to guest-initialized ITCM with an exact six-byte instruction sequence. Sets R0 to 0 and final SUBS NZCV to 0/1/1/0, preserves other APSR bits, registers, and memory, and moves to LR. It does not advance actual device time, timers, or interrupts and must not be used where cycle accuracy is required.

Eight combinations of inputs 1/2/31/1000 and two initial flag states were compared against actual Unicorn instruction execution for R0–R12/SP/LR/PC/APSR and all memory. Input 0 and altered-code rejection were also checked. Two delay-model and 21 existing runner tests passed. Summarized guest instruction count is recorded separately from observed runner instruction boundaries.

Each of three LP scenarios in private `simulator-delay-01/` ran once. Each summarized the loop once with input counter 6399985, then stopped at unimplemented read 0x4000885c. PC stock 2.3/Faceclaw 0x4e6d7e, stock 2.4 0x5055fe. Summarized 12799971 instructions are calculated from the instruction sequence/counter, not measured CPU performance/time. Next check timer meaning and firmware polling conditions.

## 0x4000885c not yet modeled as timer counter

Pinned HAL STIMER documentation defines offsets 0x50/0x54 as SNVR0/1 and 0x58 as HALSTATES, but not 0x5c. Membership in STIMER alone does not establish a counter.

Stock 2.3 after PC 0x4e6d6c checks the output pointer and reads 0x4000885c only when RAM cache is 0. It stores low 13 bits in cache and decomposes bits into the output structure's halfword and individual bytes. The observed segment is not a polling loop repeatedly waiting for ticks.

`am_hal_reset_status_get` in `mcu/apollo510/hal/mcu/am_hal_reset.c` from official Ambiq HAL commit `d3278ec49a534728384537557dd44b205ec72129` has the same status cache and individual reset-bit outputs, but the original reads RSTGEN->STAT. Therefore G2 0x5c as reset status shadow is currently a **hypothesis based on source/binary comparison**, not a confirmed official register definition. No model returning 0 or arbitrary ticks was added.

After checking full bundle CRC, 32-bit literal occurrences of 0x4000885c were searched: 2.3 main 0x44e004/0x489920/0x4e6e24; 2.4 main 0x44e8f4/0x495808/0x5056a4; two boots 0x41b0cc/0x41cb24. Preserved in private `boot-2-4-analysis/stimer-5c-literals-01.json`. Literal occurrence does not prove actual execution reference or write path. There is a data pool near boot literals, so simple disassembly of those bytes is not treated as executed code. Next trace writes to this address in data tables and initialization code.

## Explicit virtual input for G2 status latch

Searching PC-relative LDR candidates throughout boot found 0x41acb6 reading literal 0x41b0cc and 0x41c4c2 reading 0x41cb24. The former checks bit 1; the latter, if bit 1 is set, clears only bit 2 in the existing word and writes the same address. Main 2.3 has the same form at 0x44dbe8 and 0x4892f6. Earlier literal search within 1 KiB missed long LDR.W displacement references. This time all boot and up to 4 KiB displacement in main were checked. This is static reference analysis, not full boot execution evidence.

`--reset-latch VALUE` sets a virtual initial state restricted to low 13 bits. `ResetLatchScenario` permits only 4-byte reads at 0x4000885c and the observed write clearing only bit 2 from an existing value with bit 1 set. Other address/width/value writes stop. It does not establish the meaning of an undocumented offset or claim actual device state. Results record `hypothesized-reset-status-shadow`, `hardware_verified=false`.

24 runner tests passed including the address read, observed bit-clear/readback, and rejection of unobserved writes/adjacent addresses. In private `simulator-latch-01/`, each image ran once under LP/initial latch=0x2. All read latch once and stopped at next unimplemented 4-byte read 0x40024000. PC stock 2.3/Faceclaw 0x54639c, stock 2.4 0x570d70. This is the Watchdog Timer block on the official peripheral map. Next check watchdog enable/clock/reset conditions. Actual reset reproduction, full boot, and display completion remain unverified.

## Disabled watchdog configuration model

Pinned HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` `CMSIS/AmbiqMicro/Include/apollo510.h` defines WDT CFG bit 0=WDTEN, bit 1=INTEN, bit 2=RESEN, bits 15:8=RESVAL, bits 23:16=INTVAL, bits 26:24=CLKSEL. In the same checkout's `mcu/apollo510/hal/am_hal_wdt.c`, `am_hal_wdt_stop` queries clock selection then clears WDTEN and reads back. Stock 2.3 function 0x546392 matches this pattern. The material is for Apollo510; full G2 hardware equivalence unverified.

`--watchdog-disabled` is a virtual initial CFG=0 state. It provides only 4-byte CFG reads/writes. While disabled, defined field configuration storage/readback is supported; enable=1, reserved bits, unsupported clocks, other registers and widths stop. Actual timeout/interrupt/reset/clock-release/feed are unimplemented. This does not mean the owned glasses' watchdog is off.

Initial `simulator-wdt-01/` supported only CFG=0 writes and stopped at a later configuration write. Final model added disabled configuration storage and reran as `simulator-wdt-02/`. The first activation fixture mistakenly wrote 0; it was corrected to write 1 to actually test enable blocking. 27 runner tests passed including activation/adjacent-register rejection and disabled configuration readback.

Each image ran once under LP/reset-latch=2. CFG was read three times and written twice, final 0x020ce004 with WDTEN=0 in all. Then a 4-byte read at 0x40000000 stopped. PC stock 2.3/Faceclaw 0x546324, stock 2.4 0x570cf8. Official peripheral map identifies the next address as reset/BoD control. This does not support actual reset execution.

## Reset CFG storage and watchdog restart boundary

Pinned CMSIS `apollo510.h` defines RSTGEN CFG bits 1:0 as WDREN/BODHREN. SWPOI key 0x1b at offset 4 and SWPOR key 0xd4 at offset 8 request actual reset, distinct from CFG storage. Main 2.3 at 0x546324 reads CFG, reflects watchdog RESEN input in bit 1, and stores it.

`--reset-config` supports only bits 1:0 storage/readback under an explicit virtual CFG initial value 0. SWPOI/SWPOR and other offsets/widths/undefined bits stop. Storing watchdog reset-enable does not implement actual timeout/reset propagation. Tests covered CFG roundtrip, rejection of both software reset key requests and reserved-bit writes. 29 runner tests passed.

Each image ran once in private `simulator-reset-config-01/`. CFG was read and written once, final 0x2. Next stop was WDT RSTRT (0x40024004) write. Stock 2.3/Faceclaw PC=0x546374, stock 2.4 PC=0x570d48. Code value 0xb2 matches restart key in CMSIS and `am_hal_wdt.c`. Current model does not allow it.

The next necessary expansion combines virtual time, watchdog restart/enable/expiry, and reset conditions. Merely accepting register writes with a watchdog that never expires is not a normal active watchdog model. Specify relationship between elapsed real time and virtual clock, and stopping policy for unsupported interrupt/reset before expansion.

## Instruction-based virtual clock and active watchdog

Added `tools/simulator_watchdog.py` and `--watchdog-step-clock`; simultaneous selection with `--watchdog-disabled` is rejected. Initial CFG=0; only LFRC/64 used by the current path is supported while active. Defined CFG storage, restart key 0xb2, enable, disable, and threshold arrival are connected. Other active clocks, runtime reconfiguration, and unimplemented registers stop.

The clock is a test assumption of **one virtual LFRC input tick per 100000 guest instructions**. With LFRC/64, a counter tick is 6400000 instructions. It does not measure or guarantee actual chip frequency, cycles, or elapsed seconds. Counter does not advance while disabled. Reset/interrupt comparison values are checked and threshold arrival stops as `watchdog-reset-threshold-due` or `watchdog-interrupt-due`. Reset threshold and actual reset propagation are distinguished; RSTGEN CFG is included in events. Interrupt dispatch, watchdog lock, and actual reset replay remain absent. Counter wrap without a comparison value also stops as unsupported.

ITCM delay summary is not applied while watchdog is active, avoiding skipped expiry during a summarized delay. Only summarized instructions while disabled are passed to the instruction-clock model. This approximation cannot be used where timing accuracy is required.

Four unit tests passed including just-before/exact expiry boundary, extended lifetime after restart, disabled state, interrupt threshold, invalid key, unsupported clock and active reconfiguration rejection. Existing 29 runner tests also passed.

In private `simulator-wdt-clock-01/`, each actual image ran once with virtual LP/latch=2/instruction clock. All enabled CFG=0x020ce005 after one restart. Under current clock assumptions, execution stopped before expiry at next unimplemented 4-byte read 0xe000ef34. Stock 2.3/Faceclaw PC=0x44db18, stock 2.4 PC=0x44e408. counter_ticks=0 means the first virtual counter tick had not yet occurred, not that the watchdog was stopped forever. Next investigate this CPU system register and actual used bits. Full boot/screen/physical recovery verification remains incomplete.

## FPCCR configuration storage

0xe000ef34 corresponds to FPCCR in the Arm [CMSIS FPU structure](https://arm-software.github.io/CMSIS_6/v6.2.0/Core/structFPU__Type.html). The [Arm exception model guide](https://documentation-service.arm.com/static/64c7832738511951cb7a246e) describes automatic/lazy context-save control. Main 2.3 function 0x44db0a preserves interrupt mask, clears the top two bits, ORs 0x80000000 or 0xc0000000, and writes.

`--fp-context-storage` is selected with `--cpacr-storage`. With virtual initial 0 it supports aligned 4-byte reads and storage/readback only of 0/0x80000000/0xc0000000. Attempts to create other status bits or access adjacent registers stop. FPU stack-frame allocation, lazy preservation, security state, and actual context restore on exception are unimplemented; report records `exception_context_preservation=not-modeled`. Storing control values is not completion of FPU context preservation.

31 runner tests passed including valid control readback and unsupported status-bit write rejection. Each image ran once in private `simulator-fpccr-01/`; all read FPCCR once, wrote 0xc0000000, then stopped at 4-byte read 0xe000edfc. Stock 2.3/Faceclaw PC=0x4e8d0a, stock 2.4 PC=0x507596. Next investigate this system register and following trace/counter initialization. No arbitrary values were supplied to unimplemented registers.

## DEMCR trace-control disable path

TRCENA (bit 24) at 0xe000edfc controls Arm debug/trace. [Arm architecture manual DWT_CYCCNT definition](https://community.arm.com/cfs-file/__key/communityserver-discussions-components-files/471/DDI0553B_5F00_y_5F00_armv8m_5F00_arm.pdf) states both DWT_CTRL.CYCCNTENA and DEMCR.TRCENA are required for the cycle counter to advance. Observed G2 main 2.3 path at 0x4e8d08 clears TRCENA and confirms disable via a separate check function; it was not assumed to enable the cycle counter.

`--trace-control-storage` is a DEMCR TRCENA storage model selected with CPACR storage. From explicit virtual initial 0 it supports 4-byte reads and storage/readback of 0/0x01000000 only. Other debug bits and adjacent addresses stop. Actual trace, DWT counters, and debug exceptions are unimplemented and marked in the report. 33 runner tests passed including control readback and unsupported-bit rejection.

In private `simulator-demcr-01/`, this option was added to existing LP/latch/watchdog-clock assumptions and each image ran once. All performed two DEMCR reads/one write, final 0, then stopped on 4-byte read 0x40021004. Stock 2.3/Faceclaw PC=0x488fca, stock 2.4 PC=0x494eb2. This lies outside 0x40021000 supported by existing power model, so it was not automatically allowed. Next check device enable field and initialization call target. Full boot/screen/install compatibility unproven.

## Peripheral enable/status off scenario

Pinned Ambiq HAL `pwrctrl_regs.html` and CMSIS header identify 0x40021004=DEVPWREN and 0x40021008=DEVPWRSTATUS. Main 2.3 path 0x488fae obtains register/mask from input device index and returns success if enable bit is already 0. Observed device index was 0x1c; its device name was not determined from index alone.

Optional `--devices-off` with `--power-mode` sets virtual initial values of both registers to 0. This assumption concerns peripheral power domains, not verified glasses or SRAM power state. Only 4-byte reads of both and rewriting 0 to DEVPWREN are supported. Nonzero power-up requests, status writes, other fields/widths stop. No transition latency, ACK, current, or clock model. 35 runner tests passed including enable/status reads and no automatic power-up approval.

Private `simulator-device-off-01/` added devices-off to LP/latch/watchdog-clock assumptions and ran each image once. Device enable was read once, then 4-byte read 0x40020250 stopped. Stock 2.3/Faceclaw PC=0x489324, stock 2.4 PC=0x49520c. No value pretending successful transition was supplied. Next investigate the MCU control register and debug/trace power-off path. Full boot/display/physical compatibility remain unverified.

## MCUCTRL DBGCTRL debug-port-off scenario

Pinned HAL `docs/apollo510/pages/mcuctrl_regs.html` identifies DBGCTRL at 0x40020250. CMSIS defines bit 0=DBGTPIUTRACEENABLE, bits 3:1=DBGTPIUCLKSEL. Main 2.3 after 0x489324 clears bit 0, rereads, then clears bits 3:1. This is debug trace port control, not a glasses display command.

`--debug-port-off` is a virtual initial register value 0 scenario. Only aligned 4-byte reads and storing 0 are supported. Trace enable, other clock values, and neighboring MCUCTRL registers stop as unsupported. Trace clock/packets/debug interface are not reproduced; `trace_clock=not-modeled` is recorded. Tests confirmed off readback and rejection of debug enable/other MCUCTRL addresses. 37 runner tests passed.

Private `simulator-debug-off-01/` added debug-port-off to existing LP/latch/devices-off assumptions and ran each image once. DBGCTRL was read twice and 0 written twice; then 4-byte read 0xe000ed14 stopped. Stock 2.3/Faceclaw PC=0x4897ca, stock 2.4 PC=0x4956b2. Next investigate the CPU setting bits and runtime accesses. Full boot/display/physical installation remain incomplete.

## CCR cache-off query and next control write

Function at current PC 0x4897c4 reads CCR (0xe000ed14) and checks cache-enable bits 17/16. The [Arm CMSIS Cortex-M55 header](https://github.com/ARM-software/CMSIS_6/blob/v6.2.0/CMSIS/Core/Include/core_cm55.h) defines the SCB. The observed path was not assumed to change unaligned-access configuration. It then shifts three bytes from an input structure into a word and writes separate address 0xe001e300, whose behavior is not yet modeled.

`--cpu-caches-off` is a virtual CCR=0 read scenario selected with CPACR storage. Cache bits are off; assumption that other CCR fields are also 0 is stated in reports. It was not observed at actual reset or boot handoff. All CCR writes stop. Actual cache, exceptions, and alignment traps are not reproduced. 39 runner tests passed including normal read and write rejection.

In private `simulator-ccr-01/`, each image ran once and stopped on a 4-byte write to 0xe001e300 after two CCR reads. Stock 2.3/Faceclaw PC=0x4897fa, stock 2.4 PC=0x4956e2. This is not CPU cache configuration success; meaning and preservation conditions of the next control write require investigation. Full firmware simulation/screen/web installation judgment incomplete.

## CPDLPSTATE all-ON request

Official [Cortex-M55 TRM power mode control register table](https://documentation-service.arm.com/static/60e2c2fc677cf7536a55dfef) identifies 0xe001e300 as CPDLPSTATE, distinct from MSCR. [Arm CPDLPSTATE description](https://support.arm.com/documentation/101273/latest/Cortex-M55-Processor-level-components-and-system-registers---Reference-Material/Implementation-defined-power-mode-control/Core-Power-Domain-Low-Power-State-Register--CPDLPSTATE) defines core/EPU/RAM low-power fields. Source R1 of all three prior writes was 0. Value 0 requests ON in each field; it is not assumed equal to actual reset value.

`--core-domains-on` is an explicit virtual state where core/EPU/RAM are already ON and CPDLPSTATE=0. Only 4-byte reads and writing 0 are supported. RET/OFF, reserved fields, and adjacent DPDLPSTATE access stop. Actual power-channel handshake, cache/RAM retention, security/privilege, and automatic EPU power switching are not reproduced. It is not generalized to writable memory.

41 runner tests passed including normal 0 write/readback and rejection of RET/OFF, RAM OFF, and adjacent register requests. In private `simulator-core-on-01/`, each image ran once, wrote 0 to CPDLPSTATE once, and stopped at 4-byte read 0x4002021c. Stock 2.3/Faceclaw PC=0x489342, stock 2.4 PC=0x49522a. Next check MCUCTRL register fields and firmware RMW purpose. Full boot, actual power, screen, and web installation remain unverified.

## Reproducible named execution scenario

0x4002021c is WICCONTROL in pinned HAL MCUCTRL documentation. `MCUCTRL_WICCONTROL_DEEPISWIC` bit 0 controls normal sleep versus WIC sleep when SLEEPDEEP is set. Main 2.3 reads it, ORs bit 0, and intends to write. Actual WIC sleep may remove core clock/power; adding storage alone does not implement wakeup. This register access remains stopped.

Added `tools/simulator-scenarios.json`, `tools/simulator_scenarios.py`, and CLI `--scenario startup-lp-hypothesis` to reproduce model selection. The profile bundles 15 existing explicit options and instruction/wall-time limits. It is assumptions, not captured actual G2 state, and its name includes hypothesis. Catalog SHA256 and applied options are reported. Unknown profiles or mixing manual model options are rejected before image reading. Instruction/timeout overrides alone are allowed and actual values recorded.

Three profile tests and 41 existing runner tests passed. Actual CLI ran each image in private `simulator-scenario-01/` and matched existing explicit-switch stop reason, PC, access, R0–R12, DTCM SHA256, and instruction boundary. All stopped at existing WICCONTROL read. No further progress from a new model is claimed. Commands and interpretation are in [usage](simulator-usage.md).

## WIC mode configuration and sleep stop boundary

`--wic-config`, with the existing MCUCTRL debug-port scenario, supports only WICCONTROL bit 0 values 0/1 storage/readback. Initial 0 is assumed. WIC sleep entry, clock/power removal, wakeup interrupt/pending state are unimplemented. Invalid values and adjacent registers continue to stop.

Runner checks 16-bit and 32-bit WFI/WFE opcode boundaries. On reaching one it stops before execution as `unsupported-sleep-boundary` and does not manufacture wakeup. This does not mean sleep/return success. Read-only main opcodes are checked against pinned bytes, and guest-modifiable ITCM against actual virtual memory.

Existing profile options were retained and separate `startup-lp-wic-config-hypothesis` added. 43 runner tests including WIC mode readback and stop on four WFI/WFE encodings, plus three profile tests, passed. The new entry changes the existing profile catalog hash; check profile name and applied options together.

Private `simulator-wic-01/` ran each image once with actual CLI and new profile. WIC mode read once and 1 written once, then 4-byte read 0x400201bc stopped. Stock 2.3/Faceclaw PC=0x48934e, stock 2.4 PC=0x495236. Runs did not yet reach sleep instructions; stopping policy was verified with synthetic instructions. Next analyze MCUCTRL status meaning and conditional branch.

## SHADOWVALID Info1 source scenario comparison

Pinned MCUCTRL documentation identifies 0x400201bc as SHADOWVALID. Bit 3=INFO1SELOTP identifies OTP versus MRAM Info1 source. Bit 0=VALID, bit 6=OTPREADY, and OTP boot fault fields are separate. Main 2.3 at 0x489350 extracts only bit 3 for a conditional branch.

Added `--shadow-info1 mram|otp` to MCUCTRL scenarios. Virtual values 0x1/0x9 explicitly assume VALID=1 and remaining fields=0. These are not reads of actual boot shadow or OTP readiness. Information/OTP contents, secrets, and actual access are not provided. Writes to this read-only status register and adjacent information-register accesses stop. 45 runner and three profile tests passed for source bits, absence of additional data, and rejection of invalid accesses.

Added separate `startup-shadow-mram-hypothesis` and `startup-shadow-otp-hypothesis` profiles. Private `simulator-shadow-01/` ran each of three images using both sources through actual CLI. MRAM path stopped at ITCM PC=0x48 on 4-byte read 0x42003310. OTP path stopped at nonzero device power enable write to 0x40021004 (2.3/Faceclaw PC=0x488e90, 2.4 PC=0x494d78). Each condition ran once, not hardware validation.

The source branch changes the next required model. MRAM information-area contents are not supplied, and OTP power transitions do not automatically succeed. Next check official information-area definition at 0x42003310 and copy purpose/length, distinguishing actual chip information from synthetic-fixture-testable portions.

## TRIM_REV word and information-area dependency

Pinned Ambiq HAL `mcu/apollo510/regs/am_mcu_apollo510_mraminfo1.h` identifies Info1 base=0x42002000, TRIM_REV offset=0x1310/address=0x42003310. Documentation calls it trim revision number. At the previous stop R0=0x42003310, R1=0x200001ec, R2=1 and ITCM 0x48 load/store path correspond to a one-word copy. A full trim image copy is not inferred at that point.

Pinned `am_hal_pwrctrl.c` TrimVersionGet reads one revision word and uses version 0 on value 0 or read failure. No code requiring rejection of 0xffffffff was found, so erased-fixture results alone do not establish rejection or safe behavior. Actual factory trim values and boot patch metadata have not been confirmed from official distribution bundles.

`tools/simulator_info_fixture.py` and `--trim-revision-fixture zero|erased` provide exactly this one word. Reports explicitly identify it as neither actual device data nor valid calibration. Reads at other addresses/widths and all information-area writes stop. 47 runner and three profile tests passed including readback of both values and rejection of other information reads/writes.

Private `simulator-invalid-trim-01/` ran each image once with `startup-invalid-trim-zero` / `startup-invalid-trim-erased`. All read revision once then stopped at ITCM PC=0x48 on 4-byte read 0x42003240. Official Info1 header describes the next word as PATCH_TRACKER0, SBL patch tracking metadata, but all bit meanings remain reserved. Arbitrary data was not manufactured and called valid device initialization. Next determine which branches tracking metadata controls and what behavior public source supports.

## PATCH_TRACKER0 dependency and isolated display test

Pinned `am_hal_pwrctrl.c` low_power_init caches PATCH_TRACKER0 then FT1_GDR1 in the MRAM Info1 path before initializing SPOT manager. `am_hal_spotmgr.c:685` combines particular B1/B2 PCM2.1 conditions and PATCH_TRACKER0 bit 0 to produce a flag for absence of UCRG patch. PCM2.1 implementation uses the flag to control multiple power management paths. This is grounds not to fill factory metadata with arbitrary 0/1 and declare valid initialization.

Current main 2.3 cache destination is 0x20074768. A search for this absolute-address word in raw main found no occurrence. Thus identical bit checks in actual G2 code were not proven, and the relationship between public HAL and actual binary is not established. Results preserved in private `boot-2-4-analysis/patch-tracker-refs-01.json`. Absence as a literal does not prove it is unused.

In parallel with startup analysis, an [isolated CFW renderer test](../archive/cfw-renderer-probe.md) was implemented. Actual upstream drawing code executed as ARM instructions to produce a first 576×288 screen, with full framebuffer identical to native source build. It does not substitute for full firmware boot, display driver execution, or actual lens output. One display-related subgoal obtained an actual artifact; web install/recovery/full simulator goals remain incomplete.

## Invalid input scenarios for three information words

Pinned HAL [Info1 header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/regs/am_mcu_apollo510_mraminfo1.h) confirms TRIM_REV=0x42003310, PATCH_TRACKER0=0x42003240, FT1_GDR1=0x42003314. Following public HAL information initialization and earlier actual execution boundaries, an error-input model provides only these three words. `--info1-metadata-fixture zero|erased` supplies 0 or 0xffffffff to all three and cannot be mixed with `--trim-revision-fixture`. Out-of-range/partial-width reads and all information-area writes stop.

This fixture is not actual metadata or valid calibration. `invalid` names input intent, not guaranteed firmware rejection. No claim is made that actual G2 interpretation of PATCH_TRACKER bits or FT1 date meaning is implemented. Reports state per-word read counts, synthetic input, and absent calibration.

Six CLI runs were completed in persistent local venv-02: stock 2.3/2.4 and Faceclaw38 × zero/erased. Each read all three words exactly once then stopped at next MCUCTRL read 0x4002000c. 2.3/Faceclaw PC=0x489c4c, 2.4 PC=0x495b34. Results preserved outside Git in `Blackwall/simulator/info1-invalid-metadata-01/`. 50 runner unit tests and three scenario tests passed.

Follow-up report annotation: to avoid confusing shadow-register model's default `not-provided` wording with a separate fixture, selecting a synthetic Info1 fixture now states only that a separate fixture exists. Rerunning stock 2.4 zero in `Blackwall/simulator/info1-invalid-metadata-02-stock24-zero.json` confirmed the new annotation and same stop boundary. The first six reports retain prior wording and should be read with each fixture's separate record.

[MCUCTRL definition](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/mcuctrl_regs.html) names the new boundary CHIPREV. Current model does not provide its value. Next trace relationship between actual chip-revision branches and information cache. Do not treat this as identifying device revision or insert an arbitrary supported revision as default. Full boot/display transport/install compatibility incomplete.

Follow-up: [power management classification investigation](../research/spot-classification-research.md) executed 96 actual prefix conditions and confirmed six flags and tracker bit 0 checks. The earlier absolute-address search uncertainty was resolved only for this prefix scope. Added optional CHIPREV read model and four synthetic scenarios, recording stock 2.4's next boundary by branch. Actual device revision remains unconfirmed.

Follow-up SPOT configuration storage: Added limited storage for [observed power settings](../research/spot-classification-research.md#restricted-storage-of-observed-power-settings). It stores only observed ACRG/VRCTRL values without reproducing analog power. Six runs of two synthetic revision scenarios × three images advanced to next 0x40021018 read. The option was not automatically added to existing scenarios. 54 runner and three scenario tests passed. Full boot/screen/install compatibility verification incomplete.

Follow-up: Added [memory power model](../hardware/cpu-memory/memory-power-model.md). All three images stopped at ROM-disable under explicit initial ON fixture; selecting a separate zero-delay ROM-disable model advanced to next MEMRETCFG read. TCM/NVM transitions and ROM re-enable unsupported. 58 runner and three scenario tests passed. Actual device power state/response time/boot unverified.

Follow-up MEMRETCFG storage: Added two-bit storage model for [memory retention configuration](../hardware/cpu-memory/memory-power-model.md#memory-retention-configuration-storage-model). Sleep/data retention/wake-up unsupported; WFI rejection test retained. Each image read configuration twice and wrote twice, then stopped at shared SRAM status read 0x40021028. 61 runner and three scenario tests passed. Overall goal incomplete.

Follow-up shared SRAM: Added two optional [shared SRAM ON/retention configuration](../hardware/cpu-memory/memory-power-model.md#shared-sram-on-state-and-retention-configuration) models. Existing 3 MiB mapping required; power state assumed. Stock 2.4 with only ON state stopped at retention configuration read; all three images with retention configuration also provided stopped at 0x40021040 read. Actual power transitions/sleep/data preservation unimplemented. 64 runner and three scenario tests passed. Install/recovery/full boot verification incomplete.

Follow-up MMSOVERRIDE: Added [shared SRAM override storage](../hardware/cpu-memory/memory-power-model.md#shared-sram-override-configuration-storage), storing only observed configuration. Each image performed two reads/writes then stopped at 0x40004044. 66 runner and three scenario tests passed. No actual GFX/DISP power effects. Separately changed input CRC to table-based method and verified [equivalence and execution time](../research/package-validation-performance.md). Full boot/screen transport/web install compatibility remain incomplete.

Follow-up CLKGEN: Added [clock control storage](../hardware/power/clock-control-model.md). Checked pinned header Git blob and clang offsets; stored only observed MISC/CLKCTRL values. All images stopped at next MCUCTRL read 0x40020448. Clock frequency/ready/stabilization unimplemented. 68 runner and three scenario tests passed. Actual boot/display/install compatibility unverified.

Follow-up ADC delay: Added [audio ADC delay storage](../hardware/sensors-input/adc-delay-model.md). All images recorded one AUDADCPWRDLY read/write and final 0x400, then stopped at 0x4002036c. ADC power/conversion/timing unimplemented. 70 runner and three scenario tests passed. Full boot/actual display/install verification incomplete.

Follow-up trim cache: Added [public reset fixture](../hardware/power/trim-reset-fixture.md). Verified original source/reset combinations for 12 required registers and documented zero-field difference between header and HTML. Three images made 17 total reads, advanced to RAM cache completion flag storage instruction, then stopped at 0x4002037c. All fixture writes forbidden; no valid device calibration supplied. 74 runner and three scenario tests passed. Actual boot/display/install/recovery verification incomplete.

Follow-up PWRSW: Added [static-select storage](../hardware/power/power-switch-model.md), separate from read-only cache fixture, storing only observed PWRSW0/1 values. All three images passed this segment and stopped at next 0x400211a0 read in power management function. Rail switching/voltage/ready unimplemented. 76 runner and three scenario tests passed. Actual boot/display/install/recovery verification incomplete.

Follow-up TON: Added [power control configuration storage](../hardware/power/ton-configuration-model.md). Compared public reset and actual recorded values; supports configuration storage for six registers only. LP override activation/counter/comparator/voltage effects unsupported. All images passed the function and stopped at 0x40008858 write. Meaning of the address is unconfirmed, so existing shadow hypothesis was not extended. 78 runner and three scenario tests passed. Full boot/display transport/actual install/recovery verification incomplete.

Follow-up HALSTATES: Added [clock recovery state storage](../hardware/cpu-memory/hal-state-model.md). 0x40008858 is a HAL-internal status register in public STIMER definitions and 0x5af0 is a signature defined by HAL header, distinct from existing 0x4000885c reset-shadow hypothesis. All images made one read/two writes, final 0x5af00000, then stopped at next 0x400211c8 read. Actual clock mux recovery unimplemented. 80 runner and three scenario tests passed. Full boot/display transport/actual install/recovery verification incomplete.

## HFRC2 and MCU performance transition response verification

The [clock response model](../hardware/power/hfrc2-mcu-mode-response.md) was added. Limited state comparisons were verified with 122 Python and 12 native conditions and six combinations of two stock images/Faceclaw × LP/HP. M55 proceeds past MPU control code and additional cache cleaning to a PWRCTRL.GFXPWRSWSEL (0x40021090) read. Python stops at SHCSR, so this is not interpreted as endpoint equivalence, full boot, or integrated screen success. Assumptions including zero response delay, synthetic initial values, and ready apply only to selected scenarios and are unverified on physical hardware.

## GPU supply source and performance request storage

The [GPU selection storage model](../hardware/display-gpu/gfx-power-selection-storage.md) was connected to native M55. Limited verification passed in 15 synthetic conditions, three existing-behavior regressions, and six main combinations. Original main advances to CLKGEN.MISC.FRCHFRC write (0xfbbfc1) after storing selection 1 and request 3. GPU engine, physical clock/voltage, full boot, and integrated screen remain incomplete. Python retains the earlier MPU boundary.

## HFRC force control

The [HFRC control model](../hardware/power/hfrc-force-control.md) was added as opt-in. Limited verification completed for seven native conditions, four existing-behavior regressions, and six original main combinations. M55 advances past MISC=0xfbbfe1 to the point of attempting to write 0x6d3d9 to LDOREG1 (0x40020080). Actual clock, voltage, full boot, and integrated screen remain incomplete. The difference from the Python MPU boundary is retained.

## 18 GPU power preparation steps

The [power preparation sequence](../hardware/display-gpu/gpu-power-preparation-sequence.md) was connected as an optional native model. In 10 synthetic cases, four existing-behavior regressions, and six main combinations, execution passed calibration/rail/TON/restoration and reached the DEVPWREN GPU bit 18 request (0x40021004,0x40000). Physical power, GPU engine, app loop, and integrated screen remain incomplete.

## GPU power request and status response

The [GPU power response](../hardware/display-gpu/gpu-power-domain-response.md) was connected as an optional model. In 13 synthetic cases, four existing-behavior regressions, and six normal main combinations, execution advanced after power status on to the first GPU.INTERRUPTCTRL (0x400900f8) write. A stock 2.4 stuck-off observation also advanced to the same GPU access, failing to establish safe failure fallback or recovery. GPU engine, full boot, and integrated screen remain incomplete.

## GPU initialization evidence and IRQ28

The [GPU initialization investigation](../hardware/display-gpu/gpu-initialization-research.md) compared static patterns in three pinned firmware images with the official Apollo510 HAL. A separate M55 synthetic test confirmed IRQ28 pending/clear/handler entry. GPU IRQ integration and command execution are unimplemented, and the actual main execution endpoint remains as before. The ARM driver archive inspected does not replace a GPU execution model. Full boot and integrated screen remain incomplete.

## Initial GPU interrupt clear

[GPU idle clear](../hardware/display-gpu/gpu-interrupt-clear-model.md) was connected to the explicit power response. It handles only DWORD0 writes in the virtual on state and does not create GPU work, completion IRQ, or reset. Nine synthetic and four power regression cases were checked. Full boot and integrated screen remain incomplete.

## Initial GPU ID and ring candidate capture

[Initial ID0 and ring observation](../hardware/display-gpu/gpu-id-initialization-capture.md) was added. Thirteen synthetic and four LP main cases were checked; in active 3, while blocking the 0xec request, an initial footer matching 4864 bytes was observed. GPU command execution, full boot, and integrated screen remain incomplete.

## Initial GPU ring configuration

The [configuration latch model](../hardware/display-gpu/gpu-ring-configuration-model.md) was connected. Seventeen new cases, four regressions, and four LP main cases were checked. Active 3 stops at the GPU IDREG 0x400901ec read after three configuration steps, preserving initial ring snapshots of 1216 words each. GPU execution, full boot, and screen remain incomplete.

## Fixed GPU ID response

The public 0x86362000 and literals of the three inputs were compared and compiled offsets checked in the [fixed ID comparison and response](../hardware/display-gpu/gpu-identity-response-model.md). Twelve native and five main cases were observed. Normal 3 advanced to GPU 0xe8 write, absent stopped at fc read, and stuck-off at f8 write. Actual GPU capability, safe fallback, full boot, and integrated screen remain incomplete.

## Initial GPU reset request

[Limited initial reset control](../hardware/display-gpu/gpu-initial-reset-controls.md) was connected. Fifteen native and four LP main cases were checked; normal 3 stopped at 0x388 write after e8/fc requests. Ring validity after reset is unconfirmed, and active GPU reset, GPU command execution, full boot, and integrated screen remain incomplete.

## Initial-value observation mode and pending command candidates

In [optional trace-only recording](../hardware/display-gpu/gpu-raster-init-storage.md), RAST initial value 1 was recorded opaquely, and execution advanced to CONFIG read 1f0. Default remains the earlier 388 block, and rendering effects are unimplemented. The initial 25 candidate pairs and 35 word changes prepared by the CPU in RAM were confirmed. GPU execution, submission length, full boot, and screen are unverified.
