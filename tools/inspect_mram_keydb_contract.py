"""Original keydb slot reads/decisions and bounded write arguments; synthetic data only."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,BASE,SRAM,WORK,STOP
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from run_native_candidate import memory_exports,validate_memory_exports
from pinned_main import load_pinned_main
from revalidate_research_assets import PINS
from blackwall_package import parse_bundle

TAIL=0x7ff000

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def execute(raw,entry,regs,tail,stop=None,initial=None):
    u=cpu(raw,bytes(0x80000),WORK+0xf000);u.mem_map(TAIL,0x1000);u.mem_write(TAIL,tail);trace=[]
    if initial is not None:initial(u)
    for n,value in regs.items():u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
    def hook(c,pc,size,user):
        trace.append(pc)
        if stop and pc in stop:c.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry|1,STOP,count=20000);pc=u.reg_read(arm.UC_ARM_REG_PC)
    if pc not in (stop or [STOP]):raise ValueError('Original fragment escaped boundary')
    return u,dict(stop=pc,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())

def uniform(raw,h):
    rows=[]
    for fill,difference in [(0,None),(255,None),(165,None),(0,1),(255,127),(165,255)]:
        data=bytearray([fill]*256)
        if difference is not None:data[difference]^=1
        for output in [0,WORK+0x100]:
            u,t=execute(raw,h,{0:TAIL,1:output},bytes(data));result=u.reg_read(arm.UC_ARM_REG_R0)
            if result!=int(difference is None):raise ValueError('Uniform slot decision differs')
            count=None if not output else struct.unpack('<H',u.mem_read(output,2))[0]
            if output and count!=(256 if difference is None else difference):raise ValueError('Uniform prefix length differs')
            rows.append(dict(fill=fill,mismatch=difference,output_pointer=bool(output),uniform=bool(result),prefix_length=count,execution=t))
    return rows

def decide(raw,h):
    # Start immediately after actual uniform-helper return; no logger or write runs.
    rows=[];caller=h-0x880;advance=h-0x8a2;validate=h-0x99c;heal=h-0x860
    for is_uniform,fill in [(True,0),(True,255),(True,165),(False,0),(False,255)]:
        u,t=execute(raw,caller+4,{0:int(is_uniform),7:TAIL},bytes([fill])*256,stop=[advance,validate,heal])
        expected=advance if is_uniform and fill==0 else heal if is_uniform else validate
        if t['stop']!=expected:raise ValueError('Original slot-heal branch differs')
        rows.append(dict(uniform=is_uniform,first_byte=fill,result='skip-zero' if expected==advance else 'heal-uninit' if expected==heal else 'validate-record',execution=t))
    return rows

def validate_records(raw,h):
    rows=[];entry=h-0x7a;scenarios=[('zero',bytes(256),True)]
    for offset in [0x30,0x2f,0xc3,0x31,0x32,0x4f,0x86]:
        d=bytearray(256);d[offset]=2;scenarios.append(('bool-'+hex(offset),bytes(d),False))
    d=bytearray(256);d[6]=4;scenarios.append(('address-type',bytes(d),False))
    d=bytearray(256);d[0x2e]=0x10;scenarios.append(('key-mask',bytes(d),False))
    d=bytearray(256)
    for offset in [0x30,0x2f,0xc3,0x31,0x32,0x4f,0x86]:d[offset]=1
    d[6]=3;d[0x2e]=15;scenarios.append(('nonzero-flags',bytes(d),True))
    for name,data,wanted in scenarios:
        u,t=execute(raw,entry,{0:TAIL},data);actual=u.reg_read(arm.UC_ARM_REG_R0)
        if actual!=int(wanted):raise ValueError('Original record validator differs')
        rows.append(dict(name=name,accepted=bool(actual),execution=t))
    return rows

def prepare_writes(raw,h):
    rows=[];program=h+0x13e;key=literal(raw,decode(raw,program+0x26,4)[0])
    if key!=0x12344321:raise ValueError('Different MRAM programming constant')
    for slot in [0,9]:
        for half in [0,1]:
            entry=program+(0x26 if half==0 else 0x4c);call=program+(0x32 if half==0 else 0x5a)
            # Explicit state around the original lock/yield calls, not a whole helper.
            u,t=execute(raw,entry,{5:32,6:WORK+0x300,8:TAIL+slot*256,9:key},bytes(256),stop=[call])
            expected=[key,WORK+0x300+half*128,TAIL+slot*256+half*128,32]
            actual=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)]
            if actual!=expected:raise ValueError('Original split-write arguments differ')
            ins=decode(raw,call,4)[0]
            rows.append(dict(slot=slot,half=half,arguments=actual,callee=int(ins.op_str[1:],16),scope='Stops before MRAM program call; synthetic lock/yield boundary inputs',execution=t))
    return rows

def zero_prefix(raw,h):
    entry=h-0x9c2;load=decode(raw,entry+14,4)[0];buffer=literal(raw,load);size=256
    if not SRAM+16<=buffer<=SRAM+0x80000-size-16:raise ValueError('Scratch outside bounded SRAM')
    u,t=execute(raw,entry,{},bytes(256),stop=[entry+30],initial=lambda u:u.mem_write(buffer-16,b'\xa5'*(size+32)))
    if bytes(u.mem_read(buffer,size))!=bytes(size) or bytes(u.mem_read(buffer-16,16))!=b'\xa5'*16 or bytes(u.mem_read(buffer+size,16))!=b'\xa5'*16:raise ValueError('Original zero-buffer extent differs')
    return dict(buffer=buffer,length=size,neighbors_preserved=True,execution=t)

def inspect_case(s,case):
    f=s/'em9305-version-sample-main-02'/case;r=json.loads((f/'report.json').read_text());p=json.loads((f/'plan.json').read_text());ap=s/'em9305-version-saved-audit-01'/case/'report.json';audit=json.loads(ap.read_text())
    if not r['passed'] or not audit['passed']:raise ValueError('Unverified native source')
    for n,pin in audit['capture_hashes'].items():
        if sha(f/n)!=pin:raise ValueError('Changed native source '+n)
    validate_memory_exports(f,memory_exports(p),r['memory_exports']);raw=(f/'main.bin').read_bytes();regs=r['observed']['register_context'];h=regs['r15']-2;caller=(regs['r14']&~1)-4
    if regs['r0']!=TAIL or regs['r6']!=0 or caller!=h-0x880:raise ValueError('Different natural first-slot consumer')
    base=literal(raw,decode(raw,caller-24,4)[0])
    if base!=TAIL:raise ValueError('Different slot array base')
    limit=decode(raw,caller-28,2)[0]
    if (limit.mnemonic,limit.op_str)!=('cmp','r0, #0xa'):raise ValueError('Different slot count')
    logload=decode(raw,h-0x84c,4)[0];message=literal(raw,logload);text=raw[message-BASE:message-BASE+120].split(b'\0')[0].decode('ascii')
    if text.rstrip('\r\n')!='keydb heal: slot[%d] uninit fill=0x%02x -> zeroing':raise ValueError('Unidentified key database caller')
    uniform_rows=uniform(raw,h);decisions=decide(raw,h);valid=validate_records(raw,h);writes=prepare_writes(raw,h);zero=zero_prefix(raw,h)
    return dict(case=case,raw_sha256=sha(f/'main.bin'),native_report_sha256=sha(f/'report.json'),audit_sha256=sha(ap),uniform_helper=h,caller=caller,heal_entry=h-0x9c2,slot_base=TAIL,slot_stride=256,slot_count=10,slot_extent_end=TAIL+2560,source_message=text,uniform_samples=uniform_rows,decision_samples=decisions,validator_samples=valid,program_argument_samples=writes,zero_buffer=zero)

def inspect_bundles(private):
    rows=[]
    for name in ['stock_base','stock_current','cfw']:
        rel,pin=PINS[name];f=private/rel;data=f.read_bytes()
        if sha(f)!=pin:raise ValueError('Bundle pin differs')
        profile,raw=load_pinned_main(data);components=parse_bundle(data)
        if profile!=name:raise ValueError('Unexpected bundle profile')
        main=next(c for c in components if c.type_id==0);base=struct.unpack_from('<I',main.payload,20)[0];end=base+len(raw)
        if end>0x7f8000 or any(c.type_id not in [0,1,3,4,5,6] for c in components):raise ValueError('Unreviewed bundle destination or component')
        rows.append(dict(profile=name,bundle_sha256=pin,main_base=base,main_raw_end=end,tail_in_main=False,components=[dict(name=c.name,type_id=c.type_id,bytes=len(c.payload),sha256=hashlib.sha256(c.payload).hexdigest()) for c in components],scope='Pinned closed six-component OTA table; no dedicated Apollo tail segment. Other MCU payloads are not mapped as Apollo MRAM. Not a search of every possible external backup.'))
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve existing result')
    rows=[inspect_case(a.simulator,c) for c in ['stock24','stock23','cfw']];bundles=inspect_bundles(a.simulator.parent)
    count=sum(len(x['uniform_samples'])+len(x['decision_samples'])+len(x['validator_samples'])+len(x['program_argument_samples'])+1 for x in rows)
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,bundles=bundles,original_fragment_scenarios=count,native_main_rerun=False,hardware_accessed=False,real_pairing_keys_collected=False,whole_heal_function_executed=False,mram_program_executed=False,real_tail_bytes_known=False),indent=2)+'\n');print('keydb source and '+str(count)+' original ARM scenarios verified; 3 OTA bundles lack main tail')

if __name__=='__main__':main()
