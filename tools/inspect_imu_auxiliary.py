"""Bind auxiliary pad setup, interrupt packing and secondary identity gates."""
import argparse
import json
import struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_imu_power import body
from inspect_imu_edmp import frame
from inspect_iom4_command import sources
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import WORK, STOP
from prepare_vendor_startup_candidate import sha


def inspect(s, case):
    m = json.loads((s/'imu-power-verification-01/manifest.json').read_text())
    ap = s/'imu-power-saved-audit-01'/case/'report.json'
    if not m['passed'] or sha(ap) != m['files'][str(ap.relative_to(s))]:
        raise ValueError('Changed pad source audit')
    a = json.loads(ap.read_text());f = Path(a['capture'])
    for n,pin in a['capture_hashes'].items():
        if sha(f/n) != pin:raise ValueError('Changed source '+n)
    raw,ram = (f/'main.bin').read_bytes(),(f/'exports/sram-full.bin').read_bytes()
    r = json.loads((f/'report.json').read_text());sp0 = r['observed']['register_context']['r13']
    word = lambda off:struct.unpack_from('<I',ram,sp0-0x20000000+off)[0]
    read_return = word(0xb4)&~1;pad = read_return-0x12
    pb = body(raw,pad);pc = [i for i in pb if i.mnemonic=='bl']
    if len(pc)!=2 or pc[0].address+4!=read_return:raise ValueError('Changed pad RMW frame')
    mag = (word(0xc4)&~1)-0x12
    mb = body(raw,mag);mc = [i for i in mb if i.mnemonic=='bl']
    if mc[0].operands[0].imm!=pad or not any(i.mnemonic=='cmp' and i.op_str=='r0, #0x45' for i in mb):
        raise ValueError('Changed auxiliary caller/identity comparison')
    getter,setter = mc[1].operands[0].imm,mc[2].operands[0].imm
    gb,sb = body(raw,getter),body(raw,setter)
    get_call = next(i for i in gb if i.mnemonic=='bl')
    set_call = next(i for i in sb if i.mnemonic=='bl')
    if not any(i.mnemonic=='movs' and i.op_str=='r1, #0x16' for i in gb):
        raise ValueError('Changed INT1 bank')
    rows=[]
    for byte in range(256):
        u,sp=frame(raw,ram,16);u.mem_write(sp,bytes([byte]));u.reg_write(arm.UC_ARM_REG_R5,0)
        t=run(u,read_return,[pc[1].address])
        if bytes(u.mem_read(sp,1))!=bytes([(byte&0xf3)|0x14]) or u.reg_read(arm.UC_ARM_REG_R1)!=0x30:
            raise ValueError('Changed auxiliary pad mask')
        rows.append(dict(kind='pad-rmw',byte=byte,execution=t))
    values=[0,0xffff,0xa55a,0x5aa5]+[1<<k for k in range(16)]
    for value in values:
        for status in [0,0xfffffffd]:
            u,sp=frame(raw,ram,16);out=WORK+0x200
            u.mem_write(sp,struct.pack('<H',value));u.reg_write(arm.UC_ARM_REG_R4,out)
            u.reg_write(arm.UC_ARM_REG_R5,0);u.reg_write(arm.UC_ARM_REG_R0,status)
            t=run(u,get_call.address+4,[])
            if bytes(u.mem_read(out,15))!=bytes((value>>k)&1 for k in range(15)) or u.reg_read(arm.UC_ARM_REG_R0)!=status:
                raise ValueError('Changed interrupt getter/error decode')
            rows.append(dict(kind='interrupt-getter',value=value,status=status,execution=t))
    for byte in range(256):
        for value in [byte|0xa500,(byte<<8)|0x5a]:
            for enabled in [0,1]:
                u,sp=frame(raw,ram,16);conf=WORK+0x200
                flags=bytearray((value>>k)&1 for k in range(15));flags[13]=enabled
                u.mem_write(conf,bytes(flags));u.reg_write(arm.UC_ARM_REG_R0,WORK+0x100)
                u.reg_write(arm.UC_ARM_REG_R1,0);u.reg_write(arm.UC_ARM_REG_R2,conf)
                t=run(u,setter,[set_call.address]);current_sp=u.reg_read(arm.UC_ARM_REG_SP)
                got=struct.unpack('<H',bytes(u.mem_read(current_sp,2)))[0]
                args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)]
                if got!=((value&0x5fff)|(enabled<<13)) or args!=[WORK+0x100,0x16,2,current_sp]:
                    raise ValueError('Changed interrupt pack/reserved bit clear')
                rows.append(dict(kind='interrupt-packer',value=value,enabled=enabled,execution=t))
    # The initialization's sixth BL reads chip_id through the secondary transport.
    id_call=mc[5]
    id_body=body(raw,id_call.operands[0].imm)
    if not any(i.mnemonic=='movs' and i.op_str=='r1, #1' for i in id_body):
        raise ValueError('Changed secondary identity register')
    indirect=next(i for i in mb if i.mnemonic=='blx')
    for byte in range(256):
        u,sp=frame(raw,ram,64);u.mem_write(sp,bytes([byte]));u.reg_write(arm.UC_ARM_REG_R5,WORK+0x100)
        t=run(u,id_call.address+4,[indirect.address])
        if t['stop']!=(indirect.address if byte==0x45 else STOP):
            raise ValueError('Changed identity acceptance gate')
        if byte!=0x45 and u.reg_read(arm.UC_ARM_REG_R0)!=0xffffffff:
            raise ValueError('Changed identity mismatch return')
        rows.append(dict(kind='secondary-identity-gate',byte=byte,execution=t))
    if raw.lower().count(b'imu_icm45608.c')!=1:raise ValueError('Changed original driver filename evidence')
    # Resolve callback pointers from the actual initialization, not a cross-version offset.
    callback_loads=[i for i in mb if i.mnemonic=='ldr' and i.op_str.startswith('r0,')]
    callbacks=[literal(raw,i)&~1 for i in callback_loads if 0x438000 <= (literal(raw,i)&~1) < 0x438000+len(raw)][:2]
    if len(callbacks)!=2:raise ValueError('Missing original read/write callback pointers')
    return dict(case=case,source_audit_sha256=sha(ap),pad_entry=pad,mag_initialization=mag,
                pad_register=0x30,pad_preserved_mask=0xe3,pad_requested_bits=0x14,
                interrupt_getter=getter,interrupt_setter=setter,interrupt_register=0x16,
                interrupt_field=13,reserved_bit_cleared=15,secondary_identity_register=1,
                secondary_expected_identity=0x45,secondary_callbacks=callbacks,
                original_driver_filename='imu_icm45608.c',original_driver_filename_offset=raw.lower().index(b'imu_icm45608.c'),
                auxiliary_calls=[i.operands[0].imm for i in mc],samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()):raise ValueError('Fresh private output required')
    src=sources(a.simulator);rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]
    pdf=a.simulator/'imu-aux-research-01/ict-datasheet.pdf'
    if not pdf.read_bytes().startswith(b'%PDF-'):raise ValueError('Missing manufacturer datasheet')
    a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    count=sum(len(x['samples']) for x in rows)
    report=dict(passed=True,cases=rows,sources=src,original_arm_fragment_scenarios=count,
        secondary_datasheet=dict(document='TDK DS-000548 revision1.1',sha256=sha(pdf),
        url='https://d17t6iyxenbwp1.cloudfront.net/s3fs-public/2026-08/ds-000548-ict-15312-ict-15318-datasheet-v1.1.pdf',
        family=['ICT-15312','ICT-15318'],variant_identified=False),secondary_native_identity_verified=False,
        hardware_accessed=False,boot_verified=False,display_verified=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Verified auxiliary pad/INT1/identity fragments',count)


if __name__=='__main__':main()
