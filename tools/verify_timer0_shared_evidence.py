"""Audit shared Timer0/14 tests, resume validation and original stopped setup."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets
from pinned_main import load_pinned_main
from verify_timer14 import models as timer_models
from verify_mspi1_pio_reset import models as main_models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[];units=0
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')];check(tag+'-unique',len(rows)==1);return rows[0]
    check('red-missing-profile','timer0Profile' in (s/'timer0-shared-red-01/renode.log').read_text() and 'Could not find suitable constructor' in (s/'timer0-shared-red-01/renode.log').read_text())
    check('red-global-resume-bypass','global-resume-rejects-bad-primary accepted' in (s/'timer0-shared-global-red-01/renode.log').read_text())
    for folder,tag,count in [('timer0-shared-unit-03','BLACKWALL_TIMER0_UNIT',34),('timer0-timer14-regression-02','BLACKWALL_TIMER14_UNIT',27)]:
        d=s/folder;r=json.loads((d/'report.json').read_text());check(folder+'-log-report',r==marker((d/'renode.log').read_text(),tag));check(folder+'-count',r['passed'] and r['count']==len(r['checks'])==count);check(folder+'-current-model',(d/'strict.cs').read_bytes()==timer_models(s));units+=count
    source=json.loads((s/'timer0-sync-contract-03/report.json').read_text());check('source-contract118',source['passed'] and source['count']==118)
    names=[key+'-'+level for key in ['stock24','stock23','cfw'] for level in ['low','high']]+['stock24-default']
    for name in names:
        key=name.split('-')[0];level='high' if name.endswith('high') else 'low';d=s/'timer0-shared-main-02'/name;old=s/'gpio-role-main-01'/(key+'-'+level)
        r=json.loads((d/'report.json').read_text());prior=json.loads((old/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-native-report',v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==main_models(s))
        filename=dict(stock24='stock-2.4.0.24.bin',stock23='stock-2.3.0.24.bin',cfw='faceclaw-38-research-only.bin')[key]
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        obs=marker(log,'BLACKWALL_OBSERVATION');previous=prior['selected_observation']['events']
        check(name+'-whole-prior-prefix',obs['events'][:len(previous)]==previous);check(name+'-no-drop',not obs['dropped_events'] and obs['sequence']==len(obs['events']) and obs['capacity']==4096)
        t=marker(log,'BLACKWALL_TIMER0');check(name+'-nominal-only',t['nominal_hfrc_hz']==96000000 and not t['physical_timing_verified'])
        guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        if name.endswith('default'):
            check('default-unsupported',not t['selected'] and v==prior['observed'])
            check('default-observations',r['selected_observation']==prior['selected_observation'])
            check('default-board',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        else:
            check(name+'-stopped-source-config',t['selected'] and t['control']==0x120 and t['mode']==0x100 and t['compare0']==6000 and t['compare1']==0xffffffff and t['counter']==0 and not t['running'])
            check(name+'-compare-IRQ-ready-not-active',t['interrupt_enable']==1 and t['interrupt_status']==0 and not t['IRQ'] and t['global_enable']==0xffff)
            for label in ['Timer0-config-return','Timer0-setup-return']:
                check(name+'-'+label,[e['r0'] for e in obs['events'] if e['label']==label]==[0])
            check(name+'-original-ISR-not-reached',next(p for p in obs['points'] if p['label']=='Timer0-ISR-entry')['hits']==0)
            check(name+'-next-XIP-fence',guards[0]['name']=='xip_guard' and guards[0]['operation']=='read' and guards[0]['address']==0x80100000)
            check(name+'-nominal-selector-frequency',t['frequency']==6000000)
            cases.append(dict(case=name,pc=hex(v['pc']),guard=guards[0],timer=t,events=obs['sequence']))
        check(name+'-not-whole-boot-display-hardware',not any(r[k] for k in ['boot_verified','display_verified','hardware_validated']))
    cli=json.loads((s/'timer0-shared-cli-01/report.json').read_text());check('CLI-prerequisite',cli['passed'] and cli['exit_code']==2 and cli['no_output'])
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=units,cases=cases,scope='Nominal shared timer spin tests and original stopped Timer0 setup through next XIP read; no original Timer0 ISR, silicon timing, full boot/display or hardware recovery proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=units)))


if __name__=='__main__':main()
