"""Check the opt-in virtual metadata state in pinned Renode; no firmware or devices."""
import argparse,json
from pathlib import Path
from run_renode_m55_probe import execute
from native_replay import IMAGE
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
public static class BlackwallPendingStateTest {
 public static int Run() {
  int n=0;System.Action<bool> check=(v)=>{if(!v)throw new System.Exception("pending-state "+n);n++;};
  var initial=new byte[16];for(int i=0;i<16;i++)initial[i]=i<4?(byte)0x55:(byte)0xa5;
  var ff=new byte[16];for(int i=0;i<16;i++)ff[i]=255;
  var s=new BlackwallPendingMetadata(initial);initial[0]=0;check(s.Marker==0x55555555);
  var copy=s.Bytes;copy[0]=0;check(s.Marker==0x55555555);
  var marker=new BlackwallOtaMarkerRead("pending",0x44ac6c,0x483708,0x42e582);uint value;
  check(marker.TrySample(0x42e582,0x7fe000,0,0x7fe000,out value)&&value==0x55555555);
  marker.BindPersistent(s);s.Program(ff,0);check(s.Marker==0x55555555);
  s.Program(ff,1);check(s.Marker==0xffffffff&&s.Bytes[4]==0xa5);
  marker.Reset();check(marker.TrySample(0x42e582,0x7fe000,0,0x7fe000,out value)&&value==0xffffffff);
  s.Program(ff,4);check(System.Array.TrueForAll(s.Bytes,v=>v==255));
  foreach(var words in new[]{-1,5}){bool bad=false;try{s.Program(ff,words);}catch(System.ArgumentException){bad=true;}check(bad);}
  bool rejected=false;try{s.Program(new byte[15],4);}catch(System.ArgumentException){rejected=true;}check(rejected);
  rejected=false;try{new BlackwallPendingMetadata(new byte[15]);}catch(System.ArgumentException){rejected=true;}check(rejected);
  rejected=false;try{marker.BindPersistent(s);}catch(System.InvalidOperationException){rejected=true;}check(rejected);
  check(!marker.TrySample(0x42e584,0x7fe000,0,0x7fe000,out value));
  return n;
 }
}}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 out.mkdir(parents=True,mode=0o700);source=(Path(__file__).parent/'renode-ota-marker-read.cs').read_text();(out/'model.cs').write_text(source+TEST)
 (out/'run.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPendingStateTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPendingStateTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_PENDING_STATE '+str(BlackwallPendingStateTest.Run()))\n")
 (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/run.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=45)
 passed='BLACKWALL_PENDING_STATE 13' in log;(out/'report.json').write_text(json.dumps(dict(passed=passed,hardware_accessed=False))+'\n');print('passed',passed)
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()
