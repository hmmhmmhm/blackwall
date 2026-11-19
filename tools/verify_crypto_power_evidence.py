"""Audit readiness flag effects on original ARM paths; no crypto engine or key validation."""
import argparse,json
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from verify_crypto_otp_gate import PROOF


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
        check(tag+'-unique',len(rows)==1);return rows[0]
    core=(Path(__file__).resolve().parent/'renode-strict-mmio.cs').read_bytes();total=0
    units=[('crypto-power-unit-01',30,'BLACKWALL_CRYPTO_POWER_UNIT',True),('crypto-power-busy-unit-01',30,'BLACKWALL_CRYPTO_POWER_UNIT',True),('crypto-power-stuck-unit-01',28,'BLACKWALL_CRYPTO_POWER_UNIT',True),('crypto-power-nvm-unknown-unit-01',29,'BLACKWALL_CRYPTO_POWER_UNIT',True),('crypto-power-default-unit-01',2,'BLACKWALL_CRYPTO_POWER_UNIT',True),('crypto-power-otp-regression-01',21,'BLACKWALL_OTP_POWER_UNIT',True),('crypto-power-mspi-regression-01',23,'BLACKWALL_MSPI1_POWER_UNIT',False)]
    for name,count,tag,full in units:
        d=s/name;r=json.loads((d/'report.json').read_text())
        check(name+'-log-report',marker((d/'renode.log').read_text(),tag)==r)
        check(name+'-checks',r['passed'] and r['count']==len(r['checks'])==count);total+=count
        check(name+'-current-source',(d/'strict.cs').read_bytes()==models(s) if full else (d/'strict.cs').read_bytes().startswith(core))
    contract=json.loads((s/'crypto-power-contract-01/report.json').read_text());check('source-contract31',contract['passed'] and contract['count']==31)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for name in ['stock24','stock23','cfw','stock24-busy','stock24-stuck','stock24-nvm-unknown','stock24-default']:
        key='stock24' if name.startswith('stock24') else name;bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key]
        d=s/'crypto-power-main-01'/name;old=s/'otp-power-main-02'/key;oldr=json.loads((old/'report.json').read_text());oldlog=(old/'renode.log').read_text()
        log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());v=parse_log(log);validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(name+'-report',v==r['observed']);check(name+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(name+'-original-main',(d/'main.bin').read_bytes()==raw)
        meta=next(c for c in contract['cases'] if c['case']==key);caller=int(meta['caller'],0);wait=int(meta['NVM_wait_call'],0)
        cc={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[caller-0x438000:caller+8-0x438000],caller)}
        wc={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[wait-0x438000:wait+6-0x438000],wait)}
        check(name+'-original-observation-points',cc.get(caller)==('bl','#'+meta['power_entry']) and cc.get(caller+4)==('movs','r0, #1') and wc.get(wait+4)==('cmp','r0, #0'))
        obs=marker(log,'BLACKWALL_OBSERVATION');check(name+'-no-drop',obs['capacity']==4096 and not obs['dropped_events'] and obs['sequence']==len(obs['events']))
        projected=[dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if not e['label'].startswith('CRYPTO-'))]
        check(name+'-prefix',projected[:len(oldr['selected_observation']['events'])]==oldr['selected_observation']['events'])
        cp=marker(log,'BLACKWALL_CRYPTO_POWER');ot=marker(log,'BLACKWALL_OTP_POWER')
        check(name+'-OTP-preserved',ot==marker(oldlog,'BLACKWALL_OTP_POWER'))
        for tag in ['BLACKWALL_NOR_ARRAY','BLACKWALL_NOR_PROGRAM','BLACKWALL_NOR_ERASE']:
            check(name+'-'+tag+'-unchanged',marker(log,tag)==marker(oldlog,tag))
        check(name+'-no-engine-physical-boot-claim',not cp['crypto_engine'] and not cp['physical_ready_verified'] and not r['hardware_validated'] and not r['boot_verified'] and not r['display_verified'])
        events={label:[e['r0'] for e in obs['events'] if e['label']==label] for label in ['CRYPTO-NVM-wait-return','CRYPTO-enable-caller-return']}
        guards=[g for g in v['guards'] if g['accesses']];check(name+'-single-guard',len(guards)==1)
        if name.endswith('default'):
            check('default-boundary',not cp['selected'] and boundary_state(v)==boundary_state(oldr['observed']) and all(not e for e in events.values()))
            check('default-board-identical',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        elif name.endswith('nvm-unknown'):
            check('unknown-ready-read-guard',cp['phase']=='on' and cp['nvm_idle']==-1 and cp['nvm_reads']==0 and guards[0]['address']==0x400c1f10 and guards[0]['operation']=='read' and all(not e for e in events.values()))
        elif name.endswith('stuck'):
            check('stuck-power-cancelled-without-NVM',cp['phase']=='cancelled' and cp['request']==cp['status']==0 and cp['requests']==cp['responses']==1 and cp['nvm_reads']==0 and events['CRYPTO-enable-caller-return']==[4] and not events['CRYPTO-NVM-wait-return'])
            check('stuck-next-PTMSTAT-guard',guards[0]['operation']=='read' and guards[0]['address']==0x40014ac4)
        else:
            busy=name.endswith('busy');expected=4 if busy else 0
            check(name+'-ready-power-once',cp['request']==cp['status']==0x200000 and cp['requests']==cp['responses']==1 and cp['phase']=='on')
            check(name+'-NVM-read-count',cp['nvm_idle']==int(not busy) and cp['nvm_reads']==(101 if busy else 1))
            check(name+'-wait-and-caller',events['CRYPTO-NVM-wait-return']==[expected] and events['CRYPTO-enable-caller-return']==[expected])
            check(name+'-next-engine-still-unknown',guards[0]['address']==0x400c0a7c and guards[0]['operation']=='read')
        cases.append(dict(case=name,pc=hex(v['pc']),crypto=cp,events=events,guards=guards,event_count=obs['sequence']))
    cli=json.loads((s/'crypto-power-cli-01/report.json').read_text());check('CLI-three-guards',cli['passed'] and cli['count']==3 and all(c['exit_code']==2 and c['no_output'] for c in cli['cases']))
    proof=s/'crypto-power-otp-gate-01';gate=json.loads((proof/'report.json').read_text());validate_assets(proof,json.loads((proof/'derived-inputs.json').read_text())['derived'])
    check('post-halt-gate-log-report',marker((proof/'renode.log').read_text(),'BLACKWALL_CRYPTO_OTP_GATE')==gate)
    check('post-halt-gate-checks',gate['passed'] and gate['count']==len(gate['checks'])==7)
    check('post-halt-gate-current-model',(proof/'strict.cs').read_bytes()==models(s))
    normal=s/'crypto-power-main-01/stock24'
    check('post-halt-original-runtime-prefix',(proof/'run.py').read_text()==(normal/'run.py').read_text()+PROOF)
    check('post-halt-unchanged-execution-inputs',all((proof/f).read_bytes()==(normal/f).read_bytes() for f in ['board.repl','main.bin','strict.cs','probe.resc','result.py','sram-fill.bin','itcm-fill.bin']))
    check('post-halt-original-result-before-fault',parse_log((proof/'renode.log').read_text())==json.loads((normal/'report.json').read_text())['observed'])
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=total,post_halt_checks=7,cases=cases,scope='Explicit readiness flags and original paths only; no crypto keys/engine/factory calibration/whole boot/display/hardware proof')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=total,post_halt_checks=7)))


if __name__=='__main__':main()
