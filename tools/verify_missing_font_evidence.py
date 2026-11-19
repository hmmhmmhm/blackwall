"""Audit original missing-font error paths and the unchanged default XIP boundary."""
import argparse,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets,digest
from pinned_main import load_pinned_main
from probe_missing_font_main import verify_model_delta
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    labels=['font-configure-entry','font-configure-return','font-header-invalid-0','font-descriptor-cleared-0','font-header-invalid-1','font-descriptor-cleared-1','font-chain-return-0','font-chain-return-1','font-manager-return']
    current=models(s)
    for key,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d=s/'missing-font-header-main-01'/(key+'-low');r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());obs=r['selected_observation']
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        check(key+'-original-main',raw==(d/'main.bin').read_bytes() and r['original_main_sha256']==digest(d/'main.bin'))
        check(key+'-native-report',r['passed'] and r['observed']==v and r['diagnostic'] and not r['boot_verified'] and not r['display_verified'])
        log=(d/'renode.log').read_text()
        for marker,expected in [('BLACKWALL_OBSERVATION',obs),('BLACKWALL_MISSING_FONT',r['font_diagnostic'])]:
            rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(marker+' ')]
            check(key+'-'+marker+'-raw-log',rows==[expected])
        check(key+'-current-model',(d/'strict.cs').read_bytes()==current)
        prior=s/'timer0-shared-main-02'/(key+'-low');old=json.loads((prior/'report.json').read_text())
        verify_model_delta((prior/'strict.cs').read_text(),current.decode())
        filtered=[e for e in obs['events'] if e['label'] not in labels]
        prefix=[dict(e,sequence=i+1) for i,e in enumerate(filtered[:len(old['selected_observation']['events'])])]
        check(key+'-prior-event-prefix',prefix==old['selected_observation']['events'])
        check(key+'-event-accounting',obs['dropped_events']==0 and len(obs['events'])==obs['sequence'])
        points={x['label']:x for x in obs['points']};events={e['label']:e for e in obs['events'] if e['label'] in labels}
        for label in labels:check(key+'-'+label+'-once',points[label]['hits']==1)
        for i in range(2):
            invalid=events['font-header-invalid-'+str(i)];cleared=events['font-descriptor-cleared-'+str(i)]
            check(key+'-invalid-word-'+str(i),invalid['r0']==0xffffffff)
            check(key+'-descriptor-zero-'+str(i),points['font-descriptor-cleared-'+str(i)]['snapshot']['words']==[0])
            check(key+'-natural-error-order-'+str(i),invalid['sequence']<cleared['sequence']<events['font-configure-return']['sequence'])
            chain=events['font-chain-return-'+str(i)]
            check(key+'-chain-created-'+str(i),0x20000000<=chain['r0']<0x20380000 and chain['r0']%4==0)
        check(key+'-config-return-one',events['font-configure-return']['r0']==1)
        check(key+'-parent-completes-after-chains',events['font-configure-return']['sequence']<events['font-chain-return-0']['sequence']<events['font-chain-return-1']['sequence']<events['font-manager-return']['sequence'])
        expected_pc=0x494d78 if key=='stock24' else 0x488e90
        check(key+'-next-guard',v['pc']==expected_pc and [(g['name'],g['address'],g['width'],g['operation'],g['value']) for g in v['guards'] if g['accesses']]==[('guard',0x40021004,4,'write',0x600)])
        ins=next(Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[expected_pc-0x438000:expected_pc-0x438000+2],expected_pc))
        check(key+'-original-next-store',(ins.mnemonic,ins.op_str)==('str','r1, [r0]') and v['register_context']['r0']==0x40021004 and v['register_context']['r1']==0x600)
        check(key+'-two-diagnostic-reads',r['font_diagnostic']['reads']==2 and not r['font_diagnostic']['stock_font_assets'])
        cases.append(dict(case=key,pc=hex(v['pc']),next_address='0x40021004',next_write='0x600',font_manager_epilogue_reached=True,valid_external_fonts=False))
    d=s/'missing-font-header-main-01/stock24-default';r=json.loads((d/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);v=parse_log((d/'renode.log').read_text());prior=json.loads((s/'timer0-shared-main-02/stock24-low/report.json').read_text())
    check('default-current-model',(d/'strict.cs').read_bytes()==current)
    check('default-exact-CPU-and-instruction-count',v==r['observed']==prior['observed'])
    check('default-exact-observation-trace',r['selected_observation']==prior['selected_observation'])
    check('default-no-font-reads',r['passed'] and r['font_diagnostic']['reads']==0 and r['font_diagnostic']['profile'] is None)
    for name,count in [('missing-font-header-unit-01',33),('missing-font-xip-regression-02',26)]:
        unit=json.loads((s/name/'report.json').read_text());check(name,unit['passed'] and unit['count']==count and (s/name/'strict.cs').read_bytes()==current)
    cpu=json.loads((s/'missing-font-header-cpu-01/report.json').read_text());check('synthetic-CPU-contexts',cpu['passed'] and cpu['count']==3 and [c['reads'] for c in cpu['cases']]==[1,0,0])
    for case in cpu['cases']:check('synthetic-current-'+case['variant'],(s/'missing-font-header-cpu-01'/case['variant']/'strict.cs').read_bytes()==current)
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,unit_checks=59,synthetic_CPU_cases=3,original_main_cases=4,boot_verified=False,display_verified=False,hardware_accessed=False,
                scope='Two explicit invalid font magic words only; original error paths and manager completion verified, next power write remains strict, default CPU/trace unchanged')
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),native=4)))


if __name__=='__main__':main()
