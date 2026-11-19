"""Audit original read readiness and stop before unknown OTP data; no hardware validation."""
import argparse,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[];total=0
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
        check(tag+'-unique',len(rows)==1);return rows[0]
    units=[('unit-02',30),('host-busy-unit-01',30),('ptm-busy-unit-01',38),('unknown-unit-01',28),('host-unknown-unit-01',29),('ptm-unknown-unit-01',29),('foreign-otp-unit-03',1),('foreign-crypto-unit-01',1),('crypto-regression-01',30),('power-regression-01',21)]
    for suffix,count in units:
        d=s/('otp-read-ready-'+suffix);r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
        check(suffix+'-count',r['passed'] and r['count']==len(r['checks'])==count);total+=count
        check(suffix+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        if suffix.startswith('foreign'):
            check(suffix+'-expected-constructor-rejection',r['process_exit_133'] and 'OTP read readiness requires identical power owners' in log and 'Machine started.' not in log)
        else:
            tag='BLACKWALL_CRYPTO_POWER_UNIT' if suffix.startswith('crypto') else 'BLACKWALL_OTP_POWER_UNIT' if suffix.startswith('power') else 'BLACKWALL_OTP_READ_READY_UNIT'
            check(suffix+'-log-report',marker(log,tag)==r)
    contract=json.loads((s/'crypto-host-idle-contract-01/report.json').read_text());check('source-contract46',contract['passed'] and contract['count']==46)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    names=['stock24','stock23','cfw','stock24-host-busy','stock24-ptm-busy','stock24-ptm-unknown','stock24-host-unknown','stock24-default']
    for name in names:
        key='stock24' if name.startswith('stock24') else name;bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key]
        d=s/'otp-read-ready-main-01'/name;old=s/'crypto-power-main-01'/key;oldr=json.loads((old/'report.json').read_text());oldlog=(old/'renode.log').read_text()
        r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-report',v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        meta=next(c for c in contract['cases'] if c['case']==key);entry=int(meta['ready_function'],0);wrapper=int(meta['read_wrapper'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[entry-0x438000:wrapper+0x36-0x438000],entry)}
        check(name+'-source-return-points',code.get(entry+0x3a)==('bx','lr') and code.get(wrapper+0x34)==('pop','{r1, r4, r5, pc}'))
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',obs['capacity']==4096 and not obs['dropped_events'] and obs['sequence']==len(obs['events']))
        labels=r['readiness_observation_points'];check(name+'-explicit-projection-labels',labels==([] if name.endswith('default') else ['OTP-read-ready-return','OTP-word-read-return']))
        projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if e['label'] not in labels)]
        check(name+'-prior-prefix',projected[:len(oldr['selected_observation']['events'])]==oldr['selected_observation']['events'])
        rd=marker(log,'BLACKWALL_OTP_READ_READY');events={label:[e['r0'] for e in obs['events'] if e['label']==label] for label in ['OTP-read-ready-return','OTP-word-read-return']}
        guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        guard=guards[0]
        check(name+'-boundary-operation',guard['operation']==('write' if name.endswith('host-busy') else 'read'))
        check(name+'-no-data-physical-boot-claim',not rd['OTP_contents_known'] and not rd['physical_ready_verified'] and not r['hardware_validated'] and not r['boot_verified'] and not r['display_verified'])
        if name.endswith('default'):
            check('default-unknown-boundary',not rd['selected'] and boundary_state(v)==boundary_state(oldr['observed']) and all(not e for e in events.values()))
            check('default-board-identical',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        elif name.endswith('host-unknown'):
            check('HOST-unknown',rd['selected'] and rd['host_idle']==-1 and rd['host_reads']==rd['ptm_reads']==0 and guard['address']==0x400c0a7c and all(not e for e in events.values()))
        elif name.endswith('ptm-unknown'):
            check('PTM-unknown',rd['host_reads']==1 and rd['ptm_busy']==-1 and rd['ptm_reads']==0 and guard['address']==0x40014ac4 and all(not e for e in events.values()))
        elif name.endswith('ptm-busy'):
            check('bounded-busy-loop',rd['ptm_busy']==1 and rd['ptm_reads']==rd['budget']==8 and rd['budget_exhausted'] and guard['address']==0x40014ac4 and v['pc']==entry+0x32 and all(not e for e in events.values()))
        elif name.endswith('host-busy'):
            check('host-busy-actual-error7',rd['host_idle']==0 and rd['host_reads']>=1 and events['OTP-read-ready-return'] and all(x==7 for x in events['OTP-read-ready-return']) and events['OTP-word-read-return'] and all(x==7 for x in events['OTP-word-read-return']))
            check('host-busy-off-remains-unsupported',guard['address']==0x40021004 and guard['value']==0x08000400)
        else:
            check(name+'-clear-ready-but-unknown-word',rd['host_idle']==1 and rd['ptm_busy']==0 and rd['host_reads']==rd['ptm_reads']==1 and events['OTP-read-ready-return']==[0] and not events['OTP-word-read-return'] and guard['address']==0x400c2340 and v['pc']==wrapper+0x30)
        histories={}
        for tag in ['BLACKWALL_NOR_ARRAY','BLACKWALL_NOR_PROGRAM','BLACKWALL_NOR_ERASE']:
            value=marker(log,tag);histories[tag]=value
            check(name+'-'+tag+'-unchanged',value==marker(oldlog,tag))
        cases.append(dict(case=name,pc=hex(v['pc']),readiness=rd,events=events,guards=guards,event_count=obs['sequence']))
    cli=json.loads((s/'otp-read-ready-cli-01/report.json').read_text());check('CLI-four-guards',cli['passed'] and cli['count']==4 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=total,cases=cases,scope='Readiness profiles and source-executed gates only; OTP contents/bank, engine, factory init, boot/display and hardware unverified')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=total)))


if __name__=='__main__':main()
