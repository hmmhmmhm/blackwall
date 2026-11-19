"""Pin UART0 mask 1fd0 and distinguish interrupt enable from DMA enable."""
import argparse,hashlib,json,re,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    ref=json.loads((s/'uart1-research-01/source-report.json').read_text())
    for f in ['am_hal_uart.c','am_hal_uart.h']:
        check(f+'-pin',hashlib.sha256((s/'uart1-research-01'/f).read_bytes()).hexdigest()==ref['source_sha256'][f])
    svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();pinned=json.loads((s/'multi-uart-research-01/source-report.json').read_text());check('SVD-pin',hashlib.sha256(svd).hexdigest()==pinned['svd_sha256'])
    header=(s/'mspi1-source-research-01/apollo510.h').read_bytes();manifest=json.loads((s/'mspi1-source-research-01/sources.json').read_text());check('device-header-pin',hashlib.sha256(header).hexdigest()==next(x['sha256'] for x in manifest['files'] if x['path'].endswith('/apollo510.h')))
    uart=next(x for x in ET.fromstring(svd).findall('./peripherals/peripheral') if x.findtext('name')=='UART0');regs={x.findtext('name'):x for x in uart.findall('./registers/register')}
    for name,offset in [('IER',0x38),('IES',0x3c),('MIS',0x40),('IEC',0x44),('DCR',0x48)]:
        check(name+'-offset-and-reset',int(regs[name].findtext('addressOffset'),0)==offset and int(regs[name].findtext('resetValue'),0)==0)
    bits={}
    for f in regs['IER'].findall('./fields/field'):
        hi,lo=map(int,re.fullmatch(r'\[(\d+):(\d+)\]',f.findtext('bitRange')).groups());check(f.findtext('name')+'-single-bit',hi==lo);bits[f.findtext('name')]=1<<lo
        macro=re.search(r'#define UART0_IER_'+f.findtext('name')+r'_Msk\s+\((0x[0-9A-Fa-f]+)UL\)',header.decode());check(f.findtext('name')+'-header-mask',macro is not None and int(macro.group(1),0)==1<<lo)
    enabled=['DMAEIM','DMACPIM','OEIM','BEIM','PEIM','FEIM','RTIM','RXIM'];check('exact-1fd0-components',sum(bits[x] for x in enabled)==0x1fd0 and bits['DMAEIM']|bits['DMACPIM']==0x1800)
    check('no-TX-or-TXCMP-enable',0x1fd0&(bits['TXIM']|bits['TXCMPMIM'])==0)
    dcr={f.findtext('name'):f.findtext('bitRange') for f in regs['DCR'].findall('./fields/field')};check('separate-RX-TX-DMA-enables',dcr['TXDMAE']=='[1:1]' and dcr['RXDMAE']=='[0:0]')
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for key,file in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'uart0-hcpa-main-02'/key;r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);_,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes())
        check(key+'-native-original',v==r['observed'] and raw==(d/'main.bin').read_bytes());pc=v['pc'];c={i.address:i for i in md.disasm(raw[pc-0x438000-0xe:pc-0x438000+6],pc-0xe)}
        check(key+'-read-modify-write',(c[pc-8].mnemonic,c[pc-8].op_str)==('ldr','r3, [r3, #0x38]') and (c[pc-6].mnemonic,c[pc-6].op_str)==('orrs','r1, r3') and (c[pc].mnemonic,c[pc].op_str)==('str','r1, [r0, #0x38]'))
        i=c[pc-0xe];mem=next(x.mem for x in i.operands if x.type==ARM_OP_MEM and x.mem.base==ARM_REG_PC);base=struct.unpack_from('<I',raw,((i.address+4)&~3)+mem.disp-0x438000)[0]
        check(key+'-base-module0-mask',base==0x40039000 and v['register_context']['r2']==0 and v['register_context']['r1']==0x1fd0)
        ret=v['register_context']['r14']&~1;caller={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[ret-10-0x438000:ret+4-0x438000],ret-10)}
        check(key+'-caller-explicit-mask',caller[ret-10]==('movw','r1, #0x1fd0') and caller[ret]==('orrs','r4, r0'))
        u=next(x for x in v['uarts'] if x['module']==0);check(key+'-before-mask-idle',u['interrupt_mask']==0 and u['interrupt_mask_writes']==0 and not u['irq_level'] and not u['tx_bytes'] and not u['rx_dma_implemented'])
        cases.append(dict(case=key,IER_store=hex(pc),enable_entry=hex(pc-0x26),enable_return=hex(pc+4),caller_return=hex(ret),UART0_base=hex(base)))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,IER_mask='0x1fd0',enabled_fields=enabled,DMA_IRQ_mask='0x1800',DMA_enable_register='DCR+0x48',source_reset_DCR=0,
                IRQ_enable_is_DMA_start=False,actual_hardware_DMA_idle_verified=False,new_main_executed=False,
                scope='Pinned HAL/SVD/header and prior original main. Mask storage may be modeled with explicit source-reset DMA idle hypothesis; DMA start/RX data/completion remain unsupported')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),enabled_fields=enabled)))


if __name__=='__main__':main()
