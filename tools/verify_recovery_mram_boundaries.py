"""Check the isolated virtual writer's bounded policy; no silicon ROM permission claim."""
import argparse
import hashlib
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallMramBoundaryTest {
  static bool V(ulong key=0x12344321,ulong op=1,ulong offset=0xe004,ulong words=4,ulong source=0x20001000,bool masked=true,uint start=0x438010,uint length=512,bool full=false,bool boot=false) {
   return BlackwallRecoveryWriterFixture.ValidProgramRequest(key,op,offset,words,source,masked,start,length,full,boot);
  }
  public static int RunAtomic(Antmicro.Renode.Core.IMachine machine,Antmicro.Renode.Peripherals.CPU.CortexM cpu,BlackwallRecoveryWriterFixture u) {
   var bus=machine.SystemBus;var before=new byte[0x400000];
   for(int i=0;i<before.Length;i++)before[i]=(byte)(i*31+7);
   bus.WriteBytes(before,0x400000);((BlackwallProtectedMram)machine["sysbus.mram"]).Arm();
   var input=new byte[256];for(int i=0;i<input.Length;i++)input[i]=0x67;bus.WriteBytes(input,0x20001000);
   u.SeedRegister(13,0x20002000);u.SeedRegister(28,1);
   var method=typeof(BlackwallRecoveryWriterFixture).GetMethod("Program",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);
   // key, operation, destination word offset, word count, source
   var cases=new uint[][] {
    new uint[]{0,1,0xe004,4,0x20001000},new uint[]{0x12344321,0,0xe004,4,0x20001000},
    new uint[]{0x12344321,1,0x4000,4,0x20001000},new uint[]{0x12344321,1,0xe000,4,0x20001000},
    new uint[]{0x12344321,1,0xff800,4,0x20001000},new uint[]{0x12344321,1,0xe084,4,0x20001000},
    new uint[]{0x12344321,1,0xe004,65,0x20001000},new uint[]{0x12344321,1,0xe004,4,0x20080000}
   };
   int n=0;
   foreach(var c in cases) {
    u.SeedRegister(0,c[0]);u.SeedRegister(1,c[1]);u.SeedRegister(2,c[4]);u.SeedRegister(3,c[2]);bus.WriteDoubleWord(0x20002000,c[3]);
    if(cpu.GetRegister(0).RawValue!=c[0] || cpu.GetRegister(1).RawValue!=c[1] || cpu.GetRegister(2).RawValue!=c[4]
        || cpu.GetRegister(3).RawValue!=c[2] || cpu.GetRegister(13).RawValue!=0x20002000
        || cpu.GetRegister(28).RawValue!=1 || bus.ReadDoubleWord(0x20002000)!=c[3])
     throw new System.Exception("Synthetic request context differs "+n);
    var violations=u.Violations;bool blocked=false;
    try{method.Invoke(u,null);}catch(System.Reflection.TargetInvocationException e){blocked=e.InnerException.GetType().Name=="CpuAbortException";}
    var after=bus.ReadBytes(0x400000,0x400000,true);
    var expectedReason=c[3]>64 ? "ROM word address/count overflow" : "invalid ROM programming ABI/range";
    if(u.Failure!=expectedReason)throw new System.Exception("Wrong rejection reason "+n);
    if(!blocked || u.Violations!=violations+1 || u.RomCalls!=0 || u.ProgrammedBytes!=0 || u.ProgramDestinations.Count!=0 || u.ProgramLengths.Count!=0 || u.ResultSeen || u.PowerInterrupted)
     throw new System.Exception("Rejected request changed writer state "+n);
    for(int i=0;i<after.Length;i++)if(after[i]!=before[i])throw new System.Exception("Rejected request changed MRAM "+n);
    n++;
   }
   return n;
  }
  public static int RunBoot() {
   int n=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("Boot MRAM boundary "+n);n++;};
   check(BlackwallRecoveryWriterFixture.ValidWriteScope(0x410000,149776,false,true));
   check(BlackwallRecoveryWriterFixture.ValidWriteScope(0x434910,9968,false,true));
   check(BlackwallRecoveryWriterFixture.ValidWriteScope(0x410000,159744,false,true));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x410000,149776,false,false));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x410000,149776,true,true));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x410000,159760,false,true));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x438000,16,false,true));
   check(V(start:0x410000,length:149776,offset:0x4000,boot:true));
   var last=(uint)((0x410000UL+149776-16-0x400000)/4);
   check(V(start:0x410000,length:149776,offset:last,boot:true));
   check(!V(start:0x410000,length:149776,offset:last+4,boot:true));
   var end=(uint)((0x437000UL-16-0x400000)/4);
   check(V(start:0x410000,length:159744,offset:end,boot:true));
   check(!V(start:0x410000,length:159744,offset:end+4,boot:true));
   check(V(start:0x434910,length:9968,offset:(0x434910-0x400000)/4,boot:true));
   check(!V(start:0x434910,length:9968,offset:(0x434900-0x400000)/4,boot:true));
   check(!V(start:0x410000,length:159744,offset:0xff800,boot:true));
   check(!V(start:0x410000,length:159744,offset:0xe000,boot:true));
   check(!V(start:0x410000,length:159744,offset:0x4000,key:0,boot:true));
   check(!V(start:0x410000,length:159744,offset:0x4000,masked:false,boot:true));return n;
  }
  public static int RunFull() {
   int n=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("Full MRAM boundary "+n);n++;};
   check(BlackwallRecoveryWriterFixture.ValidWriteScope(0x438010,3700064,true));
   check(BlackwallRecoveryWriterFixture.ValidWriteScope(0x438000,16,true));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x438010,3700064,false));
   check(!BlackwallRecoveryWriterFixture.ValidWriteScope(0x438010,512,true));
   check(V(length:3700064,full:true));
   var last=(uint)((0x438010UL+3700064-16-0x400000)/4);
   check(V(offset:last,length:3700064,full:true));
   check(!V(offset:last+4,length:3700064,full:true));
   check(V(offset:0xe000,start:0x438000,length:16,full:true));
   check(!V(offset:0xe000,words:8,start:0x438000,length:16,full:true));
   check(!V(offset:0x4000,length:3700064,full:true));
   check(!V(offset:0xff800,length:3700064,full:true));return n;
  }
  public static int Run() {
   int n=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("MRAM boundary "+n);n++;};
   check(V());check(V(words:64));check(V(offset:0xe080,source:0x2007fff0));
   check(!V(key:0));check(!V(op:0));check(!V(offset:0x4000));check(!V(offset:0xe000));
   check(!V(offset:0xff800));check(!V(offset:0xe084));check(!V(offset:0x100000));
   check(!V(words:0));check(!V(words:1));check(!V(words:65));
   check(!V(source:0x1fffffff));check(!V(source:0x20080000));check(!V(source:ulong.MaxValue));
   check(!V(masked:false));check(!V(start:0x410000));check(!V(length:0));check(!V(length:4097));check(!V(length:17));
   check(!V(words:ulong.MaxValue));check(!V(key:ulong.MaxValue));return n;
  }
 }
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
    source=(ROOT/'tools/renode-recovery-writer-fixture.cs').read_text();out.mkdir(parents=True,mode=0o700)
    (out/'model.cs').write_text(source+TEST)
    (out/'check.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMramBoundaryTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMramBoundaryTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_MRAM_BOUNDARY '+str(BlackwallMramBoundaryTest.Run()))\nConsole.WriteLine('BLACKWALL_MRAM_BOOT_SCOPE '+str(BlackwallMramBoundaryTest.RunBoot()))\nConsole.WriteLine('BLACKWALL_MRAM_FULL_SCOPE '+str(BlackwallMramBoundaryTest.RunFull()))\nConsole.WriteLine('BLACKWALL_MRAM_ATOMIC '+str(BlackwallMramBoundaryTest.RunAtomic(monitor.Machine,monitor.Machine['sysbus.cpu'],monitor.Machine['sysbus.uart'])))\n")
    (out/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\nmram: Miscellaneous.BlackwallProtectedMram @ sysbus 0x400000\n    size: 0x400000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\nuart: Miscellaneous.BlackwallRecoveryWriterFixture @ sysbus 0x4003b000\n    cpu: cpu\n    nvic: nvic\n    initialTick: 0\n    returnPc: 0x435000\n    writerPc: 0x20010000\n    recvPc: 0x435002\n    sendPc: 0x435004\n    destination: 0x438010\n    length: 512\n')
    (out/'probe.resc').write_text('include @/work/model.cs\nmach create "mram-boundary-component"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/check.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=60)
    r={'passed':'BLACKWALL_MRAM_BOUNDARY 23' in log and 'BLACKWALL_MRAM_ATOMIC 8' in log and 'BLACKWALL_MRAM_FULL_SCOPE 11' in log and 'BLACKWALL_MRAM_BOOT_SCOPE 18' in log,'model_sha256':hashlib.sha256(source.encode()).hexdigest(),'hardware_accessed':False,'silicon_rom_permissions_verified':False,'scope':'C# policy23 + full-scope11 + boot-scope18 + actual Program rejection8 with full4MiB before/after; CPU registers are synthetic and guest does not execute.'}
    (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)

if __name__=='__main__':main()
