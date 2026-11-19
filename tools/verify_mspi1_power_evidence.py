"""Audit saved MSPI1 power probes against source pins and immutable firmware."""
import argparse, hashlib, json
from pathlib import Path
from native_replay import FILES, parse_log, validate_assets, boundary_state
from pinned_main import load_pinned_main
from mspi1_power_board import attach
from probe_mspi1_power_main import MARKER
from verify_mspi1_power import DRIVER

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;checks=[]
    def check(name,value):
        if not value:raise ValueError(name)
        checks.append(name)
    research=s/'mspi1-source-research-01'
    pins=json.loads((research/'sources.json').read_text())
    for item in pins['files']:
        data=(research/Path(item['path']).name).read_bytes()
        check(item['path']+' sha256',hashlib.sha256(data).hexdigest()==item['sha256'])
        check(item['path']+' git blob',hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['git_blob'])
    unit=s/'mspi1-power-unit-03'
    rows=[json.loads(x.split('BLACKWALL_MSPI1_POWER_UNIT ',1)[1]) for x in (unit/'renode.log').read_text().splitlines() if x.startswith('BLACKWALL_MSPI1_POWER_UNIT ')]
    check('unit marker/report',rows==[json.loads((unit/'report.json').read_text())])
    check('unit checks',rows[0]['passed'] and rows[0]['count']==len(rows[0]['checks'])==23)
    root=Path(__file__).resolve().parents[1]
    main=s/'mspi1-power-main-01'
    check('current core saved', (main/'core.cs').read_bytes()==(root/'tools/renode-strict-mmio.cs').read_bytes())
    check('unit current driver',(unit/'test.py').read_text()==DRIVER)
    check('unit full models',(unit/'strict.cs').read_bytes()==(main/'stock24/strict.cs').read_bytes())
    check('unit board',(unit/'board.repl').read_bytes()==(main/'stock24/board.repl').read_bytes())
    for name,key,bundle in [('stock24','stock24','stock-2.4.0.24.bin'),('stock23','stock23','stock-2.3.0.24.bin'),('cfw','cfw','faceclaw-38-research-only.bin'),('stock24-no-mspi1','stock24','stock-2.4.0.24.bin')]:
        d=main/name;report=json.loads((d/'report.json').read_text())
        observed=parse_log((d/'renode.log').read_text())
        check(name+' parsed report',observed==report['observed'])
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);checks.append(name+' asset hashes')
        _,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
        check(name+' original main',raw==(d/'main.bin').read_bytes())
        frozen=s/'stimer-clock-main-01'/key
        check(name+' board derivation',(d/'board.repl').read_text()==attach((frozen/'board.repl').read_text(),'active' if name!='stock24-no-mspi1' else None))
        check(name+' observation-only runtime',(d/'run.py').read_text()==(frozen/'run.py').read_text().replace('except Exception as error:\n',MARKER+'except Exception as error:\n'))
        old=(research/'base-core.cs').read_bytes();oldstrict=(frozen/'strict.cs').read_bytes()
        check(name+' unchanged suffix',oldstrict.startswith(old) and (d/'strict.cs').read_bytes()==(main/'core.cs').read_bytes()+oldstrict[len(old):])
        for file in ['result.py','probe.resc','sram-fill.bin','itcm-fill.bin']:
            check(name+' frozen '+file,(d/file).read_bytes()==(frozen/file).read_bytes())
        power=report['power'];active=name!='stock24-no-mspi1'
        check(name+' power',power==dict(enabled=False) if not active else power['phase']=='on' and power['request']==power['status']==0x8000 and power['requests']==power['responses']==1 and power['off_requests']==0)
        guards=[g for g in observed['guards'] if g['accesses']]
        check(name+' strict boundary',len(guards)==1 and guards[0]['address']==(0x40004110 if active else 0x40021004) and guards[0]['operation']==('read' if active else 'write'))
        check(name+' no completion claim',not report['boot_verified'] and not report['hardware_validated'] and not report['installable'])
        if not active:
            check(name+' full boundary preserved',boundary_state(observed)==boundary_state(parse_log((frozen/'renode.log').read_text())))
    stuck=s/'mspi1-power-stuck-main-01/stock24-stuck-off'
    r=json.loads((stuck/'report.json').read_text());v=parse_log((stuck/'renode.log').read_text())
    check('stuck saved report',v==r['observed'])
    validate_assets(stuck,json.loads((stuck/'derived-inputs.json').read_text())['derived']);checks.append('stuck hashes')
    check('stuck original main',(stuck/'main.bin').read_bytes()==(main/'stock24/main.bin').read_bytes())
    check('stuck models',(stuck/'strict.cs').read_bytes()==(main/'stock24/strict.cs').read_bytes())
    check('stuck runtime',(stuck/'run.py').read_bytes()==(main/'stock24/run.py').read_bytes())
    check('stuck board',(stuck/'board.repl').read_text()==attach((s/'stimer-clock-main-01/stock24/board.repl').read_text(),'stuck-off'))
    check('stuck response',r['power']['phase']=='stuck-off' and r['power']['status']==0 and r['power']['responses']==1)
    guards=[g for g in v['guards'] if g['accesses']]
    check('stuck still attempts next register',len(guards)==1 and guards[0]['address']==0x40004110 and guards[0]['operation']=='read')
    a.output.mkdir(mode=0o700)
    result=dict(passed=True,count=len(checks),checks=checks,scope='saved source and execution artifacts, not physical hardware or full boot')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=len(checks))))

if __name__=='__main__':main()
