"""Audit idle-only power cleanup, exact original event prefix and failure boundaries."""
import argparse
import json
from pathlib import Path
from native_replay import parse_log, validate_assets, boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700)
    checks=[];cases=[];unit_count=0
    def check(n,ok):
        if not ok:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
        check(tag+'-unique',len(rows)==1)
        return rows[0]
    red=(s/'crypto-otp-off-red-02/renode.log').read_text()
    check('red-lifecycle-type-absent','Could not resolve type' in red and 'BlackwallCryptoOtpPowerLifecycle' in red)
    for name,count in [('unit-01',23),('default-unit-01',7),('crypto-stuck-unit-01',16),('otp-stuck-unit-01',18),('foreign-unit-01',1),('unlinked-unit-01',1),('serial-regression-01',83),('readiness-regression-01',30),('crypto-regression-01',30)]:
        d=s/('crypto-otp-off-'+name);r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
        check(name+'-count',r['passed'] and r['count']==len(r['checks'])==count);unit_count+=count
        check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        if name.startswith(('foreign','unlinked')):
            expected='identical readiness owner' if name.startswith('foreign') else 'OTP requires matching mask'
            check(name+'-expected-constructor-rejection',r['process_exit_133'] and expected in log and 'Machine started.' not in log)
        else:
            tag='BLACKWALL_OTP_SERIAL_UNIT' if name.startswith('serial-regression') else 'BLACKWALL_OTP_READ_READY_UNIT' if name.startswith('readiness-regression') else 'BLACKWALL_CRYPTO_POWER_UNIT' if name.startswith('crypto-regression') else 'BLACKWALL_CRYPTO_OTP_OFF_UNIT'
            check(name+'-log-report',marker(log,tag)==r)
    contract=json.loads((s/'crypto-otp-power-off-contract-02/report.json').read_text())
    check('source-contract51',contract['passed'] and contract['count']==51)
    for name in ['stock24','stock23','cfw','stock24-crypto-stuck','stock24-otp-stuck','stock24-default','stock24-otp-unknown']:
        key='stock24' if name.startswith('stock24') else name
        d=s/'crypto-otp-off-main-01'/name;old=s/'otp-generation-main-01'/key
        r=json.loads((d/'report.json').read_text());prior=json.loads((old/'report.json').read_text())
        log=(d/'renode.log').read_text();v=parse_log(log)
        check(name+'-native-report',v==r['observed'])
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key]
        _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        check(name+'-original-main',raw==(d/'main.bin').read_bytes())
        obs=marker(log,'BLACKWALL_OBSERVATION')
        check(name+'-no-drop',not obs['dropped_events'] and obs['sequence']==len(obs['events']) and obs['capacity']==4096)
        extra=['CRYPTO-disable-caller-return','OTP-disable-caller-return']
        projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if e['label'] not in extra)]
        previous=prior['selected_observation']['events']
        check(name+'-complete-prior-event-prefix',projected[:len(previous)]==previous)
        oldpoints={p['label']:p for p in prior['selected_observation']['points']}
        newpoints={p['label']:p for p in obs['points']}
        check(name+'-scan-output-unchanged',all(newpoints[l]==oldpoints[l] for l in ['OTP-serial-scan-entry','OTP-serial-scan-end']))
        off=marker(log,'BLACKWALL_CRYPTO_OTP_OFF')
        cp,otp=off['crypto'],off['otp']
        check(name+'-idle-only-no-physical-claim',off['idle_only'] and not off['physical_verified'] and not any(r[k] for k in ['boot_verified','display_verified','hardware_validated']))
        returns={label:[e['r0'] for e in obs['events'] if e['label']==label] for label in extra}
        guards=[g for g in v['guards'] if g['accesses']]
        check(name+'-single-guard',len(guards)==1)
        guard=guards[0]
        if name.endswith('default'):
            check('default-boundary-preserved',not off['selected'] and boundary_state(v)==boundary_state(prior['observed']))
            check('default-observation-preserved',r['selected_observation']==prior['selected_observation'])
            check('default-board-preserved',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        elif name.endswith('crypto-stuck'):
            check('crypto-failure-observed-caller-continues',returns[extra[0]]==[4] and returns[extra[1]]==[] and cp['phase']=='stuck-on' and cp['status']==0x200000 and otp['phase']=='on')
            check('crypto-stuck-blocks-OTP-store',guard['operation']=='write' and guard['address']==0x40021004 and guard['value']==0x400)
        elif name.endswith('otp-unknown'):
            check('OTP-unknown-preserved',returns[extra[0]]==[0] and returns[extra[1]]==[] and cp['phase']=='powered-off' and otp['phase']=='on' and otp['off_profile']==-1)
            check('OTP-unknown-store-blocked',guard['operation']=='write' and guard['address']==0x40021004 and guard['value']==0x400)
        else:
            stuck=name.endswith('otp-stuck')
            check(name+'-actual-cleanup-results',returns[extra[0]]==[0] and returns[extra[1]]==([4] if stuck else [0]))
            check(name+'-power-result',cp['phase']=='powered-off' and cp['cycles']==1 and otp['phase']==('stuck-on' if stuck else 'powered-off') and otp['cycles']==(0 if stuck else 1))
            check(name+'-witnesses-retired',not off['host_current'] and not off['ptm_current'])
            check(name+'-next-MSPI-config-guard',guard['operation']=='write' and guard['address']==0x40061000 and guard['value']==0x100461)
            nv=[e['r0'] for e in obs['events'] if e['label']=='NVdb-initializer-return']
            check(name+'-outer-initializer-return',nv==[0])
        cases.append(dict(case=name,pc=hex(v['pc']),guard=guard,cleanup_returns=returns,power=off,event_count=obs['sequence']))
    cli=json.loads((s/'crypto-otp-off-cli-01/report.json').read_text())
    check('CLI-prerequisite-guards',cli['passed'] and cli['count']==2 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=unit_count,cases=cases,scope='Explicit idle-only off responses, original cleanup and outer initializer return; no full boot, display, crypto engine or hardware recovery proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=len(checks),unit_checks=unit_count)))


if __name__=='__main__':main()
