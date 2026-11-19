# Web installation preparation screen

`web/index.html` gained operation selection, local component-file verification, and device-readiness screens. `artifact-catalog.mjs` pins header-inclusive SHA256, size, and type for three currently verified files: Faceclaw/38 main, stock 2.4 main, and a dedicated-key boot candidate. It does not arbitrarily accept existing raw images or full bundles. Changing the file selection invalidates an in-progress verification result.

Local execution:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory web
```

Then visit `http://127.0.0.1:8765/`. Firmware is read through file selection, not copied into web/. The server exposes only web/, not key or firmware paths. External hosting, publication, and device connection were not performed.

The current screen is a verification stage. The device chooser and transfer button are not connected, and passing file checks still leaves installable=false. The overall goal of an actually installable web tool is incomplete; this screen does not lower its completion criteria.

All 29 current JS tests pass, with 0 skipped. Four new tests include acceptance of three actual files outside Git and rejection of payload tampering, a different operation, and incorrect size. Node execution of the verification module was checked, but actual browser appearance, CSP, and file selection had not yet been reviewed. The next task was to check that flow in a browser.

## Actual browser functional review

On 2026-11-10, the localhost page was checked in safari-minimized dedicated window 9446. The actual main-cfw.bin was selected in the file input and verified; the DOM showed matching SHA256, payload 3,829,864 bytes, and installation eligibility unconfirmed. Switching to the stock main operation with the same file cleared the previous success, and re-verification failed on size mismatch. The install button remained disabled.

This checked actual Safari File API, Web Crypto, module loading, and screen state behavior. It was not a screenshot visual review or verification of Safari Web Bluetooth support. The dedicated window was closed, task server PID 8584 stopped, and no listener on port 18765 confirmed. No device connection, firmware transfer, external publication, or key upload occurred.

## Target and installation plan UI integration

Fields were added for choosing one side, entering a confirmed advertisement name, reviewing the plan, and entering the operation's confirmation phrase. Plan review actually calls `prepareInstallation` and displays kind, side, advertisement name, and SHA. Changing operation, file, or target clears the previous plan and confirmation and disables transfer. Because installable=false, confirmation input and actual transfer remain disabled. Entering a name alone does not open a Bluetooth chooser.

The actual app.mjs connected to a DOM test double was tested for plan creation with a private CFW file, invalidation after target change, and disabled transfer. All **40 JS tests passed, skip 0**. This additional UI had not yet received actual browser review; the earlier Safari review covered the previous file-check screen. The actual transfer branch behind a compatibility profile remains unverified. packages/preparation-01 is an earlier snapshot and does not include this change.

## Actual browser review of plan UI

In dedicated minimized Safari window 9984, a private boot component was selected and plan review run with test name Even G2_32_L_ABCDEF and left side. No actual key value was entered or displayed. The screen showed candidate name, side, exact SHA, unconfirmed compatibility, and disabled confirmation input and transfer button. Changing the target to right invalidated the previous plan and cleared confirmation. This name is synthetic test input and is not stored as user device information.

The window was closed, the server stopped, and no listener on port 18765 confirmed. Observation JSON and execution scripts are retained outside Git in Blackwall/work/web-review-02. This was DOM functional review, not image-based visual review or Bluetooth verification.

## Distinguishing the 2.4 recovery candidate

A `boot-24` inspection option distinct from the existing 2.3.2.14 boot was added to operation selection. The 2.4.0.24 research candidate component length of 159,872 bytes and SHA256 `b95254ec99b140e7b2cf41a66ed86ebd5375bb7f80a1d97faaf5fdbad4e04b96` are pinned. Actual private files were used to confirm candidate acceptance, rejection of incorrect selection between the two boots and tampering, plan creation, and installation blocking before chooser invocation. All 41 JS tests passed, skip 0.

The new option had not yet received actual browser review; distinguish it from the existing Safari review. At the time this option was added, `boot-24` was not handled by the OTA session. All candidates remain installable=false. The private bundle including the corresponding recovery tool is recorded in [package preparation](../research/package-preparation.md).

Subsequently, `boot-24` handling was added to the low-level `ComponentOtaSession` and mock session, virtual GATT transfer, and failure-stop behavior were verified with the actual candidate file. All 53 web tests passed, skip 0. Follow the [transfer verification scope](web-protocol-verification.md#24-recovery-candidate-low-level-ota-session). The live UI still supports only file inspection and planning; the actual installation gate remains closed.
