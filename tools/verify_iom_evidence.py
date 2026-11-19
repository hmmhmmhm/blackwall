"""Audit original-main IOM run artifacts against current pinned model sources; no device access."""
import argparse,hashlib,json,re,struct
from pathlib import Path
from iom_engine_source import load_engine,UPSTREAM_SHA
from analyze_iom_metadata import definitions
from verify_iom_command_queue import DRIVER as CQ_DRIVER,MOCK_DRIVER
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--unit',default='iom-startup-adapter-01')
    parser.add_argument('--shared',default='iom-startup-shared-01')
    parser.add_argument('--comparison',default='iom-startup-main-comparison-01')
    parser.add_argument('--cq',default='iom-startup-cq-01')
    parser.add_argument('--strict-main',default='iom-startup-default-strict-01')
    parser.add_argument('--uart',default='iom-startup-uart-01')
    parser.add_argument('--uart-shared',default='iom-startup-uart-shared-01')
    a=parser.parse_args();s=a.simulator;o=a.output.resolve();o.mkdir(mode=0o700)
    def native_report(directory,marker):
        directory=s/directory;d=json.loads((directory/'report.json').read_text())
        records=[json.loads(line.split(marker,1)[1]) for line in (directory/'renode.log').read_text().splitlines() if line.startswith(marker)]
        assert len(records)==1 and records[0]==d
        assert d['passed'] and d['assertion_count']==len(d['checks'])
        return d
    unit=native_report(a.unit,'BLACKWALL_IOM ');shared=native_report(a.shared,'BLACKWALL_IOM_SHARED ')
    required={'streaming-tx-exact','long-read-finishes','unused-mi2crst-no-reset','unused-mi2crst-preserves-inflight','active-submodule-reset-unmodeled','arbitration-unmodeled','address-width-recheck','ten-bit-transfer','active-device-reroute','address-routing-preserved'}
    assert required.issubset(unit['checks'])
    uart=native_report(a.uart,'BLACKWALL_UART ')
    oldshared=native_report(a.uart_shared,'BLACKWALL_SHARED ')
    cq=native_report(a.cq,'BLACKWALL_CQ ')
    inputs=[native_report('iom-startup-pin-'+str(n)+'-01','BLACKWALL_CQ ') for n in (0,1,2,4,8,16,31)]
    assert cq['assertion_count']==79 and sum(r['assertion_count'] for r in inputs)==43
    core=(ROOT/'tools/renode-strict-mmio.cs').read_text();queue=(ROOT/'tools/renode-iom-command-queue.cs').read_text();iom=(ROOT/'tools/renode-iom.cs').read_text();engine=load_engine()
    assert (s/a.unit/'strict.cs').read_text().startswith(core+'\n'+engine+'\n'+queue+'\n'+iom)
    assert (s/a.uart/'strict.cs').read_text()==core
    core_sources=['renode-strict-mmio.cs','renode-memory-policy.cs','renode-system-control.cs','renode-reset-controller.cs','renode-watchdog.cs']
    expected='\n'.join((ROOT/'tools'/n).read_text() for n in core_sources)+'\n'+engine+'\n'+queue+'\n'+iom
    assert (s/a.shared/'strict.cs').read_text()==expected
    comparison=json.loads((s/a.comparison/'report.json').read_text());assert comparison['passed'];native=[]
    for row in comparison['main']:
        run=s/a.comparison/row['name'];d=json.loads((run/'report.json').read_text());v=d['observed']
        assert (run/'strict.cs').read_text()==expected
        for name in ['run_renode_main_probe.py','pinned_main.py','revalidate_research_assets.py','run_renode_m55_probe.py','iom_main_adapter.py','iom_engine_source.py']:
            assert (run/'host-source'/name).read_bytes()==(ROOT/'tools'/name).read_bytes()
        raw=(run/'main.bin').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==d['raw_main_sha256'] and d['reset_vector']==hex(struct.unpack_from('<I',raw,4)[0])
        assert not d['boot_verified'] and not d['installable'] and not d['hardware_validated'] and not d['unmodeled_engine_messages']
        assert d['iom_engine_provenance']['upstream_sha256']==UPSTREAM_SHA and d['iom_engine_provenance']['generated_sha256']==hashlib.sha256(engine.encode()).hexdigest()
        records=[json.loads(line.split('BLACKWALL_REPORT ',1)[1]) for line in (run/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_REPORT ')]
        assert len(records)==1 and records[0]==v
        active=not row['name'].endswith('stuck')
        for u in v['uarts']:
            reenabled=active and u['module']==1
            assert u['writes']==(34 if reenabled else 26) and u['power_downs']==1 and not u['tx_bytes'] and u['irq_exception_entries']==0
            assert u['phase']==('on' if reenabled else 'powered-off') and u['requests']==(2 if reenabled else 1) and u['responses']==(3 if reenabled else 2)

        guards=[g for g in v['guards'] if g['accesses']];assert len(guards)==1
        ioms={w['module']:w for w in v['ioms']}
        assert v['iom2']==ioms[2]
        failure=re.search(r'-(?:iom(\d+)-)?stuck$',row['name'])
        if failure:
            module=int(failure.group(1) or 2);failed=ioms[module]
            assert guards[0]['name']=='iom'+str(module) and guards[0]['address']==0x40050000+module*0x1000+0x104 and guards[0]['value']==0x1010 and guards[0]['operation']=='write'
            assert failed['power_profile']==0 and failed['power_phase']=='stuck-off' and failed['writes']==0 and failed['reads']==0 and failed['status_word']==0
            assert all(w['power_phase']=='powered-off' and w['power_downs']==1 for n,w in ioms.items() if n<module)
            assert all(w['power_phase']=='off' and w['power_requests']==0 and w['writes']==0 for n,w in ioms.items() if n>module)
        else:
            assert guards[0]['name']=='guard' and guards[0]['address']==0x4000400c and guards[0]['operation']=='read'
            for module,w in ioms.items():
                assert w['writes']==(13 if module==4 else 6) and w['reads']==(21 if module==4 else 20) and w['power_downs']==1 and w['power_phase']=='powered-off' and w['status_word']==0
                assert w['last_i2c_configuration']==(0x23040 if module==4 else 0x3f270) and w['i2c_configuration_writes']==1
            if row['name']=='stock24':
                windows={w['base']:bytes(w['bytes']) for w in v['sram_windows']}
                table=[struct.unpack_from('<4I',windows[0x20002a4c],n*16) for n in range(8)]
                for module,address in [(5,0x200413d0),(7,0x20042520)]:
                    words=struct.unpack('<8I',windows[address]);assert table[module][1]==address and words[1]==module and words[2]&255==1 and words[3]==0 and words[4]==0
                assert table[2][3]==table[5][3]==table[7][3]==0x20002a0c
        assert all(w['cq']['pairs']==0 and w['cq']['mock_input_levels']==0 and w['cq']['mock_external_inputs_assumed'] and not w['cq']['physical_flags_verified'] and not w['dma_execution_implemented'] for w in ioms.values())
        assert all(w['commands']==0 and not w['peer_attached'] for w in ioms.values())
        native.append(dict(name=row['name'],pc=hex(v['pc']),reset_vector=d['reset_vector'],guard=guards[0],iom2=v['iom2'],ioms=v['ioms']))
    for directory in [a.cq]+['iom-startup-pin-'+str(n)+'-01' for n in (0,1,2,4,8,16,31)]:
        assert (s/directory/'strict.cs').read_text().startswith(core+'\n'+engine+'\n'+queue+'\n'+iom)
        assert (s/directory/'test.py').read_text()==(CQ_DRIVER if directory==a.cq else MOCK_DRIVER)
    strict=json.loads((s/a.strict_main/'report.json').read_text());v=strict['observed']
    assert (s/a.strict_main/'strict.cs').read_text()==expected
    assert not strict['boot_verified'] and not strict['hardware_validated'] and not strict['installable'] and not strict['unmodeled_engine_messages']
    strict_raw=(s/a.strict_main/'main.bin').read_bytes()
    assert hashlib.sha256(strict_raw).hexdigest()==strict['raw_main_sha256'] and strict['reset_vector']==hex(struct.unpack_from('<I',strict_raw,4)[0])
    strict_records=[json.loads(line.split('BLACKWALL_REPORT ',1)[1]) for line in (s/a.strict_main/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_REPORT ')]
    assert len(strict_records)==1 and strict_records[0]==v
    for name in ['run_renode_main_probe.py','pinned_main.py','revalidate_research_assets.py','run_renode_m55_probe.py','iom_main_adapter.py','iom_engine_source.py']:
        assert (s/a.strict_main/'host-source'/name).read_bytes()==(ROOT/'tools'/name).read_bytes()
    assert strict['selected_hypotheses']['iom_cq_input_levels'] is None
    assert v['iom2']['cq']['mock_input_levels']==-1 and v['iom2']['cq']['unknown_external_flags_mask']==0x7f00
    block=[g for g in v['guards'] if g['accesses']]
    assert len(block)==1 and block[0]['name']=='iom2' and block[0]['address']==0x40052234 and block[0]['operation']=='cq-external-flags-unknown'
    stock=(s/a.comparison/'stock23/run.py').read_text();cfw=(s/a.comparison/'cfw/run.py').read_text()
    assert stock.replace(',3758688)',',3829832)')==cfw
    regs,_,_=definitions((s/'apollo-dfp-research-01/apollo510.svd').read_bytes(),(s/'upstream/hal-ambiq-61b293a/apollo510.h').read_bytes())
    section=iom[iom.index('private uint Mask('):iom.index('public new uint ReadDoubleWord')];actual={0:0xffffffff}
    for cases,value in re.findall(r'((?:case 0x[0-9a-f]+:)+)return (0x[0-9a-f]+|[0-9]+)u?;',section):
        for key in re.findall(r'case (0x[0-9a-f]+):',cases):actual[int(key,16)]=int(value,0)
    assert actual=={r['offset']:r['mask'] for r in regs}
    files=core_sources+['renode-iom-command-queue.cs','verify_iom_command_queue.py','analyze_iom_cq_contract.py','renode-iom.cs','iom_engine_source.py','iom_main_adapter.py','run_renode_main_probe.py','verify_iom_adapter.py','verify_iom_main.py','verify_iom_shared_bank.py','verify_iom_evidence.py','pinned_main.py','revalidate_research_assets.py','run_renode_m55_probe.py','analyze_iom_metadata.py','analyze_iom4_path.py','verify_iom_board.py']
    backup=o/'source';backup.mkdir(mode=0o700);hashes={}
    for name in files:
        data=(ROOT/'tools'/name).read_bytes();(backup/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    report=dict(passed=True,unit_directory=a.unit,shared_directory=a.shared,comparison_directory=a.comparison,uart_directory=a.uart,uart_shared_directory=a.uart_shared,cq_assertions=cq['assertion_count'],mock_input_assertions=sum(r['assertion_count'] for r in inputs),default_unknown_main_guard=block,unit_assertions=unit['assertion_count'],shared_assertions=shared['assertion_count'],uart_regression_assertions=uart['assertion_count'],old_shared_regression_assertions=oldshared['assertion_count'],mask_count=len(regs),upstream_sha256=UPSTREAM_SHA,generated_sha256=hashlib.sha256(engine.encode()).hexdigest(),native=native,sources=hashes,scope='current model/guest artifacts and source consistency; not physical timing, actual I2C main transfer, full boot or display')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,unit=unit['assertion_count'],shared=shared['assertion_count'],native=len(native),sources=len(hashes))))
if __name__=='__main__':main()
