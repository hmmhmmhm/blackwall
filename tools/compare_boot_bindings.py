"""Read-only, hash-pinned comparison of selected boot instruction windows.

Windows are analysis bounds, not proven function boundaries. No patch generation.
Requires Capstone; raw instruction listings belong outside Git.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC
from blackwall_package import parse_bundle, branch_target

BASE = 0x410000
PINS = {
    "2.3.2.14": "26b6067665a441b779c47f6b95427b8b4bb5f502aaf527466dadce628aeb00b2",
    "2.4.0.24": "363198f8d543a5c1181d8a213e9077285cb865700a1885c8dc7c1b9324fd0e05",
}
WINDOWS = [
    ("stock-main-entry", 0x41b862, 0x41b862, 100),
    ("stock-data-init-dispatch", 0x432d24, 0x432d34, 32),
    ("power-pre-dispatch", 0x41cd34, 0x41cd34, 22),
    ("power-post-dispatch", 0x41cd4a, 0x41cd4a, 22),
    ("power-table-clear-prefix", 0x41ce52, 0x41ce52, 20),
    ("board-init-wrapper", 0x430526, 0x430536, 30),
    ("manager-before-hook", 0x42e640, 0x42e650, 26),
    ("uart-init-candidate", 0x41f612, 0x41f612, 356),
    ("uart-rx-dispatch", 0x41f776, 0x41f776, 208),
    ("uart-wake", 0x41f846, 0x41f846, 116),
    ("uart-sleep", 0x41f8ba, 0x41f8ba, 94),
    ("uart-transfer-region", 0x41f918, 0x41f918, 158, 176),
    ("update-flag", 0x42e56c, 0x42e57c, 48),
    ("vector-handoff", 0x42dfd8, 0x42dfe8, 18),
    ("mram-wrapper", 0x42e83c, 0x42e84c, 26),
    ("mram-inner", 0x42e7e8, 0x42e7f8, 84),
    ("mram-rom-dispatch", 0x42ebf4, 0x42ec04, 30),
    ("manager-hook", 0x42e656, 0x42e666, 4),
    ("update-hook", 0x42e3d4, 0x42e3e4, 4),
    ("boot-hook", 0x42e440, 0x42e450, 4),
]


def load(path, version):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS[version]:
        raise ValueError("Unexpected source bundle")
    return next(c.payload for c in parse_bundle(data) if c.type_id == 1)


def window(data, address, length):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    rows = []
    for ins in decoder.disasm(data[address-BASE:address-BASE+length], address):
        row = {"address": hex(ins.address), "size": ins.size,
               "mnemonic": ins.mnemonic, "operands": ins.op_str}
        for op in ins.operands:
            if op.type == ARM_OP_MEM and op.mem.base == ARM_REG_PC:
                literal = ((ins.address + 4) & ~3) + op.mem.disp
                row["pc_relative_address"] = hex(literal)
                if ins.mnemonic in ("ldr", "ldr.w") and BASE <= literal <= BASE+len(data)-4:
                    row["literal_word"] = hex(struct.unpack_from("<I", data, literal-BASE)[0])
        if ins.mnemonic in ("bl", "blx", "b", "b.w") and ins.operands[0].type == ARM_OP_IMM:
            row["direct_target"] = hex(ins.operands[0].imm)
        rows.append(row)
    return {"address": hex(address), "requested_bytes": length,
            "decoded_bytes": sum(row["size"] for row in rows), "instructions": rows}


def compare(old, new):
    result = {"hardware_validated": False, "patch_generated": False,
              "scope": "selected-instruction-windows-not-full-ABI-proof", "images": {}, "windows": []}
    for version, data in zip(PINS, (old, new)):
        targets = {0x41ce52, 0x41cd34, 0x41cd4a, 0x41f612}
        candidates = []
        for offset in range(0, len(data)-3, 2):
            first, second = struct.unpack_from('<HH', data, offset)
            if first & 0xf800 == 0xf000 and second & 0xd000 == 0xd000:
                target = branch_target(BASE+offset, data[offset:offset+4])
                if target in targets:
                    candidates.append({'address': hex(BASE+offset), 'target': hex(target)})
        result["images"][version] = {"sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "end_exclusive": hex(BASE+len(data)),
            "first_16_byte_aligned_append": hex((BASE+len(data)+15)&~15),
            "direct_bl_candidates_not_reachability_proof": candidates}
    for name, a, b, length, *new_length in WINDOWS:
        left, right = window(old, a, length), window(new, b, new_length[0] if new_length else length)
        changes = []
        for index, (x, y) in enumerate(zip(left["instructions"], right["instructions"])):
            fields = ("size", "mnemonic", "operands", "literal_word", "direct_target")
            changed = [key for key in fields if x.get(key) != y.get(key)]
            if changed:
                changes.append({"instruction_index": index, "changed_fields": changed,
                                "old": x, "new": y})
        result["windows"].append({"name": name, "old": left, "new": right,
            "equal_instruction_count": len(left["instructions"]) == len(right["instructions"]),
            "changes": changes})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(root):
        parser.error("Store firmware disassembly outside the repository")
    report = compare(load(args.old, "2.3.2.14"), load(args.new, "2.4.0.24"))
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"images": report["images"], "windows": [
        {"name": w["name"], "changes": len(w["changes"]),
         "decoded": [w["old"]["decoded_bytes"], w["new"]["decoded_bytes"]]}
        for w in report["windows"]]}, indent=2))
