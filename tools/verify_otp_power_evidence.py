"""Audit optional OTP power readiness without OTP contents or crypto emulation claims."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from inspect_mspi1_config_contract import collect


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
        check(tag+'-unique',len(rows)==1);return rows[0]
    core=(Path(__file__).resolve().parent/'renode-strict-mmio.cs').read_bytes();total=0
    for folder,tag,expected,full in [('otp-power-unit-02','BLACKWALL_OTP_POWER_UNIT',21,True),('otp-power-stuck-unit-01','BLACKWALL_OTP_POWER_UNIT',21,True),('otp-power-unknown-unit-01','BLACKWALL_OTP_POWER_UNIT',1,True),('otp-power-mspi-regression-01','BLACKWALL_MSPI1_POWER_UNIT',23,False),('otp-power-rx-regression-01','BLACKWALL_RX_STREAM',79,True)]:
        d=s/folder;r=json.loads((d/'report.json').read_text())
        check(folder+'-log-report',marker((d/'renode.log').read_text(),tag)==r)
        check(folder+'-checks',r['passed'] and r['count']==len(r['checks'])==expected);total+=expected
        check(folder+'-current-source',(d/'strict.cs').read_bytes()==models(s) if full else (d/'strict.cs').read_bytes().startswith(core))
    source=json.loads((s/'otp-power-contract-01/report.json').read_text());check('source-contract31',source['passed'] and source['count']==31)
    collect(s)
    svd=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot()
    otpreg=next(per for per in svd.findall('./peripherals/peripheral') if per.findtext('name')=='OTP')
    ptm=next(reg for reg in otpreg.findall('./registers/register') if reg.findtext('name')=='PTMSTAT')
    check('OTP-PTMSTAT-source-address',int(otpreg.findtext('baseAddress'),0)+int(ptm.findtext('addressOffset'),0)==0x40014ac4)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for name in ['stock24','stock23','cfw','stock24-stuck','stock24-default']:
        key='stock24' if name.startswith('stock24') else name
        bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key]
        d=s/'otp-power-main-02'/name;log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());v=parse_log(log)
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-report',v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        meta=next(c for c in source['cases'] if c['case']==key);caller=int(meta['caller'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[caller-0x438000:caller+8-0x438000],caller)}
        check(name+'-unique-OTP-caller-point',code.get(caller)==('bl','#'+meta['entry']) and code.get(caller+4)==('movs','r0, #0x17'))
        obs=marker(log,'BLACKWALL_OBSERVATION');old=s/'mspi1-rx-stream-main-01'/key;oldr=json.loads((old/'report.json').read_text());oldlog=(old/'renode.log').read_text()
        check(name+'-no-drop',obs['capacity']==4096 and not obs['dropped_events'] and obs['sequence']==len(obs['events']))
        projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if e['label']!='OTP-enable-caller-return')]
        check(name+'-prior-event-prefix',projected[:len(oldr['selected_observation']['events'])]==oldr['selected_observation']['events'])
        otp=marker(log,'BLACKWALL_OTP_POWER');events=[e for e in obs['events'] if e['label']=='OTP-enable-caller-return']
        check(name+'-no-memory-or-physical-claim',not otp['OTP_contents_known'] and not otp['physical_power_verified'] and not r['boot_verified'] and not r['display_verified'] and not r['hardware_validated'])
        for tag in ['BLACKWALL_NOR_ARRAY','BLACKWALL_NOR_PROGRAM','BLACKWALL_NOR_ERASE']:
            check(name+'-'+tag+'-unchanged',marker(log,tag)==marker(oldlog,tag))
        guards=[g for g in v['guards'] if g['accesses']]
        check(name+'-single-guard',len(guards)==1)
        if name.endswith('default'):
            check('default-old-boundary',boundary_state(v)==boundary_state(oldr['observed']) and not otp['selected'] and not events)
            check('default-board-identical',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        elif name.endswith('stuck'):
            check('stuck-no-OTP-ready',otp['selected'] and otp['phase']=='stuck-off' and otp['status']==0 and otp['request']==0x08000000 and otp['requests']==otp['responses']==1)
            check('stuck-OTP-timeout-return',len(events)==1 and events[0]['r0']==4)
            check('stuck-PTMSTAT-remains-guarded',guards[0]['operation']=='read' and guards[0]['address']==0x40014ac4)
        else:
            check(name+'-ready-once',otp['phase']=='on' and otp['request']==otp['status']==0x08000000 and otp['requests']==otp['responses']==1)
            check(name+'-caller-success',len(events)==1 and events[0]['r0']==0)
            check(name+'-CRYPTO-remains-guarded',guards[0]['address']==0x40021004 and guards[0]['value']==0x08200400 and v['register_context']['r4']==23)
        cases.append(dict(case=name,pc=hex(v['pc']),otp=otp,guards=guards,events=obs['sequence']))
    cli=json.loads((s/'otp-power-cli-01/report.json').read_text());check('CLI-two-preconditions',cli['passed'] and cli['count']==2 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=total,cases=cases,scope='Explicit OTP power owner only; no OTP memory/fuses/crypto engine or whole boot/display/hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=total)))


if __name__=='__main__':main()
