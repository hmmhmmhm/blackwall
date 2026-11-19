"""Pure C# bounds/cache/control checks using exactly the integrated model source."""
import argparse,json,hashlib
from pathlib import Path
from bounded_main_rom_model import method
from native_replay import IMAGE
from run_renode_m55_probe import execute
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous { public static class BlackwallRomDomainTest {
public static int Run(){int n=0;System.Action<bool> check=(b)=>{if(!b)throw new System.Exception("ROM domain "+n);n++;};
System.Func<ulong,ulong,ulong,ulong,ulong,bool,bool> valid=(k,o,w,c,s,irq)=>BlackwallMramRangeContract.ValidProgramRequest(k,o,w,c,s,irq,0x438010,16);
check(valid(0x12344321,1,0xe004,4,0x20000000,true));check(valid(0x12344321,1,0xe004,4,0x2007fff0,true));
check(!valid(0,1,0xe004,4,0x20000000,true));check(!valid(0x12344321,0,0xe004,4,0x20000000,true));check(!valid(0x12344321,1,0xe004,4,0x20000000,false));
foreach(var w in new ulong[]{0,0xe000,0xe003,0xe005,0x100000,ulong.MaxValue})check(!valid(0x12344321,1,w,4,0x20000000,true));
foreach(var c in new ulong[]{0,1,3,8,65,ulong.MaxValue})check(!valid(0x12344321,1,0xe004,c,0x20000000,true));
foreach(var s in new ulong[]{0x1fffffff,0x2007fff1,0x20080000,ulong.MaxValue})check(!valid(0x12344321,1,0xe004,4,s,true));
var d=new BlackwallCoherentDataCache();check(!d.TryWrite(0xf5c,4,0x438010));check(!d.TryWrite(0xf5c,4,0x20000000));
bool approved=false;d.ApprovedMramInvalidation=line=>approved && line==0x438000;check(!d.TryWrite(0xf5c,4,0x438010));approved=true;
check(d.TryWrite(0xf5c,4,0x438010)&&d.AddressInvalidations==1&&d.LastAddressLine==0x438000);
foreach(var off in new long[]{0xf64,0xf68,0xf70})check(!d.TryWrite(off,4,0x438010));check(!d.TryWrite(0xf5c,4,0x438020));check(!d.TryWrite(0xf5c,2,0x438010));check(!d.TryWrite(0xf5c,4,0x100438010));check(d.AddressInvalidations==1);
var enabled=new BlackwallCoherentDataCache(true);foreach(var off in new long[]{0xf5c,0xf64,0xf68,0xf70})check(enabled.TryWrite(off,4,0x20000010));check(!enabled.TryWrite(0xf5c,4,0x20380000));check(!enabled.TryWrite(0xf5c,4,0x438010));
var control=new BlackwallRecoveryMramControl();control.WriteDoubleWord(8,0xc3);control.WriteDoubleWord(0x24,0);control.WriteDoubleWord(8,0);check(control.Writes==3&&control.ReadDoubleWord(8)==0);
bool bad=false;try{control.WriteDoubleWord(8,1);}catch(Antmicro.Renode.Peripherals.CPU.CpuAbortException){bad=true;}check(bad&&control.Writes==3);control.Reset();check(control.Writes==0&&control.ReadDoubleWord(0x24)==0);
return n;}}}'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve();model=a.model.read_text()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 code='namespace Antmicro.Renode.Peripherals.Miscellaneous { using System; using Antmicro.Renode.Core; using Antmicro.Renode.Peripherals.Bus; using Antmicro.Renode.Peripherals.CPU; '+method(model,'    public sealed class BlackwallCoherentDataCache')+method(model,'    public sealed class BlackwallRecoveryMramControl')+method(model,'internal static class BlackwallMramRangeContract')+' }'+TEST
 out.mkdir(mode=0o700);(out/'model.cs').write_text(code);(out/'test.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRomDomainTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRomDomainTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_ROM_DOMAIN '+str(BlackwallRomDomainTest.Run()))\n")
 (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=90);rows=[s for s in log.splitlines() if s.startswith('BLACKWALL_ROM_DOMAIN ')];r=dict(passed=len(rows)==1,markers=rows,model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),scope='C# domain contract, no firmware or physical ROM execution');(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
