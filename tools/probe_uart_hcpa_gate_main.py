"""Original reset replay with explicit shared HCPA local-gate lifecycle."""
import argparse,hashlib,json,shutil,difflib
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models

BASE_SHA='55b1238bac9293203eafcd42d71c773db83448f15344ae94d66ecbe1f76a215c'
CORE_SHA='ba837eb3c74101a432e9ebd9f3042a989ffe8ff49a609a1b56cb087bc5380160'

def parse_boundary(log):
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_REPORT ')]
    if len(rows)!=1:raise ValueError('Missing native report')
    v=rows[0];control=v['system_control']
    if not control['violations']:return parse_log(log),'strict-MMIO'
    if (control['violations']!=1 or v['memory_policy']['violations'] or any(g['accesses'] for g in v['guards'])
        or not v['machine_paused_before_host'] or control['pc']!=v['pc'] or control['address']!=0xe000ef68
        or control['operation']!='write' or control['width']!=4 or not 0x20000000<=control['value']<0x20380000
        or control['value']&31):raise ValueError('Unexpected system-control boundary')
    for line in log.splitlines():
        lower=line.lower()
        if (('[warning]' in lower and 'translation cache size' not in lower)
            or ('[error]' in lower and 'this machine has aborted' not in lower)
            or any(w in lower for w in ('unhandled','non existing','non-existing','could not execute','blackwall_runtime_error'))):raise ValueError('Unexpected engine message: '+line)
    return v,'unsupported-data-cache-by-address'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline-core',type=Path,required=True);p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True);p.add_argument('--default-control',action='store_true');p.add_argument('--audit-existing',action='store_true',help='Audit terminal inputs/log without rerunning or changing inputs');a=p.parse_args();s,o=a.simulator,a.output
    src=s/'uart0-idle-dma-main-01'/a.case;prior=json.loads((src/'report.json').read_text());base=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,base)
    if parse_log((src/'renode.log').read_text())!=prior['observed']:raise ValueError('Prior native log differs')
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[a.case];_,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
    if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
    old=a.baseline_core.read_bytes();frozen=(src/'strict.cs').read_bytes()
    if hashlib.sha256(old).hexdigest()!=BASE_SHA or not frozen.startswith(old):raise ValueError('Pinned baseline core differs')
    tail=frozen[len(old):]
    if a.audit_existing:
        new=(o/'strict.cs').read_bytes()
        if not tail or not new.endswith(tail):raise ValueError('Saved model tail differs')
        core=new[:-len(tail)]
    else:
        core=Path(__file__).with_name('renode-strict-mmio.cs').read_bytes();new=models(s)
    if hashlib.sha256(core).hexdigest()!=CORE_SHA or new!=core+tail:raise ValueError('Model differs beyond pinned reviewed delta')
    board=(src/'board.repl').read_text()
    if not a.default_control:
        needle='    uartHcpaStatus: true\n'
        if board.count(needle)!=1:raise ValueError('Unexpected HCPA profile')
        board=board.replace(needle,needle+'    uartHcpaGate: true\n')
    if a.audit_existing:
        if (o/'strict.cs').read_bytes()!=new or (o/'board.repl').read_text()!=board or any((o/f).read_bytes()!=(src/f).read_bytes() for f in FILES-{'strict.cs','board.repl'}):raise ValueError('Saved input differs')
        validate_assets(o,json.loads((o/'derived-inputs.json').read_text())['derived'])
    else:
        o.mkdir(mode=0o700,parents=True)
        for f in FILES:shutil.copyfile(src/f,o/f)
        (o/'baseline-core.cs').write_bytes(old);(o/'model-delta.patch').write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),core.decode().splitlines(True),fromfile='before.cs',tofile='after.cs')));(o/'strict.cs').write_bytes(new);(o/'board.repl').write_text(board)
    derived={f:digest(o/f) for f in FILES}
    if not a.audit_existing:(o/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base=base,HCPA_local_gate=not a.default_control,core_sha256=CORE_SHA,baseline_core_sha256=BASE_SHA),indent=2)+'\n')
    log=(o/'renode.log').read_text() if a.audit_existing else execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    validate_assets(o,derived);v,kind=parse_boundary(log)
    def marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing '+name)
        return rows[0]
    obs=marker('BLACKWALL_OBSERVATION');font=marker('BLACKWALL_MISSING_FONT');events=prior['selected_observation']['events'];prefix=obs['events'][:len(events)]==events
    result=dict(case=a.case,observed=v,boundary_kind=kind,selected_observation=obs,font_diagnostic=font,original_main_sha256=digest(o/'main.bin'),prior_prefix_equal=prefix,default_control=a.default_control,hardware_accessed=False,retention_hardware_verified=False,boot_verified=False,display_verified=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if obs['dropped_events'] or obs['sequence']!=len(obs['events']):raise ValueError('Observation loss')
    if a.default_control and (v!=prior['observed'] or obs!=prior['selected_observation']):raise ValueError('Default CPU/instructions/events changed')
    result['passed']=True;(o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,case=a.case,pc=hex(v['pc']),prefix_equal=prefix,font_reads=font['reads'],guards=[g for g in v['guards'] if g['accesses']])),flush=True)

if __name__=='__main__':main()
