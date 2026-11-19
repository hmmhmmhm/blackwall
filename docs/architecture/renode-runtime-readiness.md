# Renode Runtime and Register Reuse Readiness

Status: Mac native CoreCLR startup failure remains unresolved. Later, Renode ran in a Linux ARM64 container and passed [M55, MVE, and exception tests](renode-m55-probe.md). The existing Unicorn runner was retained.

## Installation checks

Following [Renode installation instructions](https://renode.readthedocs.io/en/latest/introduction/installing.html), the official v1.17.0 Apple Silicon portable distribution was selected. The archive is 75,720,019 bytes, SHA-256 `63b1fb691207f503cea937e4ec8fad3e068a517d0abac3c24c0206c62f6c4d12`. It was confirmed to match the GitHub release asset digest; the disk image was mounted read-only, copied, and unmounted. The app was not registered in Applications or system PATH.

Renode's bundled runtime is .NET 8.0.21. Execution produced CoreCLR HRESULT 0x8007000C, and an attempt selecting system .NET 10 produced the same error. Host traces showed that Renode continued selecting the bundled CoreCLR in its own folder, so this was not a successful .NET 10 comparison.

With user approval to install .NET 8, osx-arm64 runtime 8.0.33 was downloaded from Microsoft's official [8.0 release metadata](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/8.0/releases.json) and its official SHA-512 checked. This was not an SDK installation. It is outside Git at `Blackwall/simulator/dotnet-8/8.0.33/`; existing .NET installations were not changed. Archive URL, hash, and installation path are retained in manifest.json in the same parent folder.

Running a separate probe folder containing only a copy of Renode.dll and no bundled CoreCLR with .NET 8.0.33 produced the same error and exit 137. This cannot be explained solely as a bundled-runtime path problem. The exact host cause remains unconfirmed; system security settings were not changed. Execution records and traces are retained in `Blackwall/simulator/renode-1.17.0/`.

Subsequent native diagnostics: MAP_JIT allocation and first executable-memory setup succeeded. In LLDB, the seventh mprotect failed while changing a 16 KiB page to RW; the caller was EEStartupHelper via VirtualProtect. This was interpreted as consistent with the public runtime's InitGSCookie path. The exact macOS-side reason for rejection was not established. CPU tests proceeded in Linux without modifying runtime code or system security settings.

## Source checks independent of execution

`tools/audit_renode_register_layout.py` checks hashes of existing pinned Renode source and Apollo510 headers, then compares locations of selected timer/STIMER, watchdog, and power registers. Apollo510 C structs are extracted from the original header, and ARM Cortex-M55 Clang actually compiles `_Static_assert(offsetof(...))` against Renode enum offsets.

Thirty-two register locations matched. This verifies locations only, not bit meanings, reset values, IRQ, FIFO, clocks, power behavior, or model implementation scope. Cases with differing meanings at the same location, such as NVRAM2 and HALSTATES, are separately marked. Do not extend matching some registers into full peripheral compatibility. Nor is this presented as a passed CPU execution test.

Reproduction example:

```sh
python3 tools/audit_renode_register_layout.py \
  "$HOME/Library/Application Support/Blackwall/simulator/emulator-reuse-research-01" \
  "$HOME/Library/Application Support/Blackwall/simulator/upstream/hal-ambiq-61b293a/apollo510.h" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-renode-layout-audit"
```

The output folder must be a new path. C files containing original headers and objects remain outside Git. Results are retained in `Blackwall/simulator/renode-layout-audit-01/`. Next was investigating runtime startup and behavior/IRQ/clock differences for matching register locations. Migration to Renode was not yet decided, and actual glasses were not accessed.
