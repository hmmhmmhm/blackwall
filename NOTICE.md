# Upstream sources

Blackwall's offline research uses the pinned repositories listed in
`docs/data/upstream-snapshot.json`. No proprietary firmware is included in Git.

`tools/blackwall_package.py` adapts the boot layout, hook validation and Thumb BL
decoding from `drdaeman/g2-bootloader-patch`, commit
`6198d70e18293caebf8314d2e40bd3b1d0a5ee16`, `tools/g2patch/firmware.py`.
The applicable MIT license is reproduced in `licenses/g2-bootloader-patch.txt`.

Faceclaw and g2flash are GPL-3.0 sources. Local generated CFW files remain outside
Git. Their source, license and build provenance must accompany any future
distribution under the applicable license; this notice is not a distribution
authorization or a substitute for those obligations.

`web/ota-packets.mjs` adapts the same pinned upstream commit’s
`tools/g2patch/ble_ota.py` under MIT. Its fixtures contain synthetic counter bytes, not firmware.

`web/component-ota-session.mjs` also adapts the pinned MIT `ble_ota.py` flow.

The Renode evaluation uses the official Linux ARM64 1.17.0 portable release;
its archive digest and runtime image identity are recorded in the simulator docs.
Renode is MIT licensed; the root license is reproduced in `licenses/renode.txt`,
and dependency licenses remain in the unmodified external runtime archive.
`tools/renode-watchdog.cs` is a bounded Blackwall model using Renode's timer/GPIO
APIs and public Apollo510 register definitions, not the unmodified Apollo4 model.
Reviewed upstream source revisions and the observed differences are recorded in
`docs/architecture/emulator-reuse-research.md` and `docs/architecture/renode-watchdog-model.md`.

`docs/data/gpu-sdk-register-map.json` derives diagnostic constants from Think Silicon
NemaGFX headers in AmbiqMicro/ambiqhal_ambiq commit
`d3278ec49a534728384537557dd44b205ec72129`. The header permission notice, including
the normative-version warning, is reproduced in
`licenses/think-silicon-nema-headers.txt`. The catalog supplies names and offsets,
not GPU behavior. Original headers remain in the private research snapshot.

`tools/nema-ring-consumer.cs` also uses register offsets and MMUL flag names
from those pinned headers. Its binary-solid raster profile is Blackwall's
explicit functional model; it does not incorporate a vendor GPU implementation
or establish shader-ISA or physical raster equivalence.

`tools/timer14_engine_source.py` adapts Renode infrastructure's
`AmbiqApollo4_Timer.cs`, commit `066a7f13c052215632d469c995c89aea37c573b1`,
under MIT. The original copyright banner is preserved in generated source;
`licenses/renode.txt` reproduces the license. Pinned original source and its
license hash remain in the external research directory. Apollo510 field and
clock adaptations and engine timing limitations are described in
`docs/hardware/power/timer14-counter-model.md`.

The NOR KVDB investigation references RT-Thread-packages/fal commit
`aa0211218634a613d3638425a830854bd07a0b76` and armink/FlashDB commit
`360a68d0b1f9f02b0d597a9f08c141e28b332c1e`, both Apache-2.0.
Pinned source and license files remain in the private research snapshot;
the analysis does not identify the exact library versions linked into G2 firmware.
See `docs/hardware/cpu-memory/nor-kvdb-region-contract.md` for provenance and comparison limits.

`docs/data/imu-gaf-default-profile.json` records parameter names, addresses, sizes and
published defaults from TDK/InvenSense ICM45608 `inv_imu_edmp_memmap.h`, commit
`646f55a6ec119b59d9ebce47af660842b53e5506`. The file-specific permission/as-is
notice is reproduced in `licenses/tdk-invensense-edmp-memmap.txt`. This is an
explicit research input profile, disabled at runtime; it does not certify the
ROM defaults or internal algorithm version of a physical G2 sensor.

`BlackwallImuGafParameters` in `tools/renode-imu-identity.cs` uses the same pinned
TDK field-address/size map. Its ordered read fixture is Blackwall implementation;
it does not incorporate the sensor ROM or implement GAF sensor fusion.
