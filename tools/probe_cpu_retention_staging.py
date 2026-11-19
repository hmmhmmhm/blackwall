"""Original reset -> qualified retention configuration, stopping before deep-sleep preparation."""
import argparse,json,hashlib,shutil
from pathlib import Path
from cpu_retention_staging_model import compose
from probe_original_system_reset import build as reset_build
from run_renode_m55_probe import execute
from native_replay import IMAGE


def build(s,out):
    if shutil.disk_usage(s).free<1024**3:raise ValueError('Native retention probe requires at least 1 GiB free space before preparing inputs')
    reset_build(s,out,'stock24')
    raw=(out/'main.bin').read_bytes()
    for pc,code in [(0x4956ac,'01b40021'),(0x4956ca,'9df8000051ea00219df8010051ea00119df8020001437e480160'),(0x44df5a,'029847f0a6fb0220')]:
        if raw[pc-0x438000:pc-0x438000+len(bytes.fromhex(code))]!=bytes.fromhex(code):raise ValueError('Unverified original retention ABI')
    p=out/'strict.cs';p.write_text(compose(p.read_text()))
    p=out/'board.repl';t=p.read_text();anchor='cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n';assert t.count(anchor)==1;t=t.replace(anchor,anchor+'    retentionStorePc: 0x4956e2\n    retentionReturnPc: 0x44df60\n');p.write_text(t)
    p=out/'run.py';t=p.read_text();a="    reset_hold=BlackwallUiActivationHold(m,cpu,p['getter'])";assert t.count(a)==1;t=t.replace(a,"    reset_hold=BlackwallResetEntryObserver(m,cpu,0x44df60)")
    t=t.replace("later['held']=bool(reset_hold.Held)","later['held']=False;later['retention_return_seen']=bool(reset_hold.Seen);later['cpd_value']=int(g.CpuNormalSleep.CpdValue);later['retention_stages']=int(g.CpuNormalSleep.RetentionStages)")
    p.write_text(t);p=out/'connection-inputs.json';inputs=json.loads(p.read_text())
    for n in inputs:inputs[n]=hashlib.sha256((out/n).read_bytes()).hexdigest()
    p.write_text(json.dumps(inputs,indent=2)+'\n')
    (out/'retention-profile.json').write_text(json.dumps(dict(scope='configuration staging only; stops before deep-sleep power-state update',store=0x4956e2,returned=0x44df60,fields=[0,2,2],value=0x22,deep_sleep_executed=False),indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--prepare-only',action='store_true');a=p.parse_args();build(a.simulator,a.output)
    if a.prepare_only:return
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=240)
    r=json.loads((a.output/'exports/system-reset-later.json').read_text())
    if not r['retention_return_seen'] or r['pc']!=0x44df60 or r['cpd_value']!=0x22 or r['retention_stages']!=1 or any(x['accesses'] for x in r['guards']) or r['cfsr'] or r['hfsr']:raise ValueError('Retention staging did not return cleanly')
    print(json.dumps(dict(staged=True,pc=hex(r['pc']),value=r['cpd_value'],deep_sleep_executed=False)))
if __name__=='__main__':main()
