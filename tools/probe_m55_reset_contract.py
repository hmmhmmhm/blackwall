"""Synthetic M55 guest tests device SYSRESETREQ, vector initialization and reset mask state."""
import argparse
import json
from pathlib import Path
from run_renode_m55_probe import execute
from native_replay import IMAGE

ASM='''.syntax unified
.thumb
.cpu cortex-m55
.section .vectors,"a",%progbits
.word 0x20001000
.word reset
.rept 14
.word trap
.endr
.word irq0
.section .text,"ax",%progbits
.global reset, irq0, trap
.thumb_func
reset:
 ldr r4, =0x20000000
 ldr r0, [r4]
 adds r0, #1
 str r0, [r4]
 ldr r1, =0xe000e400
 movs r2, #0x80
 strb r2, [r1]
 ldr r1, =0xe000e100
 movs r2, #1
 str r2, [r1]
 cmp r0, #1
 bne capture
 ldr r0, [r4, #16]
 cmp r0, #1
 beq set_primask
 msr basepri, r0
 b capture
set_primask:
 cpsid i
capture:
 mrs r0, basepri
 str r0, [r4, #8]
 mrs r0, primask
 str r0, [r4, #12]
loop:
 ldr r0, [r4, #20]
 cmp r0, #0
 beq loop
 movs r0, #0
 str r0, [r4, #20]
 ldr r0, =0x05fa0004
 ldr r1, =0xe000ed0c
 str r0, [r1]
 dsb
 b loop
.thumb_func
irq0:
 ldr r0, =0x20000004
 ldr r1, [r0]
 adds r1, #1
 str r1, [r0]
 bx lr
.thumb_func
trap:
 b trap
'''

SCRIPT='''import clr,json
from System import Console
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Time import TimeInterval
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];nvic=m['sysbus.nvic'];e=EmulationManager.Instance.CurrentEmulation
def run():e.RunFor(TimeInterval.FromMilliseconds(1))
def state():return dict(words=[int(b.ReadDoubleWord(0x20000000+4*k)) for k in range(9)],cached_basepri=int(nvic.BASEPRI_NS),pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),vtor=int(cpu.VectorTableOffset),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),cfsr=int(b.ReadDoubleWord(0xe000ed28)),implementation=str(nvic.GetType().FullName),reset_completions=int(nvic.ResetCompletions) if hasattr(nvic,'ResetCompletions') else 0)
b.WriteDoubleWord(0x20000010,__MODE__);b.WriteDoubleWord(0x20000020,0xcafebabe)
run();first=state();nvic.OnGPIO(0,True);run();masked=state();nvic.OnGPIO(0,False)
if '__METHOD__'=='guest-aircr':b.WriteDoubleWord(0x20000014,1);run()
else:m.Reset();run()
reboot=state();nvic.OnGPIO(0,True);run();after=state();nvic.OnGPIO(0,False)
Console.WriteLine('BLACKWALL_M55_RESET '+json.dumps(dict(mode=__MODE__,method='__METHOD__',init_vector=__INIT__,first=first,masked=masked,reboot=reboot,after=after,original_firmware_executed=False,hardware_accessed=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--reset-aware',action='store_true');a=p.parse_args();o=a.output;o.mkdir(mode=0o700,parents=True,exist_ok=False)
    (o/'guest.s').write_text(ASM);(o/'guest.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { *(.vectors) } .text : { *(.text*) } }\n')
    execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-nostdlib','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(o/'guest.ld'),str(o/'guest.s'),'-o',str(o/'guest.elf')],o,'compiler')
    results=[]
    cases=[(method,mode,True) for method in ('machine-reset','guest-aircr') for mode in (0,0x50,1)]+[('machine-reset',0,False)]
    for method,mode,init in cases:
        cap=o/(method+'-'+str(mode)+'-'+str(init).lower());cap.mkdir(mode=0o700);(cap/'guest.elf').write_bytes((o/'guest.elf').read_bytes())
        board='cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\n'+('    InitVectorTableOffset: 0x438000\n' if init else '')+'nvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x438000\n    size: 0x1000\nitcm: Memory.MappedMemory @ sysbus 0x0\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\n'
        
        if a.reset_aware:
            board=board.replace('IRQControllers.NVIC @','Miscellaneous.BlackwallResetAwareNVIC @');(cap/'reset-aware-nvic.cs').write_bytes(Path(__file__).with_name('renode-reset-aware-nvic.cs').read_bytes())
        (cap/'board.repl').write_text(board);(cap/'test.py').write_text(SCRIPT.replace('__MODE__',str(mode)).replace('__METHOD__',method).replace('__INIT__',str(init)))
        (cap/'probe.resc').write_text(('include @/work/reset-aware-nvic.cs\n' if a.reset_aware else '')+'mach create "m55-reset"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/guest.elf\ncpu VectorTableOffset 0x438000\ninclude @/work/test.py\nquit\n')
        log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={cap},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],cap,'renode',timeout=60)
        rows=[json.loads(x.split('BLACKWALL_M55_RESET ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_M55_RESET ')]
        if len(rows)!=1:raise ValueError(log[-1700:])
        r=rows[0];results.append(r);(cap/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(method=method,mode=mode,init_vector=init,boot_count=r['after']['words'][0],architectural_basepri=r['after']['words'][2],cached_basepri=r['after']['cached_basepri'],irq_count=r['after']['words'][1])),flush=True)
    from verify_m55_reset_contract import verify
    verify(o,o/'audit',a.reset_aware)

if __name__=='__main__':main()
