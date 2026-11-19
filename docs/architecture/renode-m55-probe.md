# Renode M55 Instruction and Exception Execution Test

Status: Independent M55 test code ran on Linux ARM64 Renode. Full G2 boot and reproduction of Apollo510B peripherals were not yet verified.

## Execution environment

Separate from the Mac native CoreCLR startup failure, the official Renode 1.17.0 ARM64 portable distribution started in OrbStack's installed Linux Docker environment. Its bundled runtime is .NET 8.0.16. Do not confuse this with separately installed Mac .NET 8.0.33.

Linux archive SHA-256:
`e9051578411441bfb47b77de0381cfba3badce03663367fab561472fd7807f1f`.
It was confirmed to match the official GitHub release asset digest. The base Debian image digest is `734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc`. `tools/renode-container.Dockerfile` rechecks the archive hash. Apt packages depend on repositories at build time, so the recipe alone does not guarantee an identical image. Each execution report records the actual immutable image ID.

The final test image ID is `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649`. The image contains only public Renode and OS dependencies, not stock images or device backups.

## Actual test code

`tests/fixtures/m55-exceptions-smoke.c` is built as an ARM Cortex-M55 ELF with LLVM/LLD 21. After building, disassembly is checked for actual `vdup.32` and `vadd.i32` instructions. The test board has only M55/NVIC and two 64 KiB memories; it is not called a G2 board.

| RAM mailbox | Meaning | M55 observed value |
| --- | --- | --- |
| Word 0 | Entire test complete | 0x600d |
| Word 1 | IPSR read in SVC | 11 |
| Word 2 | IPSR read in PendSV | 14 |
| Word 3 | IPSR of software-pended external IRQ0 | 16 |
| Word 4 | SysTick handler count | 3 |
| Word 5 | IPSR read in SysTick | 15 |
| Word 6 | Result of doubling 7 with MVE vectors | 14 |
| Word 7 | Fault-handler entry number | 0 |

A virtual interrupt returned from WFI waiting for SysTick; after three occurrences SysTick was disabled and the completion value written. This is execution evidence for that virtual CPU/interrupt path. It does not verify actual G2 clock, sleep/wakeup, power consumption, interrupt wiring, or correctness of all MVE instructions.

In a control running the same ELF on M4F, HardFault (IPSR=3) occurred at the MVE segment and the remaining mailbox values were zero. It was assessed only as the expected control result, not correct completion. This supports not assuming the current Unicorn main runner can substitute for all M55 instructions.

## Reproduction and isolation

Use a separate build-context folder containing the official Linux archive.

```sh
docker build --platform linux/arm64 -f tools/renode-container.Dockerfile \
  -t blackwall-renode:1.17.0-local \
  "$HOME/Library/Application Support/Blackwall/simulator/renode-linux-1.17.0"
python3 tools/run_renode_m55_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-m55-probe"
```

The tool accepts only new output paths and retains compiler/disassembly/version logs, both CPU execution logs, and a structured report. Execution uses the image ID. The container runs with network none, 512 MiB, one CPU, 128 PID limit, removed capabilities, and no-new-privileges. Only its own test folder is mounted read-only; actual devices, Docker socket, and other projects are not mounted. Each task uses a unique container name and cleans up only that container on timeout or failure.

The final execution record is outside Git at `Blackwall/simulator/renode-m55-smoke-04/`. The existing native .NET error is not claimed resolved; the Linux path made CPU testing possible. Next was checking behavior differences in Apollo4 peripheral models and connecting G2 main execution to Renode. Migration of the main runner was not yet decided.

Subsequently, [actual G2 main startup code](renode-main-probe.md) was connected. Two stock versions and Faceclaw reached the first power-register read and matched the existing Unicorn runner's address, width, and PC. Full board port and boot remained incomplete.
