"""Audit original ARM format, remount and application init on synthetic RAM NOR."""
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
    red=json.loads((s/'littlefs-writable-red-01/report.json').read_text());check('pre-option-rejection',red['unknown_option'] and red['exit_code']==2 and red['no_output'])
    for name in ['stock24','stock23','cfw','stock24-read-only']:
        key='stock24' if name.startswith('stock24') else name;d=s/'littlefs-format-main-01'/name;old=s/'littlefs-blank-main-02'/key
        r=json.loads((d/'report.json').read_text());prior=json.loads((old/'report.json').read_text());log=(d/'renode.log').read_text();oldlog=(old/'renode.log').read_text();v=parse_log(log)
        check(name+'-native-report',v==r['observed']);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-unchanged-current-model',(d/'strict.cs').read_bytes()==models(s)==(old/'strict.cs').read_bytes())
        filename=dict(stock24='stock-2.4.0.24.bin',stock23='stock-2.3.0.24.bin',cfw='faceclaw-38-research-only.bin')[key]
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',not obs['dropped_events'] and obs['sequence']==len(obs['events']) and obs['capacity']==4096)
        previous=prior['selected_observation']['events'];check(name+'-whole-read-only-event-prefix',obs['events'][:len(previous)]==previous)
        vol=marker(log,'BLACKWALL_LITTLEFS_VOLUME');check(name+'-synthetic-only',vol['synthetic'] and not vol['stock_contents_known'] and vol['start']==0x1400000 and vol['length']==0xbc0000)
        if name.endswith('read-only'):
            check('read-only-CPU-state-preserved',v==prior['observed'])
            check('read-only-observation-preserved',r['selected_observation']==prior['selected_observation'])
            check('read-only-board-preserved',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
            check('read-only-permissions-preserved',not vol['program_allowed'] and not vol['erase_allowed'] and r['littlefs_access']=='read-only')
        else:
            check(name+'-explicit-RAM-write-permissions',vol['program_allowed'] and vol['erase_allowed'] and r['littlefs_access']=='read-write')
            expected={'LittleFS-first-mount-return':[0xffffffac],'LittleFS-format-return':[0],'LittleFS-remount-return':[0],'LittleFS-app-init-return':[0]}
            for label,values in expected.items():check(name+'-'+label,[e['r0'] for e in obs['events'] if e['label']==label]==values)
            points={p['label']:p for p in obs['points']};check(name+'-mount-twice-format-once',points['LittleFS-mount-entry']['hits']==2 and points['LittleFS-format-entry']['hits']==1)
            check(name+'-written-littlefs-magic',bytes(vol['prefix'][8:16])==b'littlefs')
            er=marker(log,'BLACKWALL_NOR_ERASE');old_er=marker(oldlog,'BLACKWALL_NOR_ERASE')
            pp=marker(log,'BLACKWALL_NOR_PROGRAM');old_pp=marker(oldlog,'BLACKWALL_NOR_PROGRAM')
            check(name+'-additional-erase-completed',er['starts']==er['completions']>old_er['completions'] and not er['busy'])
            check(name+'-additional-program-completed',pp['starts']==pp['completions']>old_pp['completions'] and pp['bytes']>old_pp['bytes'] and not pp['busy'])
            check(name+'-DB-header-preserved',pp['prefix_words']==old_pp['prefix_words'])
            guards=[g for g in v['guards'] if g['accesses']]
            check(name+'-next-hardware-read',len(guards)==1 and guards[0]['operation']=='read' and guards[0]['address']==0x40010414)
            cases.append(dict(case=name,pc=hex(v['pc']),guard=guards[0],events=obs['sequence'],erase_delta=er['completions']-old_er['completions'],program_delta=pp['completions']-old_pp['completions'],program_bytes_delta=pp['bytes']-old_pp['bytes']))
        check(name+'-no-full-boot-display-or-physical-claim',not any(r[k] for k in ['boot_verified','display_verified','hardware_validated']))
    cli=json.loads((s/'littlefs-writable-cli-01/report.json').read_text());check('CLI-prerequisites',cli['passed'] and cli['count']==2 and all(c['exit_code']==2 and c['no_output'] and c['explicit_error'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Original format/remount/app filesystem init on initially blank synthetic RAM volume; no stock assets, complete boot, physical flash or recovery proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),cases=cases)))


if __name__=='__main__':main()
