# B0 power initialization and original recovery worker integration

2026-11-17 · bw-0576. Overall **10/12=83.3%**; BV05/06 authentication/recovery commands remain incomplete. This task connected **original reset → recovery worker → actual UART2 HELO → stock main reset** under separate synthetic B0/trim 1. It is not interpreted as actual G2 B0 compatibility or physical recovery success.

## Changes and evidence

`b0TonConfiguration`, default off, was added to `BlackwallHalStorage`. HAL owner requires explicit MCU revision 0x21 and runner allows only chip 21/trim 1. INFO1 metadata and HAL owners remain separate. Existing chip23/default TON write restrictions and B2 power contract remain.

- SIMOBUCK1/2/4/6/7: stores only public reset, HP enable bit 31, and six TON fields. Other bit changes and TON writes before HP enable are rejected before side effects. Power, analog, and factory-calibration accuracy are not claimed.
- MCUCTRL VRCTRL: public `buck_ldo_override_init` B0 initial-0-based ten steps are separated from existing B2 e000-based ten steps. The cause was the model's version assumption rejecting original first write `0x20000` without recording it.
- LDO: PCM0.7 uses core active trim reduction 6, mem active trim 0, MEMLDOREF 1. Existing B2 used reduction 7, mem 1, ref 2. Original `0x42f74a` instructions and pinned public PCM0.7 c/h were compared. New header Git blob was verified against pinned tree. Existing stages, cache observations, and mask rejection remain.

Pinned public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`, original current 2.3 patch SHA `7010d103…e55a7e`, and same-bundle main SHA `69f9ef63…13b9c` were used. `tools/run_upstream_boot_probe.py --b0-ton --chip-revision 0x21 --trim 1` composes only this group into the frozen model. No firmware modification, callback injection, forced branches, or fabricated factory INFO1 occurred.

## Actual execution results

| Saved run | Result |
| --- | --- |
| native01 | TON 7-field writes completed; strict stop on VRCTRL `0x20000` write at `0x41c7e8` |
| native02 | TON/VRCTRL passed; strict stop on core LDO reduction 6 write at `0x42f74a` |
| native03 | Override 10/buck 3/core applied/mem 2 completed; entered original worker and main |

Final observed order was boot-reset → boot-manager → storage-wrapper → patched-manager → power-slots-before-manager → patched-worker → marker-load → stock-handoff → main-reset, each once. Two Tempco slots were `[0,0]` as a result of original initialization. UART2 actually transmitted 21-byte HELO (version 2), including checksum. Full guest boot/main hashes matched inputs; CPU fault, policy, strict access, and missed observations were all 0. Runtime addition was only post-stop property export, compared against existing runtime with it removed.

This runner stops after observing main hit. It does not verify complete main boot/display. No authentication request or recovery command was sent. This path alone does not establish full timeout/retry handling or BV05/06 completion.

## Verification and cleanup

- **109 actual C# component checks** passed: default strict, B0 TON reset/mask/HP order, B0/B2 override, LDO contracts for both, and invalid-value rejection.
- Staged REDs: initial compile failure for missing new API, B0 VRCTRL strict rejection, and B0 core reduction mismatch. GREEN followed each fix; failure source/logs retained.
- **5 runner Python tests** and **39 frozen native/source audit checks** passed. Frozen audit-source.py was rerun in `/tmp` and the same 39 passed.
- Eleven owned native jobs confirmed removed. Runner cleaned twelve duplicate firmware files totaling **24,494,088 bytes**. Compile cache was removed with ephemeral containers; original inputs, source, hashes, logs, model, and failure diagnostics remain.

Final evidence: `private:simulator/upstream23-b0-ton-native-bw576-03/report.json`, `private:simulator/b0-ldo-unit-green-bw576-01/report.json`, `private:simulator/b0-power-recovery-audit-bw576-02/{report,cleanup-summary}.json`.

Next connect a virtual peer to the same B0 board's actual UART2 receive path to verify valid HMAC, invalid HMAC, and timeout/retry, then compare natural main entry after recovery-command completion. Reuse public source, keep test keys private, and use no physical serial/BLE.
