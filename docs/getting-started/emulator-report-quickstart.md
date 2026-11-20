# Emulator report quickstart

> **Current support:** The stock model and pinned Renode container are available, and initial memory fill patterns are generated automatically. The stock report runner supports one pinned stock 2.4 boot/main pair. A separate `faceclaw38` command starts the pinned Faceclaw 38 main image at its reset vector; arbitrary custom firmware is not supported.

## Required files

You need Python 3.9 or later, a running Docker installation, and the pinned Renode Docker image. Host Python manages commands and reports; Renode runs in a network-isolated container. No glasses are connected or flashed.

Pull the public image by manifest digest. It is a Linux ARM64 image; other CPU architectures require Docker support for ARM64 emulation.

```sh
docker pull --platform linux/arm64 ghcr.io/hmmhmmhm/blackwall-renode@sha256:4f5f20c390e8c0d2b6336cdb708023cd2110e98ebaed9ae59f995bc057cbc0f8
```

The resulting image ID must be `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649`. The manifest digest and image ID identify different objects.

For the stock profile, the virtual hardware model is included and the SRAM/ITCM initial patterns are reproducible synthetic `0xa5` fills. Missing fill files are regenerated and checked against the pinned hashes during setup. You must provide the matching stock bootloader and main images; firmware is not included. Other research profiles may still require private files.

```sh
python3 blackwall assets --source /path/to/support-files
```

This command prints the relative paths and SHA-256 hashes required by the profile. Select a profile with `--profile stock`, `timed`, `detailed`, or `imu`, or use the default `auto` selection.

## Prepare the Docker volume

Check and store the input files in a new volume once. You can specify the bootloader and main image paths separately.

```sh
python3 blackwall setup --source . --profile stock \
  --boot-image /path/to/boot.bin --main-image /path/to/main.bin
python3 blackwall doctor
```

If the images already exist at the profile paths under the source directory, both image options can be omitted. Files are stored only after validating profile sizes, SHA-256 hashes, vectors, and model hashes. The default volume is `blackwall-assets`. To use another name, pass the same `--volume NAME` to `setup`, `doctor`, and `report`. Existing volumes are not overwritten.

The image can also be moved with `docker image save` and `docker image load`. Rebuilding the [Dockerfile](../../tools/renode-container.Dockerfile) does not guarantee the same image ID.

For development, the Dockerfile's build context must contain the official [Renode 1.17.0 Linux ARM64 portable archive](https://github.com/renode/renode/releases/download/v1.17.0/renode-1.17.0.linux-arm64-portable.tar.gz), named `renode-1.17.0.linux-arm64-portable.tar.gz`. Its expected SHA-256 is `e9051578411441bfb47b77de0381cfba3badce03663367fab561472fd7807f1f`; the Dockerfile verifies it. Build using `docker build --platform linux/arm64 -f tools/renode-container.Dockerfile -t blackwall-renode:dev .` with the archive in the repository root. A rebuilt development image is not automatically accepted by the pinned report runner; use the published image above for the reviewed profile.

## Run stock firmware

```sh
python3 blackwall scenarios
python3 blackwall report --scenario normal --serve
```

To specify different files for a run, add `--boot-image` and `--main-image`. The inputs must match the profile in the volume. The specified images are copied into the run directory; the originals and the volume are not modified.

```sh
python3 blackwall report --scenario normal --boot-image /path/to/boot.bin --main-image /path/to/main.bin --serve
```

Open the address printed by the command to view the report, and press `Ctrl-C` to stop the server. By default, output is created in the system temporary directory; you can select another location. The output must be a new directory outside the repository.

```sh
python3 blackwall report --output /path/to/new-report --serve --port 8766
python3 blackwall report --scenario-file scenarios/screen-boot.json --serve
python3 blackwall report --capture /path/to/old-report/run/capture --output /path/to/new-audit
```

Re-auditing requires the inputs retained in the original report directory. **The report directory contains copies of firmware and model inputs.** Do not add it to Git or share it; manually remove a run directory only when it is no longer needed. The original inputs and Docker volume are not deleted automatically.

[Normal scenario](../scenarios/normal.md) · [Rejection scenario](../scenarios/unknown-boot-marker.md) · [Custom scenarios](../scenarios/custom-scenarios.md) · [Original boot reproduction](../bootloader/original-boot-reproduction.md)
