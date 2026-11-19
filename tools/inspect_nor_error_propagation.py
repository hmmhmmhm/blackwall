"""Run original NOR/poll/FAL/FlashDB return paths with explicit hardware ABI leaves.

No main boot, device timing, backing commit, or recovery is simulated here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu, WORK, STOP
from kvtime_layout import discover, literal
from pinned_main import MAIN_LAYOUT
from runtime_firmware_candidate import PROFILES
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm


def body(raw, entry, length):
    result=[]
    for i in decode(raw,entry,length):
        result.append(i)
        if i.mnemonic.startswith('pop') and 'pc' in i.op_str:
            return result
    raise ValueError('Missing original return')


def discover_chain(raw, ram, profile):
    def word(a):
        if 0x20000000<=a<=0x2037fffc:return struct.unpack_from('<I',ram,a-0x20000000)[0]
        if 0x438000<=a<=0x438000+len(raw)-4:return struct.unpack_from('<I',raw,a-0x438000)[0]
        raise ValueError('Unmapped descriptor word')
    layout=discover(raw,profile)
    signature=bytes.fromhex('38b50025447e002c01d0032007e0')
    off=raw.find(signature)
    if off<0 or raw.find(signature,off+1)>=0:raise ValueError('Ambiguous FlashDB write wrapper')
    fdb=off+0x438000;fdb_body=body(raw,fdb,0x30)
    part=next(i.operands[0].imm for i in fdb_body if i.mnemonic=='bl')
    part_body=body(raw,part,0x60)
    lookup=next(i.operands[0].imm for i in part_body if i.mnemonic=='bl')
    look=decode(raw,lookup,16)
    if (len(look)<6 or look[0].mnemonic!='ldr' or not look[0].op_str.startswith('r2, [pc,')
            or look[1].mnemonic!='ldr' or not look[1].op_str.startswith('r1, [pc,')
            or [(i.mnemonic,i.op_str) for i in look[2:6]]!=[
                ('ldr','r1, [r1]'),('subs','r0, r0, r1'),('asrs','r0, r0, #6'),
                ('ldr.w','r0, [r2, r0, lsl #2]')]):
        raise ValueError('Unknown device lookup')
    partition=word(layout['database']+8)
    table=literal(raw,look[0]);base=word(literal(raw,look[1]))
    if partition<base or (partition-base)%64:raise ValueError('Unknown partition table stride')
    device=word(table+4*((partition-base)//64))
    adapter=word(device+0x2c)&~1
    adapter_body=body(raw,adapter,0x80)
    nor=next(i.operands[0].imm for i in adapter_body if i.mnemonic=='bl')
    nor_body=body(raw,nor,0x120)
    if raw[nor-0x438000:nor-0x438000+12]!=bytes.fromhex('2de9fc4107000e0015000024'):
        raise ValueError('Unknown original NOR write')
    def call_after(mnemonic,operands):
        hits=[nor_body[n+1].operands[0].imm for n,i in enumerate(nor_body[:-1])
              if (i.mnemonic,i.op_str)==(mnemonic,operands) and nor_body[n+1].mnemonic=='bl']
        if len(hits)!=1:raise ValueError('Ambiguous original command call')
        return hits[0]
    transfer=call_after('movs','r0, #2');poll=call_after('movs','r0, #0xa')
    poll_body=body(raw,poll,0x60)
    calls=[i.operands[0].imm for i in poll_body if i.mnemonic=='bl']
    if len(calls)!=6 or calls[0]!=calls[-2] or calls[1]!=calls[-1]:
        raise ValueError('Unknown original bounded poll')
    delay,status,context,task_delay=calls[:4]
    return dict(layout=layout,fdb=fdb,part=part,partition=partition,device=device,adapter=adapter,nor=nor,
                transfer=transfer,poll=poll,status=status,delay=delay,context=context,task_delay=task_delay,
                partition_length=word(partition+0x38)),(fdb_body,part_body,adapter_body,nor_body,poll_body)


def inspect_case(source):
    pins=json.loads((source/'capture-files.json').read_text())['files']
    for name in ('main.bin','connection-profile.json','exports/sram-full.bin'):
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=pins[name]:raise ValueError('Source changed')
    raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes()
    profile=json.loads((source/'connection-profile.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=MAIN_LAYOUT[PROFILES[profile['case']]][3]:raise ValueError('Not original main')
    c,bodies=discover_chain(raw,ram,profile)
    fdb_body,part_body,adapter_body,nor_body,poll_body=bodies
    nor_leaves={i.operands[0].imm for i in nor_body if i.mnemonic=='bl'}-{c['poll']}
    adapter_leaves={i.operands[0].imm for i in adapter_body if i.mnemonic=='bl'}-{c['nor']}
    # The last adapter call reports the concrete device error; it is an ABI
    # boundary, and its arguments are recorded rather than treated as recovery.
    notification=[i.operands[0].imm for i in adapter_body if i.mnemonic=='bl'][-1]
    scenarios=[('normal',0,0,False,1,0),('timeout-bare',1,0,False,1,0),
               ('timeout-task',1,0,False,1,2),('transfer-error',0,7,False,1,0),
               ('zero-length',0,0,False,0,0),('partition-out-of-range',0,0,False,1,0),
               ('read-only-db',0,0,True,1,0)]
    rows=[]
    for name,busy,transfer_error,readonly,length,context_value in scenarios:
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK,b'\xa5'*0x10000)
        if readonly:u.mem_write(c['layout']['database']+0x19,b'\x01')
        initial=bytes(u.mem_read(0x20000000,len(ram)))
        u.reg_write(arm.UC_ARM_REG_R0,c['layout']['database'])
        u.reg_write(arm.UC_ARM_REG_R1,c['partition_length']+1 if name=='partition-out-of-range' else 0)
        u.reg_write(arm.UC_ARM_REG_R2,WORK+0x100)
        u.reg_write(arm.UC_ARM_REG_R3,length)
        returned={};status_reads=[];delays=[];notices=[];transfers=[];trace=[]
        returns={fdb_body[-1].address:'flashdb',part_body[-1].address:'partition',
                 adapter_body[-1].address:'adapter',nor_body[-1].address:'nor'}
        leaves=nor_leaves|adapter_leaves|{c['status'],c['delay'],c['context'],c['task_delay']}
        def abi(core,pc,size,user):
            trace.append(pc)
            if pc in returns:returned[returns[pc]]=core.reg_read(arm.UC_ARM_REG_R0)&0xffffffff
            if pc not in leaves:return
            result=0
            if pc==c['status']:
                status_reads.append(busy);result=busy
            elif pc==c['transfer']:
                transfers.append([core.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)])
                result=transfer_error
            elif pc==c['context']:result=context_value
            elif pc in (c['delay'],c['task_delay']):delays.append([pc,core.reg_read(arm.UC_ARM_REG_R0)])
            elif pc==notification:notices.append([core.reg_read(arm.UC_ARM_REG_R0),core.reg_read(arm.UC_ARM_REG_R1)])
            core.reg_write(arm.UC_ARM_REG_R0,result)
            core.reg_write(arm.UC_ARM_REG_PC,core.reg_read(arm.UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,abi);u.emu_start(c['fdb']|1,STOP,count=100000)
        expected=({'flashdb':3} if readonly else {'partition':0xffffffff,'flashdb':3} if name=='partition-out-of-range'
                  else {'nor':4 if busy else transfer_error if transfer_error else 6 if not length else 0,
                        'adapter':0 if busy or transfer_error or not length else length,
                        'partition':0 if busy or transfer_error or not length else length,'flashdb':0})
        checks=dict(returned_to_caller=u.reg_read(arm.UC_ARM_REG_PC)==STOP,
            stack_restored=u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000,
            exact_layer_returns=returned==expected,
            exact_original_busy_poll=len(status_reads)==(210 if busy else 1 if name=='normal' else 0),
            concrete_error_notice=notices==([[2,expected['nor']]] if expected.get('nor',0)!=0 else []),
            source_sram_unchanged=bytes(u.mem_read(0x20000000,len(ram)))==initial)
        if not all(checks.values()):raise ValueError((name,returned,len(status_reads),notices,checks))
        rows.append(dict(fixture=name,returns=returned,status_reads=len(status_reads),delays=delays,
            notifications=notices,transfers=transfers,checks=checks,
            trace_sha256=hashlib.sha256(b''.join(struct.pack('<I',pc) for pc in trace)).hexdigest()))
    return dict(case=profile['case'],passed=True,chain=c,scenarios=rows,
        original_main_sha256=hashlib.sha256(raw).hexdigest(),
        stubbed_abi_entries=sorted(nor_leaves|adapter_leaves|{c['status'],c['delay'],c['context'],c['task_delay']}))


def inspect_erase_case(source):
    pins=json.loads((source/'capture-files.json').read_text())['files']
    for name in ('main.bin','connection-profile.json','exports/sram-full.bin'):
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=pins[name]:raise ValueError('Source changed')
    raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes()
    profile=json.loads((source/'connection-profile.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=MAIN_LAYOUT[PROFILES[profile['case']]][3]:raise ValueError('Not original main')
    c,_=discover_chain(raw,ram,profile)
    signature=bytes.fromhex('10b50024437e002b01d0012007e0')
    off=raw.find(signature)
    if off<0 or raw.find(signature,off+1)>=0:raise ValueError('Ambiguous erase wrapper')
    fdb=off+0x438000;fb=body(raw,fdb,0x30)
    part=next(i.operands[0].imm for i in fb if i.mnemonic=='bl');pb=body(raw,part,0x50)
    adapter=struct.unpack_from('<I',raw,c['device']+0x30-0x438000)[0]&~1
    ab=body(raw,adapter,0x150)
    calls=[i.operands[0].imm for i in ab if i.mnemonic=='bl']
    targets=[a for a in set(calls) if raw[a-0x438000:a-0x438000+4]==bytes.fromhex('3eb50500')]
    if len(targets)!=1:raise ValueError('Unknown NOR sector erase callback')
    nor=targets[0];nb=body(raw,nor,0x110)
    ready=[]
    for i in nb:
        if i.mnemonic!='bl':continue
        candidate=i.operands[0].imm
        code=decode(raw,candidate,12)
        if len(code)==4 and [(x.mnemonic,x.op_str) for x in code]==[
                ('push','{r7, lr}'),('mov.w','r0, #0x3e8'),('bl','#'+hex(c['poll'])),('pop','{r1, pc}')]:
            ready.append(candidate)
    if len(ready)!=2 or ready[0]!=ready[1]:raise ValueError('Unknown erase readiness polls')
    leaves=({i.operands[0].imm for i in nb if i.mnemonic=='bl'}-{ready[0]})|(
        set(calls)-{nor})|{c['status'],c['delay'],c['context'],c['task_delay']}
    notification=calls[-1]
    physical=struct.unpack_from('<I',raw,c['partition']+0x34-0x438000)[0]
    # name, offset, length, timeout-after-transfer-count, transfer-error, readonly
    fixtures=[('normal-sector',0,4096,None,0,False),('rounded-byte',0,1,None,0,False),
        ('normal-two-sectors',0,8192,None,0,False),('timeout-after-command',0,4096,1,0,False),
        ('timeout-before-command',0,4096,0,0,False),('second-sector-timeout',0,8192,2,0,False),
        ('transfer-error',0,4096,None,7,False),('unaligned-address',1,4096,None,0,False),
        ('zero-length',0,0,None,0,False),('partition-out-of-range',c['partition_length']+1,4096,None,0,False),
        ('read-only-db',0,4096,None,0,True)]
    rows=[]
    for name,offset,length,timeout_after,transfer_error,readonly in fixtures:
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(WORK,b'\xa5'*0x10000)
        if readonly:u.mem_write(c['layout']['database']+0x19,b'\x01')
        initial=bytes(u.mem_read(0x20000000,len(ram)))
        for n,v in enumerate((c['layout']['database'],offset,length)):
            u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
        returned={};nor_returns=[];transfers=[];notices=[];status=[];trace=[]
        returns={fb[-1].address:'flashdb',pb[-1].address:'partition',ab[-1].address:'adapter',nb[-1].address:'nor'}
        def abi(core,pc,size,user):
            trace.append(pc)
            if pc in returns:
                value=core.reg_read(arm.UC_ARM_REG_R0)&0xffffffff;returned[returns[pc]]=value
                if returns[pc]=='nor':nor_returns.append(value)
            if pc not in leaves:return
            result=0
            if pc==c['status']:
                result=int(timeout_after is not None and len(transfers)>=timeout_after);status.append(result)
            elif pc==c['transfer']:
                transfers.append([core.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(4)])
                result=transfer_error
            elif pc==notification:notices.append([core.reg_read(arm.UC_ARM_REG_R0),core.reg_read(arm.UC_ARM_REG_R1)])
            core.reg_write(arm.UC_ARM_REG_R0,result)
            core.reg_write(arm.UC_ARM_REG_PC,core.reg_read(arm.UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,abi);u.emu_start(fdb|1,STOP,count=150000)
        no_device=readonly or name=='partition-out-of-range'
        no_nor=no_device or name in ('unaligned-address','zero-length')
        error=3 if timeout_after==0 else 4 if timeout_after is not None else transfer_error
        expected=({'flashdb':1} if readonly else {'partition':0xffffffff,'flashdb':1} if no_device
            else {'adapter':0,'partition':0,'flashdb':0} if no_nor
            else {'nor':error,'adapter':0 if error else 4096,'partition':0 if error else 4096,'flashdb':0})
        count=0 if no_nor or timeout_after==0 else 2 if length==8192 else 1
        expected_status=0 if no_nor else 1200 if timeout_after==0 else 1201 if timeout_after==1 else 1203 if timeout_after==2 else 1 if transfer_error else 2*count
        expected_nor=[] if no_nor else [0,error] if count==2 else [error]
        checks=dict(returned_to_caller=u.reg_read(arm.UC_ARM_REG_PC)==STOP,
            stack_restored=u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000,
            exact_layer_returns=returned==expected and nor_returns==expected_nor,
            exact_original_polls=len(status)==expected_status,
            actual_sector_commands=transfers==[[0x20,physical+offset+4096*n,1,0] for n in range(count)],
            concrete_error_notice=notices==([[3,error]] if error and not no_nor else []),
            source_sram_unchanged=bytes(u.mem_read(0x20000000,len(ram)))==initial)
        if not all(checks.values()):raise ValueError((name,returned,nor_returns,len(status),transfers,notices,checks))
        rows.append(dict(fixture=name,requested_offset=offset,requested_length=length,returns=returned,
            nor_returns=nor_returns,status_reads=len(status),transfers=transfers,notifications=notices,checks=checks,
            trace_sha256=hashlib.sha256(b''.join(struct.pack('<I',pc) for pc in trace)).hexdigest()))
    return dict(case=profile['case'],passed=True,chain=dict(fdb=fdb,part=part,adapter=adapter,nor=nor,ready=ready[0],
        poll=c['poll'],partition=c['partition'],physical=physical),scenarios=rows,
        original_main_sha256=hashlib.sha256(raw).hexdigest(),stubbed_abi_entries=sorted(leaves))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--operation',choices=('program','erase'),default='program');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    inspector=inspect_case if a.operation=='program' else inspect_erase_case
    cases=[inspector(a.simulator/'runtime-kv-commit-native-01'/n) for n in ('stock24','stock23','cfw')]
    a.output.mkdir(mode=0o700,parents=True)
    report=dict(passed=True,cases=cases,engine='isolated original ARM on Unicorn M7',
        peripheral_and_lifecycle_abi_stubbed=True,original_poll_loop_executed=True,
        nor_backing_committed=False,natural_main_recovery_verified=False,e08_complete=False,hardware_accessed=False)
    if a.operation=='erase':report['operation']='erase'
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,original_images=len(cases),scenarios=sum(len(c['scenarios']) for c in cases))))


if __name__=='__main__':main()
