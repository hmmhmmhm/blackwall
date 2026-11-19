# Original MSPI0 Power Request Contract

bw-0303. Compared the power request following [VBUS consumption](../power/pmic-vbus-status-model.md) with original main, pinned SVD/header, and HAL source. Models, native execution, and actual devices were unchanged.

The original request sets MSPI0 bit 14 (`0x4000`) in `DEVPWREN(0x40021004)`. SVD enable/status fields match the MSPI0 table in public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`. Header, SVD, and HAL source pins were checked. Rather than copying a public enum number directly to G2, verified the original's **enum 16** table entry `[0x40021004, 0x4000, 0x40021008, 0x4000]` directly.

Stock 2.4 power entry/store are `0x494ca0`/`0x494d78`; older stock/Faceclaw are `0x488db8`/`0x488e90`. The original MSPI function adds `0x10` to handle module 0 to produce this enum. Current handle magic is `0x01bebebe`, and retain argument is false. ORing `0x4000` into existing shared enable word `0x0e00` produces request `0x4e00`.

After this write, the original waits for the status mask. The upper MSPI function does not check the power function's return; on the retain=false path it stores 4 in the handle's state byte and requests clock command 4, enum 16. Synthetic return values 0, 1, 4, and `0xffffffff` all reached immediately before the same clock call. This alone does not guarantee safe fallback after status timeout or a power check inside the clock function.

The model at that point has only an MSPI1 owner, no MSPI0 owner. Bit 14 is absent from the shared power bank's allowed mask, so the request is rejected. Do not interpret this stop as actual MSPI0 power failure or failed reactivation.

Executed original ARM in Unicorn M7 using synthetic stack/registers and full native SRAM. For each image checked three table-loader conditions (normal/null/out of range), five read-OR-store conditions, and four post-call return-value conditions, verifying **36 fragments** total. In store tests the status word retained its sentinel, confirming that a ready value was not manufactured. This differs from complete natural M55 boot or actual power-response testing.

Repeated with 67 pinned dependencies; report and tool matched byte for byte. Six existing model hashes were unchanged. Tool: `tools/inspect_mspi0_power_contract.py`; evidence: `private:simulator/mspi0-power-verification-01/manifest.json`.

Next connect an optional MSPI0 owner to the same shared bank. Retain default unattached blocking and distinguish active/stuck-off. Preserve other owner bits and reject reserved or simultaneous changes. MSPI0 clock, registers, bus, DMA, and display remain unsupported while observing the actual original's next request. Do not automatically permit shutdown lifetime behavior without source and quiescence contracts. Scope v2 remains 13/29 = 44.8%.
