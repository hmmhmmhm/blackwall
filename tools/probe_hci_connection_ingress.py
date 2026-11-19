"""Original H4/LE connection decoder and live DM callback contract, isolated ARM."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UcError, UC_HOOK_MEM_INVALID
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu, BASE, SRAM, WORK, STOP
from inspect_ambiq_target import decode
from probe_display_queue_producer import literal


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def event(handle=0x40, role=1, status=0):
    params=bytes([1,status])+struct.pack('<H',handle)+bytes([role,0])+bytes.fromhex('112233445566')+struct.pack('<HHHB',24,0,200,0)
    assert len(params)==19
    return bytes([4,0x3e,len(params)])+params


def execute(u, entry, args, end=STOP):
    u.reg_write(arm.UC_ARM_REG_SP,WORK+0xf000)
    u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
    for k,v in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(k)),v)
    u.emu_start(entry|1,end,count=400000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==end


def discover(raw,hci):
    candidates=[]
    for instruction in decode(raw,hci['upper_handler'],0x90):
        if instruction.mnemonic!='bl':continue
        target=instruction.operands[0].imm
        prefix=decode(raw,target,0x10)
        if len(prefix)>=4 and prefix[0].op_str=='{r2, r3, r4, r5, r6, r7, r8, lr}' and prefix[1].op_str=='r8, #0' and prefix[3].op_str=='r5, [r1, #8]':candidates.append(target)
    assert len(candidates)==1
    core=candidates[0]
    body=decode(raw,core,0x460)
    sites=[y.address for x,y in zip(body,body[1:]) if x.mnemonic=='movs' and x.op_str=='r0, r4' and y.mnemonic=='blx' and y.op_str=='r5']
    assert len(sites)==1
    return dict(h4_parser=hci['application_parser'],upper_handler=hci['upper_handler'],event_processor=core,callback_call=sites[0])


def machine(raw,ram):
    u=cpu(raw,ram,WORK+0xf000);invalid=[]
    def reject(m,access,address,size,value,user):
        invalid.append(dict(address=address,pc=m.reg_read(arm.UC_ARM_REG_PC),access=access));return False
    u.hook_add(UC_HOOK_MEM_INVALID,reject)
    return u,invalid


def gpio_contract(raw,ram):
    isr=struct.unpack_from('<I',raw,(16+59)*4)[0]&~1
    instructions=decode(raw,isr,0x28)
    calls=[i.operands[0].imm for i in instructions if i.mnemonic=='bl']
    assert len(calls)==4
    dispatcher=calls[-1]
    table=literal(raw,decode(raw,dispatcher+0x52,2)[0])
    params=literal(raw,decode(raw,dispatcher+0x5c,2)[0])
    index=3*128+21*4
    callback=struct.unpack_from('<I',ram,table+index-SRAM)[0]&~1
    parameter=struct.unpack_from('<I',ram,params+index-SRAM)[0]
    counter=literal(raw,decode(raw,callback+2,4)[0])
    handler_slot=literal(raw,decode(raw,callback+0xe,4)[0])
    set_event=decode(raw,callback+0x14,4)[0]
    assert set_event.mnemonic=='bl'
    c=dict(pin=117,group=3,bit=21,irq=59,isr=isr,dispatcher=dispatcher,
           callback=callback,parameter=parameter,counter=counter,
           handler_id=ram[handler_slot-SRAM],set_event=set_event.operands[0].imm)
    u,invalid=machine(raw,ram);before=struct.unpack_from('<I',ram,counter-SRAM)[0]
    execute(u,dispatcher,[59,1<<21])
    after=struct.unpack('<I',u.mem_read(counter,4))[0]
    assert after==(before+1)&0xffffffff and u.reg_read(arm.UC_ARM_REG_R0)==0 and not invalid
    return c,dict(kind='gpio117-original-dispatch-callback',counter_before=before,counter_after=after,original_callback_returned=True,physical_irq_injected=False)


def inspect(raw,ram,c,dm):
    rows=[];callback=None;dm_handler=None
    for name,handle,role,status,split in [
        ('peripheral-40',64,1,0,None),('peripheral-41',65,1,0,None),
        ('central',64,0,0,None),('failed-status',64,1,1,None),
        *[('split-'+str(n),64,1,0,n) for n in [1,2,3,21]],
    ]:
        data=event(handle,role,status);u,invalid=machine(raw,ram);u.mem_write(WORK+0x100,data)
        if split is not None:
            execute(u,c['h4_parser'],[WORK+0x100,split])
            # A partial H4 event must not reach the connection callback.
            execute(u,c['upper_handler'],[1,0])
            assert bytes(u.mem_read(dm,144))==ram[dm-SRAM:dm-SRAM+144]
            execute(u,c['h4_parser'],[WORK+0x100+split,len(data)-split])
        else:execute(u,c['h4_parser'],[WORK+0x100,len(data)])
        execute(u,c['upper_handler'],[1,0],c['callback_call'])
        ptr=u.reg_read(arm.UC_ARM_REG_R0);cb=u.reg_read(arm.UC_ARM_REG_R5)&~1
        assert SRAM<=ptr<SRAM+len(ram)-40
        decoded=bytes(u.mem_read(ptr,40))
        assert struct.unpack_from('<HBB',decoded)==(handle,1,status)
        assert decoded[4]==status and struct.unpack_from('<H',decoded,6)[0]==handle
        assert decoded[8:16]==bytes([role,0])+bytes.fromhex('112233445566')
        assert struct.unpack_from('<HHHB',decoded,16)==(24,0,200,0)
        assert decoded[24:36]==bytes(12)
        assert bytes(u.mem_read(dm,144))==ram[dm-SRAM:dm-SRAM+144]
        assert not invalid
        if callback is None:callback=cb
        assert callback==cb
        body=decode(raw,cb,0x54)
        stop=next(k for k,i in enumerate(body) if i.mnemonic.startswith('pop') and 'pc' in i.op_str)
        body=body[:stop+1]
        calls=[i.address for i in body if i.mnemonic=='blx' and i.op_str=='r1']
        assert len(calls)==1
        # Continue the original callback with its current stack/regs, no reseed.
        u.emu_start(c['callback_call']|1,calls[0],count=400000)
        assert u.reg_read(arm.UC_ARM_REG_PC)==calls[0]
        handler=u.reg_read(arm.UC_ARM_REG_R1)&~1
        assert u.reg_read(arm.UC_ARM_REG_R0)==ptr
        if dm_handler is None:dm_handler=handler
        assert dm_handler==handler
        rows.append(dict(kind=name,event=data.hex(),decoded=decoded.hex(),callback=cb,dm_handler=handler,split=split,connection_memory_unchanged=True))
    data=event();u,invalid=machine(raw,ram);u.mem_write(WORK+0x100,data[:-1])
    execute(u,c['h4_parser'],[WORK+0x100,len(data)-1]);execute(u,c['upper_handler'],[1,0])
    assert not invalid and bytes(u.mem_read(dm,144))==ram[dm-SRAM:dm-SRAM+144]
    rows.append(dict(kind='truncated-event',complete_callback=False,connection_memory_unchanged=True))
    # Run the full original path to expose the actual isolated-fixture boundary.
    u,invalid=machine(raw,ram);u.mem_write(WORK+0x100,data)
    execute(u,c['h4_parser'],[WORK+0x100,len(data)])
    try:execute(u,c['upper_handler'],[1,0])
    except UcError as exc:failure=str(exc)
    else:raise AssertionError('Reassess the expected isolated UART1 boundary')
    assert len(invalid)==1 and invalid[0]['address']==0x4003a018
    assert bytes(u.mem_read(dm,144))==ram[dm-SRAM:dm-SRAM+144]
    rows.append(dict(kind='full-path-boundary',error=failure,invalid=invalid,connection_created=False))
    code=decode(raw,dm_handler,0x72)
    assert any(i.mnemonic=='ldrb' and i.op_str=='r1, [r5, #8]' for i in code)
    assert any(i.mnemonic=='cmp' and i.op_str=='r1, #1' for i in code)
    allocation=decode(raw,dm_handler+0x3e,4)[0]
    assert allocation.mnemonic=='bl'
    c.update(hci_callback=callback,dm_handler=dm_handler,dm_allocation=allocation.operands[0].imm)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    s,out=a.simulator.resolve(),a.output.resolve()
    if not out.is_relative_to(s) or s.is_relative_to(Path(__file__).resolve().parents[1]):p.error('Fresh private simulator output required')
    out.mkdir()
    source=s/'application-hci-transaction-source-02/report.json'
    assert sha(source)==json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    hc=json.loads(source.read_text())['cases']
    dp=s/'eus-att-source-04/report.json';pin=json.loads((s/'eus-att-research-01/manifest.json').read_text())
    assert sha(dp)==pin['files'][str(dp.relative_to(s))]
    dc=json.loads(dp.read_text())['cases'];native_pin=json.loads((s/'tpl-time-research-01/manifest.json').read_text());cases=[]
    for name in ['stock24','stock23','cfw']:
        src=s/'tpl-time-native-01'/name;capture=src/'capture-files.json'
        assert sha(capture)==native_pin['files'][str(capture.relative_to(s))]
        files=json.loads(capture.read_text())['files']
        for f in ['main.bin','exports/sync-after-sram.bin']:assert sha(src/f)==files[f]
        raw=(src/'main.bin').read_bytes();ram=(src/'exports/sync-after-sram.bin').read_bytes()
        old=next(x for x in hc if x['case']==name);assert old['raw_sha256']==files['main.bin']
        dm=next(x['contract']['dm_global'] for x in dc if x['case']==name)
        c=discover(raw,old);rows=inspect(raw,ram,c,dm)
        gpio,gpio_row=gpio_contract(raw,ram);c['gpio']=gpio;rows.append(gpio_row)
        cases.append(dict(case=name,main_sha256=files['main.bin'],ram_sha256=files['exports/sync-after-sram.bin'],dm_global=dm,contract=c,rows=rows))
        (out/'partial.json').write_text(json.dumps(dict(cases=cases,complete=False),indent=2)+'\n')
    result=dict(passed=True,scenarios=sum(len(x['rows']) for x in cases),cases=cases,layer='isolated original H4 parser/HCI decoder/live callback boundary',connection_created=False,host_connection_or_security_write=False,spi_runtime_event=False,native_runs=0,physical_hardware_access=False)
    (out/'probe.py').write_bytes(Path(__file__).read_bytes());(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,scenarios=result['scenarios'])))


if __name__=='__main__':main()
