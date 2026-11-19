"""Exercise read-only synthetic INFO1 trim revisions, not real device calibration."""
import argparse
import hashlib
import json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'


def bind_trim_profile(source):
    if 'public int Info1TrimRevision' in source:return source
    edits=[('BlackwallGpioInterruptIdle gpioInterruptController = null)','BlackwallGpioInterruptIdle gpioInterruptController = null, int info1TrimRevision = -1)'),
    ('            Info1Metadata = info1Metadata;','''            Info1Metadata = info1Metadata;
            if(info1TrimRevision < -1 || info1TrimRevision>2 || info1TrimRevision!=-1 && (info1Metadata!="zero" || (shadowInfo1!="mram" && (gpuControlOwner==null || gpuControlOwner.ShadowInfo1!="mram"))))
                throw new System.ArgumentException("Explicit synthetic MRAM trim revision0..2 requires zero metadata baseline");
            Info1TrimRevision=info1TrimRevision;'''),
    ('if(address == 0x42003310) { TrimRevisionReads++; return MetadataValue; }','if(address == 0x42003310) { TrimRevisionReads++; return Info1TrimRevision<0 ? MetadataValue : (uint)Info1TrimRevision; }'),
    ('        public string Info1Metadata { get; }','        public string Info1Metadata { get; }\n        public int Info1TrimRevision {get;}')]
    for old,new in edits:
        if source.count(old)!=1:raise ValueError('Unique INFO1 trim source anchor required')
        source=source.replace(old,new)
    return source


TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public static class BlackwallTrimProfileTest {
  public static int Run() {
   int count=0;System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("trim contract "+count);count++;};
   foreach(var trim in new[]{-1,0,1,2}) {
    var g=new BlackwallG2StartupFixture(0x1000,0x42003000,startupControls:true,shadowInfo1:"mram",info1Metadata:"zero",info1TrimRevision:trim);
    check(g.ReadDoubleWord(0x310)==(uint)(trim<0?0:trim));
    check(g.ReadDoubleWord(0x314)==0 && g.ReadDoubleWord(0x240)==0);
    check(g.TrimRevisionReads==1 && g.TrackerReads==1 && g.Ft1Reads==1);
    bool rejected=false;try{g.WriteDoubleWord(0x310,7);}catch(System.Exception){rejected=true;}check(rejected);
    check(g.ReadDoubleWord(0x310)==(uint)(trim<0?0:trim));
    g.Reset();check(g.TrimRevisionReads==0 && g.TrackerReads==0 && g.Ft1Reads==0);
    check(g.ReadDoubleWord(0x310)==(uint)(trim<0?0:trim));
   }
   foreach(var trim in new[]{-2,3}) {bool bad=false;try{new BlackwallG2StartupFixture(0x1000,0x42003000,startupControls:true,shadowInfo1:"mram",info1Metadata:"zero",info1TrimRevision:trim);}catch(System.ArgumentException){bad=true;}check(bad);}
   bool none=false;try{new BlackwallG2StartupFixture(0x1000,0x42003000,info1TrimRevision:1);}catch(System.ArgumentException){none=true;}check(none);
   var owner=new BlackwallG2StartupFixture(0x1000,0x40020000,startupControls:true,shadowInfo1:"mram");
   var shared=new BlackwallG2StartupFixture(0x1000,0x42003000,info1Metadata:"zero",info1TrimRevision:1,gpuControlOwner:owner);
   check(shared.ReadDoubleWord(0x310)==1);
   bool wrong=false;try{new BlackwallG2StartupFixture(0x1000,0x42003000,info1Metadata:"zero",info1TrimRevision:1,gpuControlOwner:new BlackwallG2StartupFixture(0x1000,0x40020000));}catch(System.ArgumentException){wrong=true;}check(wrong);
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
    (out/'check.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallTrimProfileTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallTrimProfileTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_TRIM_PROFILE '+str(BlackwallTrimProfileTest.Run()))\n")
    (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/check.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=120)
    r={'passed':'BLACKWALL_TRIM_PROFILE 33' in log,'model_sha256':hashlib.sha256(source.encode()).hexdigest(),'hardware_accessed':False,'valid_calibration':False,'scope':'Synthetic read-only trim0/1/2 + unchanged zero baseline; not a device revision observation'}
    (out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)

if __name__=='__main__':main()
