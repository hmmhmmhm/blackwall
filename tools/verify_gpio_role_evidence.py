"""Audit original five-sample low/high role paths and unknown/budget fences."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')];check(tag+'-unique',len(rows)==1);return rows[0]
    check('red-type-absent','BlackwallGpioRoleInput was not found' in (s/'gpio-role-input-red-01/renode.log').read_text())
    d=s/'gpio-role-input-unit-02';u=json.loads((d/'report.json').read_text());check('unit-log-report',u==marker((d/'renode.log').read_text(),'BLACKWALL_GPIO_ROLE_UNIT'))
    check('unit38',u['passed'] and u['count']==len(u['checks'])==38);check('unit-current-model',(d/'strict.cs').read_bytes()==models(s))
    source=json.loads((s/'gpio-role-input-contract-03/report.json').read_text());check('source-contract49',source['passed'] and source['count']==49)
    names=[key+'-'+level for key in ['stock24','stock23','cfw'] for level in ['low','high']]+['stock24-budget1','stock24-default']
    for name in names:
        key='stock24' if name.startswith('stock24') else name.split('-')[0];d=s/'gpio-role-main-01'/name;old=s/'littlefs-format-main-01'/key
        r=json.loads((d/'report.json').read_text());prior=json.loads((old/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log)
        check(name+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        filename=dict(stock24='stock-2.4.0.24.bin',stock23='stock-2.3.0.24.bin',cfw='faceclaw-38-research-only.bin')[key]
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',not obs['dropped_events'] and obs['sequence']==len(obs['events']) and obs['capacity']==4096)
        previous=prior['selected_observation']['events'];check(name+'-whole-prior-event-prefix',obs['events'][:len(previous)]==previous)
        gi=marker(log,'BLACKWALL_GPIO_ROLE_INPUT');check(name+'-bounded-hypothesis',gi['pin']==156 and gi['known_mask']==0x10000000 and gi['consumer_gated'] and gi['other_bits_are_padding'] and not gi['physical_level_known'])
        guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        if name.endswith('default'):
            check('default-unselected',not gi['selected'] and gi['reads']==0)
            check('default-CPU-state',v==prior['observed'])
            check('default-observations',r['selected_observation']==prior['selected_observation'])
            check('default-board',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        else:
            meta=next(c for c in source['cases'] if c['case']==key)
            check(name+'-actual-source-CPU-context',gi['selected'] and gi['last_context_pc']==gi['read_pc']==int(meta['input_read_pc'],0) and gi['last_context_pin']==156)
            samples=[e['r0'] for e in obs['events'] if e['label']=='GPIO-role-sample-return'];roles=[e['r0'] for e in obs['events'] if e['label']=='GPIO-role-return']
            points={p['label']:p for p in obs['points']}
            if name.endswith('budget1'):
                check('budget1-no-extra-samples',gi['reads']==gi['budget']==1 and samples==[0] and roles==[])
                check('budget1-next-input-blocked',guards[0]['operation']=='read' and guards[0]['address']==0x40010414)
            else:
                level=int(name.endswith('high'))
                check(name+'-five-original-HAL-returns',gi['level']==level and gi['reads']==gi['budget']==5 and samples==[0]*5)
                check(name+'-original-extracted-bit',points['GPIO-role-sample-return']['snapshot']['words']==[level])
                check(name+'-original-role-return',roles==[level+1])
                check(name+'-next-hardware-boundary',guards[0]['operation']=='read' and guards[0]['address']==0x40008200)
            cases.append(dict(case=name,pc=hex(v['pc']),guard=guards[0],reads=gi['reads'],sample_returns=samples,role_returns=roles,events=obs['sequence']))
        check(name+'-no-complete-boot-display-hardware-claim',not any(r[k] for k in ['boot_verified','display_verified','hardware_validated']))
    cli=json.loads((s/'gpio-role-cli-01/report.json').read_text());check('CLI-three-guards',cli['passed'] and cli['count']==3 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,unit_checks=u['count'],scope='Bounded source-consumer GPIO adapter and original stable low/high role branch; no generic GPIO/electrical/IRQ, temple identity, complete boot or hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=u['count'])))


if __name__=='__main__':main()
