"""Actual native first command plus original capacity/opcode/trim fragments."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import discover,literal
from inspect_nema_blocking_wait import cpu,WORK,STOP,BASE,SRAM
from run_native_candidate import memory_exports,validate_memory_exports


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run_fragment(raw,start,boundaries,stack,registers):
    u=cpu(raw,b'\0'*0x80000,WORK+0xf000);u.mem_map(0x40010000,0x1000);u.mem_write(WORK+0xf000,stack);trace=[];stops=[]
    for n,value in registers.items():u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
    def observer(c,pc,size,user):
        trace.append(pc)
        if pc in boundaries:stops.append(boundaries[pc]);c.emu_stop()
    u.hook_add(UC_HOOK_CODE,observer)
    return u,trace,stops


def capacity(raw,read,status,amount,index):
    writer=read-0x29a;start=read-0x1ce;retry=read-0x23a;done=read-0x196
    u,trace,stops=run_fragment(raw,start,{retry:'retry',done:'return'},bytes([status,amount])+b'\0'*14,{0:0,5:index})
    u.emu_start(start|1,STOP,count=1000)
    valid=status==0xc0 and amount!=0;expected='return' if valid or index==9 else 'retry'
    if stops!=[expected]:raise ValueError('Capacity control differs')
    result=u.reg_read(arm.UC_ARM_REG_R0);counter=u.reg_read(arm.UC_ARM_REG_R5);gpio=struct.unpack('<I',u.mem_read(0x4001044c,4))[0]
    if counter!=index+(not valid) or gpio!=(0 if valid else 0x200000):raise ValueError('Original retry/cs release differs')
    if expected=='return' and result!=amount:raise ValueError('Original returned capacity differs')
    return dict(status=status,capacity=amount,retry_index=index,result=expected,return_value=result if expected=='return' else None,
                retry_index_after=counter,gpio149_release_store=gpio,invalid_status_can_return_capacity_at_limit=not valid and expected=='return' and amount!=0,
                trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def match_opcode(raw,read,packet,response_opcode,status,event_code):
    start=read+0x49e;retry=read+0x494;matched=read+0x4bc
    u,trace,stops=run_fragment(raw,start,{retry:'retry-read',matched:'opcode-match'},b'\0'*32,{4:0,5:WORK+0x100,6:WORK+0x200,7:WORK+0x300,8:WORK+0x400})
    response=bytes([4,event_code,12,1])+struct.pack('<H',response_opcode)+bytes([status])+bytes(range(8))
    u.mem_write(WORK+0x100,packet);u.mem_write(WORK+0x200,response);u.emu_start(start|1,STOP,count=1000)
    expected='opcode-match' if response_opcode==0xfd01 else 'retry-read'
    if stops!=[expected]:raise ValueError('Original opcode wait differs')
    return dict(response_opcode=response_opcode,status=status,event_code=event_code,result=expected,response=response.hex(),
                scope='Original opcode-match fragment only; not whole event validation')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());prior_path=a.simulator/'em9305-active-event-contract-02/report.json';prior=json.loads(prior_path.read_text());rows=[]
    if not prior['passed']:raise ValueError('Unverified preceding host acceptance')
    for case in ['stock24','stock23','cfw']:
        source=a.simulator/'em9305-active-event-main-03'/case;r=json.loads((source/'report.json').read_text());plan=json.loads((source/'plan.json').read_text());accepted=next(x for x in prior['cases'] if x['case']==case and x['accepted'])
        if sha(source/'report.json')!=accepted['native_report_sha256'] or sha(source/'main.bin')!=accepted['raw_sha256']:raise ValueError('Changed capture')
        validate_memory_exports(source,memory_exports(plan),r['memory_exports']);raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes();c=discover(raw);regs=r['observed']['register_context']
        address,length=regs['r10'],regs['r8']
        if not SRAM<=address<=SRAM+len(ram)-length or length!=9 or regs['r9']!=0:raise ValueError('Unexpected original write buffer')
        packet=ram[address-SRAM:address-SRAM+length]
        if packet.hex()!='0101fd05884bf00008' or packet[3]+4!=len(packet):raise ValueError('Different first HCI command')
        ctor=c['read']+0xeb2;load=decode(raw,ctor+0xc,4)[0];template=literal(raw,load)
        if raw[template-BASE:template-BASE+9]!=packet:raise ValueError('Native packet differs from original ROM constructor')
        body=decode(raw,ctor,0x46);ordered=[(i.mnemonic,i.op_str) for i in body]
        if ('movs','r2, #9') not in ordered or ('movs','r2, #8') not in ordered or ('add.w','r1, sp, #0xf') not in ordered:raise ValueError('Unknown memory-read helper contract')
        if any(i.mnemonic.startswith('b') and i.mnemonic not in ['bl','bx'] for i in body):raise ValueError('Read helper has unexamined local status branch')
        caps=[capacity(raw,c['read'],s,n,k) for s,n in [(0xc0,9),(0xc0,8),(0xc0,0),(0,9),(0x80,0)] for k in [0,9]]
        matches=[match_opcode(raw,c['read'],packet,op,status,event) for op,status,event in [(0xfd01,0,0x0e),(0xfd01,1,0x0e),(0xfd02,0,0x0e),(0xfc01,0,0x0e),(0xfd01,0,0xff)]]
        trim=ctor+0x64
        requested=decode(raw,c['read']-0x378,2)[0];trim_call=decode(raw,c['read']-0x374,4)[0]
        if (requested.mnemonic,requested.op_str)!=('movs','r1, #7') or trim_call.mnemonic!='bl' or trim_call.operands[0].imm!=trim:raise ValueError('Unverified requested trim')
        trims=[]
        for value in [0,0x380,0x1f80,0xffff,0x0123456789abcdef]:
            start,stop=trim+0x38,trim+0x56;u,trace,stops=run_fragment(raw,start,{stop:'before-log'},value.to_bytes(8,'little')+b'\0'*24,{6:7})
            u.emu_start(start|1,STOP,count=1000);actual=u.reg_read(arm.UC_ARM_REG_R7);expected=(value>>7)&63
            if stops!=['before-log'] or actual!=expected or u.reg_read(arm.UC_ARM_REG_R1)!=expected or u.reg_read(arm.UC_ARM_REG_R2)!=7:raise ValueError('Original trim extraction differs')
            trims.append(dict(synthetic_read_value_hex=value.to_bytes(8,'little').hex(),original_extracted_trim=actual,requested_trim=7,would_match_requested_trim=actual==7))
        rows.append(dict(case=case,raw_sha256=accepted['raw_sha256'],native_report_sha256=sha(source/'report.json'),sram_sha256=sha(source/'exports/sram-full.bin'),
            native_packet_pointer=address,packet=packet.hex(),opcode=struct.unpack_from('<H',packet,1)[0],parameter_length=packet[3],read_address=struct.unpack_from('<I',packet,4)[0],read_length=packet[8],
            command_transmitted=False,constructor=ctor,rom_template=template,expected_command_complete_data_offset=7,helper_checks_status_byte=False,
            capacity_fragments=caps,opcode_fragments=matches,trim_fragments=trims))
    result=dict(passed=True,cases=rows,preceding_analysis_sha256=sha(prior_path),native_main_rerun=False,hardware_accessed=False,
        fragment_engine='Unicorn M7 original ARM, synthetic entries/stack/registers, original GPIO helper, plain MMIO store capture; bounded stops',
        response_data_unknown=True,no_reply_inserted_into_native=True,no_firmware_or_peripheral_model_change=True,
        whole_command_helper_or_hci_transaction_replayed=False)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=3,original_fragment_scenarios=60,first_packet='0101fd05884bf00008',read_response_unknown=True)))


if __name__=='__main__':main()
