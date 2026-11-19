"""Bounded original ARM delay-path observations at an unchanged fixed virtual boundary."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from reset_restart_profiles import RENODE_IMAGE
from run_renode_m55_probe import execute
from verify_observer_suspension import validate

SOURCE='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using System.Collections.Generic;using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallGafDelayPathObserver {
  public BlackwallGafDelayPathObserver(IMachine machine,CortexM cpu) {
   cpu.AddHook(0x55597e,(c,a)=>{Polls++;record=Polls<=16;if(record)Save(machine,cpu,0,a);});
   foreach(var pair in new ulong[][]{new ulong[]{1,0x4b2f9e},new ulong[]{2,0x4b2fa4},new ulong[]{3,0x495ea2},new ulong[]{4,0x495ed2}}) {
    var kind=pair[0];var pc=pair[1];cpu.AddHook(pc,(c,a)=>{if(record) {
      Save(machine,cpu,kind,a);
      if(kind==4 && ItcmBytes==null)ItcmBytes=machine.SystemBus.ReadBytes(0x40,32,true);
    }});
   }
  }
  private void Save(IMachine machine,CortexM cpu,ulong kind,ulong pc) {
   if(Rows.Count>=256){Overflow=true;return;}
   Rows.Add(new ulong[]{kind,Polls,pc,machine.ElapsedVirtualTime.TimeElapsed.Ticks,cpu.ExecutedInstructions,cpu.GetRegister(0).RawValue,cpu.GetRegister(1).RawValue,cpu.GetRegister(13).RawValue,cpu.GetRegister(14).RawValue,cpu.GetRegister(25).RawValue});
  }
  public List<ulong[]> Rows {get;}=new List<ulong[]>();public byte[] ItcmBytes {get;private set;}
  public ulong Polls {get;private set;}public bool Overflow {get;private set;}private bool record;
 }
}
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(s,o):
 if o.exists() or not o.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output and 1 GiB required')
 ref=s/'main-read-routing-pilot-01/01-baseline';validate(ref);inputs=json.loads((ref/'connection-inputs.json').read_text());o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir()
 for n,h in inputs.items():
  if sha(ref/n)!=h:raise ValueError('Changed reference '+n)
  if subprocess.run(['cp','-c',str(ref/n),str(o/n)],capture_output=True).returncode:shutil.copyfile(ref/n,o/n)
 raw=(o/'main.bin').read_bytes()
 for pc,hexbytes in [(0x4b2f9e,'80b5e2f772ff01bd'),(0x495ea2,'022901d00f21'),(0x55599e,'07d10521')]:
  if raw[pc-0x438000:pc-0x438000+len(bytes.fromhex(hexbytes))]!=bytes.fromhex(hexbytes):raise ValueError('Changed original path '+hex(pc))
 with (o/'activation.cs').open('a') as f:f.write('\n'+SOURCE)
 code=(o/'run.py').read_text();anchor='    phase_wall=time.time()\n'
 if code.count(anchor)!=1:raise ValueError('Unknown fixed observation boundary')
 code=code.replace(anchor,"    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallGafDelayPathObserver').Assembly)\n    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallGafDelayPathObserver\n    delay_path=BlackwallGafDelayPathObserver(m,cpu)\n"+anchor)
 anchor="    File.WriteAllBytes('/work-output/frozen-core-sram.bin',m.SystemBus.ReadBytes(0x20000000,0x380000,True))"
 if code.count(anchor)!=1:raise ValueError('Unknown snapshot boundary')
 code=code.replace(anchor,"    File.WriteAllText('/work-output/delay-path.json',json.dumps(dict(rows=[[int(v) for v in row] for row in delay_path.Rows],polls=int(delay_path.Polls),overflow=bool(delay_path.Overflow),itcm_bytes=[] if delay_path.ItcmBytes is None else [int(v) for v in delay_path.ItcmBytes],sync_time_called=False,host_pc_register_seed=False,hardware_accessed=False)))\n"+anchor)
 compile(code,'generated-run.py','exec');(o/'run.py').write_text(code)
 meta=dict(reference=str(ref.relative_to(s)),reference_capture_sha256=sha(ref/'capture-files.json'),observation_source_sha256=hashlib.sha256(SOURCE.encode()).hexdigest(),fixed_virtual_ms=500,performance_in_mips=10,original_main_sha256=sha(o/'main.bin'),original_code_unchanged=True,physical_timing_verified=False)
 (o/'delay-clock-profile.json').write_text(json.dumps(meta,indent=2)+'\n');inputs['delay-clock-profile.json']=''
 for n in inputs:inputs[n]=sha(o/n)
 (o/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');return meta
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.simulator,a.output)
 execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180,stream=True)
 r=json.loads((a.output/'exports/delay-path.json').read_text());print(json.dumps(dict(rows=len(r['rows']),polls=r['polls'],overflow=r['overflow'])))
