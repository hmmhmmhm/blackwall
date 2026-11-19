"""Check opt-in B0 TON digital storage; no analog or factory calibration claim."""
import argparse,hashlib,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'

def bind_b0_ldo(source):
 if 'private uint Reduction => hal.B0TonConfiguration' in source:return source
 old='public uint ReducedTrim => (OriginalWord & 0x3ff) > 7 ? (OriginalWord & 0x3ff)-7 : 0;'
 new='private uint Reduction => hal.B0TonConfiguration ? 6u : 7u;\n        public uint ReducedTrim => (OriginalWord & 0x3ff) > Reduction ? (OriginalWord & 0x3ff)-Reduction : 0;'
 if source.count(old)!=1:raise ValueError('Unique CORE LDO reduction required')
 source=source.replace(old,new)
 a=source.index('    public sealed class BlackwallMemLdoSetup');b=source.index('\nnamespace ',a);block=source[a:b]
 old='            if(value != ((r.Value & ~Masks[StepsCompleted]) | Fields[StepsCompleted])) return false;'
 new='            var field = hal.B0TonConfiguration ? (StepsCompleted==0 ? 0u : 0x8000u) : Fields[StepsCompleted];\n            if(value != ((r.Value & ~Masks[StepsCompleted]) | field)) return false;'
 if block.count(old)!=1:raise ValueError('Unique MEM LDO field boundary required')
 return source[:a]+block.replace(old,new)+source[b:]


def bind_b0_override(source):
 if 'var b0TonOverride =' in source:return source
 old='''                    var ordered = BuckOverrideStep < BuckSteps.Length && value == BuckSteps[BuckOverrideStep]
                        && (BuckOverrideStep > 0 || VrctrlValue == 0xe000);'''
 new='''                    var b0TonOverride = HalStorage!=null && HalStorage.B0TonConfiguration;
                    var ordered = BuckOverrideStep < BuckSteps.Length && value == (b0TonOverride ? BuckSteps[BuckOverrideStep]&~0xe000u : BuckSteps[BuckOverrideStep])
                        && (BuckOverrideStep > 0 || VrctrlValue == (b0TonOverride ? 0u : 0xe000u));'''
 if source.count(old)!=1:raise ValueError('Unique VRCTRL override sequence required')
 return source.replace(old,new)


def bind_b0_ton(source):
 if 'bool b0TonConfiguration = false' in source:
  if source.count('bool b0TonConfiguration = false')!=2:raise ValueError('Partial B0 TON binding')
  return bind_b0_ldo(bind_b0_override(source))
 edits=[
  ('int info1TrimRevision = -1)', 'int info1TrimRevision = -1, bool b0TonConfiguration = false)'),
  ('            HalStorage = halStorage ? new BlackwallHalStorage() : null;', '''            if(b0TonConfiguration && (!halStorage || chipRevision!=0x21))
                throw new System.ArgumentException("B0 TON requires explicit B0 HAL profile");
            HalStorage = halStorage ? new BlackwallHalStorage(b0TonConfiguration) : null;'''),
  ('public BlackwallHalStorage()\n        {', '''public BlackwallHalStorage(bool b0TonConfiguration = false)
        {
            B0TonConfiguration=b0TonConfiguration;
            if(b0TonConfiguration) Add(0x40020340,0x00400000);''')]
 for old,new in edits:
  if source.count(old)!=1:raise ValueError('Unique B0 constructor anchor required')
  source=source.replace(old,new)
 a=source.index('    public sealed class BlackwallHalStorage');b=source.index('\nnamespace ',a)
 block=source[a:b]
 old='''            if(!registers.TryGetValue(address,out var register) || System.Array.IndexOf(allowed[address],value) < 0)
                return false;'''
 new='''            if(!registers.TryGetValue(address,out var register)) return false;
            uint mask=B0TonConfiguration ? TonMask(address) : 0;
            if(mask!=0)
            {
                if(((register.Value^value)&~mask)!=0) return false;
                if(address!=0x40020340 && (registers[0x40020340].Value&0x80000000u)==0) return false;
            }
            else if(System.Array.IndexOf(allowed[address],value)<0) return false;'''
 if block.count(old)!=1:raise ValueError('Unique HAL write boundary required')
 block=block.replace(old,new)
 anchor='        public bool TrimReadsObserved'
 extra='''        public bool B0TonConfiguration {get;}
        private static uint TonMask(ulong address)
        {
            switch(address)
            {
                case 0x40020340:return 0x80000000u;
                case 0x40020344:case 0x4002034c:return 0x3e00f800u;
                case 0x40020354:return 0x003e0000u;
                case 0x40020358:return 0x00001f00u;
                default:return 0;
            }
        }

'''
 if block.count(anchor)!=1:raise ValueError('Unique HAL metadata anchor required')
 block=block.replace(anchor,extra+anchor)
 return bind_b0_ldo(bind_b0_override(source[:a]+block+source[b:]))


TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallB0TonTest {
  public static int Run() {
   int count=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("B0 TON contract "+count);count++;};
   uint value;
   var strict=new BlackwallHalStorage();
   check(!strict.TryRead(0x40020340,out value));
   foreach(var a in new ulong[]{0x40020344,0x4002034c,0x40020354,0x40020358}) {
    check(strict.TryRead(a,out value)&&value==0);check(!strict.TryWrite(a,0));
   }
   var g=new BlackwallHalStorage(b0TonConfiguration:true);
   check(g.TryRead(0x40020340,out value)&&value==0x400000);
   check(!g.TryWrite(0x40020344,0x02000000));
   check(g.Registers[0x40020344].Value==0 && g.Registers[0x40020344].Writes==0);
   check(!g.TryWrite(0x40020340,0x80000000));
   check(g.TryWrite(0x40020340,0x80400000));
   foreach(var pair in new[]{new ulong[]{0x40020344,0x3e00f800},new ulong[]{0x4002034c,0x3e00f800},new ulong[]{0x40020354,0x3e0000},new ulong[]{0x40020358,0x1f00}}) {
    var a=pair[0];var mask=(uint)pair[1];
    foreach(var v in new uint[]{0,mask,mask & (0u-mask),0}) {check(g.TryWrite(a,v));check(g.TryRead(a,out value)&&value==v);}
    var writes=g.Registers[a].Writes;
    check(!g.TryWrite(a,1));check(g.Registers[a].Value==0&&g.Registers[a].Writes==writes);
   }
   check(!g.TryWrite(0x4002033c,0));check(!g.TryRead(0x40020348,out value));
   check(g.TryWrite(0x40020340,0x400000));check(!g.TryWrite(0x40020344,0));
   g.Reset();check(g.Registers[0x40020340].Value==0x400000&&g.Registers[0x40020340].Writes==0);
   foreach(var a in new ulong[]{0x40020344,0x4002034c,0x40020354,0x40020358})check(g.Registers[a].Value==0&&g.Registers[a].Writes==0);
   bool rejected=false;try{new BlackwallG2StartupFixture(0x1000,0x40020000,halStorage:true,chipRevision:0x23,info1TrimRevision:1,info1Metadata:"zero",shadowInfo1:"mram",b0TonConfiguration:true);}catch(System.ArgumentException){rejected=true;}check(rejected);
   var fixture=new BlackwallG2StartupFixture(0x1000,0x40020000,halStorage:true,chipRevision:0x21,info1TrimRevision:1,info1Metadata:"zero",shadowInfo1:"mram",b0TonConfiguration:true);
   check(fixture.ReadDoubleWord(0x340)==0x400000);fixture.WriteDoubleWord(0x340,0x80400000);check(fixture.ReadDoubleWord(0x340)==0x80400000);
   var power=new BlackwallG2StartupFixture(0x1000,0x40020000,halStorage:true,spotStorage:true,buckOverrideStorage:true,chipRevision:0x21,b0TonConfiguration:true);
   foreach(var v in new uint[]{0x20000,0x60000,0xe0000,0xf0000,0xf0000,0xf000e,0xf000f,0xf000f,0xf01cf,0xf01ef}) {power.WriteDoubleWord(0x60,v);check(power.ReadDoubleWord(0x60)==v);}
   check(power.BuckOverrideComplete&&power.BuckOverrideStep==10);power.Reset();check(!power.BuckOverrideComplete&&power.ReadDoubleWord(0x60)==0);
   var b2=new BlackwallG2StartupFixture(0x1000,0x40020000,halStorage:true,spotStorage:true,buckOverrideStorage:true,chipRevision:0x23);
   b2.WriteDoubleWord(0x60,0xe000);
   foreach(var v in new uint[]{0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef}) {b2.WriteDoubleWord(0x60,v);check(b2.ReadDoubleWord(0x60)==v);}
   check(b2.BuckOverrideComplete&&b2.BuckOverrideStep==10);
   foreach(var b0 in new[]{false,true}) {
    var hal=new BlackwallHalStorage(b0);var start=new BlackwallBuckStart();var core=new BlackwallCoreLdoReduction(hal,start);var mem=new BlackwallMemLdoSetup(hal,start,core);
    foreach(var pair in hal.Registers)hal.TryRead(pair.Key,out value);
    check(core.ReducedTrim==((0x6d3d4u&0x3ffu)-(b0?6u:7u)));
    check(start.TryWrite(0x40020378,0x80000000,true));check(start.TryWrite(0x4002033c,15,true));
    check(core.TryWrite(0x40020080,(0x6d3d4u&~0x3ffu)|core.ReducedTrim));check(start.TryWrite(0x40021100,1,true));
    check(!mem.TryWrite(0x40020088,(0x207c0774u&~63u)|(b0?1u:0u)));
    check(mem.StepsCompleted==0);
    check(mem.TryWrite(0x40020088,(0x207c0774u&~63u)|(b0?0u:1u)));
    check(mem.TryWrite(0x400201b0,b0?0x8000u:0x10000u));check(mem.StepsCompleted==2);
   }
   return count;
  }
 }
}
'''


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 source=(ROOT/'tools/renode-strict-mmio.cs').read_text();out.mkdir(parents=True,mode=0o700)
 (out/'model.cs').write_text(source+TEST)
 (out/'check.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallB0TonTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallB0TonTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_B0_TON '+str(BlackwallB0TonTest.Run()))\n")
 (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/check.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120)
 rows=[x for x in log.splitlines() if x.startswith('BLACKWALL_B0_TON ')]
 r=dict(passed=len(rows)==1,marker=rows,model_sha256=hashlib.sha256(source.encode()).hexdigest(),hardware_accessed=False,scope='Digital TON reset/storage/masks/HP gate/default strict; not calibration or analog response')
 (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
if __name__=='__main__':main()
