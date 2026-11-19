"""Check declared ROM power functional responses using pinned HAL/header; no ROM code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from run_renode_m55_probe import execute
from native_replay import IMAGE
from verify_mram_control_sources import PINS

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'


def block(source):
    pos=source.index('    public sealed class BlackwallMemoryRegister')
    start=source.rfind('namespace Antmicro.',0,pos)
    end=source.index('\nnamespace Antmicro.',source.index('    public sealed class BlackwallMemoryStartup',pos))
    return source[start:end]


TEST='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
public static class BlackwallRomPowerTest {
 public static int Run() {
  int checks=0; uint value;var legacy=new BlackwallMemoryStartup();
  System.Action<bool> check=(ok)=>{if(!ok)throw new System.Exception("ROM power contract check "+checks);checks++;};
  check(legacy.TryWrite(0x40021014,0x1f));
  check(!legacy.TryWrite(0x40021014,0x3f));
  check(legacy.TryRead(0x40021018,out value) && value==0x4f);
  foreach(var response in new[]{0,1}) {
   var m=new BlackwallMemoryStartup(response);
   check(m.TryRead(0x40021014,out value) && value==0x3f);
   check(m.TryWrite(0x40021014,0x1f));
   check(m.TryRead(0x40021018,out value) && value==0x4f);
   check(m.TryWrite(0x40021014,0x3f));
   check(m.TryRead(0x40021018,out value) && value==(response==1?0xcfu:0x4fu));
   check(m.RomEnables==1 && m.RomDisables==1);
   check(!m.TryWrite(0x40021014,0x7f));
   check(m.TryRead(0x40021014,out value) && value==0x3f);
   check(!m.TryWrite(0x40021018,0xcf));
   m.Reset();check(m.RomEnables==0 && m.RomDisables==0);
   check(m.TryRead(0x40021018,out value) && value==0xcf);
  }
  bool rejected=false;try{new BlackwallMemoryStartup(2);}catch(System.ArgumentException){rejected=true;}
  check(rejected);return checks;
 }
}}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
    sources=PRIVATE/'simulator/upstream/hal-ambiq-61b293a'
    for n,h in PINS.items():
        if hashlib.sha256((sources/n).read_bytes()).hexdigest()!=h:raise ValueError('Pinned public source changed')
    h=(sources/'apollo510.h').read_text();hal=(sources/'am_hal_pwrctrl.c').read_text()
    for token in ['PWRCTRL_MEMPWREN_PWRENROM_Msk     (0x20UL)','PWRCTRL_MEMPWRSTATUS_PWRSTROM_Msk (0x80UL)']:
        if token not in h:raise ValueError('ROM request/status field changed')
    if 'PWRCTRL->MEMPWREN_b.PWRENROM = PWRCTRL_MEMPWREN_PWRENROM_EN;' not in hal:raise ValueError('HAL enable sequence changed')
    out.mkdir(parents=True,mode=0o700)
    model=block((ROOT/'tools/renode-strict-mmio.cs').read_text())
    (out/'model.cs').write_text(model+TEST)
    (out/'check.py').write_text("import clr\nfrom Antmicro.Renode.Utilities import TypeManager\nclr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRomPowerTest').Assembly)\nfrom Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRomPowerTest\nfrom System import Console\nConsole.WriteLine('BLACKWALL_ROM_POWER '+str(BlackwallRomPowerTest.Run()))\n")
    (out/'probe.resc').write_text('include @/work/model.cs\ninclude @/work/check.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'native',timeout=60)
    passed='BLACKWALL_ROM_POWER 26' in log
    report=dict(passed=passed,source_sha256=PINS,model_sha256=hashlib.sha256(model.encode()).hexdigest(),functional_profiles=['legacy unsupported re-enable','ready','stuck'],hardware_validated=False,boot_rom_executed=False,scope='Pure C# ROM power contract in pinned Renode; no firmware execution')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
