"""Synthetic M55: cache register overlay and initialization leases across reset."""
import argparse,hashlib,json,shutil
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

SOURCE=r'''#include <stdint.h>
#define W(a) (*(volatile uint32_t*)(a))
static void init(void) {
 W(0xe000ef50)=0;
 W(0xe000ed14)=(W(0xe000ed14)&~0x30000u)|0x20000u;
 W(0xe000ed84)=0;
 for(uint32_t set=0;set<512;set++)for(uint32_t way=0;way<4;way++)W(0xe000ef60)=(set<<5)|(way<<30);
 W(0xe000ed14)=W(0xe000ed14)|0x10000u;
}
void reset(void) {
 const uint32_t boot=++W(0x20000000);
 if(boot==1) {
  init(); W(0x20000004)=1;
  for(;;)if(W(0x20000008)) {W(0x20000008)=0;W(0xe000ed0c)=0x05fa0004;__asm volatile("dsb\nisb":::"memory");}
 }
 W(0x2000000c)=W(0xe000ed14);
 W(0x20000010)=0x11112222;
#if MODE == 2
 W(0xe000ed14)=(W(0xe000ed14)&~0x30000u)|0x20000u;
#elif MODE == 3
 W(0xe000ed14)=(W(0xe000ed14)&~0x30000u)|0x10000u;
#elif MODE == 4
 init();
#endif
 W(0x20000010)=0x33334444;
 for(;;){}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[]={0x2007fb00,(uintptr_t)reset};
'''
SCRIPT='''import clr,time,json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallSystemControl').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallSystemControl
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];nvic=m['sysbus.nvic'];em=EmulationManager.Instance.CurrentEmulation
c=BlackwallSystemControl(m,cpu,nvic,True,True,True);c.Attach()
def state():return dict(boot=int(b.ReadDoubleWord(0x20000000)),ready=int(b.ReadDoubleWord(0x20000004)),ccr_after=int(b.ReadDoubleWord(0x2000000c)),marker=int(b.ReadDoubleWord(0x20000010)),icache=bool(c.ICacheEnabled),dcache=bool(c.DataCache.Enabled),selected=bool(c.DataCache.Selected),initialized=int(c.DataCache.InitializedLines),invalidations=int(c.Invalidations),violations=int(c.Violations),operation=str(c.LastOperation),address=int(c.LastAddress),resets=int(nvic.ResetCompletions),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))
em.StartAll();deadline=time.time()+5
while b.ReadDoubleWord(0x20000004)!=1 and not c.Violations and time.time()<deadline:time.sleep(0.001)
m.Pause();before=state()
if before['ready']!=1 or not before['icache'] or not before['dcache'] or before['initialized']!=2048 or before['violations']:raise ValueError('Initial cache setup failed')
if '__METHOD__'=='guest-aircr':b.WriteDoubleWord(0x20000008,1)
else:b.WriteDoubleWord(0xe000ed0c,0x05fa0004)
em.StartAll();deadline=time.time()+5
while time.time()<deadline:
 if b.ReadDoubleWord(0x20000010)==0x33334444 or c.Violations or b.ReadDoubleWord(0xe000ed28) or b.ReadDoubleWord(0xe000ed2c):break
 time.sleep(0.001)
m.Pause()
Console.WriteLine('BLACKWALL_RESET_CACHE '+json.dumps(dict(mode=__MODE__,method='__METHOD__',before=before,after=state(),original_g2_executed=False,host_pc_register_seed=False,hardware_accessed=False)))
'''

def validate(v):
 a=v['after'];mode=v['mode'];blocked=mode in (2,3)
 checks=dict(actual_reset=a['boot']==2 and a['resets']==1,clean_core=a['cfsr']==a['hfsr']==0,initial_caches=v['before']['icache'] and v['before']['dcache'] and v['before']['initialized']==2048,guest_reset_ccr=a['ccr_after']&0x30000==0,expected_violation=a['violations']==int(blocked),marker=a['marker']==(0x11112222 if blocked else 0x33334444),no_hardware=v['original_g2_executed'] is False and v['host_pc_register_seed'] is False and v['hardware_accessed'] is False)
 if blocked:checks['blocked_ccr']=a['operation']=='write' and a['address']==0xe000ed14
 if mode!=4:checks['cache_state_reset']=not a['icache'] and not a['dcache'] and not a['selected'] and a['initialized']==a['invalidations']==0
 else:checks['fresh_initialization']=a['icache'] and a['dcache'] and a['selected'] and a['initialized']==2048 and a['invalidations']==1
 return dict(passed=all(checks.values()),checks=checks,observed=v)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--control',type=Path,default=Path(__file__).with_name('renode-system-control.cs'));a=p.parse_args();s=a.simulator;o=a.output
 if o.exists() or not o.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output and 1 GiB free required')
 o.mkdir(parents=True,mode=0o700);(o/'fixture.c').write_text(SOURCE);(o/'fixture.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.comment*) } }\n')
 control=a.control.read_bytes();nvic=Path(__file__).with_name('renode-reset-aware-nvic.cs').read_bytes();rows=[]
 for mode in range(1,5):
  execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-O1','-Wl,--nmagic','-ffreestanding','-fno-builtin','-nostdlib','-DMODE='+str(mode),'-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(o/'fixture.ld'),str(o/'fixture.c'),'-o',str(o/('mode-'+str(mode)+'.elf'))],o,'compile-'+str(mode))
  for method in ('device-aircr','guest-aircr'):
   cap=o/(str(mode)+'-'+method);cap.mkdir();(cap/'fixture.elf').write_bytes((o/('mode-'+str(mode)+'.elf')).read_bytes());(cap/'control.cs').write_bytes(control);(cap/'nvic.cs').write_bytes(nvic)
   (cap/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    InitVectorTableOffset: 0x438000\n    PerformanceInMips: 1\nnvic: Miscellaneous.BlackwallResetAwareNVIC @ sysbus 0xe000e000\n    -> cpu@0\nmain: Memory.MappedMemory @ sysbus 0x438000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\n')
   (cap/'run.py').write_text(SCRIPT.replace('__MODE__',str(mode)).replace('__METHOD__',method));(cap/'probe.resc').write_text('include @/work/control.cs\ninclude @/work/nvic.cs\nmach create "reset-cache"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/fixture.elf\ncpu VectorTableOffset 0x438000\ninclude @/work/run.py\nquit\n')
   log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={cap},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],cap,'renode',timeout=30)
   values=[json.loads(l.split('BLACKWALL_RESET_CACHE ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RESET_CACHE ')]
   if len(values)!=1:raise ValueError('Missing result: '+str(cap))
   row=dict(case=cap.name,**validate(values[0]));(cap/'report.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print(json.dumps(dict(case=cap.name,passed=row['passed'],failed=[k for k,v in row['checks'].items() if not v])),flush=True)
 report=dict(passed=all(r['passed'] for r in rows),cases=rows,control_sha256=hashlib.sha256(control).hexdigest(),image=RENODE_IMAGE,original_g2_executed=False,hardware_accessed=False);(o/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
