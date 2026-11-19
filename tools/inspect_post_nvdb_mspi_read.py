"""Identify the post-NVdb original PIO request and LittleFS read callback, without supplying data."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from inspect_mspi1_config_contract import collect
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    collect(s)
    source=s/'mspi1-source-research-01';manifest=json.loads((source/'sources.json').read_text())
    hal=(source/'am_hal_mspi.c').read_bytes();header=(source/'am_hal_mspi.h').read_bytes()
    for filename,data in [('am_hal_mspi.c',hal),('am_hal_mspi.h',header)]:
        pin=next(f for f in manifest['files'] if f['path'].endswith('/'+filename))
        check(filename+'-pin',hashlib.sha256(data).hexdigest()==pin['sha256'] and manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
    text=hal.decode();start=text.index('am_hal_mspi_blocking_transfer(void *pHandle,');body=text[start:]
    check('HAL-PIO-start-before-FIFO',body.index('MSPIn(ui32Module)->CTRL = ui32Control;')<body.index('ui32Status = mspi_fifo_read'))
    check('HAL-start-transfer-count', '_VAL2FLD(MSPI0_CTRL_XFERBYTES, pTransaction->ui32NumBytes)' in body and '_VAL2FLD(MSPI0_CTRL_START, 1)' in body)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'crypto-otp-off-main-01'/key;r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log)
        check(key+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        check(key+'-original-main',raw==(d/'main.bin').read_bytes())
        def code(start,length):return {i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[start-0x438000:start+length-0x438000],start)}
        def literal(addr):
            i=next(md.disasm(raw[addr-0x438000:addr+4-0x438000],addr));mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC)
            return struct.unpack_from('<I',raw,(((addr+4)&~3)+mem.disp)-0x438000)[0]
        def string(addr):
            if not 0x438000<=addr<0x438000+len(raw):raise ValueError('Non-main string')
            return raw[addr-0x438000:addr-0x438000+256].split(b'\0')[0].decode('ascii')
        def marker(tag):
            rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
            check(key+'-'+tag+'-unique',len(rows)==1);return rows[0]
        cfg=marker('BLACKWALL_MSPI1_CONFIG')['registers'];guards=[g for g in v['guards'] if g['accesses']]
        check(key+'-CTRL-transfer-not-config',len(guards)==1 and guards[0]['address']==0x40061000 and guards[0]['operation']=='write' and guards[0]['value']==0x100461)
        check(key+'-QREAD4B16-at-1400000',cfg['12']==0x6c and cfg['8']==0x1400000 and (guards[0]['value']>>16)==16)
        check(key+'-same-logical-quad-SDR',cfg['4']==5 and (cfg['132']&~0x1c00000)==0x10861 and (cfg['136']&0x1f)==0)
        check(key+'-NOR-QE-ready',marker('BLACKWALL_NOR_LATCH')['current']&0x41==0x40)
        backing=marker('BLACKWALL_NOR_ARRAY')
        check(key+'-outside-declared-backing',backing['start']==0x1fc0000 and backing['length']==0x40000 and cfg['8']+16<=backing['start'])
        ctx,stack=v['register_context'],v['stack_context'];words=stack['words'];pc=v['pc']
        check(key+'-original-start-store',code(pc,4)[pc]==('str.w','lr, [r2]') and ctx['r14']==0x100461 and ctx['r2']==0x40061000)
        check(key+'-transaction-location',ctx['r1']==stack['base']+32 and words[8:13]==[16,0x1000000,0x1400000,0x6c0001,1])
        pio_return=words[7]&~1;cb_return=words[19]&~1;dispatch_return=words[27]&~1
        cb=cb_return-0x1a;c=code(cb,0x38)
        check(key+'-read-callback-address-formula',c[cb]==('push','{r1, r2, r3, r4, r5, r6, r7, lr}') and c[cb+8]==('adds.w','r7, r5, r4, lsl #12') and c[cb+12]==('adds.w','r7, r7, #0x1400000'))
        check(key+'-callback-read-call',c[cb+0x16][0]=='bl' and c[cb+0x1a]==('cmp','r0, #0') and c[cb+0x1c]==('beq','#'+hex(cb+0x34)))
        message=string(literal(cb+0x28))
        check(key+'-lfs-read-diagnostic',message=='lfs READ fail: block=%u, off=%u, size=%u, addr=0x%08X, st=%d\n')
        check(key+'-read-error-minus5',c[cb+0x2e]==('mvns','r0, #4') and c[cb+0x34]==('movs','r0, #0'))
        dispatch=code(dispatch_return-2,0x1a)
        check(key+'-indirect-read-dispatch',dispatch[dispatch_return-2]==('blx','ip') and dispatch[dispatch_return]==('mov','sl, r0') and dispatch[dispatch_return+2]==('cmp.w','sl, #1'))
        path=string(literal(dispatch_return+0xa));assertion=string(literal(dispatch_return+0xe))
        check(key+'-littlefs-source-path',path.endswith('third_party\\littlefs\\lfs.c') and assertion=='err <= 0')
        call=code(pio_return-4,8)
        check(key+'-PIO-caller-chain',call[pio_return-4][0]=='bl' and call[pio_return]==('movs','r4, r0'))
        needle=struct.pack('<I',cb|1);references=[];offset=0
        while True:
            offset=raw.find(needle,offset)
            if offset<0:break
            references.append(offset);offset+=1
        check(key+'-unique-read-callback-table-reference',len(references)==1 and references[0]%4==0)
        table_offset=references[0]-4;table=list(struct.unpack_from('<16I',raw,table_offset))
        check(key+'-candidate-table-values',table[:4]==[0,cb|1,(cb+0x38)|1,(cb+0x70)|1] and table[5:12]==[16,256,4096,3008,500,4096,256])
        cases.append(dict(case=key,pc=hex(pc),instruction=hex(cfg['12']),device_address=hex(cfg['8']),bytes=16,
                          block_bytes=4096,read_callback=hex(cb),read_call=c[cb+0x16][1],pio_call=hex(pio_return-4),pio_function=call[pio_return-4][1],dispatch_return=hex(dispatch_return),
                          observed_buffer=hex(words[13]),config_table_candidate=hex(table_offset+0x438000),config_candidate_words=table,
                          meaning='LittleFS read callback; table candidate is not a captured live configuration, volume bound and format policy require further tracing'))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Original PIO request and LittleFS callback contract only; no filesystem data, geometry upper bound, mount success, boot or hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
