# RTC Module Contract and Existing Model Reuse Investigation

bw-0129. This module-level investigation supports continuing from the current original main stop at RTC.RTCCTL. The existing Apollo4 RTC was not connected merely because its address matched; Apollo510 material, HAL, and original code were compared, and differences reproduced in isolated virtual-time tests. These tests did not execute original main.

## Pinned material and reproduction

- Renode infrastructure `066a7f13c052215632d469c995c89aea37c573b1`, [AmbiqApollo4_RTC.cs](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Timers/AmbiqApollo4_RTC.cs), MIT. SHA256 `dc22ac4df09190011dd70cce0e03b2eabace64246c4118d58e681a26d8623dc9`.
- HAL `61b293a49db34030c545f99101f7ebf6a3050314`, [am_hal_rtc.c](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_rtc.c), BSD 3-Clause terms. SHA256 `faccd6d5aa9774f2fd71d1f19b45881d80bc6294dddf4830de53d87179df60f9`.
- Existing pinned Apollo510 SVD/header. SHA and source provenance are preserved in `rtc-osel-source-01` and `rtc-module-research-01`. New GitHub sources were also checked against Git blob SHA in the pinned tree.

`tools/probe_rtc_reuse.py` changes only two class-name occurrences in the pinned original source, preserves the MIT header, and compiles it in isolation. A newly written two-byte ARM spin guest advances virtual time. It uses the existing pinned Docker image and is distinct from device, BLE, USB, or original firmware execution.

```sh
python3 tools/probe_rtc_reuse.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/rtc-reuse-probe-new"
```

Pinned sources from private `rtc-module-research-01` and the existing SVD/header are required. Original firmware and proprietary assets are not placed in Git.

## Reusable portions

SVD and C header compilation confirmed RTC base 0x40004800, IRQ 2, and offsets of 10 registers. These match the existing model layout: control 0, status 4, counter 20/24, alarm 30/34, IRQ 200/204/208/20c. Matching addresses do not establish matching field semantics, initial state, or timing.

Fifteen virtual tests confirmed candidate behavior:

- From explicit start 2000-01-01, hundredths=3 after 30 ms, retained during 50 ms stopped by RSTOP, and hundredths=5 after 20 ms resumed.
- Software INTSET state does not raise IRQ while masked; after INTEN it appears in IRQ level and NVIC pending 2, and INTCLR lowers the level. This is not an alarm occurrence or actual CPU ISR execution test.
- Candidate lower → upper writes change busy from 1 to 0 and commit a year 2000 value.

This supports reuse of the candidate's virtual clock/calendar/IRQ foundation; it is not an Apollo510 hardware compatibility pass.

## Differences preventing direct installation and conflicting sources

| Item | Pinned Apollo510 material | Candidate model/test result |
| --- | --- | --- |
| CB century bit | SVD: 1 for 2000s, 0 for 2100s | Explicit 2000 reads 0, 2100 reads 1 |
| Late split counter read | SVD: CTERR if upper is not read within 1/100 second | Reading UP 20 ms after LOW just before midnight still gives CTERR 0 and next day's date |
| Counter write order | SVD WRITEBUSY description says UP → LOW | HAL uses LOW → UP; candidate also commits LOW → UP |
| 24-hour disable bit | SVD HR1224 bit 5 value 1 disables 24h | Candidate treats bit 5 as reserved |
| Unsupported address/width | Blackwall default is strict stop | Candidate uses general peripheral default handling and permits byte/word translation |
| Century rollover | SVD CEB notes ERR129 restriction | General DateTime behavior does not establish that silicon erratum |

CB and split-read results are preserved in `private:simulator/rtc-reuse-probe-01/report.json`. `drop_in_compatible=false`; the 15 checks include reproducing mismatches. This is not described as passing an RTC compatibility test. The SVD descriptions themselves were not verified on target silicon.

To narrow the write-order conflict, adjacent candidate writers in two original versions and CFW were statically analyzed. `tools/analyze_rtc_writer.py` checks original hashes, instructions, and literal pools and found these stores:

| Original | CTRLOW store | CTRUP store |
| --- | --- | --- |
| Stock 2.4 | 0x507074 | 0x5070c0 |
| Stock 2.3/Faceclaw38 | 0x4e87e8 | 0x4e8834 |

Material is `private:simulator/rtc-writer-static-01/report.json`. It is evidence that LOW → UP is laid out in the candidate code, not evidence of actual reachability, execution order of all branches, successful writes, or silicon behavior. Function names were inferred without symbols from HAL shape and adjacent instructions and are not established.

HAL time_get also waits for a STIMER or internal TIMER clock edge before counter reads. Modeling only RTC read and bypassing that wait with a success return would undermine original-path verification. This timer dependency must also be supported in the original path or remain a strict boundary.

## Next implementation direction

Direct installation, full reimplementation, and a limited adapter were compared. Direct installation would hide the differences above; full reimplementation would duplicate existing clock/calendar/IRQ code. A **strict adapter based on the pinned candidate** is recommended.

- State virtual epoch and 100 Hz clock assumptions explicitly, separating them from host real time and actual oscillator state.
- Check defined addresses, 32-bit accesses, and field masks at the adapter boundary and reject unknown behavior.
- Separately verify century encoding, coherent split reads, and CTERR against the Apollo510 contract.
- Do not conceal conflicting write-order/busy sources. Test against the observed original LOW → UP path and explicit virtual profile without elevating it to silicon verification. Block unsupported orders in advance.
- Keep ERR129, 24h disable, and unobserved clock effects unsupported or unknown until implemented/verified.

The adapter has not been implemented or connected to original main. The latest original endpoint remains RTCCTL read. Full boot, integrated display, and real-device recovery verification remain incomplete; product conditions are 13/29. Astra was not used.
