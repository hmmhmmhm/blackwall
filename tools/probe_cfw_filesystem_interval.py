"""Observe original CFW post-FS call stacks with no firmware, peripheral or input changes."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--independent',action='store_true');p.add_argument('--watch-logger',action='store_true',help='Experimental extra PCs may perturb scheduling; changed canonical state is rejected');a=p.parse_args();s,o=a.simulator,a.output
    key='cfw-independent' if a.independent else 'cfw';src=s/'uart0-hcpa-main-02'/key;prior=json.loads((src/'report.json').read_text());validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
    if parse_log((src/'renode.log').read_text())!=prior['observed'] or (src/'strict.cs').read_bytes()!=models(s):raise ValueError('Current source/runtime differs')
    pts={p['label']:p['address'] for p in prior['selected_observation']['points']}
    sites=[pts[n] for n in ['LittleFS-app-init-return','GPIO-role-sample-return','LittleFS-read-entry']]
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    (o/'strict.cs').write_bytes((src/'strict.cs').read_bytes()+b'\n'+Path(__file__).with_name('renode-phase-stack-observer.cs').read_bytes())
    runtime=(src/'run.py').read_text();extra="    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPhaseStackObserver').Assembly)\n    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPhaseStackObserver\n    phase=BlackwallPhaseStackObserver(m,m['sysbus.cpu'],%d,%d,%d,4,0x200778a8,0x20077680,8)\n" % tuple(sites)
    if a.watch_logger:extra+="    phase.AddWatch('logger-wait-return',0x44b542)\n    phase.AddWatch('compress-entry',0x43d534)\n    phase.AddWatch('compress-work',0x43d570)\n    phase.AddWatch('compress-notify',0x44b634)\n"
    if runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unexpected start boundary')
    runtime=runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n')
    marker="    def phase_sample(x):\n        return None if x is None else dict(pc=int(x.PC),sp=int(x.SP),lr=int(x.LR),active_vector=int(x.ActiveVector),direct=[int(v) for v in x.Direct],indirect_pointer=int(x.IndirectPointer),indirect_word=int(x.IndirectWord),indirect_valid=bool(x.IndirectValid),registers=[int(v) for v in x.Registers],stack=[int(v) for v in x.Stack])\n    Console.WriteLine('BLACKWALL_FS_PHASE '+json.dumps(dict(open_hits=int(phase.OpenHits),close_hits=int(phase.CloseHits),sample_hits=int(phase.SampleHits),rejected=int(phase.RejectedSnapshots),active=bool(phase.Active),budget=int(phase.Budget),open=phase_sample(phase.Open),close=phase_sample(phase.Close),samples=[phase_sample(x) for x in phase.Samples],watches=[dict(label=w.Label,pc=int(w.PC),total_hits=int(w.TotalHits),hits=int(w.Hits),first_any=phase_sample(w.FirstAny),samples=[phase_sample(x) for x in w.Samples]) for w in phase.Watches])))\n"
    needle="    Console.WriteLine('BLACKWALL_REPORT "
    if runtime.count(needle)!=1:raise ValueError('Unexpected report boundary')
    marker+="    if not m.IsPaused:raise ValueError('Stopped log flag capture requires paused CPU')\n    Console.WriteLine('BLACKWALL_STOPPED_LOG_FLAGS '+json.dumps(dict(paused=bool(m.IsPaused),base=0x20078424,words=[int(m.SystemBus.ReadDoubleWord(0x20078424+4*i)) for i in range(2)])))\n"
    runtime=runtime.replace(needle,marker+needle);compile(runtime,'run.py','exec');(o/'run.py').write_text(runtime)
    derived={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base={f:digest(src/f) for f in FILES},observer_sites=sites),indent=2)+'\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None);validate_assets(o,derived);v=parse_log(log)
    def read_marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing marker '+name)
        return rows[0]
    phase=read_marker('BLACKWALL_FS_PHASE');obs=read_marker('BLACKWALL_OBSERVATION')
    result=dict(case=key,extra_watchpoints=a.watch_logger,observed=v,selected_observation=obs,phase=phase,stopped_log_flags=read_marker('BLACKWALL_STOPPED_LOG_FLAGS'),original_main_sha256=digest(o/'main.bin'),guest_writes_added=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if v!=prior['observed'] or obs!=prior['selected_observation']:raise ValueError('Observation changed native CPU/instructions/events')
    if phase['open_hits']!=1 or phase['close_hits']!=1 or phase['active'] or phase['rejected']:raise ValueError('Phase boundaries invalid')
    if phase['sample_hits']!=(30 if a.independent else 0) or len(phase['samples'])!=(4 if a.independent else 0):raise ValueError('Unexpected post-FS callback count')
    result['passed']=True;(o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,case=key,sample_hits=phase['sample_hits'],stack_samples=len(phase['samples']))),flush=True)


if __name__=='__main__':main()
