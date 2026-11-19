"""Verify explicit synchronous off responses and default lazy-response rejection."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallRecoveryPowerCycleTest {
  public static int Run() {
   int count=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("power cycle "+count);count++;};
   var old=new BlackwallPeripheralPower(256,1,0);
   check(old.TryWrite(256,true)&&old.ReadStatus()==256);check(old.TryWrite(0,true,true)&&old.Phase=="off-requested");check(!old.TryWrite(256,true));check(old.ReadStatus()==0&&old.TryWrite(256,true));
   var p=new BlackwallPeripheralPower(256,1,0,synchronousOffResponse:true);int events=0;p.PoweredOff+=()=>events++;
   for(var n=0;n<3;n++) {
    check(p.TryWrite(256,true)&&p.ReadStatus()==256);
    check(!p.TryWrite(0,true,false)&&p.Phase=="on");
    check(p.TryWrite(0,true,true)&&p.Phase=="powered-off"&&p.StatusWord==0&&p.RequestWord==0);
    check(events==n+1&&p.PowerCycles==n+1);check(p.ReadStatus()==0&&events==n+1);
   }
   p.Reset();check(p.Phase=="off"&&p.PowerCycles==0&&p.Responses==0);
   foreach(var off in new[]{-1,1}) {bool bad=false;try{new BlackwallPeripheralPower(256,1,off,synchronousOffResponse:true);}catch(System.ArgumentException){bad=true;}check(bad);}
   var stuck=new BlackwallPeripheralPower(256,1,1);check(stuck.TryWrite(256,true)&&stuck.ReadStatus()==256&&stuck.TryWrite(0,true,true));check(stuck.ReadStatus()==256&&stuck.Phase=="stuck-on"&&!stuck.TryWrite(256,true));
   return count;
  }
 }
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 out.mkdir(mode=0o700);(out/'model.cs').write_text((ROOT/'tools/renode-strict-mmio.cs').read_text()+TEST);(out/'test.py').write_text("import clr\nfrom System import Console\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRecoveryPowerCycleTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRecoveryPowerCycleTest\nConsole.WriteLine('BLACKWALL_RECOVERY_POWER '+str(BlackwallRecoveryPowerCycleTest.Run()))\n")
 (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120);rows=[s for s in log.splitlines() if s.startswith('BLACKWALL_RECOVERY_POWER ')];r=dict(passed=len(rows)==1,marker=rows);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
