# Connecting Virtual Web Installation, RAM Storage, and ARM Handoff

bw-0241. The browser virtual-installation screen and existing OTA session were connected to RAM storage. A separate CLI passes the storage image installed by the same modules to the original ARM handoff test. **This does not validate actual OTA acceptance, normal boot, or physical recovery.**

Later bw244 [recovery-owner research](../bootloader/recovery-owner-flow.md) separately confirmed compiled worker authentication → RAM-call entry. It did not connect retransmission from the virtual OTA storage below to actual recovery boot/transport.

## Implemented flow

`web/simulator.html` → `virtual-app.mjs` → existing `ComponentOtaSession`/packet encoder → `VirtualTemple` independent fragment/CRC parsing → virtual staging → application to RAM address ranges. The actual installation screen does not call this path; `installable=false` in the catalog and the block before chooser remain.

Each VirtualTemple represents one side. Boot is placed from 0x410000; main from 0x438000 after excluding the 128-byte OTA header and 32-byte preamble. The range ends at 0x7f8000. Wrong side, unsupported boot version, hash, range, and concurrent operations are rejected. This profile is a virtual test configuration for the 2.4 research boot and pinned main, not an actual mixed compatibility profile.

Browser state exists only in page RAM. File selection is local and does not call network or Bluetooth. The server serves only web/ and does not serve firmware or recovery keys.

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

Then open `http://127.0.0.1:8765/simulator.html`. The review server has already been stopped.

## Virtual failure model and limitations

| Condition | Storage/session result |
| --- | --- |
| Disconnect before END | Only model staging remains; active RAM is preserved. No automatic retry |
| Corrupt fragment CRC | staging-rejected, session outcome-unknown. Nothing applied |
| Interruption during apply | In-place writes stop at the specified byte; apply-interrupted. Damaged state is not automatically reverted |
| END response lost after apply | RAM actually changed, but applied-acknowledgement-lost / outcome-unknown |
| Separate explicit stock transfer | Only stock main body restored. Boot, other temple, and existing bytes outside the body are preserved |

The ordering that applies at END after staging and byte-level fault injection are a **synthetic model**. They were not implemented by reverse-engineering actual stock OTA storage, application timing, or erase granularity. Generic virtual transport is called independently of the main CPU. A test that can invoke another transfer after corruption must not be interpreted as actual BLE reconnection or UART2/case recovery. Actual transport availability after failure and connection to the recovery boot manager remain absent.

CFW raw main is 3,829,832 bytes and stock raw main 3,700,068 bytes. Rewriting the shorter stock body leaves a **129,764-byte CFW residual region** and patched boot. Do not present this as full-stock restoration. No unsupported tail erase or boot restoration was added automatically.

## From stored image to original ARM

`tools/simulate_web_install.mjs` transmits actual pinned components through the existing session to generate MRAM copies for CFW, interrupted stock apply, restored stock, and interrupted boot apply outside Git. Output inside the repository is rejected; copies use 0600 and directories 0700.

`--virtual-install` was added to the existing `tools/emulate_combined_handoff.py`.

```sh
blackwall_private="$HOME/Library/Application Support/Blackwall"
"$blackwall_private/simulator/venv-02/bin/python" tools/emulate_combined_handoff.py \
  "$blackwall_private/recovery/private-boot-24-candidate-01" \
  "$blackwall_private/recovery/web-components" \
  --output "$blackwall_private/simulator/my-new-run/report.json" --virtual-install
```

Create the report's parent folder first and specify a new output. Do not supply the actual key as an argument. The CLI performs Node virtual installation, verifies snapshot SHA and all pinned boot/main bytes, then uses **bytes extracted from storage** to execute original boot data initialization, patched handoff, and stock vector leaf.

Two hooks/four selection conditions each for CFW and restored stock, 16 conditions total, passed up to immediately before reset entry. Two main/boot copies corrupted by partial writes were rejected by the complete-byte check and not executed. The starting PC is the existing limited-test hook; R0, selection, and initial memory are synthetic. This is not evidence of natural complete boot from ROM or execution of the main reset body.

The browser does not call the ARM engine. Browser UI → common modules → RAM and Node common modules → RAM → ARM were checked separately; connecting a single browser operation through ARM execution remains outstanding.

## Verification

- Existing 53 web tests plus nine new tests: **62 passed, zero skipped**. Four actual private components were used.
- Virtual storage: separation of both temples, preservation of boot/main, wire corruption, partial boot/main apply, lost response, busy/range/read copy, and stock-body restoration were checked.
- A Faceclaw file was selected in dedicated minimized Safari window 9505. Left RAM readback SHA matched original raw main `4118af85…8dd8f`; right partial apply preserved left state and displayed outcome-unknown.
- Install/confirmation disabled was confirmed on the original installation screen. This was DOM functional review, not image-based visual review.
- The task Safari page was closed, server PID 30043 stopped, and listener 18766 confirmed absent. A hidden zero-tab record retained by Safari was not controlled again. Shared Safari was not quit.
- Private `simulator/virtual-web-install-handoff-01/report.json`: 16 original ARM conditions and two corruption rejections.
- Private `simulator/virtual-ota-storage-verification-01/report.json`: 26 checks and retained source/log/browser results. Browser session material is in private `work/virtual-web-ui-01`.

W5 is updated to partial. Complete UI → normal startup → independent recovery from failure/full stock, physical compatibility, and installation approval remain incomplete. Product progress 13/29 = 44.8% and scope v2 remain unchanged. Next is connecting IOM6 initialization to the existing shared engine and schema 2 semantic contract to advance natural main execution.
