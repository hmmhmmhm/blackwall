"""Original LE buffer metadata stores/getter; observer equivalence and malformed returns."""
import argparse,hashlib,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_application_vendor_address import call,sha
from inspect_nema_blocking_wait import cpu,WORK
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

PROFILES=[('small',0,27,4),('large',0,251,8),('zero-size',0,0,4),('zero-credits',0,27,0),('both-zero',0,0,0),('marker',0,0x1234,127),('maximum',0,65535,255),('error-status',1,27,4),('short-return',0,27,4),('wire-truncated',0,27,4),('unknown-opcode',0,27,4),('no-event',0,27,4)]


def discover(raw,ctx):
    callbacks=[]
    for ins in decode(raw,ctx['upper_handler'],0x90):
        if ins.mnemonic=='bl':
            pc=ins.operands[0].imm
            if ('cmp','r1, #0xe') in [(i.mnemonic,i.op_str) for i in decode(raw,pc,12)]:callbacks.append(pc)
    if len(callbacks)!=1:raise ValueError('Ambiguous original initialization callback')
    callback=callbacks[0];writer=callback+0xc8;base=literal(raw,decode(raw,writer,4)[0])
    for offset,mnemonic,operands in [(12,'strh','r0, [r1, #0x7e]'),(20,'strb','r2, [r1, #0x83]'),(30,'strb','r0, [r1, #0x82]')]:
        i=decode(raw,writer+offset,4)[0]
        if i.mnemonic.split('.')[0]!=mnemonic or i.op_str!=operands:raise ValueError('Unknown buffer metadata stores')
    getters=[];body=decode(raw,ctx['upper_dispatch'],0x100)
    for n,ins in enumerate(body):
        if ins.mnemonic.split('.')[0]=='ldrh' and ins.op_str=='r0, [r0, #0x7e]' and literal(raw,body[n-1])==base:getters.append(body[n-1].address)
    if len(getters)!=1 or not 0x20000000<=base<=0x20380000-0x84:raise ValueError('Unknown original getter/control block')
    return dict(callback=callback,writer=writer,base=base,getter=getters[0])


def execute(raw,ram,ctx,ring,c,profile,observe):
    name,status,size,count=profile;u=cpu(raw,ram,WORK+0xf000);phases=[call(u,ctx['ring_pop'],(ring,0,1))]
    initial=(struct.unpack_from('<H',ram,c['base']+0x7e-0x20000000)[0],ram[c['base']+0x82-0x20000000],ram[c['base']+0x83-0x20000000])
    opcode=0 if name=='unknown-opcode' else 0x2002
    event=bytes([4,14,7,1,opcode&255,opcode>>8,status])+struct.pack('<H',size)+bytes([count])
    if name=='short-return':event=bytes.fromhex('040e0401022000')
    if name=='wire-truncated':event=event[:-1]
    if name=='no-event':event=None
    if event is not None:u.mem_write(WORK+0x100,event);phases.append(call(u,ctx['application_parser'],(WORK+0x100,len(event))))
    observations=dict(callback_packets=[],data_reads=[],stores=[])
    if observe:
        sites={c['writer']+12:(0,0x7e,2),c['writer']+20:(2,0x83,1),c['writer']+30:(0,0x82,1)}
        def hook(current,pc,size_,unused):
            if pc==c['callback']:
                pointer=current.reg_read(arm.UC_ARM_REG_R0);header=bytes(current.mem_read(pointer,2))
                observations['callback_packets'].append(dict(pointer=pointer,event_code=header[0],declared_bytes=header[1]+2,end=pointer+header[1]+2))
            if pc==c['writer']+2:observations['data_reads'].append(dict(address=current.reg_read(arm.UC_ARM_REG_R4),required_bytes=3))
            if pc in sites:
                source,offset,width=sites[pc];address=current.reg_read(arm.UC_ARM_REG_R1)+offset;value=current.reg_read(getattr(arm,'UC_ARM_REG_R'+str(source)))&((1<<(width*8))-1)
                observations['stores'].append(dict(pc=pc,address=address,width=width,value=value))
        u.hook_add(UC_HOOK_CODE,hook)
    phases.append(call(u,ctx['upper_handler'],(1,0)))
    fields=(struct.unpack('<H',bytes(u.mem_read(c['base']+0x7e,2)))[0],int(bytes(u.mem_read(c['base']+0x82,1))[0]),int(bytes(u.mem_read(c['base']+0x83,1))[0]))
    phases.append(call(u,c['getter'],()))
    getter=u.reg_read(arm.UC_ARM_REG_R0)
    if getter!=fields[0]:raise ValueError('Original buffer-length getter differs from stored field')
    inactive=name in ['wire-truncated','unknown-opcode','no-event']
    if inactive:
        if fields!=initial:raise ValueError('Incomplete/unknown input changed metadata')
    elif name!='short-return' and fields!=(size,count,count):raise ValueError('Original buffer metadata copy differs')
    queue=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))));next_packet=None
    if not inactive:
        ptr=queue[5]+queue[1];n=struct.unpack('<I',bytes(u.mem_read(ptr,4)))[0];next_packet=bytes(u.mem_read(ptr+4,n)).hex()
        if queue[:5]!=[520,260,260,2080,260] or next_packet!='011c2000':raise ValueError('Different next initialization query')
    elif queue[:5]!=[260,260,0,2080,260]:raise ValueError('Incomplete/unknown input queued a command')
    if observe:
        if inactive and (observations['stores'] or observations['data_reads']):raise ValueError('Inactive consumer executed buffer stores')
        if not inactive:
            expected=[(c['base']+0x7e,2,fields[0]),(c['base']+0x83,1,fields[2]),(c['base']+0x82,1,fields[1])]
            if [(x['address'],x['width'],x['value']) for x in observations['stores']]!=expected or len(observations['callback_packets'])!=1 or len(observations['data_reads'])!=1:raise ValueError('Different observed original stores')
            packet=observations['callback_packets'][0];read=observations['data_reads'][0];outside=read['address']+3>packet['end']
            if outside!=(name=='short-return') or read['address']!=packet['pointer']+6:raise ValueError('Different command return boundary')
            observations['read_beyond_declared_return']=outside
    special=[arm.UC_ARM_REG_XPSR,arm.UC_ARM_REG_CONTROL,arm.UC_ARM_REG_PRIMASK,arm.UC_ARM_REG_BASEPRI,arm.UC_ARM_REG_FAULTMASK,arm.UC_ARM_REG_MSP,arm.UC_ARM_REG_PSP]
    state=(bytes(u.mem_read(0x20000000,len(ram))),bytes(u.mem_read(WORK,0x10000)),tuple(u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(16)),phases,bytes(u.mem_read(0xe000e000,0x2000)),tuple(u.reg_read(reg) for reg in special))
    result=dict(profile=name,event=event.hex() if event else None,fields_before=list(initial),fields_after=list(fields),getter=getter,next_packet=next_packet,queue_words=queue,executions=phases,observations=observations)
    return result,state


