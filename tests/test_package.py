from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from blackwall_package import PackageError, parse_bundle, validate_bootloader, make_operation, validate_main, crc32c


def bundle(payload=b"test", name="ota/s200_bootloader.bin", type_id=1):
    # Independent CRC test vector algorithm, matching Even's non-reflected CRC32C.
    crc = 0
    for byte in payload:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1EDC6F41 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
    header = bytearray(128)
    struct.pack_into("<4I", header, 0, 0, 0, len(payload), crc)
    struct.pack_into("<I", header, 36, type_id)
    header[48:48 + len(name)] = name.encode()
    prefix = bytearray(80)
    prefix[:8] = b"EVENOTA\0"
    struct.pack_into("<I", prefix, 8, 1)
    struct.pack_into("<4I", prefix, 64, 1, 80, 128 + len(payload), crc)
    return bytes(prefix + header + payload)


class BundleValidation(unittest.TestCase):
    def test_crc_known_answers_from_pinned_g2flash(self):
        for payload, expected in [(b'', 0), (b'123456789', 0xc052a8c8),
                                  (bytes(range(256)), 0xd7b91914), (b'\xff'*4096, 0x59fd1cbd)]:
            self.assertEqual(crc32c(payload), expected)

    def test_reads_component_and_preserves_exact_ota_header(self):
        raw = bundle()
        component, = parse_bundle(raw)
        self.assertEqual(component.name, "ota/s200_bootloader.bin")
        self.assertEqual(component.header, raw[80:208])
        self.assertEqual(component.payload, b"test")

    def test_payload_corruption_is_rejected(self):
        raw = bytearray(bundle())
        raw[-1] ^= 1
        with self.assertRaisesRegex(PackageError, "CRC"):
            parse_bundle(bytes(raw))

    def test_table_cannot_point_into_itself(self):
        raw = bytearray(bundle())
        struct.pack_into("<I", raw, 68, 64)
        with self.assertRaisesRegex(PackageError, "bounds"):
            parse_bundle(bytes(raw))

    def test_trailing_or_truncated_bytes_are_rejected(self):
        for raw in (bundle() + b"x", bundle()[:-1]):
            with self.assertRaises(PackageError):
                parse_bundle(raw)

    def test_component_filename_cannot_escape_package(self):
        with self.assertRaisesRegex(PackageError, "component"):
            parse_bundle(bundle(name="../../boot.bin"))

    def test_main_preamble_destination_is_checked(self):
        payload = bytearray(64)
        struct.pack_into("<I", payload, 0, len(payload))
        struct.pack_into("<I", payload, 20, 0x410000)
        struct.pack_into("<I", payload, 4, zlib.crc32(payload[8:]))
        with self.assertRaisesRegex(PackageError, "destination"):
            parse_bundle(bundle(payload, "ota/s200_firmware_ota.bin", 0))


class OperationBoundary(unittest.TestCase):
    def test_main_operation_cannot_include_bootloader(self):
        component, = parse_bundle(bundle())
        with self.assertRaisesRegex(PackageError, "bootloader"):
            make_operation("install-cfw", [component])

    def test_boot_operation_cannot_include_other_components(self):
        component, = parse_bundle(bundle(name="firmware/touch.bin", type_id=3))
        with self.assertRaisesRegex(PackageError, "bootloader"):
            make_operation("install-recovery-boot", [component])

    def test_unknown_operation_is_rejected(self):
        with self.assertRaises(PackageError):
            make_operation("erase-everything", [])

    def test_boot_patch_rejects_stock_sized_image_without_extension(self):
        stock = bytes(149760)
        with self.assertRaisesRegex(PackageError, "stock"):
            validate_bootloader(stock, {})

    def test_boot_patch_requires_key_metadata_before_accepting_receipt(self):
        image = bytes(159744)
        with self.assertRaisesRegex(PackageError, "key identifier"):
            validate_bootloader(image, {"raw_bytes": 155876})


class MainSafetyCeiling(unittest.TestCase):
    def test_rejects_application_past_upstream_safe_ceiling(self):
        for extra in (0, 4):
            payload = bytearray(0x7F8000 - 0x438000 + 32 + extra)
            struct.pack_into('<I', payload, 0, len(payload))
            struct.pack_into('<I', payload, 20, 0x438000)
            struct.pack_into('<II', payload, 32, 0x20010000, 0x438009)
            struct.pack_into('<I', payload, 4, zlib.crc32(payload[8:]))
            if extra:
                with self.assertRaisesRegex(PackageError, 'boundary'):
                    validate_main(payload)
            else:
                validate_main(payload)

if __name__ == "__main__":
    unittest.main()
