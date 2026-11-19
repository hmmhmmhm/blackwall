"""Original reset replay with opt-in UART0 idle DMA masks; no injected receive data."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

def previous_core(core):
    edits=[(',bool idleDmaInterrupts=false)',')'),
           ('            if(idleDmaInterrupts && (module!=0 || !interrupts)) throw new System.ArgumentException("idle DMA masks require interrupt-enabled UART0");\n            IdleDmaInterrupts=idleDmaInterrupts;\n',''),
           ('(value&~(IdleDmaInterrupts ? 0x1fffu : 0x7ffu))','(value&~0x7ffu)'),
           ('                if((value&0x1800u)!=0 && engine.ReadDoubleWord(0x48)!=0) return false;\n',''),
           ('        public bool IdleDmaInterrupts { get; }\n','')]
    for before,after in edits:
        if core.count(before)!=1:raise ValueError('Unexpected idle mask model edit')
        core=core.replace(before,after)
    return core.encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True);p.add_argument('--default-control',action='store_true');a=p.parse_args();s,o=a.simulator,a.output
    src=s/'uart0-hcpa-main-02'/a.case;prior=json.loads((src/'report.json').read_text());source=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,source)
    if parse_log((src/'renode.log').read_text())!=prior['observed']:raise ValueError('Prior log differs')
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[a.case];_,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
    if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
    core=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes();old=previous_core(core.decode());frozen=(src/'strict.cs').read_bytes();new=models(s)
    if not frozen.startswith(old) or new!=core+frozen[len(old):]:raise ValueError('Model differs beyond reviewed UART edit')
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    (o/'strict.cs').write_bytes(new)
    if not a.default_control:
        board=(src/'board.repl').read_text();needle='uart0_adapter: Miscellaneous.BlackwallUartAdapter\n    module: 0\n    interrupts: true\n'
        if board.count(needle)!=1:raise ValueError('Unexpected UART0 profile')
        (o/'board.repl').write_text(board.replace(needle,needle+'    idleDmaInterrupts: true\n'))
    derived={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base=source,idle_DMA_interrupt_masks=not a.default_control),indent=2)+'\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    validate_assets(o,derived);observed=parse_log(log)
    def marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing '+name)
        return rows[0]
    obs=marker('BLACKWALL_OBSERVATION');font=marker('BLACKWALL_MISSING_FONT');events=prior['selected_observation']['events']
    result=dict(case=a.case,observed=observed,selected_observation=obs,font_diagnostic=font,original_main_sha256=digest(o/'main.bin'),prior_prefix_equal=obs['events'][:len(events)]==events,default_control=a.default_control,hardware_accessed=False,DMA_implemented=False,boot_verified=False,display_verified=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if obs['dropped_events'] or obs['sequence']!=len(obs['events']) or font['reads']!=2:raise ValueError('Observation loss or font contract changed')
    if a.default_control and (observed!=prior['observed'] or obs!=prior['selected_observation']):raise ValueError('Default changed CPU/instructions/events')
    if not result['prior_prefix_equal']:raise ValueError('Prior trace prefix changed')
    result['passed']=True;(o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(case=a.case,passed=True,pc=hex(observed['pc']),prefix_equal=True,guards=[g for g in observed['guards'] if g['accesses']])),flush=True)

if __name__=='__main__':main()
