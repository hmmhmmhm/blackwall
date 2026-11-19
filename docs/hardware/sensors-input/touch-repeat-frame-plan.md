# Repeated touch report implementation plan

bw-0453. This is detailed implementation within the already approved E11 device-input and additional-lifetime verification scope. It does not define a new hardware FIFO, gesture meaning, or project scope. Design and implementation are performed by Codex alone; physical devices and CFW opcodes are unchanged.

## Design choice

Automatic repetition reuses the first frame and makes independent input hard to distinguish from duplication. An internal queue assuming a hardware FIFO lacks current source evidence. Therefore **explicit loading of the next report** is selected. The wire format pointer03 → 16 bytes/four chunks remains, and GPIO pulses are independent inputs. This virtual emulator input adapter is distinct from a claim about actual controller FIFO behavior.

Add default-off `reusableEventFrames` and host-only `TryLoadEventFrame(byte[])` to the existing peer. Copy exactly 16 bytes for the next frame only when the existing frame is fully consumed, IOM owner.Quiescent, and no configuration reply pending. Return false and preserve state for an unconsumed first frame, transfer in progress, completion IRQ/FIFO, duplicate loading, wrong size, or option off.

A new pointer03 write is still required after reload. A stale read from the previous pointer cannot consume the new frame. Read/completion counts accumulate and reload count is separate. Controller reset alone does not resupply the peer report. peer.Reset restores the original constructor fixture and initializes counters. An initial copy and host-buffer copy prevent aliasing.

## Sequence and judgment

- [x] Add reload success/rejection, distinct payload, stale read, host alias, and reset checks to existing unit harness; preserve current model failure.
- [x] Change one peer to implement the contract while retaining wire and existing defaults.
- [x] Run new units and existing one-shot/event/config/version controls to confirm the optional feature does not change single-report policy.
- [x] Connect two independent original M55 pulses → consumption of two reports in a bounded experiment. Preserve unsupported subsequent points with guards.
- [x] Pin model/source/execution and failure evidence, update work record/capability. Do not promote to complete E11 or pixel success.

Modified files are `tools/renode-iom-register-probe.cs`, `tools/verify_iom_register_probe.py`, and documentation of this implementation. Proprietary raw/native assets remain outside Git. Proceed as detailed model implementation within existing approval, without expanding into approval for new scope/architecture or physical work.

Result: [Repeated touch report lifetime](touch-repeat-frame-lifecycle.md). Natural execution was confirmed only on stock 2.4; E11 remains partial.
