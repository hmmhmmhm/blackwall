"""Original OTA-marker branches, conditional setter, and 16-byte write intent."""
import argparse,json,hashlib,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,WORK,STOP,BASE
from inspect_keydb_record_load import run
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

MARKER=0x7fe000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def setup(raw,value):
    u=cpu(raw,bytes(0x80000),WORK+0xf000);u.mem_map(MARKER,4096);u.mem_write(MARKER,struct.pack('<I',value)+b'\xa5'*28);return u

def inspect(s,case):
    f=s/'keydb-record-zero-main-01'/case;ap=s/'keydb-record-saved-audit-01'/case/'report.json';a=json.loads(ap.read_text());r=json.loads((f/'report.json').read_text())
    if not a['passed']:raise ValueError('Unverified native input')
    for n,h in a['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed native '+n)
    raw=(f/'main.bin').read_bytes();read=r['observed']['pc'];setter=int(decode(raw,read+30,4)[0].op_str[1:],16);version=int(decode(raw,read+8,4)[0].op_str[1:],16);logger=int(decode(raw,read+22,4)[0].op_str[1:],16)
    if literal(raw,decode(raw,read-4,4)[0])!=MARKER or literal(raw,decode(raw,setter+6,2)[0])!=MARKER:raise ValueError('Different marker address')
    template=literal(raw,decode(raw,setter+0x5e,2)[0]);template_data=raw[template-BASE:template-BASE+16]
    if template_data!=b'\xff'*16:raise ValueError('Different setter template')
    samples=[]
    for old in [0xffffffff,0x55555555,0,0x12345678]:
        u=setup(raw,old);u.reg_write(arm.UC_ARM_REG_R0,MARKER);t=run(u,read,[read+8,read+26]);pending=old==0x55555555
        if t['stop']!=(read+8 if pending else read+26):raise ValueError('Different pending-startup branch')
        samples.append(dict(kind='startup-marker',current=old,pending_branch=pending,execution=t))
        for wanted in [0xffffffff,0x55555555,0]:
            u=setup(raw,old);u.reg_write(arm.UC_ARM_REG_R4,MARKER);u.reg_write(arm.UC_ARM_REG_R5,wanted);t=run(u,setter+0x56,[setter+0x5c,setter+0x102]);write=old!=wanted
            if t['stop']!=(setter+0x5c if write else setter+0x102):raise ValueError('Setter equality decision differs')
            samples.append(dict(kind='setter-equality',current=old,requested=wanted,write_prepared=write,execution=t))
    for wanted in [0xffffffff,0x55555555,0x12345678]:
        u=setup(raw,0x55555555);u.reg_write(arm.UC_ARM_REG_R4,MARKER);u.reg_write(arm.UC_ARM_REG_R5,wanted);t=run(u,setter+0x5c,[setter+0x68]);payload=bytes(u.mem_read(WORK+0xf010,16))
        if payload!=struct.pack('<I',wanted)+b'\xff'*12 or bytes(u.mem_read(MARKER,32))!=struct.pack('<I',0x55555555)+b'\xa5'*28:raise ValueError('Different write buffer or unexpected marker write')
        samples.append(dict(kind='setter-payload',requested=wanted,payload=payload.hex(),adjacent12_initialized_ff=True,actual_marker_unchanged=True,execution=t))
    u=setup(raw,0x55555555);u.reg_write(arm.UC_ARM_REG_R4,MARKER);u.mem_write(WORK+0xf010,b'\xff'*16);t=run(u,setter+0xae,[setter+0xb6]);args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)]
    if args!=[0x12344321,WORK+0xf010,MARKER,4]:raise ValueError('Different 4-word write intent')
    samples.append(dict(kind='program-arguments',arguments=args,program_call=setter+0xb6,program_callee=int(decode(raw,setter+0xb6,4)[0].op_str[1:],16),execution=t))
    version_literal=literal(raw,decode(raw,version+4,4)[0]);text=raw[version_literal-BASE:version_literal-BASE+32].split(b'\0')[0].decode('ascii');parts=[int(v) for v in text.split('.')]
    if len(parts)!=4 or any(not 0<=v<=255 for v in parts):raise ValueError('Unexpected source version string')
    ram_path=f/'exports/sram-full.bin'
    u=cpu(raw,ram_path.read_bytes(),WORK+0xf000);t=run(u,version,[]);packed=u.reg_read(arm.UC_ARM_REG_R0);expected=int.from_bytes(bytes(parts),'big')
    if packed!=expected:raise ValueError('Original version parser differs')
    samples.append(dict(kind='pending-version',source_version=text,packed=packed,input_sram_sha256=sha(ram_path),input_scope='Initialized native full SRAM; zero SRAM lacks original C-library callback',execution=t))
    event=decode(raw,read+18,4)[0]
    if literal(raw,event)!=0x70108:raise ValueError('Different pending log identifier')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.skipdata=True;calls=[i.address for i in md.disasm(raw,BASE) if i.mnemonic=='bl' and i.op_str=='#'+hex(setter)]
    if len(calls)!=2 or read+30 not in calls:raise ValueError('Setter caller discovery changed')
    commit=next(pc for pc in calls if pc!=read+30);arg=decode(raw,commit-4,4)[0]
    if (arg.mnemonic,arg.op_str)!=('movs.w','r0, #0x55555555'):raise ValueError('Commit caller requested marker differs')
    dump=int(decode(raw,setter+0x52,4)[0].op_str[1:],16);gate=literal(raw,decode(raw,dump+0x1c,2)[0]);ram=ram_path.read_bytes()
    if not 0x20000000<=gate<=0x20380000-0xf2:raise ValueError('Hexdump gate outside captured SRAM')
    minimum=decode(raw,dump+0x2a,2)[0]
    if (minimum.mnemonic,minimum.op_str)!=('cmp','r0, #4'):raise ValueError('Different hexdump minimum level')
    dump_gate=dict(address=gate,level=ram[gate-0x20000000],enabled=ram[gate-0x20000000+0xf1],minimum_level=4,scope='Source early-exit condition and saved native SRAM, not executed dump or physical device')
    return dict(case=case,raw_sha256=sha(f/'main.bin'),audit_sha256=sha(ap),startup_read=read,setter=setter,setter_template=template,version_parser=version,pending_logger=logger,pending_log_id=0x70108,setter_callers=calls,commit_call=commit,hexdump_gate=dump_gate,samples=samples,discovery_scope='Direct BL and PC-literal forms in pinned Thumb decode; not proof against indirect or constructed-address accesses')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior result')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];count=sum(len(r['samples']) for r in rows);a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=count,native_main_rerun=False,hardware_accessed=False,mram_program_executed=False,full_update_or_reset_executed=False,real_marker_known=False),indent=2)+'\n');print('original OTA marker scenarios: '+str(count)+' passed')
if __name__=='__main__':main()
