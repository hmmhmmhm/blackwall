#!/usr/bin/env python3
"""Run upstream tests against the private 2.4 research build, without devices."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import bleak
import serial


def main():
    candidate = Path(sys.argv[1]).resolve()
    root = candidate / "source"
    output = candidate / "upstream-tests-24-summary.json"
    if output.exists():
        raise SystemExit("Preserve the existing report before rerunning")
    attempts = []

    def deny(*args, **kwargs):
        attempts.append("serial-open")
        raise RuntimeError("Hardware access prohibited in offline tests")

    async def deny_ble(*args, **kwargs):
        attempts.append("ble-connect-or-scan")
        raise RuntimeError("Hardware access prohibited in offline tests")

    serial.Serial.open = deny
    serial.serial_for_url = deny
    bleak.BleakClient.connect = deny_ble
    bleak.BleakScanner.start = deny_ble
    os.environ["G2_BOOT_KEY"] = (candidate / "recovery.key").read_text().strip()
    original_run = subprocess.run
    host_adaptations = []

    def host_compile(args, *a, **kw):
        if isinstance(args, list) and any(str(x).endswith("/crypto.c") for x in args):
            args = ["/usr/bin/clang", *[
                x for x in args[1:] if x not in ("-nostdlib", "-fuse-ld=lld")
            ]]
            host_adaptations.append("Apple clang/system runtime for host crypto test only")
        return original_run(args, *a, **kw)

    subprocess.run = host_compile
    replacements = {
        "test_altboot": {
            "0x0042DFD8": "0x0042DFE8",
            "0x42E56C": "0x42E57C",
            "0x00434210": "0x00434220",
            "build/official-2.3.2.14.bin": "build/stock-boot-2.4.0.24.bin",
        },
        "test_watchdog": {"0x434210": "0x434220"},
        "test_recovery": {
            "build/official-2.3.2.14.bin": "build/stock-boot-2.4.0.24.bin",
        },
    }
    sys.path.insert(0, str(root / "tests"))
    suite = unittest.TestSuite()
    sources = {}
    for path in sorted((root / "tests").glob("test_*.py")):
        original = path.read_bytes()
        source = original.decode()
        for before, after in replacements.get(path.stem, {}).items():
            if before not in source:
                raise RuntimeError(f"Expected test adaptation absent: {path.name}: {before}")
            source = source.replace(before, after)
        sources[path.name] = hashlib.sha256(original).hexdigest()
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        exec(compile(source, str(path), "exec"), module.__dict__)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    artifacts = {
        name: hashlib.sha256((root / "build" / name).read_bytes()).hexdigest()
        for name in ("patch.bin", "recover.bin", "case.bin", "stock-boot-2.4.0.24.bin")
    }
    report = {
        "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": [(str(test), reason) for test, reason in result.skipped],
        "hardware_open_attempts_blocked": attempts,
        "host_adaptations": host_adaptations,
        "in_memory_test_adaptations": replacements,
        "upstream_test_sha256": sources, "artifact_sha256": artifacts,
        "success": result.wasSuccessful() and not result.skipped and not attempts,
        "installable": False,
        "scope": "Host tests and emulation with upstream stubs; no hardware validation",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("tests_run", "failures", "errors", "skipped", "success")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
