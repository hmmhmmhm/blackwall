"""Audit HCPA lifecycle evidence and preserve the unsupported cache boundary."""
import argparse,copy,hashlib,json
from pathlib import Path
from native_replay import FILES,digest,validate_assets
from probe_uart_hcpa_gate_main import BASE_SHA,CORE_SHA,parse_boundary
from verify_mspi1_pio_reset import models

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    r=json.loads((s/'uart0-hcpa-restart-contract-01/report.json').read_text());check('original-helper-contract',r['passed'] and r['count']==79 and r['original_helper_executions']==60)
    red=s/'uart-hcpa-gate-red-01';check('red-original-failure','shared-port-gated-without-poll' in (red/'renode.log').read_text() and not (red/'report.json').exists())
    for name,count in [('uart-hcpa-gate-unit-03',38),('uart-hcpa-gate-stuck-unit-01',37),('uart-hcpa-gate-uart-regression-01',117),('uart-hcpa-gate-status-regression-01',30)]:
        r=json.loads((s/name/'report.json').read_text());check(name,r['passed'] and r.get('count',r.get('assertion_count'))==count)
        check(name+'-current-model',(s/name/'strict.cs').read_bytes()==models(s))
    core=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes();check('reviewed-core-pin',hashlib.sha256(core).hexdigest()==CORE_SHA)
    for name in ['stock24','stock23','cfw','stock24-default']:
        d=s/'uart-hcpa-gate-main-01'/name;r=json.loads((d/'report.json').read_text());key=r['case'];source=s/'uart0-idle-dma-main-01'/key;prior=json.loads((source/'report.json').read_text());validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);v,kind=parse_boundary((d/'renode.log').read_text())
        check(name+'-native-evidence',r['passed'] and v==r['observed'] and kind==r['boundary_kind'])
        old=(d/'baseline-core.cs').read_bytes();check(name+'-only-reviewed-core',hashlib.sha256(old).hexdigest()==BASE_SHA and (source/'strict.cs').read_bytes().startswith(old) and (d/'strict.cs').read_bytes()==models(s)==core+(source/'strict.cs').read_bytes()[len(old):])
        check(name+'-original-input-runtime',digest(d/'main.bin')==r['original_main_sha256']==prior['original_main_sha256'] and all((d/f).read_bytes()==(source/f).read_bytes() for f in FILES-{'strict.cs','board.repl'}))
        check(name+'-prefix-and-fonts',r['prior_prefix_equal'] and not r['selected_observation']['dropped_events'] and r['font_diagnostic']['reads']==2)
        check(name+'-no-completion-claim',not r['boot_verified'] and not r['display_verified'] and not r['retention_hardware_verified'] and not r['hardware_accessed'])
        if r['default_control']:
            check(name+'-default-exact',v==prior['observed'] and r['selected_observation']==prior['selected_observation'] and (d/'board.repl').read_bytes()==(source/'board.repl').read_bytes())
        else:
            check(name+'-one-explicit-option',(d/'board.repl').read_text().replace('    uartHcpaGate: true\n','')==(source/'board.repl').read_text())
            u=next(x for x in v['uarts'] if x['module']==0)
            check(name+'-UART0-reopened-retained',u['phase']=='on' and u['requests']==u['responses']==2 and u['off_requests']==1 and u['power_downs']==u['power_cycles']==0 and u['control']==0x319 and u['interrupt_mask']==0x1fd0 and u['interrupt_mask_writes']==2)
            check(name+'-cache-strict-stop',kind=='unsupported-data-cache-by-address' and v['system_control']['address']==0xe000ef68 and v['system_control']['violations']==1 and v['pc']==(0x57f35c if key=='stock24' else 0x5a1e9e))
            check(name+'-no-RX-DMA-IRQ',not u['tx_bytes'] and not u['rx_dma_implemented'] and not u['irq_level'] and u['irq_exception_entries']==0)
    specimen=json.loads((s/'uart-hcpa-gate-main-01/stock24/report.json').read_text())['observed']
    bad=[('memory','memory_policy','violations',1),('count','system_control','violations',2),('address','system_control','address',0xe000ef6c),('width','system_control','width',8),('operation','system_control','operation','read'),('unaligned','system_control','value',0x2035cc61),('outside','system_control','value',0x80000000),('PC','system_control','pc',0x438000)]
    for name,section,key,value in bad:
        v=copy.deepcopy(specimen);v[section][key]=value
        try:parse_boundary('BLACKWALL_REPORT '+json.dumps(v))
        except ValueError:check('boundary-reject-'+name,True)
        else:raise ValueError('Unsafe boundary accepted: '+name)
    v=copy.deepcopy(specimen);v['machine_paused_before_host']=False
    try:parse_boundary('BLACKWALL_REPORT '+json.dumps(v))
    except ValueError:check('boundary-reject-host-timeout',True)
    else:raise ValueError('Host timeout accepted')
    report=dict(passed=True,count=len(checks),checks=checks,original_main_runs=4,unsupported_cache_operation_retained=True,boot_verified=False,display_verified=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))

if __name__=='__main__':main()
