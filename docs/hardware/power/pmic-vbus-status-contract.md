# VBUS Status Query Contract After Advertising

bw-0301. IOM7 payload `02 07` requested by three originals after [advertising initialization](../communication/advertising-initialization-peer.md) was investigated. Peripheral models and native execution were not changed in this work.

## Public specification and original request

[Nordic's current register map](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/vbusin.html-topic?contentId=I_u18WjSiVeUsCOQmx7zgw) defines VBUSIN base `0x0200` and VBUSINSTATUS offset `0x07`. Bits 0–5 of the [status register specification](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/vbusin.html-register.vbusinstatus?contentId=hcauA_AwKIXg1Tl5z_b3Yg) represent VBUS presence, current limit, overvoltage, undervoltage, suspend, and VBUSOUT status. The upper two bits are not defined status fields. Documented reset 0 does not mean actual current G2 state.

The [VBUS driver](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_vbusin.c) in pinned npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` reads one byte from the register. Existing tree/source-manifest SHA-256 and Git blob, ADK read-only offset, and six fields were reverified. Nordic code was not copied or compiled as an execution model. Driver and ADK license scopes remain as in existing research records.

| Input | Original wrapper | Call site | Internal status byte |
| --- | --- | --- | --- |
| Stock 2.4 | `0x5801ac` | `0x50044e` | `0x20076551` |
| Stock 2.3 | `0x57d174` | `0x52e06a` | `0x20076f19` |
| Faceclaw38 | Same | Same | Same |

Original wrapper reads the instance backend pointer and passes register `0x0207`, output pointer, and length 1 to the backend. Each image has one pinned wrapper instruction prefix and one BL calling it. Actual natural execution is blocked at pointer request, so status-byte reception itself is not yet evidenced as complete.

## Isolated consumption behavior

Original ARM code and verified full native SRAM were used in Unicorn M7. Stack, instance, and post-call registers are explicit synthetic inputs. This is not presented as natural M55 execution skipping hardware checks or injecting actual backend success.

- Wrapper ran until immediately before backend entry to compare actual arguments and length 1.
- Original return-success comparison constant was `0x2bad0000`. The consumer fragment after a successful call ran for all byte values 0–255. After executing through the original setter, internal status byte matched `status & 1`; final values in remaining SRAM were preserved. This final comparison is not generalized as proof that all transient writes were absent.
- Testing 0–255 including undefined upper bits checks software masking; it does not mean actual PMIC or a new model must allow those values.
- Return values 0, 1, bit changes to the success constant, and `0xffffffff` branched to the error-logging boundary before status consumption. Execution stopped there; the entire error handler or recovery success was not tested.

A total of 3 × (one wrapper + 256 successful consumptions + four error branches) = **783 bounded ARM fragments** were verified. Repetition with 54 frozen dependencies produced byte-identical report and two tool files. Four existing peripheral model hashes were unchanged. Evidence is `private:simulator/vbus-status-verification-01/manifest.json`; tool is `tools/inspect_vbus_status_contract.py`.

## Next model scope

Default remains unknown and blocked. The next experiment separately selects explicit `test-vbus-absent` (0) and `test-vbus-present` (1) snapshots for comparison. These are virtual inputs assuming power conditions, not determinations of current actual glasses state. Connect only read-only one-byte status and pointer/STOP contract; do not automatically generate voltage, charging, rails, VBUSOUT, or events. Reject unknown bits, bursts, and status writes.

Then observe branches and subsequent PMIC, app, and display boundaries in original M55 under both conditions. This stage does not establish full boot, app loop, integrated display, or real-device installation. Overall scope v2 remains 13/29=44.8%.