def inspect(s,case):
    f=s/'standard-hci-main-01'/case;ap=s/'standard-hci-saved-audit-01'/case/'report.json';a=json.loads(ap.read_text());r=json.loads((f/'report.json').read_text())
    if not a['passed'] or not r['passed'] or r['hardware_accessed']:raise ValueError('Unverified native source')
    for n,digest in a['capture_hashes'].items():
        if sha(f/n)!=digest:raise ValueError('Changed native source '+n)
    p=s/'application-hci-transaction-source-02/report.json';pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(p)!=pin:raise ValueError('Changed original parser/ring source')
    ctx=next(x for x in json.loads(p.read_text())['cases'] if x['case']==case)
    p=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(p)!=pin:raise ValueError('Changed original ring metadata')
    old=next(x for x in json.loads(p.read_text())['cases'] if x['case']==case);ring=old['tx_ring'];raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes()
    regs=r['observed']['register_context'];packet=ram[regs['r10']-0x20000000:regs['r10']-0x20000000+regs['r8']]
    if packet.hex()!='01022000':raise ValueError('Source is not the pending LE buffer query')
    c=discover(raw,ctx);rows=[]
    for profile in PROFILES:
        off,before=execute(raw,ram,ctx,ring,c,profile,False);on,after=execute(raw,ram,ctx,ring,c,profile,True)
        if before!=after:raise ValueError('Code observer changed trace/RAM/WORK/registers')
        on['observer_on_off_equal']=True;on['final_sram_sha256']=hashlib.sha256(after[0]).hexdigest();rows.append(on)
    return dict(case=case,raw_sha256=sha(f/'main.bin'),sram_sha256=sha(f/'exports/sram-full.bin'),audit_sha256=sha(ap),contract=c,samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_software_scenarios=36,observer_equivalence_pairs=36,engine='Original ARM on Unicorn M7; synthetic calls/registers/stack; validated full native SRAM; code/register read observer, no memory-write hook',native_executions=0,peripheral_models_changed=False,actual_acl_transmission_or_credit_consumption_verified=False,physical_controller_data_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('LE buffer source:36 software scenarios/36 observer-equivalence pairs passed; short return exceeds declared data')


if __name__=='__main__':main()
