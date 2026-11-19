"""Synthetic M55 guest: the production memory policy before and after device reset."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

SOURCE=r'''#include <stdint.h>
#define WORD(a) (*(volatile uint32_t*)(a))
void reset(void) {
 WORD(0x20000000)++;
 const uint32_t boot=WORD(0x20000000);
 WORD(0x2000001c)=0;
#if MODE == 5
 if(boot==1) {
  WORD(0x100)=0x47702007;
  WORD(0x20000008)=((uint32_t(*)(void))0x101)();
  WORD(0x20000008)=0;
 }
#endif
 WORD(0x2000001c)=1;
 while(boot<WORD(0x20000010)) {
  if(WORD(0x20000014)) {
   WORD(0x20000014)=0;
   WORD(0xe000ed0c)=0x05fa0004;
   __asm volatile("dsb\nisb" ::: "memory");
  }
 }
 WORD(0x20000004)=0x11112222;
#if MODE == 1
 *(volatile uint8_t*)0x438800=0x5a;
#elif MODE == 2
 *(volatile uint16_t*)0x438800=0x5a5a;
#elif MODE == 3
 WORD(0x438800)=0x5a5a5a5a;
#elif MODE == 4 || MODE == 5
 WORD(0x20000008)=((uint32_t(*)(void))0x101)();
#elif MODE == 7
 WORD(0x20000008)=WORD(0x439000);
#elif MODE == 8
 WORD(0x20000008)=((uint32_t(*)(void))0x439001)();
#elif MODE == 9
 WORD(0x20000008)=((uint32_t(*)(void))0x20010001)();
#endif
 WORD(0x20000004)=0x33334444;
 for(;;){}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[]={0x2007fb00,(uintptr_t)reset};
'''
SCRIPT='''import clr,time,json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];nvic=m['sysbus.nvic'];em=EmulationManager.Instance.CurrentEmulation
b.WriteDoubleWord(0x20000010,__TARGET__);b.WriteDoubleWord(0x20000020,0xcafebabe)
p=BlackwallMemoryPolicy(m,cpu,m['sysbus.main'],m['sysbus.itcm'],0x1000) if __GUARDED__ else None
if p is not None:p.Attach()
def state():return dict(boot=int(b.ReadDoubleWord(0x20000000)),marker=int(b.ReadDoubleWord(0x20000004)),result=int(b.ReadDoubleWord(0x20000008)),ready=int(b.ReadDoubleWord(0x2000001c)),cookie=int(b.ReadDoubleWord(0x20000020)),main_word=int(b.ReadDoubleWord(0x438800)),itcm_word=int(b.ReadDoubleWord(0x100)),pc=int(cpu.PC.RawValue),vtor=int(cpu.VectorTableOffset),reset_count=int(nvic.ResetCompletions),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),policy=None if p is None else dict(violations=int(p.Violations),operation=str(p.LastOperation),address=int(p.LastAddress),pc=int(p.LastPC),width=int(p.LastWidth),written=int(p.WrittenBytes)))
first=None
if __TARGET__==2:
 em.StartAll();deadline=time.time()+3
 while int(b.ReadDoubleWord(0x2000001c))!=1 and time.time()<deadline:time.sleep(0.001)
 m.Pause();first=state()
 if first['boot']!=1 or first['ready']!=1 or (p is not None and p.Violations):raise ValueError('Initial guest reset wait failed')
 if '__METHOD__'=='guest-aircr':b.WriteDoubleWord(0x20000014,1)
 else:b.WriteDoubleWord(0xe000ed0c,0x05fa0004)
em.StartAll();deadline=time.time()+3
while time.time()<deadline:
 if int(b.ReadDoubleWord(0x20000004))==0x33334444 or (p is not None and p.Violations):break
 if b.ReadDoubleWord(0xe000ed28) or b.ReadDoubleWord(0xe000ed2c):break
 time.sleep(0.001)
m.Pause();after=state()
Console.WriteLine('BLACKWALL_RESET_MEMORY '+json.dumps(dict(mode=__MODE__,target_boot=__TARGET__,method='__METHOD__',guarded=__GUARDED__,first=first,after=after,original_g2_executed=False,host_pc_register_seed=False,hardware_accessed=False)))
'''
CASES={'main-byte':(1,'write-main',0x438800),'main-half':(2,'write-main',0x438800),'main-word':(3,'write-main',0x438800),'unwritten-itcm':(4,'execute-unwritten-itcm',0x100),'retained-itcm':(5,'none',0),'padding-read':(7,'read-main-padding',0x439000),'padding-execute':(8,'execute-outside-code',0x439000),'sram-execute':(9,'execute-outside-code',0x20010000)}

def validate(v):
 mode=v['mode'];a=v['after'];guarded=v['guarded'];target=v['target_boot'];op=next(x[1] for x in CASES.values() if x[0]==mode)
 checks=dict(actual_boot=a['boot']==target,actual_reset_count=a['reset_count']==target-1,cookie_retained=a['cookie']==0xcafebabe,initialized_vector=a['vtor']==0x438000,no_architectural_fault=a['cfsr']==a['hfsr']==0,not_original_g2=v['original_g2_executed'] is False and v['host_pc_register_seed'] is False and v['hardware_accessed'] is False)
 if target==2:checks['first_boot_wait']=v['first']['boot']==1 and v['first']['ready']==1 and v['first']['reset_count']==0 and v['first']['marker']==0
 if guarded:
  p=a['policy'];blocked=op!='none';expected=next(x[2] for x in CASES.values() if x[0]==mode)
  checks.update(main_preserved=a['main_word']==0xa1b2c3d4,operation=p['operation']==op,violations=p['violations']==int(blocked),address=p['address']==expected,guard_before_continuation=a['marker']==(0x11112222 if blocked else 0x33334444),result_not_fabricated=a['result']==(7 if mode==5 else 0))
  if mode==5:checks['written_provenance_retained']=p['written']==4 and (target==1 or v['first']['policy']['written']==4)
 else:
  expected_main={1:0xa1b2c35a,2:0xa1b25a5a,3:0x5a5a5a5a}.get(mode,0xa1b2c3d4)
  checks.update(control_completes=a['marker']==0x33334444,control_main_effect=a['main_word']==expected_main,control_result=a['result']==(9 if mode in (4,8,9) else 7 if mode==5 else 0),no_policy=a['policy'] is None)
 return dict(passed=all(checks.values()),checks=checks,observed=v)

def main():
 q=argparse.ArgumentParser(description=__doc__);q.add_argument('simulator',type=Path);q.add_argument('output',type=Path);q.add_argument('--baseline-policy',action='store_true');a=q.parse_args();s=a.simulator;o=a.output
 if o.exists() or not o.resolve().is_relative_to(s.resolve()) or shutil.disk_usage(s).free<1024**3:raise ValueError('Fresh private output and 1 GiB free required')
 root=Path(__file__).parent;baseline=(s/'reset-memory-protection-research-01/baseline-memory-policy.cs').read_bytes();policy=baseline if a.baseline_policy else (root/'renode-memory-policy.cs').read_bytes();nvic=(root/'renode-reset-aware-nvic.cs').read_bytes()
 if hashlib.sha256(baseline).hexdigest()!='330182ef865a41085daf853a2e5a8678049db8dd4fe2314fb3fe851939880d29' or (s/'cpu-retention-preparation-native-06/strict.cs').read_bytes().count(baseline)!=1 or (s/'cpu-retention-preparation-native-06/activation.cs').read_bytes().count(nvic)!=1:raise ValueError('Baseline policy/NVIC differ from original application runs')
 o.mkdir(mode=0o700,parents=True);compiled=o/'compiled';compiled.mkdir();(compiled/'fixture.c').write_text(SOURCE);(compiled/'fixture.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.comment*) } }\n')
 for mode,_,_ in CASES.values():
  execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-O1','-Wl,--nmagic','-ffreestanding','-fno-builtin','-nostdlib','-DMODE='+str(mode),'-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(compiled/'fixture.ld'),str(compiled/'fixture.c'),'-o',str(compiled/('mode-'+str(mode)+'.elf'))],compiled,'compile-'+str(mode))
 plan=[(name,target,'device-aircr',True) for name in CASES for target in (1,2)]+[(name,2,'guest-aircr',True) for name in ('main-byte','unwritten-itcm','retained-itcm','padding-read')]+[(name,2,'device-aircr',False) for name in ('main-byte','unwritten-itcm','padding-execute','sram-execute')]
 results=[]
 for name,target,method,guarded in plan:
  mode=CASES[name][0];cap=o/(name+'-'+str(target)+'-'+method+'-'+str(guarded).lower());cap.mkdir();(cap/'fixture.elf').write_bytes((compiled/('mode-'+str(mode)+'.elf')).read_bytes());(cap/'memory-policy.cs').write_bytes(policy);(cap/'reset-aware-nvic.cs').write_bytes(nvic)
  (cap/'seed-itcm.bin').write_bytes(struct.pack('<I',0x47702009));(cap/'seed-main.bin').write_bytes(struct.pack('<I',0xa1b2c3d4));(cap/'seed-padding.bin').write_bytes(struct.pack('<I',0x47702009))
  board='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    InitVectorTableOffset: 0x438000\n    PerformanceInMips: 1\nnvic: Miscellaneous.BlackwallResetAwareNVIC @ sysbus 0xe000e000\n    -> cpu@0\nmain: Memory.MappedMemory @ sysbus 0x438000\n    size: 0x3c0000\nitcm: Memory.MappedMemory @ sysbus 0\n    size: 0x40000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\n'
  (cap/'board.repl').write_text(board);script=SCRIPT.replace('__TARGET__',str(target)).replace('__GUARDED__',str(guarded)).replace('__METHOD__',method).replace('__MODE__',str(mode));(cap/'run.py').write_text(script)
  (cap/'probe.resc').write_text('include @/work/memory-policy.cs\ninclude @/work/reset-aware-nvic.cs\nmach create "reset-memory"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/fixture.elf\nsysbus LoadBinary @/work/seed-itcm.bin 0x100\nsysbus LoadBinary @/work/seed-itcm.bin 0x20010000\nsysbus LoadBinary @/work/seed-main.bin 0x438800\nsysbus LoadBinary @/work/seed-padding.bin 0x439000\ncpu VectorTableOffset 0x438000\ninclude @/work/run.py\nquit\n')
  log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={cap},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],cap,'renode',timeout=30)
  values=[json.loads(x.split('BLACKWALL_RESET_MEMORY ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RESET_MEMORY ')]
  if len(values)!=1:raise ValueError('Missing reset memory result; preserve '+str(cap))
  v=validate(values[0]);(cap/'report.json').write_text(json.dumps(v,indent=2)+'\n');results.append(dict(case=cap.name,**v));print(json.dumps(dict(case=cap.name,passed=v['passed'],operation=v['observed']['after']['policy']['operation'] if guarded else 'unguarded')),flush=True)
 report=dict(passed=all(x['passed'] for x in results),cases=results,policy_sha256=hashlib.sha256(policy).hexdigest(),nvic_sha256=hashlib.sha256(nvic).hexdigest(),image=RENODE_IMAGE,original_g2_executed=False,hardware_accessed=False)
 (o/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
