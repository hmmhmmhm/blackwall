"""Audit local research files; never import a hardware transport or write firmware."""

import argparse
import json
from pathlib import Path

from blackwall_package import (
    BOOT_BASE, MAIN_BASE, PackageError, make_operation, parse_bundle,
    sha256, validate_bootloader,
)


PINS = {
    "stock_base": "187ccf2bcc5c17a212106e8a376745511e8289c4232b634a7ea94b9bf25a0979",
    "stock_boot": "26b6067665a441b779c47f6b95427b8b4bb5f502aaf527466dadce628aeb00b2",
    "stock_current": "363198f8d543a5c1181d8a213e9077285cb865700a1885c8dc7c1b9324fd0e05",
    "cfw": "4aac023f49ec6965186d9106e328a516f20a2915ab400d561f662f984023a432",
}


def audit(paths):
    bundles, inputs = {}, {}
    for label, expected in PINS.items():
        data = paths[label].read_bytes()
        if sha256(data) != expected:
            raise PackageError(f"{label}: exact research input SHA256 mismatch")
        components = parse_bundle(data)
        if {c.type_id for c in components} != {0, 1, 3, 4, 5, 6}:
            raise PackageError(f"{label}: six expected components required")
        bundles[label] = {c.type_id: c for c in components}
        inputs[label] = {"bytes": len(data), "sha256": expected}

    base, current, cfw = (bundles[k] for k in ("stock_base", "stock_current", "cfw"))
    for kind in (1, 3, 4, 5, 6):
        if base[kind].ota_bytes() != cfw[kind].ota_bytes():
            raise PackageError("CFW changes an unexpected component outside main")

    receipt = json.loads(paths["boot_receipt"].read_text())
    boot = paths["boot_image"].read_bytes()
    boot_check = validate_bootloader(boot, receipt)
    main = cfw[0]
    main_end = MAIN_BASE + len(main.payload) - 32
    boot_end = BOOT_BASE + len(boot)
    if boot_end > MAIN_BASE:
        raise PackageError("bootloader/main ranges overlap")

    findings = [
        "Device hardware, independent left/right main, boot and case identities are unknown.",
        "Mixed recovery boot 2.3.2.14 + Faceclaw main 2.3.0.24 is not hardware-verified.",
        "Unmodified full Faceclaw OTA contains stock boot and can overwrite the recovery patch.",
        "Stock 2.4 and Faceclaw codec payloads differ; main-only migration needs resource review.",
        "Full-stock restoration needs original appended-page contents, not just a stock boot prefix.",
        "No browser component writer or device readback has been validated by this audit.",
    ]
    if boot_check["publicDefaultKey"]:
        findings.append("Boot research build uses the publicly known default recovery key.")

    return {
        "schema": "blackwall-offline-audit/1",
        "scope": "local-files-only",
        "integrity": "passed",
        "readyForHardwareInstall": False,
        "hardwareValidation": "none",
        "inputs": inputs,
        "bootResearchBuild": boot_check,
        "nonOverlappingAddressRanges": {
            "boot": {"start": BOOT_BASE, "endExclusive": boot_end},
            "cfwMain": {"start": MAIN_BASE, "endExclusive": main_end},
        },
        "componentPayloadsMatchCurrentStock": {
            str(k): sha256(cfw[k].payload) == sha256(current[k].payload)
            for k in (1, 3, 4, 5, 6)
        },
        "mainOperationDescriptorsForReviewOnly": [
            make_operation("install-cfw", [main]),
            make_operation("restore-stock-main", [current[0]]),
        ],
        "unresolved": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for label in (*PINS, "boot_image", "boot_receipt"):
        parser.add_argument("--" + label.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(vars(args))
    except (PackageError, OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Audit rejected: {exc}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
