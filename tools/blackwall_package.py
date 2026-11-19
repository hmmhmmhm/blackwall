"""Offline package validation. This module has no device or network access."""

from dataclasses import dataclass
import hashlib
import re
import struct
import zlib


class PackageError(ValueError):
    pass


COMPONENTS = {
    "ota/s200_firmware_ota.bin": 0,
    "ota/s200_bootloader.bin": 1,
    "firmware/touch.bin": 3,
    "firmware/codec.bin": 4,
    "firmware/ble_em9305.bin": 5,
    "firmware/box.bin": 6,
}
BOOT_BASE = 0x410000
MAIN_BASE = 0x438000
MAIN_END = 0x7F8000
STOCK_BOOT_BYTES = 149760
STOCK_BOOT_SHA = "22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7"
HOOKS = ((0x42E656, "fff789ff"), (0x42E3D4, "fff700fe"), (0x42E440, "fff7cafd"))
DEFAULT_KEY_ID = "a8b1b9b094f02ebe77411aaea4caef8cd556fef0fe04ce8c8e477e2d6cda315a"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _crc32c_table():
    # Non-reflected CRC convention cross-checked with pinned g2flash; see NOTICE.md.
    table = []
    for byte in range(256):
        crc = byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1EDC6F41 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        table.append(crc)
    return tuple(table)


_CRC32C_TABLE = _crc32c_table()


def crc32c(data):
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC32C_TABLE[((crc >> 24) ^ byte) & 255]
    return crc


@dataclass(frozen=True)
class Component:
    name: str
    type_id: int
    header: bytes
    payload: bytes

    def ota_bytes(self):
        return self.header + self.payload


def validate_main(payload):
    if len(payload) < 40:
        raise PackageError("main preamble or vectors truncated")
    size = struct.unpack_from("<I", payload)[0] & 0xFFFFFF
    if size != len(payload):
        raise PackageError("main preamble length mismatch")
    if struct.unpack_from("<I", payload, 20)[0] != MAIN_BASE:
        raise PackageError("main destination must preserve the bootloader")
    if zlib.crc32(payload[8:]) != struct.unpack_from("<I", payload, 4)[0]:
        raise PackageError("main preamble CRC mismatch")
    if MAIN_BASE + len(payload) - 32 > MAIN_END:
        raise PackageError("main exceeds MRAM application boundary")
    stack, reset = struct.unpack_from("<II", payload, 32)
    if stack % 8 or not 0x20000000 < stack <= 0x20400000:
        raise PackageError("main stack vector invalid")
    if not reset & 1 or not MAIN_BASE + 8 <= reset & ~1 < MAIN_BASE + len(payload) - 32:
        raise PackageError("main reset vector invalid")


def parse_bundle(data):
    if len(data) < 80 or data[:8] != b"EVENOTA\0":
        raise PackageError("EVENOTA header missing")
    count = struct.unpack_from("<I", data, 8)[0]
    if not 1 <= count <= 6 or 64 + 16 * count > len(data):
        raise PackageError("component table bounds invalid")
    result, seen = [], set()
    expected_offset = None
    for index in range(count):
        _, offset, size, expected_crc = struct.unpack_from("<4I", data, 64 + index * 16)
        if offset < 64 + 16 * count or size < 129 or offset + size > len(data):
            raise PackageError("component bounds invalid")
        if expected_offset is not None and offset != expected_offset:
            raise PackageError("component bounds overlap or contain a gap")
        header = data[offset:offset + 128]
        length, inner_crc = struct.unpack_from("<II", header, 8)
        if length != size - 128:
            raise PackageError("component payload bounds mismatch")
        try:
            name = header[48:].split(b"\0")[0].decode("ascii")
        except UnicodeDecodeError as exc:
            raise PackageError("component name invalid") from exc
        type_id = struct.unpack_from("<I", header, 36)[0]
        if name not in COMPONENTS or COMPONENTS[name] != type_id or name in seen:
            raise PackageError("unexpected or duplicate component")
        seen.add(name)
        payload = data[offset + 128:offset + size]
        if expected_crc != inner_crc or crc32c(payload) != expected_crc:
            raise PackageError("component CRC mismatch")
        if type_id == 0:
            validate_main(payload)
        result.append(Component(name, type_id, header, payload))
        expected_offset = offset + size
    if expected_offset != len(data):
        raise PackageError("component bounds do not close at EOF")
    return tuple(result)


