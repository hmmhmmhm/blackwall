"""Audit synthetic slot reads and original candidate selection before unsupported cleanup."""
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
    units=[('unit-02',55),('empty-unit-01',55),('last-unit-01',55),('prefix-unit-01',55),('digit-unit-01',55),('default-unit-01',6),('foreign-unit-01',1),('host-busy-unit-01',6),('host-unknown-unit-01',7),('ptm-busy-unit-01',6),('ptm-unknown-unit-01',7),('readiness-regression-01',30),('crypto-regression-01',30)]
    for suffix,count in units:
        d=s/('otp-serial-slots-'+suffix);r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text()
        check(suffix+'-count',r['passed'] and r['count']==len(r['checks'])==count);total+=count
        check(suffix+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        if suffix.startswith('foreign'):check('foreign-readiness-rejected',r['process_exit_133'] and 'OTP serial slots require identical readiness owner' in log and 'Machine started.' not in log)
        else:
            tag='BLACKWALL_CRYPTO_POWER_UNIT' if suffix.startswith('crypto') else 'BLACKWALL_OTP_READ_READY_UNIT' if suffix.startswith('readiness') else 'BLACKWALL_OTP_SERIAL_UNIT'
            check(suffix+'-log-report',marker(log,tag)==r)
    contract=json.loads((s/'otp-window-consumer-contract-02/report.json').read_text());check('consumer-contract89',contract['passed'] and contract['count']==89)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for name in ['stock24','stock23','cfw','stock24-first','stock24-empty','stock24-prefix','stock24-digit','stock24-default']:
        key='stock24' if name.startswith('stock24') else name;file={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key]
        d=s/'otp-serial-slots-main-01'/name;old=s/'otp-read-ready-main-01'/key;oldr=json.loads((old/'report.json').read_text());oldlog=(old/'renode.log').read_text()
        r=json.loads((d/'report.json').read_text());log=(d/'renode.log').read_text();v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-native-report',v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/file).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        meta=next(c for c in contract['cases'] if c['case']==key);entry=int(meta['consumer_entry'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[entry-0x438000:entry+0x1d4-0x438000],entry)}
        check(name+'-scan-observation-sites',code.get(entry)==('push.w','{r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}') and code.get(entry+0x1d0)==('movs','r0, #0x17'))
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',obs['capacity']==4096 and not obs['dropped_events'] and obs['sequence']==len(obs['events']))
        labels=r['readiness_observation_points'];expected=['OTP-read-ready-return','OTP-word-read-return']+([] if name.endswith('default') else ['OTP-serial-scan-entry','OTP-serial-scan-end'])
        check(name+'-explicit-projection',labels==expected)
        def project(events):return [dict(e,sequence=i+1) for i,e in enumerate(e for e in events if e['label'] not in labels)]
        check(name+'-prior-selected-events',project(obs['events'])==project(oldr['selected_observation']['events']))
        slots=marker(log,'BLACKWALL_OTP_SERIAL_SLOTS');guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        check(name+'-no-physical-or-boot-claim',slots['synthetic'] and not slots['hardware_contents_known'] and not r['boot_verified'] and not r['display_verified'] and not r['hardware_validated'])
        if name.endswith('default'):
            check('default-unknown-word',not slots['selected'] and boundary_state(v)==boundary_state(oldr['observed']))
            check('default-board-identical',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        else:
            profile='mock-first' if name.endswith('first') else 'empty' if name.endswith('empty') else 'invalid-prefix' if name.endswith('prefix') else 'invalid-digit' if name.endswith('digit') else 'mock-last'
            check(name+'-bounded32-reads',slots['selected'] and slots['profile']==profile and slots['start']==0x400c2340 and slots['length']==128 and slots['reads']==32 and slots['last_address']==0x400c23bc)
            pts={p['label']:p for p in obs['points']}
            check(name+'-scan-entry-and-end-once',all(pts[l]['hits']==1 for l in ['OTP-serial-scan-entry','OTP-serial-scan-end']))
            def snap(label):return b''.join(int(w).to_bytes(4,'little') for w in pts[label]['snapshot']['words'])
            before,after=snap('OTP-serial-scan-entry'),snap('OTP-serial-scan-end')
            valid=profile in ['mock-first','mock-last'];index=0 if profile=='mock-first' else 7 if profile=='mock-last' else 0xffffffff
            check(name+'-candidate-state-index',v['register_context']['r7']==index)
            check(name+'-actual-output-bytes',after[:15]==((b'S211MOCK000001\0' if profile=='mock-first' else b'P100MOCK000002\0') if valid else before[:15]))
            ready=[e['r0'] for e in obs['events'] if e['label']=='OTP-read-ready-return'];words=[e['r0'] for e in obs['events'] if e['label']=='OTP-word-read-return']
            check(name+'-actual-read-wrapper-results',ready==[0]*32 and words==[0]*32)
            check(name+'-cleanup-not-completed',guards[0]['operation']=='write' and guards[0]['address']==0x40021004 and guards[0]['value']==0x08000400)
        for tag in ['BLACKWALL_NOR_ARRAY','BLACKWALL_NOR_PROGRAM','BLACKWALL_NOR_ERASE']:
            check(name+'-'+tag+'-unchanged',marker(log,tag)==marker(oldlog,tag))
        cases.append(dict(case=name,pc=hex(v['pc']),profile=slots,register_r7=v['register_context']['r7'],event_count=obs['sequence']))
    cli=json.loads((s/'otp-serial-slots-cli-01/report.json').read_text());check('CLI-three-guards',cli['passed'] and cli['count']==3 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=total,cases=cases,scope='Synthetic slot input and original selected output before cleanup guard; no actual OTP contents/keys, full consumer return, factory init, boot/display/hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=total)))


if __name__=='__main__':main()
