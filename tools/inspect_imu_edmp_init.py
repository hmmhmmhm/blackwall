"""Execute original EDMP init wrappers with explicit bus/SRAM/delay ABI stubs."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_imu_power import body
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import cpu, WORK, STOP
from prepare_vendor_startup_candidate import sha


def calls(raw, entry):
    return [i for i in body(raw, entry) if i.mnemonic == 'bl']


def exercise(raw, ram, entry, leaves, initial, pending, read_error, enabled):
    sp = WORK + 0xf000
    u = cpu(raw, ram, sp)
    u.reg_write(arm.UC_ARM_REG_R0, WORK + 0x100)
    registers = {0x29: initial & 0xef, 0x2a: (initial & 0xaf) | (0x40 if enabled else 0),
                 0xa2a7: initial, 0xa271: initial, 0xa272: initial, 0xa273: initial, 0x73: initial}
    before = dict(registers)
    transfers, trace, delays = [], [], []
    polls = 0
    failure_sent = False
    def code(c, pc, size, user):
        nonlocal polls, failure_sent
        trace.append(pc)
        if pc not in leaves:
            return
        kind = leaves[pc]
        args = [c.reg_read(getattr(arm, 'UC_ARM_REG_R' + str(i))) for i in range(4)]
        assert args[0] == WORK + 0x100
        status = 0
        if kind == 'delay':
            assert args[1] in [5, 200]
            delays.append(args[1])
        else:
            _, reg, length, ptr = args
            assert 1 <= length <= 6
            if kind == 'read':
                assert length == 1 and reg in registers.keys() | {0xa297}
                if reg == 0xa297:
                    polls += 1
                    value = 0 if polls <= pending else 2
                else:
                    value = registers[reg]
                c.mem_write(ptr, bytes([value]))
                if read_error and not failure_sent and reg == 0xa2a7:
                    status, failure_sent = 0xfffffffd, True
                data = bytes([value])
            else:
                data = bytes(c.mem_read(ptr, length))
                if kind == 'write':
                    assert reg in [0xa24f, 0xa255, 0xa2a7, 0xa271, 0xa272, 0xa273, 0x29, 0x2a, 0x73]
                    if length == 1:
                        registers[reg] = data[0]
                else:
                    assert reg in [0x118, 0x11c, 0x120, 0x11e]
            transfers.append(dict(kind=kind, register=reg, data=data.hex(), status=status))
        c.reg_write(arm.UC_ARM_REG_R0, status)
        c.reg_write(arm.UC_ARM_REG_PC, c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(entry | 1, STOP, count=50000)
    assert u.reg_read(arm.UC_ARM_REG_PC) == STOP and u.reg_read(arm.UC_ARM_REG_SP) == sp
    writes = [(x['register'], x['data']) for x in transfers if x['kind'] == 'write']
    assert writes[:3] == [(0xa24f, '004004400840'), (0xa255, '02'), (0xa2a7, bytes([initial | 3]).hex())], writes[:3]
    requests = [(x['register'], x['data']) for x in transfers if x['kind'] == 'sram-write']
    if enabled:
        assert not requests and polls == 0 and not delays and len(writes) == 3
        expected = 0xffffffff
    else:
        assert requests == [(0x118, '01000000'), (0x11c, '0000'), (0x120, '0018'), (0x11e, '00')]
        assert registers[0x29] == before[0x29] and registers[0x2a] == before[0x2a]
        assert registers[0xa271] == 0x3c and registers[0xa272] == 0x3f and registers[0xa273] == 0x3f
        assert registers[0x73] == initial | 0x20
        assert polls == pending + 2 and delays == [200] + [5] * pending + [200]
        assert bytes(u.mem_read(WORK + 0x112, 1)) == b'\x03'
        expected = 0xfffffffd if read_error else 0
    assert u.reg_read(arm.UC_ARM_REG_R0) == expected
    return dict(initial=initial, pending_idle_polls=pending, enabled_input=enabled, injected_read_error=read_error,
                returned_status=expected, transfers=transfers, delays_us=delays, idle_reads=polls,
                trace_instructions=len(trace), trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace), *trace)).hexdigest())


def inspect(s, case):
    m = json.loads((s/'imu-odr-verification-01/manifest.json').read_text())
    p = s/'imu-odr-saved-audit-01'/case/'report.json'
    assert m['passed'] and sha(p) == m['files'][str(p.relative_to(s))]
    audit = json.loads(p.read_text()); f = Path(audit['capture'])
    for name, pin in audit['capture_hashes'].items():
        assert sha(f/name) == pin
    r = json.loads((f/'report.json').read_text())
    raw, ram = (f/'main.bin').read_bytes(), (f/'exports/sram-full.bin').read_bytes()
    sp = r['observed']['register_context']['r13']
    ret = lambda off: struct.unpack_from('<I', ram, sp-0x20000000+off)[0] & ~1
    configure = decode(raw, ret(0x114)-4, 4)[0].operands[0].imm
    init = decode(raw, ret(0x12c)-4, 4)[0].operands[0].imm
    ic = calls(raw, init); assert ic[0].operands[0].imm == configure
    cc = calls(raw, configure); write = cc[0].operands[0].imm
    assert write == decode(raw, ret(0xfc)-4, 4)[0].operands[0].imm
    read = ic[1].operands[0].imm
    memset = ic[3].operands[0].imm; recompute = ic[4].operands[0].imm
    mc = calls(raw, memset)
    sram_write = mc[2].operands[0].imm
    delay = mc[7].operands[0].imm
    assert len(ic) == 5 and len(mc) == 12
    leaves = {read:'read', write:'write', sram_write:'sram-write', delay:'delay'}
    assert len(leaves) == 4
    samples = [exercise(raw, ram, init, leaves, byte, pending, error, enabled)
               for byte in [0, 0xa5, 0xff] for pending,error,enabled in
               [(0,False,False),(2,False,False),(0,True,False),(0,False,True)]]
    after = decode(raw, ret(0x12c), 6)
    assert [i.mnemonic for i in after] == ['orrs', 'cmp', 'beq']
    success = after[2].operands[0].imm
    caller_samples = []
    for accumulated in [0, 4]:
        for status in [0, 0xfffffffd]:
            u = cpu(raw, ram, WORK+0xf000)
            u.reg_write(arm.UC_ARM_REG_R4, accumulated)
            u.reg_write(arm.UC_ARM_REG_R0, status)
            t = run(u, ret(0x12c), [success, ret(0x12c)+6])
            assert t['stop'] == (success if accumulated | status == 0 else ret(0x12c)+6)
            caller_samples.append(dict(accumulated=accumulated,status=status,execution=t))
    return dict(case=case, source_audit_sha256=sha(p), init_entry=init, configure_entry=configure,
                memset_entry=memset, recompute_entry=recompute, abi_stubs=leaves, samples=samples, caller_samples=caller_samples)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]
    a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_wrapper_scenarios=sum(len(x['samples']) for x in rows), original_caller_gate_scenarios=sum(len(x['caller_samples']) for x in rows),
        bus_and_sram_and_delay_callees_stubbed=True,physical_edmp_execution=False,native_main_rerun=False,
        hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Original EDMP init wrapper scenarios',sum(len(x['samples']) for x in rows))
if __name__=='__main__':main()
