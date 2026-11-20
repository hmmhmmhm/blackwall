# Emulator report quickstart

> **Availability:** A fresh public checkout cannot currently reproduce this report because the pinned Docker image is not yet available. The stock model is included, and its initial memory fill patterns can be generated automatically. The report runner supports one pinned stock 2.4 boot/main pair; Faceclaw and other custom firmware are not selectable here.

## Required files

You need Python 3.9 or later, a running Docker installation, and the pinned Renode Docker image. Host Python manages commands and reports; Renode runs in a network-isolated container. No glasses are connected or flashed.

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

To move the pinned Renode image to another Docker environment, export it from the existing environment with `docker image save -o blackwall-renode.tar blackwall-renode:1.17.0-local` and import it on the target with `docker image load -i blackwall-renode.tar`. Rebuilding the [Dockerfile](../../tools/renode-container.Dockerfile) does not guarantee the same image ID. Other CPU architectures require Docker support for running arm64 images.

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