def branch_target(address, instruction):
    first, second = struct.unpack("<HH", instruction)
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
        raise PackageError("bootloader hook is not Thumb BL")
    sign = first >> 10 & 1
    delta = ((sign << 24) | ((~((second >> 13) ^ sign) & 1) << 23)
             | ((~((second >> 11) ^ sign) & 1) << 22)
             | ((first & 1023) << 12) | ((second & 2047) << 1))
    if sign:
        delta -= 1 << 25
    return address + 4 + delta


def validate_bootloader(data, receipt):
    if not STOCK_BOOT_BYTES < len(data) <= MAIN_BASE - BOOT_BASE or len(data) % 4096:
        raise PackageError("stock bootloader/partition size mismatch")
    raw = receipt.get("raw_bytes")
    if type(raw) is not int or not STOCK_BOOT_BYTES < raw <= len(data):
        raise PackageError("bootloader raw length mismatch")
    key_id = receipt.get("auth_key_sha256")
    if not isinstance(key_id, str) or not re.fullmatch(r"[0-9a-f]{64}", key_id):
        raise PackageError("bootloader key identifier missing or malformed")
    prefix = bytearray(data[:STOCK_BOOT_BYTES])
    for address, old_hex in HOOKS:
        offset = address - BOOT_BASE
        call = data[offset:offset + 4]
        if call == bytes.fromhex(old_hex):
            raise PackageError("bootloader recovery hook absent")
        target = branch_target(address, call)
        if not BOOT_BASE + STOCK_BOOT_BYTES <= target < BOOT_BASE + raw:
            raise PackageError("bootloader hook target outside appended code")
        prefix[offset:offset + 4] = bytes.fromhex(old_hex)
    if sha256(prefix) != STOCK_BOOT_SHA:
        raise PackageError("stock bootloader prefix modified outside reviewed hooks")
    if (receipt.get("stock_sha256") != STOCK_BOOT_SHA or receipt.get("base") != BOOT_BASE
            or receipt.get("bytes") != len(data) or receipt.get("sha256") != sha256(data)):
        raise PackageError("bootloader build receipt mismatch")
    if receipt.get("raw_sha256") != sha256(data[:raw]):
        raise PackageError("bootloader raw hash mismatch")
    if data[raw:] != b"\xff" * (len(data) - raw):
        raise PackageError("bootloader page padding is not erased bytes")
    return {"sha256": sha256(data), "bytes": len(data),
            "keyId": receipt.get("auth_key_sha256"),
            "publicDefaultKey": receipt.get("auth_key_sha256") == DEFAULT_KEY_ID}


def make_operation(kind, components):
    allowed = {"install-recovery-boot": 1, "restore-stock-boot": 1,
               "install-cfw": 0, "restore-stock-main": 0,
               "install-codec": 4, "restore-stock-codec": 4}
    if kind not in allowed:
        raise PackageError("unknown operation")
    if len(components) != 1 or components[0].type_id != allowed[kind]:
        raise PackageError("operation must contain exactly its allowed component; bootloader is isolated")
    c = components[0]
    if c.type_id == 0:
        validate_main(c.payload)
    return {"kind": kind, "component": c.name, "typeId": c.type_id,
            "sha256": sha256(c.ota_bytes()), "payloadSha256": sha256(c.payload),
            "payloadBytes": len(c.payload), "headerBytes": 128,
            "requiresIndependentConfirmation": True,
            "requiresSingleTemple": True, "automaticNextOperation": False,
            "touchesBootloader": c.type_id == 1,
            "completion": "transfer-and-readback-required"}
