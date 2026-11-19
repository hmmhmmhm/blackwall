# Memory Protection Lifecycle After Reset

bw-0419. A defect was fixed in which CPU reset cleared I/O routing for main pages, letting data reads outside file range bypass the protection hook. Protection and side effects before/after reset were checked in 24 synthetic M55 guests. This is not verification of full original G2 boot or physical memory protection.

## Failure and cause

Existing model SHA256 is `330182ef865a41085daf853a2e5a8678049db8dd4fe2314fb3fe851939880d29`. Before the fix, 22 of 23 native-02 cases passed. The sole failure was `padding-read-2-device-aircr-true`: a `0x439000` read was blocked before reset, but afterward `0x47702009` from that location was recorded in guest results and the subsequent completion marker ran. Protection count was also 0. Writes and invalid code execution remained blocked.

[TranslationCPU](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Peripherals/Peripherals/CPU/TranslationCPU.cs) in pinned Renode infrastructure `cd4b002aac2398994c4a61a34a8b31b5700facf2` configures page I/O routing in tlib and calls TlibReset on Reset. [CPU common state](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/include/cpu-defs.h) in its gitlink tlib `167decf9129758829762e582939128c0694e90d6` puts `io_access_regions_count` and array in the reset-clear region. [ARM reset](https://github.com/antmicro/tlib/blob/167decf9129758829762e582939128c0694e90d6/arch/arm/helper.c) memsets that region. Even if the C# bus-read hook remains, a CPU directly reading MappedMemory does not reach it.

## Fix scope

`BlackwallMemoryPolicy.Attach()` subscribes once to `IMachine.PeripheralReset` and reapplies only main-page I/O routing immediately after the target CPU resets. Both full Reset and RequestResetInSafeState in pinned [Machine](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Core/Machine.cs) invoke this event after each peripheral.Reset.

Corrected policy SHA256 is `29daafce028464c94a217260df7cc0016617b8be3c158498b4dced63b6837c5e`. It does not install duplicate MMU windows, bus hooks, or block hooks and does not clear guest-written history of retained ITCM. Explicit Reset of the policy itself retains its existing history-initialization meaning. Direct CPU.Reset outside the machine is outside this support contract.

## Synthetic execution and controls

Guests use actual M55 instructions for boot counts, markers, and memory accesses. Reset is performed by virtual device AIRCR or guest AIRCR write; host does not reset PC/SP. Small synthetic images are distinct from original-main execution evidence.

- Main byte/halfword/word writes: blocked before and after reset, original word preserved. MMU callback width 0 is unknown.
- Execution of host-filled ITCM, main padding, and SRAM code: stopped before subsequent completion marker.
- Main padding data reads: stopped before and after reset without passing value to result marker.
- ITCM code written by guest on first boot: executed after reset without rewriting, returning 7 and retaining four guest-written bytes.
- Four protection-disabled controls: confirmed actual main-write changes or code return 9 and completion marker.
- Four guest AIRCR controls: checked main writes, unwritten ITCM, retained ITCM, and padding reads under the same policy.

Native-03's 24 cases and 299 behavior checks passed. Native-02 saved-log audit retains the sole failure (23 cases, 286 checks). Both compare actual logs, reports, execution scripts, policy, and ELF. Five counterexamples consistently tampering logs/reports for read bypass, changing execution script, omitting/duplicating policy, or incorrectly registering a candidate as baseline were rejected. native-01 is a C-string compilation-error artifact, not an ARM execution success.

## Original execution and reproduction

The three-original reset/restart recipe preserves defaults. Explicit `--memory-policy` replaces the pinned baseline exactly once and records candidate hash. The same pinned candidate path is passed to audit. Historical material is not made retroactively dependent on current development files.

```sh
<private-python> tools/probe_reset_memory_protection.py <simulator-root> <new-output>
<private-python> tools/verify_reset_memory_protection.py <capture> <pinned-policy.cs> <new-audit>
<private-python> tools/probe_reset_restart_versions.py <simulator-root> <new-output> --case stock24 --memory-policy <pinned-policy.cs>
<private-python> tools/verify_reset_restart_versions.py <simulator-root> <capture> <new-audit> --memory-policy <pinned-policy.cs>
```

Original integration regression results and source/capture pins are recorded in private `reset-memory-protection-research-01/manifest.json`. Synthetic material is in `reset-memory-protection-native-02/03`; original regression is in `reset-memory-protection-original-native-01`. No physical-device access, writes, Astra/subagents, or external publication occurred. Full E06 completion or six seconds of stable post-boot operation are not claimed from this narrow test alone.

All corrected-candidate stock 2.4, stock 2.3, and Faceclaw runs passed original reset-vector re-entry, original WFI/sleep caller, service reinitialization, new connection/ATT handling, and one RTC commit. Each has 31 saved audits and guard/fault/memory violations 0. Existing bw418 material was also re-audited under unchanged default recipe with 30/31/31 checks. New original runs replaced only protection policy, without changing original ARM, PC/SP, or branches.

E06 remains partially complete. This result covers restart and protection lifecycle in a pinned service/ATT scenario, not E05's incomplete required initialization and full app lifecycle. Next synthesize volatile/retained-domain declarations and evidence against acceptance conditions and audit E05 dependency. Scope v3 retains 16 conditions and eight completed (50.0%).

Follow-up bw420's [reset domain audit](reset-domain-acceptance-audit.md) also corrected a cache-helper enable/initialization-history retention defect. Pinned bw419 material remains unchanged and new candidates/captures are separate.
