"""Synthetic M55 self-modifying executable-IO control, not stock firmware/cache physics."""
import argparse
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''
namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallCodeCoherencyTest {
  public static void Attach(Antmicro.Renode.Core.IMachine m,Antmicro.Renode.Peripherals.CPU.CortexM cpu,int policy) {
   var memory=(BlackwallProtectedMram)m["sysbus.mram"];bool patched=false;
   cpu.AddHook(0x20000104,(c,a)=>{if(!patched){patched=true;memory.ProgramDoubleWord(0x10000,0x47702034);if(policy==1)cpu.InvalidateTranslationBlocks();if(policy==2)cpu.OrderTranslationBlocksInvalidation(new System.IntPtr(0x410000),new System.IntPtr(0x410004));}});
   cpu.AddHook(0x2000010a,(c,a)=>{cpu.IsHalted=true;});
   cpu.SetRegister(13,0x2007f000u);cpu.PC=0x20000101u;
  }
 }
}
'''

def run(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
    output.mkdir(parents=True,mode=0o700);rows=[]
    for policy in (0,1,2):
        p=output/('default','drain-only','ordered-range')[policy];p.mkdir(mode=0o700);(p/'exports').mkdir(mode=0o700)
        (p/'model.cs').write_text((ROOT/'tools/renode-recovery-writer-fixture.cs').read_text()+TEST)
        (p/'guest.bin').write_bytes(bytes.fromhex('034b9847044698470546fee700bf00bf01004100'))
        (p/'callee.bin').write_bytes(bytes.fromhex('12207047'))
        (p/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\nmram: Miscellaneous.BlackwallProtectedMram @ sysbus 0x400000\n    size: 0x400000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\n')
        script='''import json,time,clr
from System.IO import File
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallCodeCoherencyTest').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCodeCoherencyTest
m=monitor.Machine;cpu=m['sysbus.cpu'];b=m.SystemBus
m['sysbus.mram'].Arm();BlackwallCodeCoherencyTest.Attach(m,cpu,INVALIDATE)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not cpu.IsHalted and not m.IsPaused and time.time()<deadline:time.sleep(0.001)
m.Pause()
File.WriteAllText('/work-output/result.json',json.dumps(dict(first=int(cpu.GetRegister(4).RawValue),second=int(cpu.GetRegister(5).RawValue),pc=int(cpu.PC.RawValue),callee=int(b.ReadDoubleWord(0x410000)),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))))
'''.replace('INVALIDATE',str(policy))
        (p/'run.py').write_text(script);(p/'probe.resc').write_text('include @/work/model.cs\nmach create "executable-io-cache"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/guest.bin 0x20000100\nsysbus LoadBinary @/work/callee.bin 0x410000\ninclude @/work/run.py\nquit\n')
        execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={p},target=/work,readonly','--mount',f'type=bind,source={p/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],p,'native',timeout=45,stream=True)
        r=json.loads((p/'exports/result.json').read_text());r['policy']=policy;rows.append(r);print(json.dumps(r),flush=True)
    (output/'report.json').write_text(json.dumps(dict(cases=rows,scope='Synthetic SRAM caller and executable MRAM callee; host-modeled ROM code change; not physical I-cache behavior',hardware_accessed=False),indent=2)+'\n')
    assert rows[2]['first']==0x12 and rows[2]['second']==0x34 and rows[2]['callee']==0x47702034 and rows[2]['cfsr']==rows[2]['hfsr']==0

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
if __name__=='__main__':main()
