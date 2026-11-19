"""Cross-check pinned Apollo510 IOM register offsets and fields; no hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

SVD_SHA='a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276'
HEADER_SHA='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'


def definitions(svd,header):
    if hashlib.sha256(svd).hexdigest()!=SVD_SHA or hashlib.sha256(header).hexdigest()!=HEADER_SHA:
        raise ValueError('Unreviewed Apollo510 register metadata')
    text=header.decode()
    root=ET.fromstring(svd)
    iom=next(p for p in root.find('peripherals') if p.findtext('name')=='IOM0')
    regs=[];fields=0
    for reg in iom.find('registers'):
        name=reg.findtext('name');mask=0
        for field in reg.find('fields'):
            hi,lo=map(int,field.findtext('bitRange').strip('[]').split(':'))
            expected=((1<<(hi-lo+1))-1)<<lo
            macro='IOM0_'+name+'_'+field.findtext('name')+'_Msk'
            m=re.search(r'#define\s+'+re.escape(macro)+r'\s+\((0x[0-9a-fA-F]+)UL\)',text)
            if not m or int(m.group(1),16)!=expected:raise ValueError('IOM field mismatch: '+macro)
            mask|=expected;fields+=1
        regs.append(dict(name=name,offset=int(reg.findtext('addressOffset'),0),reset=int(reg.findtext('resetValue'),0),mask=mask))
    end=text.index('} IOM0_Type;')+len('} IOM0_Type;')
    start=text.rfind('typedef struct {',0,end)
    if start<0:raise ValueError('IOM0 C type absent')
    return regs,fields,text[start:end]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    svd=(args.simulator/'apollo-dfp-research-01/apollo510.svd').read_bytes()
    header=(args.simulator/'upstream/hal-ambiq-61b293a/apollo510.h').read_bytes()
    regs,fields,ctype=definitions(svd,header)
    args.output.mkdir(mode=0o700)
    code='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+ctype+'\n'
    code+='\n'.join('_Static_assert(offsetof(IOM0_Type,%s)==%s,"%s offset");'%(r['name'],hex(r['offset']),r['name']) for r in regs)
    (args.output/'layout.c').write_text(code)
    cmd=['/opt/homebrew/opt/llvm@21/bin/clang','-std=c11','-c',str(args.output/'layout.c'),'-o',str(args.output/'layout.o')]
    result=subprocess.run(cmd,capture_output=True,text=True)
    (args.output/'compile.json').write_text(json.dumps(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    if result.returncode:raise ValueError('IOM C layout compile failed')
    report=dict(passed=True,registers=regs,offset_assertions=len(regs),field_masks_checked=fields,svd_sha256=SVD_SHA,header_sha256=HEADER_SHA,scope='pinned numeric definitions and current Mac C structure layout, not physical behavior or firmware config ABI',hardware_validated=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,offsets=len(regs),field_masks=fields)))


if __name__=='__main__':main()
