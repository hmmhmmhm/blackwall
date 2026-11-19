"""Bounded original ARM constructors and trim fragments; no controller execution."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,BASE,SRAM,WORK,STOP
from inspect_em9305_hci_framing import discover,literal
from inspect_ambiq_target import decode
from run_native_candidate import memory_exports,validate_memory_exports,MAIN_LAYOUT


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(raw,entry,ends,registers,data=b'',stack=b''):
    u=cpu(raw,b'\0'*0x80000,WORK+0xf000);u.mem_write(WORK+0x300,data);u.mem_write(WORK+0xf000,stack);trace=[];stopped=[]
    for n,v in registers.items():u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
    def hook(c,pc,size,user):
        trace.append(pc)
        if pc in ends:stopped.append(pc);c.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry|1,STOP,count=20000)
    if len(stopped)!=1:raise ValueError('Fragment did not reach declared boundary')
    return u,dict(stop=stopped[0],instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def constructor(raw,c,kind,data):
    offsets={'version':0xd08,'factory':0xd92,'erase':0xdd8,'program':0xe0a}
    entry=c['read']+offsets[kind];command=c['read']+0x432
    u,t=run(raw,entry,{command},{0:WORK+0x200,1:WORK+0x300},data)
    n=u.reg_read(arm.UC_ARM_REG_R2);p=u.reg_read(arm.UC_ARM_REG_R1)
    if not 0<n<=24:raise ValueError('Unexpected packet length')
    packet=bytes(u.mem_read(p,n))
    expected={'version':bytes.fromhex('0101fd050020400004'),'factory':bytes.fromhex('0101fd05a07c400008'),'erase':bytes.fromhex('0107fd020102'),'program':bytes.fromhex('0103fd14805c400002000000')+struct.pack('<I',zlib.crc32(data))+data}[kind]
    if packet!=expected or u.reg_read(arm.UC_ARM_REG_R0)!=WORK+0x200:raise ValueError('Different original packet construction')
    return dict(kind=kind,entry=entry,command_wait=command,packet=packet.hex(),data=data.hex() if kind=='program' else None,crc32=zlib.crc32(data) if kind=='program' else None,execution=t)


def trim_bits(raw,c,data,desired):
    entry=c['read']+0xfb2;end=c['read']+0xfd6
    u,t=run(raw,entry,{end},{6:desired},stack=data)
    actual=bytes(u.mem_read(WORK+0xf000,8));value=int.from_bytes(data,'little');mask=0x3f<<39
    expected=((value&~mask)|((desired&0x3f)<<39)).to_bytes(8,'little')
    if actual!=expected:raise ValueError('Original trim update changed other bits')
    return dict(input=data.hex(),desired=desired,output=actual.hex(),mask=mask,execution=t)


def read_status(raw,c,status,transport):
    entry=c['read']+0x8d8;ok=c['read']+0x8f4;error=c['read']+0x8e4;done=c['read']+0x902
    # Stop at the error logger or data-copy prefix, before their external effects.
    stack=bytearray(32);stack[14]=status
    u,t=run(raw,entry,{ok,error,done},{5:transport},stack=bytes(stack))
    expected=done if transport else error if status else ok
    if t['stop']!=expected:raise ValueError('Generic read status handling differs')
    return dict(status=status,transport=transport,result='transport-error' if transport else 'status-error' if status else 'copy-data',execution=t)


def version_log(raw,c,value,transport):
    entry=c['read']-0x352;logger=c['read']-0x32a;skip=c['read']-0x326
    u,t=run(raw,entry,{logger,skip},{0:transport,4:WORK+0x300},struct.pack('<I',value))
    logged=not transport and value!=0xffffffff
    if t['stop']!=(logger if logged else skip):raise ValueError('Different version-log decision')
    digits=None
    if logged:
        digits=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in [1,2,3]]+[struct.unpack('<I',u.mem_read(WORK+0xf000,4))[0]]
        if digits!=list(value.to_bytes(4,'big')):raise ValueError('Different version-log byte order')
    return dict(value=value,transport=transport,logged=logged,digits=digits,execution=t)


def trim_error_exit(raw,c,kind):
    # Start after the diagnostic call, with the original r4=0 initializer.
    # This isolates return-value handling and does not simulate the logger.
    offsets={'first-read':0xf4c,'reset':0xf9a,'factory-read':0xfb0,'erase':0xfe6,'program':0xffa,'reinit':0x100c}
    u,t=run(raw,c['read']+offsets[kind],{c['read']+0x1012},{4:0})
    result=u.reg_read(arm.UC_ARM_REG_R0);expected=1 if kind=='reset' else 5 if kind=='reinit' else 0
    if result!=expected:raise ValueError('Different trim error return fragment')
    return dict(error=kind,return_value=result,scope='After diagnostic call; r4 initialized to original zero, not whole error path',execution=t)


def strings(raw,c):
    rows={}
    for name,delta in [('version-log',-0x32e),('normal-update',0xf34),('trim-values',0xf6a),('already-updated',0xf7a),('force-update',0xf84),('reset-error',0xf94),('factory-error',0xfaa),('erase-error',0xfe0),('write-error',0xff4),('reinit-error',0x1006)]:
        i=decode(raw,c['read']+delta,4)[0];a=literal(raw,i);text=raw[a-BASE:a-BASE+160].split(b'\0')[0].decode('ascii')
        rows[name]=dict(load_pc=i.address,address=a,text=text)
    return rows


def static_contract(raw,c):
    trim=c['read']+0xf16;instructions=decode(raw,trim,0x100);calls=[(i.address,int(i.op_str[1:],16)) for i in instructions if i.mnemonic=='bl']
    targets=[target for _,target in calls]
    required=[c['read']+0xeb2,c['read']+0x6e8,c['read']+0xd92,c['read']+0xdd8,c['read']+0xe0a,c['init']]
    if any(target not in targets for target in required):raise ValueError('Unknown trim call graph')
    if [target for target in targets if target in required]!=required:raise ValueError('Different trim operation order')
    initializer=decode(raw,c['read']+0xf20,2)[0]
    if (initializer.mnemonic,initializer.op_str)!=('movs','r4, #0'):raise ValueError('Unknown trim return initializer')
    reset=decode(raw,c['read']+0x6e8,0x78)
    template_load=decode(raw,c['read']+0x6fe,4)[0];template=literal(raw,template_load)
    if raw[template-BASE:template-BASE+4]!=bytes.fromhex('04ff0103'):raise ValueError('Different reset event template')
    reset_call=next(i for i in reset if i.mnemonic=='bl' and i.address==c['read']+0x70e)
    reset_pin_function=int(reset_call.op_str[1:],16);pin_body=decode(raw,reset_pin_function,0x18)
    if ('movs','r0, #0x5d') not in [(i.mnemonic,i.op_str) for i in pin_body]:raise ValueError('Different reset GPIO')
    return dict(trim_entry=trim,calls=[dict(pc=pc,target=target) for pc,target in calls],reset_entry=c['read']+0x6e8,reset_pin_function=reset_pin_function,reset_rdy_pc=c['read']+0x72a,reset_expected_event='04ff0103',strings=strings(raw,c))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    verification=json.loads((a.simulator/'em9305-read-transport-verification-01/manifest.json').read_text());rows=[]
    for case in ['stock24','stock23','cfw']:
        folder='em9305-read-command-trim7-main-01/'+case;source=a.simulator/folder;report=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text());pin=next(x for x in verification['captures'] if x['path']==folder)
        if not verification['passed'] or not report['passed'] or sha(source/'report.json')!=pin['report_sha256']:raise ValueError('Unverified native input')
        if sha(source/'main.bin')!=MAIN_LAYOUT[plan['cases'][case]][3]:raise ValueError('Original main hash differs')
        validate_memory_exports(source,memory_exports(plan),report['memory_exports']);raw=(source/'main.bin').read_bytes();c=discover(raw)
        ram=(source/'exports/sram-full.bin').read_bytes();regs=report['observed']['register_context'];p,n=regs['r10'],regs['r8'];pending=ram[p-SRAM:p-SRAM+n]
        if pending.hex()!='0101fd050020400004':raise ValueError('Different actual next packet')
        data=bytes.fromhex('0123456789abcdef');constructors=[constructor(raw,c,k,data) for k in ['version','factory','erase','program']]
        variants=[trim_bits(raw,c,d,w) for d in [bytes(8),b'\xff'*8,data] for w in [0,7,63]]
        statuses=[read_status(raw,c,status,transport) for status in [0,1,255] for transport in [0,8]]
        versions=[version_log(raw,c,value,transport) for value in [0,0xffffffff,0x01020304,0x12345678] for transport in [0,8]]
        exits=[trim_error_exit(raw,c,k) for k in ['first-read','reset','factory-read','erase','program','reinit']]
        rows.append(dict(case=case,raw_sha256=sha(source/'main.bin'),native_report_sha256=sha(source/'report.json'),actual_pending_packet=pending.hex(),contract=static_contract(raw,c),constructors=constructors,trim_samples=variants,read_status_samples=statuses,version_log_samples=versions,trim_error_exit_samples=exits))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_fragment_scenarios=99,native_main_rerun=False,hardware_accessed=False,whole_trim_function_executed=False,controller_nvm_modified=False,real_controller_version_or_trim_known=False),indent=2)+'\n');print('original constructors/trim/status/version/error exits: 99 bounded ARM scenarios passed')

if __name__=='__main__':main()
