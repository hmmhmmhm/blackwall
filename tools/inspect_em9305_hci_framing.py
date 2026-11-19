"""Source-backed HCI read framing, boot event constant, and original retry fragment."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_nema_blocking_wait import cpu,WORK,STOP,BASE

READ=bytes.fromhex('2de9f84f90b0050089461600')
INIT=bytes.fromhex('f8b588b00500002007900024')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(raw,signature):
    if raw.count(signature)!=1:raise ValueError('Missing or ambiguous original function')
    return BASE+raw.index(signature)


def literal(raw,i):
    if i.mnemonic not in ['ldr','ldr.w'] or i.operands[1].mem.base!=arm.UC_ARM_REG_PC:raise ValueError('Expected literal load')
    address=((i.address+4)&~3)+i.operands[1].mem.disp
    return struct.unpack_from('<I',raw,address-BASE)[0]


def discover(raw):
    read,init=entry(raw,READ),entry(raw,INIT)
    def instruction(pc):return decode(raw,pc,4)[0]
    def call(pc):
        i=instruction(pc)
        if i.mnemonic!='bl':raise ValueError('Expected original call')
        return i.operands[0].imm
    if call(init+0xa2)!=read:raise ValueError('Boot init does not call same HCI reader')
    constant=literal(raw,instruction(init+0x16));expected=raw[constant-BASE:constant-BASE+4]
    if expected!=b'\x04\xff\x01\x01':raise ValueError('Different active-state event')
    comparison=decode(raw,init+0xac,10)
    if [(i.mnemonic,i.op_str) for i in comparison[:3]]!=[('movs','r2, #4'),('add','r1, sp, #8'),('add','r0, sp, #0xc')]:raise ValueError('Unknown boot event comparison')
    if comparison[3].mnemonic!='bl':raise ValueError('Missing original memcmp')
    low_call=read+0xea;gpio=call(low_call)
    if call(read+0xd8)!=gpio or call(read+0x1d6)!=gpio:raise ValueError('Different GPIO helpers')
    for pc,value in [(low_call-2,0x95),(read+0xd8-2,0x95),(read+0x1d6-2,0x95)]:
        i=instruction(pc)
        if i.op_str!='r0, #0x95':raise ValueError('Not pin149 framing')
    clear_base=literal(raw,instruction(gpio+0x1c));set_base=literal(raw,instruction(gpio+0x34))
    if clear_base!=0x40010458 or set_base!=0x4001043c:raise ValueError('Different GPIO set/clear bank')
    if instruction(read+0xe0).op_str!='sb, #0xa':raise ValueError('Different header retry bound')
    if literal(raw,instruction(read+0x32))!=0x40010410:raise ValueError('Different RDY word')
    header=call(read+0x12e);payload=call(read+0x1bc)
    # Source argument descriptors: direction=2, length=2 for full-duplex header;
    # direction=1 for subsequent input payload. The source leaves pin149 low
    # along the successful branch until after payload read.
    checks={read+0x10a:('movs','r0, #2'),read+0x114:('movs','r0, #2'),read+0x18c:('movs','r0, #1')}
    for pc,want in checks.items():
        i=instruction(pc)
        if (i.mnemonic,i.op_str)!=want:raise ValueError('Changed transfer descriptor')
    return dict(read=read,init=init,expected_event=expected.hex(),expected_event_address=constant,comparison_call=comparison[3].address,
                gpio_helper=gpio,cs_pin=149,cs_mask=1<<21,cs_set_address=set_base+16,cs_clear_address=clear_base+16,
                header_call=read+0x12e,header_hal=header,payload_call=read+0x1bc,payload_hal=payload,
                decision=read+0xc4,next_assert=read+0xe6,accepted=read+0x156,error_release=read+0x24e,
                retry_limit=10,rdy_pin=117,rdy_address=0x40010410,rdy_bit=21)


def replay_retry(raw,c,status,length,retries):
    u=cpu(raw,b'\0'*0x80000,WORK+0xf000);u.mem_map(0x40010000,0x1000)
    u.mem_write(WORK+0xf000,bytes([status,length])+b'\0'*14);u.reg_write(arm.UC_ARM_REG_R9,retries)
    trace=[];stop=[];boundaries={c['next_assert']:'retry',c['accepted']:'accepted',c['error_release']:'header-error'}
    def hook(cpu,pc,size,user):
        trace.append(pc)
        if pc in boundaries:stop.append(boundaries[pc]);cpu.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(c['decision']|1,STOP,count=1000)
    valid=status==0xc0 and length!=0
    wanted='accepted' if valid else ('header-error' if retries==9 else 'retry')
    next_count=u.reg_read(arm.UC_ARM_REG_R9);gpio_store=struct.unpack('<I',u.mem_read(c['cs_set_address'],4))[0]
    if stop!=[wanted] or next_count!=retries+(not valid) or gpio_store!=(0 if valid else c['cs_mask']) or trace.count(c['gpio_helper'])!=(0 if valid else 1):raise ValueError('Original retry fragment differs')
    return dict(status=status,length=length,retry_index_before=retries,retry_index_after=next_count,result=wanted,
                original_gpio_helper_executed=not valid,gpio_set_store=gpio_store,
                instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());rows=[]
    for case in ['stock24','stock23','cfw']:
        source=a.simulator/'iom6-full-duplex-main-01'/case;r=json.loads((source/'report.json').read_text());raw=(source/'main.bin').read_bytes()
        acceptance=json.loads((a.simulator/'iom6-first-spi-contract-02/report.json').read_text());pin=next(x for x in acceptance['cases'] if x['case']==case)
        if not acceptance['passed'] or not r['passed'] or sha(source/'main.bin')!=pin['raw_sha256'] or sha(source/'report.json')!=pin['source_report_sha256']:raise ValueError('Changed verified original source')
        c=discover(raw);samples=[replay_retry(raw,c,status,length,retries) for status,length in [(0xc0,4),(0xc0,1),(0xc0,255),(0xc0,0),(0,4),(0x80,4)] for retries in [0,9]]
        rows.append(dict(case=case,raw_sha256=sha(source/'main.bin'),source_report_sha256=sha(source/'report.json'),contract=c,samples=samples))
    result=dict(passed=True,cases=rows,whole_main_executed=False,native_main_rerun=False,hardware_accessed=False,
                replay='Original ARM retry fragment and actual GPIO helper on M7; synthetic stack/counter, plain MMIO store capture, bounded stops',
                physical_cs_or_rdy_timing_verified=False,expected_event_is_source_and_manufacturer_supported_not_hardware_verified=True,
                spi_finish_callback_is_not_gpio149_deassertion=True)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=3,retry_scenarios=36,source_expected_event='04ff0101')))


if __name__=='__main__':main()
