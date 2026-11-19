"""Audit the bounded UART0 idle-mask extension and original-main evidence."""
import argparse,json
from pathlib import Path
from native_replay import FILES,digest,parse_log,validate_assets
from probe_uart0_idle_dma_main import previous_core
from verify_mspi1_pio_reset import models

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);checks=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    contract=json.loads((s/'uart0-interrupt-mask-contract-01/report.json').read_text());check('source-contract-53',contract['passed'] and contract['count']==53 and not contract['IRQ_enable_is_DMA_start'])
    red=s/'uart0-idle-dma-mask-red-01';check('red-native-mask-rejection','source-reset-DMA-idle-mask-accepted' in (red/'renode.log').read_text() and not (red/'report.json').exists())
    unit=json.loads((s/'uart0-idle-dma-mask-unit-02/report.json').read_text());check('unit-33',unit['passed'] and unit['count']==33 and not unit['DMA_implemented'] and not unit['hardware_accessed'])
    legacy=json.loads((s/'uart0-idle-dma-uart-regression-01/report.json').read_text());check('existing-UART-behavior',legacy['passed'] and legacy['assertion_count']>=100)
    core=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes();old=previous_core(core.decode());current=models(s)
    check('red-model-old-core',(red/'strict.cs').read_bytes().startswith(old))
    check('units-use-current-model',all((s/name/'strict.cs').read_bytes()==current for name in ['uart0-idle-dma-mask-unit-02','uart0-idle-dma-uart-regression-01']))
    for name in ['stock24','stock23','cfw','stock24-default']:
        d=s/'uart0-idle-dma-main-01'/name;r=json.loads((d/'report.json').read_text());key=r['case'];source=s/'uart0-hcpa-main-02'/key;prior=json.loads((source/'report.json').read_text())
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived']);check(name+'-native-log',r['passed'] and parse_log((d/'renode.log').read_text())==r['observed'])
        check(name+'-original-main',digest(d/'main.bin')==prior['original_main_sha256']==r['original_main_sha256'])
        check(name+'-model-only-reviewed-edit',(source/'strict.cs').read_bytes().startswith(old) and (d/'strict.cs').read_bytes()==current==core+(source/'strict.cs').read_bytes()[len(old):])
        check(name+'-no-runtime-hook-edit',all((d/f).read_bytes()==(source/f).read_bytes() for f in FILES-{'board.repl','strict.cs'}))
        check(name+'-prior-trace-prefix',r['prior_prefix_equal'] and not r['selected_observation']['dropped_events'])
        check(name+'-no-completion-claim',not r['boot_verified'] and not r['display_verified'] and not r['hardware_accessed'] and not r['DMA_implemented'])
        check(name+'-missing-font-diagnostic',r['font_diagnostic']['reads']==2)
        u=next(x for x in r['observed']['uarts'] if x['module']==0)
        if name.endswith('default'):
            check(name+'-exact-CPU-and-events',r['observed']==prior['observed'] and r['selected_observation']==prior['selected_observation'])
            check(name+'-board-identical',(d/'board.repl').read_bytes()==(source/'board.repl').read_bytes())
        else:
            guards=[g for g in r['observed']['guards'] if g['accesses']]
            check(name+'-power-reenable-guard',len(guards)==1 and guards[0]['address']==0x40021004 and guards[0]['value']==0x600 and guards[0]['operation']=='write' and guards[0]['width']==4 and r['observed']['pc']==(0x494d78 if key=='stock24' else 0x488e90))
            check(name+'-mask-and-shutdown',u['interrupt_mask']==0x1fd0 and u['interrupt_mask_writes']==1 and u['control']==0 and u['phase']=='off-requested' and u['request_word']==0 and u['status_word']==0x200 and u['off_requests']==1)
            check(name+'-no-RX-DMA-IRQ',not u['tx_bytes'] and not u['rx_dma_implemented'] and not u['irq_level'] and u['irq_exception_entries']==0)
            check(name+'-board-only-opt-in',(d/'board.repl').read_text().replace('    idleDmaInterrupts: true\n','')==(source/'board.repl').read_text())
    report=dict(passed=True,count=len(checks),checks=checks,original_main_runs=4,hardware_accessed=False,boot_verified=False,display_verified=False,DMA_implemented=False)
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))

if __name__=='__main__':main()
