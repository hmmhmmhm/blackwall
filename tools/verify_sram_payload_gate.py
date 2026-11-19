"""Native unit checks for a byte-exact SRAM code authorization domain."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallPayloadGateTests {
  public static int Run() {
   int count=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("payload gate "+count);count++;};
   var expected=new byte[]{0x70,0xb5,0x00,0x20,0x70,0xbd};var actual=(byte[])expected.Clone();ulong start=0x2001c7a0;
   System.Func<ulong,int,byte[]> read=(a,n)=>{if(a<start||a+(ulong)n>start+(ulong)actual.Length)return null;var b=new byte[n];System.Array.Copy(actual,(int)(a-start),b,0,n);return b;};
   var gate=new BlackwallSramPayloadGate(expected,0,read);expected[0]^=1;
   ushort word;check(!gate.TryReadWord(start,out word));
   check(!gate.TryEnter(start+2)&&gate.BaseAddress==0);
   actual[3]^=1;check(!gate.TryEnter(start)&&gate.BaseAddress==0);actual[3]^=1;
   check(gate.TryEnter(start)&&gate.BaseAddress==start&&gate.Length==6);
   check(gate.TryReadWord(start,out word)&&word==0xb570);
   check(gate.TryReadWord(start+4,out word)&&word==0xbd70);
   check(!gate.TryReadWord(start-2,out word));check(!gate.TryReadWord(start+6,out word));check(!gate.TryReadWord(start+1,out word));check(!gate.TryReadWord(0xfffffffffffffffe,out word));
   actual[1]^=1;check(!gate.TryReadWord(start,out word));actual[1]^=1;
   check(!gate.TryEnter(start+32)&&gate.BaseAddress==start);
   gate.Reset();check(gate.BaseAddress==0&&!gate.TryReadWord(start,out word));
   foreach(var size in new[]{0,1,3,514}) {bool bad=false;try {new BlackwallSramPayloadGate(new byte[size],0,read);}catch(System.ArgumentException){bad=true;}check(bad);}
   foreach(var entry in new uint[]{1,6,8}) {bool bad=false;try {new BlackwallSramPayloadGate(actual,entry,read);}catch(System.ArgumentException){bad=true;}check(bad);}
   foreach(var pc in new ulong[]{0,0x410000,0x1ffffffe,0x2007fffe,0x20080000,0x2001c7a1})check(!gate.TryEnter(pc)&&gate.BaseAddress==0);
   return count;
  }
 }
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 out.mkdir(mode=0o700);source=ROOT/'tools/renode-sram-payload-gate.cs';(out/'model.cs').write_text((source.read_text() if source.exists() else '')+TEST);(out/'test.py').write_text("import clr\nfrom System import Console\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallPayloadGateTests').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallPayloadGateTests\nConsole.WriteLine('BLACKWALL_PAYLOAD_GATE '+str(BlackwallPayloadGateTests.Run()))\n")
 (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120);rows=[s for s in log.splitlines() if s.startswith('BLACKWALL_PAYLOAD_GATE ')];r=dict(passed=len(rows)==1,marker=rows);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
