"""Verify pinned IOM CQ numeric contract and stock24 register table; static analysis only."""
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pinned_main import MAIN_LAYOUT
from analyze_iom_metadata import definitions

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
    raw=(s/'iom4-main-comparison-01/stock24/main.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()==MAIN_LAYOUT['stock_current'][3]
    svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();header=(s/'upstream/hal-ambiq-61b293a/apollo510.h').read_bytes();definitions(svd,header)
    pins={'am_hal_cmdq.c':'60aa2126ca01cd72f746a92d6f34a13e909fdab24ebfab6d6b0a70b026d8fa83','am_hal_cmdq.h':'0113aed2f109c5f022d38055b83a75c2cf141e8621177296757fc8315926762f'}
    for file,sha in pins.items():assert hashlib.sha256((s/'iom-cq-research-01'/file).read_bytes()).hexdigest()==sha
    def literal(pc,offset):return struct.unpack_from('<I',raw,((pc+4)&~3)+offset-0x438000)[0]
    table=literal(0x572b90,0x460);record=struct.unpack_from('<10I',raw,table+4*40-0x438000)
    assert list(record)==[0x40054228,0x4005422c,0x40054240,0x40054244,0x4005423c,0x8000,0x40054230,1,4,2]
    iom=next(x for x in ET.fromstring(svd).find('peripherals') if x.findtext('name')=='IOM0');regs=[]
    for reg in iom.find('registers'):
        if reg.findtext('name').startswith('CQ'):
            regs.append(dict(name=reg.findtext('name'),offset=int(reg.findtext('addressOffset'),0),reset=int(reg.findtext('resetValue'),0),fields=[dict(name=f.findtext('name'),bits=f.findtext('bitRange'),description=f.findtext('description')) for f in reg.find('fields')]))
    c=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);instructions=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in c.disasm(raw[0x572b04-0x438000:0x572c36-0x438000],0x572b04)]
    report=dict(passed=True,raw_main_sha256=hashlib.sha256(raw).hexdigest(),hal_sources=pins,stock24_table=table,stock24_iom4_register_record=list(record),registers=regs,instructions=instructions,confirmed=['address/value entries are 2x32bit','CQADDR self-write redirects next fetch','disabled CQSTAT clears all bits','CQTIP remains1 when paused','software flag bits0..7; index equality flag15','CQCFG.CQEN starts fetch; CQPRI is priority','HAL entry address bit0 requests CQUPD interrupt'],unknown=['set/toggle/clear overlap precedence','IOM input signal relation to active transaction/DMA','unconnected GPIO/BLE/MSPI inputs','physical scheduling and bus timing','DMA memory bus errors and early power-off timing'],scope='pinned DFP/HAL plus stock24 static register table and init instructions, not hardware/CQ execution')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cq_registers=len(regs),register_record=list(record),unknown=report['unknown'])))
if __name__=='__main__':main()
