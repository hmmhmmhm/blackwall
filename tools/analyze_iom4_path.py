"""Inspect pinned stock2.4 IOM4 NB arithmetic and earliest CQ initialization; no execution."""
import argparse,hashlib,json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from pinned_main import MAIN_LAYOUT
from analyze_iom_metadata import definitions

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
    raw=(s/'iom-unused-field-main-comparison-02/stock24/main.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==MAIN_LAYOUT['stock_current'][3]
    svd=(s/'apollo-dfp-research-01/apollo510.svd').read_bytes();header=(s/'upstream/hal-ambiq-61b293a/apollo510.h').read_bytes();definitions(svd,header)
    assert '#define PWRCTRL_DEVPWREN_PWRENIOM4_Msk    (0x20UL)' in header.decode()
    per=ET.fromstring(svd).find('peripherals');iom4=next(x for x in per if x.findtext('name')=='IOM4')
    assert iom4.attrib['derivedFrom']=='IOM0' and int(iom4.findtext('baseAddress'),0)==0x40054000
    irqs=[int(x.findtext('value'),0) for x in iom4.findall('interrupt')];assert irqs==[10]
    c=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);regions=[]
    for address,length in [(0x582000,0xc),(0x58200e,0x14),(0x582088,0x20),(0x58182e,0x68)]:
        code=[dict(address=hex(i.address),bytes=i.bytes.hex(),mnemonic=i.mnemonic,operands=i.op_str) for i in c.disasm(raw[address-0x438000:address-0x438000+length],address)]
        regions.append(dict(address=hex(address),instructions=code))
    indexed={int(i['address'],16):i for region in regions for i in region['instructions']}
    assert indexed[0x582012]['operands']=='r0, r0, r1, lsl #2'
    assert indexed[0x58208c]['operands']=='r0, r0, #2'
    assert indexed[0x581848]['operands']=='r1, [r0, #0x238]'
    literal=((0x581844+4)&~3)+0xba8;flag_word=struct.unpack_from('<I',raw,literal-0x438000)[0];assert flag_word==0x800040
    old=json.loads((s/'iom-research-01/call-path-report-v2.json').read_text());cfg=old['iom4'];assert cfg['nb_buffer']==0x203366e0 and cfg['nb_length_field_value']==0x800
    cq=next(x for x in next(p for p in per if p.findtext('name')=='IOM0').find('registers') if x.findtext('name')=='CQSETCLEAR')
    report=dict(passed=True,raw_main_sha256=hashlib.sha256(raw).hexdigest(),module=4,base=0x40054000,irq=10,power_mask=0x20,config_intent=cfg,nb_length_arithmetic=dict(unit='4-byte words in checked size/capacity arithmetic',length=0x800,computed_byte_size=0x2000,computed_end=0x203386e0,actually_allocated_and_dma_accessible=False),predicted_nb_enable_cq_request=dict(pc=0x581848,offset=0x238,absolute_for_module4=0x40054238,value=flag_word,set_software_flags=0x40,clear_software_flags=0x80,enable_command_queue=False),cq_fields=[dict(name=f.findtext('name'),bits=f.findtext('bitRange'),description=f.findtext('description')) for f in cq.find('fields')],regions=regions,nb_path_executed=False,peer_identified=False,hardware_validated=False,scope='stock2.4 static code plus prior config snapshot; IOM4 first CQ request predicted, not dynamically observed')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['regions','cq_fields','config_intent']}))
if __name__=='__main__':main()
