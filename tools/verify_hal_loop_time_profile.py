"""Isolated original ARM HAL delays and independent peripheral clocks; no G2 boot claim."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

CALLER=r'''#include <stdint.h>
#define M ((volatile uint32_t *)0x20000000)
__attribute__((naked,noinline)) void invoke(uint32_t us){__asm volatile("push {r4,lr}\nldr r3,=0x495e89\nblx r3\n.global delay_return\ndelay_return:\npop {r4,pc}");}
void fault(void){uint32_t n;__asm volatile("mrs %0,ipsr":"=r"(n));M[15]=n;for(;;){}}
void reset(void){
 *(volatile uint32_t *)0xe000ed88=0xf00000;__asm volatile("dsb\nisb");
 const uint32_t args[]={0,1,5,50,1000};
 M[0]=1;
 for(unsigned i=0;i<5;i++){M[1]=i;invoke(args[i]);M[2]++;}
 M[0]=0x600d;
 __asm volatile(".global probe_ready\nprobe_ready:");
 for(;;){__asm volatile("nop");}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[64]={0x20010000,(uintptr_t)reset,(uintptr_t)fault,(uintptr_t)fault,(uintptr_t)fault,(uintptr_t)fault,(uintptr_t)fault};
'''
OBSERVER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
 using System.Collections.Generic;using Antmicro.Renode.Time;using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.CPU;
 public sealed class BlackwallHalDelayTimeObserver {
  public BlackwallHalDelayTimeObserver(IMachine machine,CortexM cpu,ulong returned,ulong readyPc) {
   this.cpu=cpu;this.readyPc=readyPc;
   foreach(uint rate in new uint[]{10,64,167}) {
    for(ulong n=1;n<=rate;n++) { ulong remainder;var t=TimeInterval.FromCPUCycles(n,rate,out remainder);
     if(t.Ticks>0){QuantumProbes.Add(new ulong[]{rate,n,t.Ticks,remainder});break;}
    }
   }
   cpu.AddHook(0x495e88,(c,a)=>{startInstructions=cpu.ExecutedInstructions;startTicks=machine.ElapsedVirtualTime.TimeElapsed.Ticks;argument=cpu.GetRegister(0).RawValue;});
   cpu.AddHook(returned,(c,a)=>Rows.Add(new ulong[]{argument,startInstructions,cpu.ExecutedInstructions,startTicks,machine.ElapsedVirtualTime.TimeElapsed.Ticks}));
   ready=(c,a)=>{machine.Pause();Ready=true;};cpu.AddHook(readyPc,ready);
  }
  public void Release(){cpu.RemoveHook(readyPc,ready);}
  public List<ulong[]> QuantumProbes {get;}=new List<ulong[]>();
  public List<ulong[]> Rows {get;}=new List<ulong[]>();public bool Ready {get;private set;}
  private ulong startInstructions,startTicks,argument;private readonly CortexM cpu;private readonly ulong readyPc;private readonly CpuAddressHook ready;
 }
}
'''
SCRIPT='''import clr,time,json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallHalDelayTimeObserver').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallHalDelayTimeObserver
m=monitor.Machine;b=m.SystemBus;c=m['sysbus.cpu'];g=m['sysbus.guard'];w=m['sysbus.wdt'];s=g.Stimer
o=BlackwallHalDelayTimeObserver(m,c,RETURNED,READY)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+15
while not o.Ready and time.time()<deadline:time.sleep(0.001)
if not o.Ready:raise ValueError('Original HAL caller did not complete')
m.Pause();delay_rows=[[int(v) for v in row] for row in o.Rows];mail=[int(b.ReadDoubleWord(0x20000000+4*i)) for i in range(16)]
o.Release();EmulationManager.Instance.CurrentEmulation.PauseAll()
g.WriteDoubleWord(0x7800,0x40000003);g.WriteDoubleWord(0x7800,3)
w.WriteDoubleWord(0,0x02010003)
start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);instructions=int(c.ExecutedInstructions)
EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMilliseconds(200))
r=dict(quantum_probes=[[int(v) for v in row] for row in o.QuantumProbes],delay_rows=delay_rows,mail=mail,guard_accesses=int(g.AccessCount),wdt_accesses=int(w.AccessCount),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),start_ticks=start,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),spin_instructions=int(c.ExecutedInstructions)-instructions,stimer=dict(config=int(s.Config),count=int(s.Counter),frequency=int(s.Frequency)),watchdog=dict(count=int(w.ReadDoubleWord(12)),interrupt_events=int(w.InterruptEvents),pending=bool(w.InterruptPending),irq=bool(w.IRQ.IsSet),reset_due=bool(w.ResetDue)),original_hal_executed=True,synthetic_caller=True,full_main_boot=False,hardware_accessed=False)
Console.WriteLine('BLACKWALL_HAL_TIME '+json.dumps(r))
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(s,o,mode,baseline):
 if o.exists() or not o.resolve().is_relative_to(s.resolve()):raise ValueError('Fresh private output required')
 o.mkdir(mode=0o700,parents=True);ref=s/'gaf-delay-clock-native-02';pins=json.loads((ref/'connection-inputs.json').read_text())
 for n in ('main.bin','strict.cs'):
  if sha(ref/n)!=pins[n]:raise ValueError('Changed parent '+n)
  if subprocess.run(['cp','-c',str(ref/n),str(o/n)],capture_output=True).returncode:shutil.copyfile(ref/n,o/n)
 mips=10
 if not baseline:
  from hal_loop_time_profile import profile
  meta=profile(mode);mips=meta['mips']
 else:meta=dict(name='legacy-10-mips-control',mips=10,mode=mode,physical_clock_verified=False)
 (o/'profile.json').write_text(json.dumps(meta,indent=2)+'\n')
 (o/'caller.c').write_text(CALLER);(o/'caller.ld').write_text((Path(__file__).resolve().parents[1]/'tests/fixtures/m55-exceptions-smoke.ld').read_text().replace('0x00000000','0x00010000'))
 execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-O1','-ffreestanding','-fno-builtin','-nostdlib','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(o/'caller.ld'),str(o/'caller.c'),'-o',str(o/'caller.elf')],o,'compiler')
 nm=subprocess.check_output(['/opt/homebrew/opt/llvm@21/bin/llvm-nm','--defined-only',str(o/'caller.elf')],text=True);(o/'symbols.txt').write_text(nm);symbols={line.split()[2]:int(line.split()[0],16) for line in nm.splitlines() if len(line.split())==3}
 loop=bytes(json.loads((ref/'exports/delay-path.json').read_text())['itcm_bytes'])[:6]
 if loop.hex()!='0138fdd17047':raise ValueError('Changed original ITCM loop')
 (o/'delay-itcm.bin').write_bytes(loop)
 with (o/'strict.cs').open('a') as f:f.write('\n'+OBSERVER)
 board=f'cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: {mips}\n    InitVectorTableOffset: 0x10000\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\ncaller: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x10000\nitcm: Memory.MappedMemory @ sysbus 0\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x10000\nmain: Memory.MappedMemory @ sysbus 0x438000\n    size: '+hex(((o/'main.bin').stat().st_size+4095)//4096*4096)+'\nstimer: Miscellaneous.BlackwallStimerClockCounter @ none\n    profile: "nominal-source-clocks"\nguard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000\n    baseAddress: 0x40001000\n    size: 0x23000\n    powerMode: "'+mode+'"\n    stimer: stimer\nwdt: Miscellaneous.BlackwallApollo510Watchdog @ sysbus 0x40024000\n'
 (o/'board.repl').write_text(board);(o/'run.py').write_text(SCRIPT.replace('RETURNED',str(symbols['delay_return'])).replace('READY',str(symbols['probe_ready'])));compile((o/'run.py').read_text(),'generated-run.py','exec')
 (o/'probe.resc').write_text('include @/work/strict.cs\nmach create\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/main.bin 0x438000\nsysbus LoadBinary @/work/delay-itcm.bin 0x40\nsysbus LoadELF @/work/caller.elf\ninclude @/work/run.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=60,stream=True)
 rows=[json.loads(l.split('BLACKWALL_HAL_TIME ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_HAL_TIME ')]
 if len(rows)!=1:raise ValueError('Missing actual HAL run result')
 r=rows[0]
 quantum=next(x[2] for x in r['quantum_probes'] if x[0]==mips)
 delays=[dict(request_us=x[0],instructions=x[2]-x[1],virtual_ns=x[4]-x[3],instruction_equivalent_ns=(x[2]-x[1])*1000/mips,raw_clock_within_calibration_window=abs((x[4]-x[3])/1000-x[0])<=max(.3,x[0]*.01),within_calibration_window=abs((x[2]-x[1])/mips-x[0])<=max(.3,x[0]*.01),quantized_clock_consistent=abs((x[4]-x[3])-(x[2]-x[1])*1000/mips)<quantum) for x in r['delay_rows']]
 checks=dict(returned=r['mail'][0]==0x600d and r['mail'][2]==5 and r['mail'][15]==0,all_arguments=[x['request_us'] for x in delays]==[0,1,5,50,1000],hal_delay_calibration=all(x['within_calibration_window'] for x in delays),quantized_clock_consistent=all(x['quantized_clock_consistent'] for x in delays),native_quantum_contract=r['quantum_probes']==[[10,1,100,0],[64,8,125,0],[167,167,1000,0]],fault_free=r['cfsr']==r['hfsr']==r['guard_accesses']==r['wdt_accesses']==0,two_hundred_ms=r['end_ticks']-r['start_ticks']==200000000,stimer_independent=r['stimer']==dict(config=3,count=6553,frequency=32768),watchdog_independent=r['watchdog']==dict(count=3,interrupt_events=1,pending=True,irq=False,reset_due=False),cpu_kept_executing=r['spin_instructions']>1000000)
 result=dict(measurement_protocol='retired-instructions-plus-native-time-quantization-v2',calibration_window_us=dict(absolute=.3,relative=.01),passed=all(checks.values()),checks=checks,profile=meta,delays=delays,observed=r,original_main_boot=False,hardware_accessed=False)
 (o/'report.json').write_text(json.dumps(result,indent=2)+'\n');(o/'files.json').write_text(json.dumps({p.name:sha(p) for p in o.iterdir() if p.is_file() and p.name!='files.json'},indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=checks,delays=delays)),flush=True)
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--mode',choices=['lp','hp'],required=True);p.add_argument('--baseline',action='store_true');a=p.parse_args();run(a.simulator,a.output,a.mode,a.baseline)
