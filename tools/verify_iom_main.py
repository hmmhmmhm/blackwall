"""Compare three pinned original mains through IOM2 initialization to the next strict boundary, without devices."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
from pinned_main import load_pinned_main
ROOT=Path(__file__).resolve().parents[1]

def arguments(hypotheses):
    aliases={'nominal_lfrc_watchdog':'watchdog-model','synthetic_reset_controller':'reset-controller',
             'invalid_info1_metadata':'info1-metadata-fixture','chip_revision':'chip-revision-fixture',
             'coreldo_reduction_storage':'coreldo-reduction-storage','memldo_setup_storage':'memldo-setup-storage'}
    result=[]
    for key,value in hypotheses.items():
        if value is None or value is False or key in ('iom2_model','iom2_off_response','iom_modules','iom4_model','iom_cq_input_levels','iom_power_profiles'):continue
        if key in ('observe_pc','observe_sram'):
            for item in value:result+=['--'+key.replace('_','-'),str(item)]
            continue
        if key=='capture_sram_windows':
            for address,size in value:result+=['--capture-sram-window',f'{hex(address)}:{size}']
            continue
        if key=='uart_modules':value=','.join(map(str,value))
        result+=['--'+aliases.get(key,key.replace('_','-'))]
        if value is not True:result+=[str(value)]
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('inputs',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--cq-input-levels',type=lambda v:int(v,0),help='Explicit mock CQ signal vector; omitted keeps external inputs unknown')
    parser.add_argument('--expected-guard-operation')
    parser.add_argument('--iom-modules',default='2')
    parser.add_argument('--expected-guard-address',type=lambda v:int(v,0))
    parser.add_argument('--expected-guard-value',type=lambda v:int(v,0))
    parser.add_argument('--expected-guard-name')
    args=parser.parse_args()
    modules=tuple(sorted(int(n) for n in args.iom_modules.split(',')))
    if not modules or modules[0]!=2 or len(set(modules))!=len(modules) or any(n not in (2,4,5,7) for n in modules):raise ValueError('Comparison requires unique selected startup modules including2')
    if args.cq_input_levels is not None and not 0<=args.cq_input_levels<=31:raise ValueError('CQ inputs must be an explicit five-bit mock vector')
    if args.expected_guard_address is None:args.expected_guard_address=0x40052234 if args.cq_input_levels is None else (0x4000400c if modules==(2,4,5,7) else 0x40021004)
    if args.expected_guard_value is None:args.expected_guard_value=0 if args.cq_input_levels is None or modules==(2,4,5,7) else next(1<<(n+1) for n in (2,4,5,7) if n not in modules)
    if args.expected_guard_name is None:args.expected_guard_name='iom2' if args.cq_input_levels is None else 'guard'
    if args.expected_guard_operation is None:args.expected_guard_operation='cq-external-flags-unknown' if args.cq_input_levels is None else ('read' if modules==(2,4,5,7) else 'write')
    out=args.output.resolve();out.mkdir(mode=0o700)
    options=arguments(json.loads(args.baseline.read_text())['selected_hypotheses'])+['--wall-run-seconds','15','--iom-modules',args.iom_modules]
    if args.cq_input_levels is not None:options+=['--iom-cq-input-levels',str(args.cq_input_levels)]
    rows=[]
    cases=[('stock24','stock-2.4.0.24.bin','active',None),('stock23','stock-2.3.0.24.bin','active',None),('cfw','faceclaw-38-research-only.bin','active',None),('stock24-stuck','stock-2.4.0.24.bin','stuck-off',None)]
    if args.cq_input_levels is not None:
        cases += [('stock24-iom'+str(n)+'-stuck','stock-2.4.0.24.bin','active',n) for n in modules if n!=2]
    for name,file,mode,override in cases:
        bundle=(args.inputs/file).resolve();run=out/name
        cmd=[sys.executable,str(ROOT/'tools/run_renode_main_probe.py'),str(bundle),str(run),*options,'--iom2-model',mode]
        if mode=='active':cmd+=['--iom2-off-response','off']
        if override==4:cmd+=['--iom4-model','stuck-off']
        elif override is not None:cmd+=['--iom-power-profile',str(override)+':stuck-off']
        result=subprocess.run(cmd,capture_output=True,text=True)
        (out/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2)+'\n')
        if result.returncode:raise RuntimeError('Main probe failed: '+name)
        report=json.loads((run/'report.json').read_text());o=report['observed']
        _,raw=load_pinned_main(bundle.read_bytes())
        assert (run/'main.bin').read_bytes()==raw
        assert report['reset_vector']==hex(struct.unpack_from('<I',raw,4)[0])
        assert not report['boot_verified'] and not report['hardware_validated'] and not report['installable']
        assert all(not u['tx_bytes'] and u['irq_exception_entries']==0 for u in o['uarts'])
        assert o['iom2']['commands']==0 and o['iom2']['power_requests']==1
        guards=[g for g in o['guards'] if g['accesses']]
        if override is not None:
            ports={w['module']:w for w in o['ioms']};w=ports[override]
            assert len(guards)==1 and guards[0]['name']=='iom'+str(override) and guards[0]['address']==0x40050000+override*0x1000+0x104 and guards[0]['value']==0x1010
            assert w['power_phase']=='stuck-off' and w['power_profile']==0 and w['status_word']==0 and w['writes']==0 and w['commands']==0
            assert all(ports[n]['power_phase']=='powered-off' and ports[n]['power_downs']==1 for n in modules if n<override)
            assert all(ports[n]['power_requests']==0 and ports[n]['power_phase']=='off' for n in modules if n>override)
        elif mode=='active':
            assert len(guards)==1 and guards[0]['name']==args.expected_guard_name and guards[0]['address']==args.expected_guard_address and guards[0]['operation']==args.expected_guard_operation and guards[0]['value']==args.expected_guard_value
            if args.cq_input_levels is None:
                assert o['iom2']['power_phase']=='on' and o['iom2']['cq']['last_error']=='external-flags-unknown'
            else:
                assert o['iom2']['power_phase']=='powered-off' and o['iom2']['status_word']==0 and o['iom2']['power_downs']==1
                assert o['iom2']['last_i2c_configuration']==0x3f270 and o['iom2']['i2c_configuration_writes']==1
                for w in o['ioms']:
                    assert w['power_phase']=='powered-off' and w['status_word']==0 and w['power_downs']==1 and w['last_i2c_configuration']==(0x23040 if w['module']==4 else 0x3f270) and w['commands']==0
            assert all(w['cq']['pairs']==0 for w in o['ioms'])
        else:
            assert o['iom2']['power_phase']=='stuck-off' and o['iom2']['status_word']==0
            assert len(guards)==1 and guards[0]['name']=='iom2' and guards[0]['address']==0x40052104 and guards[0]['value']==0x1010 and o['iom2']['writes']==0
        row=dict(name=name,pc=hex(o['pc']),raw_main_sha256=report['raw_main_sha256'],reset_vector=report['reset_vector'],iom2=o['iom2'],ioms=o['ioms'],guards=guards,reason=report['reason'])
        rows.append(row);print(json.dumps(row),flush=True)
    sources=['renode-strict-mmio.cs','renode-iom.cs','iom_main_adapter.py','run_renode_main_probe.py','verify_iom_adapter.py','verify_iom_main.py','iom_engine_source.py']
    backup=out/'source';backup.mkdir(mode=0o700)
    hashes={}
    for name in sources:
        data=(ROOT/'tools'/name).read_bytes();(backup/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    summary=dict(passed=True,main=rows,source_sha256=hashes,scope='original main reset under declared CQ input assumptions to strict boundary, no full boot/display or physical validation')
    (out/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main()
