"""Check pinned Apollo510 RTC selection definitions, including the silicon limitation."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

PINS={
    'apollo-dfp-research-01/apollo510.svd':'a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276',
    'upstream/hal-ambiq-61b293a/apollo510.h':'b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797',
    'upstream/hal-ambiq-61b293a/am_hal_clkgen.c':'fd1d50990a9a62e699c9bed05ec2983f2c766e62c5a9eb9e08387e2bcc39bddf',
}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();a.output.mkdir(mode=0o700)
    texts={}
    for name,digest in PINS.items():
        data=(a.simulator/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Pinned source differs: '+name)
        texts[Path(name).name]=data.decode()
    root=ET.fromstring(texts['apollo510.svd'])
    clk=next(n for n in root.findall('./peripherals/peripheral') if n.findtext('name')=='CLKGEN')
    r=next(n for n in clk.findall('./registers/register') if n.findtext('name')=='OCTRL')
    f=r.find('./fields/field');description=f.findtext('description')
    assert int(clk.findtext('baseAddress'),0)==0x40004000
    assert int(r.findtext('addressOffset'),0)==12 and int(r.findtext('resetValue'),0)==0 and int(r.findtext('resetMask'),0)==128
    assert f.findtext('name')=='OSEL' and f.findtext('bitRange')=='[7:7]'
    assert 'inoperable in silicon revisions A and B0' in description
    values={v.findtext('name'):int(v.findtext('value'),0) for v in f.findall('./enumeratedValues/enumeratedValue')}
    assert values=={'XT_512Hz':0,'LFRC_DIV2':1}
    h=texts['apollo510.h'];hal=texts['am_hal_clkgen.c']
    for suffix,expected in [('Pos',7),('Msk',128)]:
        m=re.search(r'#define CLKGEN_OCTRL_OSEL_'+suffix+r'\s+\((0x[0-9a-fA-F]+|\d+)UL\)',h)
        assert m and int(m[1],0)==expected
    for name in values:assert 'CLKGEN->OCTRL_b.OSEL = CLKGEN_OCTRL_OSEL_'+name+';' in hal
    status=hal[hal.index('am_hal_clkgen_status_get(am_hal_clkgen_status_t *psStatus)'):]
    status=status[:status.index('} // am_hal_clkgen_status_get()')]
    assert 'psStatus->eRTCOSC = AM_HAL_CLKGEN_STATUS_RTCOSC_LFRC;' in status and 'OCTRL' not in status
    end=h.index('} CLKGEN_Type;');begin=h.rfind('typedef struct {',0,end)
    source='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+h[begin:end]+'} CLKGEN_Type;\n_Static_assert(offsetof(CLKGEN_Type,OCTRL)==12,"OCTRL");\n'
    (a.output/'layout.c').write_text(source)
    command=['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(a.output/'layout.c'),'-o',str(a.output/'layout.o')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    (a.output/'compiler.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Pinned C layout failed')
    report=dict(passed=True,source_sha256=PINS,upstream_hal_commit='61b293a49db34030c545f99101f7ebf6a3050314',address='0x4000400c',mask=128,source_reset_value=0,values=values,silicon_limitation=description,hal_status_is_constant_lfrc=True,main_entry_initial_state_known=False,chip_revision_0x23_mapping_known=False,effective_oscillator_verified=False,compiler_command=command,scope='source-defined request bits, not physical oscillator behavior')
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
