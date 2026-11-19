"""Opt-in, context-qualified CPDLP retention configuration; does not implement deep sleep."""

def compose(model):
    start=model.index('    public sealed class BlackwallCpuNormalSleep : IPeripheral')
    end=model.index('    public class BlackwallPeripheralPower',start)
    c=model[start:end]
    edits=[('string profile,uint flushReadPc)','string profile,uint flushReadPc,uint retentionStorePc=0,uint retentionReturnPc=0)'),
           ('            this.machine=machine;FlushReadPc=flushReadPc;Reset();','''            if((retentionStorePc==0)!=(retentionReturnPc==0) || (retentionStorePc!=0 &&
                (retentionStorePc<0x438000 || retentionStorePc>=0x800000 || (retentionStorePc&1)!=0 || retentionReturnPc<0x438000 || retentionReturnPc>=0x800000 || (retentionReturnPc&1)!=0)))
                throw new System.ArgumentException("Retention staging requires a pinned store and return pair");
            this.machine=machine;FlushReadPc=flushReadPc;RetentionStorePc=retentionStorePc;RetentionReturnPc=retentionReturnPc;Reset();'''),
           ('PowerControlReads=CpdReads=CpdWrites=FlushReads=CpdValue=0;', 'PowerControlReads=CpdReads=CpdWrites=FlushReads=CpdValue=RetentionStages=0;'),
           ('            if(address!=0xe001e300 || (value!=0 && value!=0x11u)', '''            if(address==0xe001e300 && value==0x22u)
            {
                if(RetentionStorePc==0 || !machine.SystemBus.TryGetCurrentCPU(out var current))return false;
                var cpu=current as CortexM;
                if(cpu==null || cpu.PC.RawValue!=RetentionStorePc || cpu.GetRegister(14).RawValue!=(RetentionReturnPc|1u))return false;
                var sp=cpu.GetRegister(13).RawValue;
                if(sp<0x20000000 || sp>0x20380000-3 || machine.SystemBus.ReadByte(sp)!=0 || machine.SystemBus.ReadByte(sp+1)!=2 || machine.SystemBus.ReadByte(sp+2)!=2)return false;
                CpdValue=value;CpdWrites++;RetentionStages++;return true;
            }
            if(address!=0xe001e300 || (value!=0 && value!=0x11u)'''),
           ('        public uint PowerControlReads {', '''        public uint RetentionStorePc { get; }
        public uint RetentionReturnPc { get; }
        public uint RetentionStages { get; private set; }
        public uint PowerControlReads {''')]
    for old,new in edits:
        if c.count(old)!=1:raise ValueError('Unknown CPU sleep staging boundary: '+old)
        c=c.replace(old,new)
    return model[:start]+c+model[end:]

def compose_boot_binding(model):
    start=model.index('    public sealed class BlackwallCpuNormalSleep : IPeripheral')
    end=model.index('    public class BlackwallPeripheralPower',start)
    c=model[start:end]
    if 'bool bootRetentionBinding=false' in c:return model
    edits=[
      ('bool retentionFlush=false)', 'bool retentionFlush=false,bool bootRetentionBinding=false)'),
      ('if(machine==null || profile!="normal-sleep-storage" || flushReadPc<0x438000 || flushReadPc>=0x800000 || (flushReadPc&1)!=0)',
       'if(machine==null || profile!="normal-sleep-storage" || (!bootRetentionBinding && (flushReadPc<0x438000 || flushReadPc>=0x800000 || (flushReadPc&1)!=0)))'),
      ('            if((retentionStorePc==0)!=(retentionReturnPc==0) || (retentionStorePc!=0 &&',
       '''            if(bootRetentionBinding && (flushReadPc!=0x41a9ce || retentionStorePc!=0x41ca00 || retentionReturnPc!=0x41a7c0))
                throw new System.ArgumentException("Boot retention requires exact stock2.3 store/return/flush triplet");
            if(!bootRetentionBinding && ((retentionStorePc==0)!=(retentionReturnPc==0) || (retentionStorePc!=0 &&'''),
      ('retentionReturnPc&1)!=0)))', 'retentionReturnPc&1)!=0))))')]
    for old,new in edits:
        if c.count(old)!=1:raise ValueError('Unknown exact boot retention constructor: '+old)
        c=c.replace(old,new)
    return model[:start]+c+model[end:]


