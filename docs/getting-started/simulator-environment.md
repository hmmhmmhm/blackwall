# Persistent local simulator environment

> This document records an earlier research environment. For current installation and execution, use the [Docker volume guide](emulator-report-quickstart.md).

A separate environment was created on the current Mac so execution does not depend on a temporary research virtual environment or input directory. It does not include physical-device connectivity and is not evidence of a complete G2 simulator or installation compatibility.

The historical base path is `~/Library/Application Support/Blackwall/simulator/`.

| Path | Contents |
| --- | --- |
| venv-02/ | Validated Python 3.14.4 environment, Unicorn 2.1.4, and Capstone 5.0.9 |
| wheels/macos-arm64-py314-01/ | Two hash-pinned wheels |
| inputs/verified-01/ | Pinned stock 2.3, stock 2.4, and Faceclaw38 bundles with file manifests |
| upstream/g2flash-845f665/ | Independent Git clone of pinned upstream source |
| startup-stock24-02.json | Stock 2.4 reset execution result in the new environment |
| renderer-sequence-02/ | Four-frame PNG, raw data, and report built and run in the new environment |

`venv-01` and the first execution results were also retained. The new clone was created without hardlinks or Git alternates. Input bundles were checked against existing pins and SHA-256 and retained outside Git with mode 0600. They are not firmware bundles for sharing or public distribution.

## Create an offline environment

The pinned wheel set is **macOS arm64 and Python 3.14** only. Other OS/Python combinations are not automatically accepted. Exact filenames, versions, and SHA-256 values are in `tools/simulator-wheels.json`.

```sh
python3 tools/setup_simulator.py \
  --wheels "$HOME/Library/Application Support/Blackwall/simulator/wheels/macos-arm64-py314-01" \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-venv"
```

The output must be a new path. The tool first checks wheel hashes and platform, and rejects paths inside the repository and attempts to overwrite an existing environment. After creating the virtual environment, it installs only local wheels using pip in Python isolated mode with `--no-index --require-hashes --only-binary=:all:`. It does not build from source or automatically upgrade versions. Failed intermediate outputs are not deleted, and an environment without `blackwall-environment.json` is not considered complete.

The completion report records the wheel-lock hash, Python and package versions, and actual module paths. It fails if modules load outside the new environment. The environment's distribution packages are limited to pip, Unicorn, and Capstone; it contains no BLE, serial, or PyObjC packages. This package list is not itself a security sandbox for all system access, although the tools actually run have no device-access path.

The initial wheels were acquired through a separate pip download, and both files were retained in the local cache. Environment creation does not use a network index. The generator fails if a wheel is missing and does not automatically fetch it.

## Execution checks

Ran stock 2.4 and `startup-shadow-mram-hypothesis` in `venv-02`. Execution stopped at PC `0x48` with `unsupported-memory-access` on a read of `0x42003310`. This was the same boundary as in the prior temporary environment; arbitrary information-region values were not supplied to declare boot success.

Also rebuilt the renderer using the pinned clone and `tests/fixtures/renderer-sequence.json`. It generated four distinct 576×288 frames and rechecked the SHA and PNG dimensions for each 82,944-byte packed framebuffer. Every frame matched the ARM/native result byte-for-byte, and the framebuffer guard was preserved. This was an isolated `draw.c` execution, not the full firmware display path. The renderer build separately used the existing LLVM/LLD 21 and Apple clang.

Three environment-generator tests also passed: rejection of tampered wheels before environment creation, preservation of existing output, and rejection of output inside the repository. Full boot, display transport, sensors, codec communication, and power/timing reproduction remain incomplete.

For run commands, see [simulator usage](../architecture/simulator-usage.md).
