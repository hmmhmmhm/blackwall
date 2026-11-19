"""Audit blank read-only LittleFS mount failure and first format erase rejection."""
import argparse,json
from pathlib import Path
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[];units=0
    def check(n,ok):
        if not ok:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')];check(tag+'-unique',len(rows)==1);return rows[0]
    check('red-additional-window-absent','takes at most 5 arguments (6 given)' in (s/'nor-additional-red-01/renode.log').read_text())
    for folder,tag,count in [('nor-additional-unit-03','BLACKWALL_NOR_ADDITIONAL_UNIT',31),('littlefs-blank-array-regression-01','BLACKWALL_ARRAY_UNIT',None),('littlefs-blank-program-regression-01','BLACKWALL_PROGRAM_UNIT',None)]:
        d=s/folder;r=json.loads((d/'report.json').read_text());check(folder+'-report',r==marker((d/'renode.log').read_text(),tag))
        check(folder+'-checks',r['passed'] and r['count']==len(r['checks']) and (count is None or r['count']==count));units+=r['count']
        check(folder+'-current-model',(d/'strict.cs').read_bytes()==models(s))
    labels=['LittleFS-mount-entry','LittleFS-format-entry','LittleFS-read-entry','LittleFS-first-mount-return','LittleFS-format-return','LittleFS-remount-return']
    for name in ['stock24','stock23','cfw','stock24-default']:
        key='stock24' if name.startswith('stock24') else name;d=s/'littlefs-blank-main-02'/name;old=s/'crypto-otp-off-main-01'/key
        r=json.loads((d/'report.json').read_text());prior=json.loads((old/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log)
        check(name+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/dict(stock24='stock-2.4.0.24.bin',stock23='stock-2.3.0.24.bin',cfw='faceclaw-38-research-only.bin')[key]).read_bytes())
        check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',not obs['dropped_events'] and obs['sequence']==len(obs['events']))
        projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if e['label'] not in labels)]
        previous=prior['selected_observation']['events'];check(name+'-all-prior-event-prefix',projected[:len(previous)]==previous)
        vol=marker(log,'BLACKWALL_LITTLEFS_VOLUME');guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        if name.endswith('default'):
            check('default-unknown-volume',not vol['selected'] and boundary_state(v)==boundary_state(prior['observed']))
            check('default-all-observations',r['selected_observation']==prior['selected_observation'])
        else:
            check(name+'-read-only-blank-volume',vol['selected'] and vol['start']==0x1400000 and vol['length']==0xbc0000 and vol['prefix']==[255]*16 and not vol['erase_allowed'] and not vol['program_allowed'] and vol['synthetic'] and not vol['stock_contents_known'])
            points={p['label']:p for p in obs['points']}
            check(name+'-first-mount-and-format',points[labels[0]]['hits']==points[labels[1]]['hits']==points[labels[3]]['hits']==1)
            check(name+'-mount-result-minus84',[e['r0'] for e in obs['events'] if e['label']==labels[3]]==[0xffffffac])
            check(name+'-format-not-completed',points[labels[4]]['hits']==points[labels[5]]['hits']==0)
            check(name+'-first-erase-guard',guards[0]['operation']=='write' and guards[0]['address']==0x40061000 and guards[0]['value']==0xe1)
            cfg=marker(log,'BLACKWALL_MSPI1_CONFIG')['registers'];check(name+'-erase-target-in-volume',cfg['12']==0x20 and cfg['8']==0x1400000)
            erase=marker(log,'BLACKWALL_NOR_ERASE');olderase=marker((old/'renode.log').read_text(),'BLACKWALL_NOR_ERASE')
            check(name+'-no-additional-erase',all(erase[k]==olderase[k] for k in ['starts','completions','last_address']))
            check(name+'-program-state-unchanged',marker(log,'BLACKWALL_NOR_PROGRAM')==marker((old/'renode.log').read_text(),'BLACKWALL_NOR_PROGRAM'))
        check(name+'-no-boot-display-hardware',not any(r[k] for k in ['boot_verified','display_verified','hardware_validated']))
        cases.append(dict(case=name,pc=hex(v['pc']),guard=guards[0],volume=vol,events=obs['sequence']))
    d=s/'littlefs-blank-main-01/stock24';r=json.loads((d/'report.json').read_text());v=parse_log((d/'renode.log').read_text());check('small-RX-limit-report',v==r['observed']);check('small-RX-limit-preserved',next(g for g in v['guards'] if g['accesses'])['value']==0x10000461)
    cli=json.loads((s/'littlefs-blank-cli-01/report.json').read_text());check('CLI-prerequisites',cli['passed'] and cli['exit_code']==2 and cli['no_output'])
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=units,cases=cases,scope='Read-only synthetic LittleFS -> original mount -84 -> format entry -> erase rejected; no format completion, stock assets, boot or hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=units)))


if __name__=='__main__':main()