BOOT_TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallBootRetentionBindingTest {
  public static int Run(Antmicro.Renode.Core.IMachine m) {
   int count=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("boot retention binding "+count);count++;};
   var c=new BlackwallCpuNormalSleep(m,"normal-sleep-storage",0x41a9ce,retentionStorePc:0x41ca00,retentionReturnPc:0x41a7c0,retentionFlush:true,bootRetentionBinding:true);
   check(c.RetentionStorePc==0x41ca00&&c.RetentionReturnPc==0x41a7c0&&c.FlushReadPc==0x41a9ce);
   check(c.CpdValue==0&&c.RetentionStages==0);
   check(!c.TryWrite(0xe001e300,0x22)&&c.CpdValue==0&&c.CpdWrites==0);
   check(!c.TryWrite(0xe001e300,0x23)&&c.CpdWrites==0);
   uint value;check(!c.TryReadFlush(0x41a9ce,0x47ff0000,out value)&&c.RetentionFlushes==0);
   c.Reset();check(c.CpdValue==0&&c.RetentionStages==0);
   foreach(var wrong in new uint[]{0x41ca02,0x4956e2,0}) {
    bool bad=false;try {new BlackwallCpuNormalSleep(m,"normal-sleep-storage",0x41a9ce,retentionStorePc:wrong,retentionReturnPc:0x41a7c0,bootRetentionBinding:true);}catch(System.ArgumentException){bad=true;}check(bad);
   }
   foreach(var wrong in new uint[]{0x41a7c2,0x44df60,0}) {
    bool bad=false;try {new BlackwallCpuNormalSleep(m,"normal-sleep-storage",0x41a9ce,retentionStorePc:0x41ca00,retentionReturnPc:wrong,bootRetentionBinding:true);}catch(System.ArgumentException){bad=true;}check(bad);
   }
   foreach(var wrong in new uint[]{0x41a9d0,0x44e16e,0}) {
    bool bad=false;try {new BlackwallCpuNormalSleep(m,"normal-sleep-storage",wrong,retentionStorePc:0x41ca00,retentionReturnPc:0x41a7c0,bootRetentionBinding:true);}catch(System.ArgumentException){bad=true;}check(bad);
   }
   bool unselected=false;try{new BlackwallCpuNormalSleep(m,"normal-sleep-storage",0x41a9ce,retentionStorePc:0x41ca00,retentionReturnPc:0x41a7c0);}catch(System.ArgumentException){unselected=true;}check(unselected);
   var old=new BlackwallCpuNormalSleep(m,"normal-sleep-storage",0x44e16e,retentionStorePc:0x4956e2,retentionReturnPc:0x44df60,retentionFlush:true);
   check(old.CpdValue==0&&old.RetentionStorePc==0x4956e2);check(!old.TryWrite(0xe001e300,0x22)&&old.RetentionStages==0);
   check(old.TryRead(0x40021050,out value)&&old.TryWrite(0xe001e300,0x11));check(old.TryReadFlush(0x44e16e,0x47ff0000,out value));
   return count;
  }
 }
}
'''

def verify_boot_binding(output,baseline=False):
    import hashlib,json,shutil
    from pathlib import Path
    from native_replay import IMAGE
    from run_renode_m55_probe import execute
    private=Path.home()/'Library/Application Support/Blackwall';out=Path(output).resolve()
    if out.exists() or not out.is_relative_to(private):raise ValueError('Fresh private output required')
    source=(private/'simulator/upstream23-b0-ton-native-bw576-03/strict.cs').read_text()
    if not baseline:source=compose_boot_binding(source)
    out.mkdir(mode=0o700);(out/'model.cs').write_text(source+BOOT_TEST)
    (out/'test.py').write_text("import clr\nfrom System import Console\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallBootRetentionBindingTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallBootRetentionBindingTest\nConsole.WriteLine('BLACKWALL_BOOT_RETENTION '+str(BlackwallBootRetentionBindingTest.Run(monitor.Machine)))\n")
    (out/'probe.resc').write_text('include @/work/model.cs\nmach create "boot-retention-binding"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120)
    rows=[x for x in log.splitlines() if x.startswith('BLACKWALL_BOOT_RETENTION ')];r=dict(passed=len(rows)==1,marker=rows,model_sha256=hashlib.sha256(source.encode()).hexdigest(),baseline=baseline)
    (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return r

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--baseline',action='store_true');a=p.parse_args();r=verify_boot_binding(a.output,a.baseline);raise SystemExit(0 if r['passed'] else 1)
