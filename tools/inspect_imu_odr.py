"""Bind real ODR configuration bytes and source field setters across three images."""
import argparse,json,struct,re
from pathlib import Path
import unicorn.arm_const as arm
from inspect_imu_power import body
from inspect_imu_edmp import frame
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_keydb_record_load import run
from inspect_nema_blocking_wait import WORK
from prepare_vendor_startup_candidate import sha

def inspect(s,case):
    m=json.loads((s/'imu-i2cm-verification-01/manifest.json').read_text());ap=s/'imu-i2cm-saved-audit-02'/case/'report.json';assert m['passed'] and sha(ap)==m['files'][str(ap.relative_to(s))]
    a=json.loads(ap.read_text());f=Path(a['capture'])
    for n,pin in a['capture_hashes'].items():assert sha(f/n)==pin
    r=json.loads((f/'report.json').read_text());raw,ram=(f/'main.bin').read_bytes(),(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13']
    word=lambda off:struct.unpack_from('<I',ram,sp+off-0x20000000)[0]
    ret=word(0xb4)&~1;entry=ret-0x14;caller_ret=word(0xcc)&~1
    load=decode(raw,caller_ret-12,4)[0];config=literal(raw,load);assert 0x20000000<=config<0x20380000
    settings=list(ram[config-0x20000000:config-0x20000000+3]);assert settings==[2,9,9]
    caller=decode(raw,caller_ret-14,0x300);targets=sorted({i.operands[0].imm for i in caller if i.mnemonic=='bl' and entry-0x1000<=i.operands[0].imm<=entry})
    expected={(0x27,0,3),(0x1b,0,4),(0x1c,0,4),(0xa258,4,1),(0xa581,0,4),(0xa583,0,3),(0xa4aa,1,4),(0xa4ac,0,3),(0x1b,4,3),(0x1c,4,4)}
    rows=[];fields=[]
    for target in targets:
        b=body(raw,target);calls=[i for i in b if i.mnemonic=='bl']
        match=next((re.fullmatch(r'r0, r5, #(\d+), #(\d+)',i.op_str) for i in b if i.mnemonic=='bfi' and re.fullmatch(r'r0, r5, #(\d+), #(\d+)',i.op_str)),None)
        if match:shift,width=map(int,match.groups())
        elif any(i.mnemonic=='orrs.w' and i.op_str=='r0, r0, r5, lsl #4' for i in b):shift,width=4,4
        else:continue
        if len(calls)!=2:continue
        constants=[i.operands[1].imm for i in b if (i.mnemonic=='movs' and i.op_str.startswith('r1, #')) or (i.mnemonic=='movw' and i.op_str.startswith('r7, #'))]
        if not constants:continue
        reg=constants[0]
        if (reg,shift,width) not in expected:continue
        mask=((1<<width)-1)<<shift
        for byte in range(256):
            for value in [0,(1<<width)-1]:
                u,p=frame(raw,ram);u.reg_write(arm.UC_ARM_REG_R5,value);u.reg_write(arm.UC_ARM_REG_R6,0)
                u.reg_write(arm.UC_ARM_REG_R7,reg);u.mem_write(p,bytes([byte]));t=run(u,calls[0].address+4,[calls[1].address])
                args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)]
                assert args==[WORK+0x100,reg,1,p] and bytes(u.mem_read(p,1))==bytes([(byte&~mask)|((value<<shift)&mask)])
                rows.append(dict(kind='field-rmw',register=reg,shift=shift,width=width,initial=byte,value=value,execution=t))
        fields.append(dict(entry=target,register=reg,shift=shift,width=width))
    assert {(x['register'],x['shift'],x['width']) for x in fields}==expected
    gyro_load=next(i for i in caller if i.mnemonic=='ldr.w' and i.op_str.startswith('sl,'));gyro_flag=literal(raw,gyro_load)
    flag=ram[gyro_flag-0x20000000];assert flag==0
    return dict(case=case,source_audit_sha256=sha(ap),entry=entry,config_address=config,apex_odr=settings[0],accel_odr=settings[1],gyro_odr=settings[2],gyro_enabled=flag,fields=fields,samples=rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];n=sum(len(x['samples']) for x in rows);a.output.mkdir(mode=0o700)
    (a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_fragment_scenarios=n,native_configuration_executed=False,hardware_accessed=False),indent=2)+'\n');print('Verified source ODR/filter/FSR fields and actual config',n)
if __name__=='__main__':main()
