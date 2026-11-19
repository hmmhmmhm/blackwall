"""Compare read-only observer context with M55 guest MRS/MSR stack selection."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from run_renode_m55_probe import execute


ASM = '''.syntax unified
.cpu cortex-m55
.thumb
.section .vectors,"a"
.word 0x2007fb00
.word reset
.section .text,"ax"
.global reset,psp_point,msp_point,done_point
.thumb_func
reset:
 mrs r0,msp
 ldr r1,=0x20000100
 str r0,[r1]
 ldr r0,=0x20001000
 msr psp,r0
 movs r0,#2
 msr control,r0
 isb
 b psp_point
.thumb_func
psp_point:
 mrs r0,psp
 str r0,[r1,#4]
 movs r0,#0
 msr control,r0
 isb
 b msp_point
.thumb_func
msp_point:
 mrs r0,msp
 str r0,[r1,#8]
.thumb_func
done_point:
 wfi
 b done_point
'''

SETUP = '''import json,clr
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallExecutionObserver').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallExecutionObserver
m=monitor.Machine;cpu=m['sysbus.cpu'];checks=[];setup_error=None
def check(name,condition):
 if not condition:raise Exception(name)
 checks.append(name)
def rejected(name,action):
 try:action()
 except Exception:checks.append(name);return
 raise Exception(name+' accepted')
try:
 observer=BlackwallExecutionObserver(cpu,16)
 for label in ('reset','psp_point','msp_point'):
  observer.AddPoint(label,SYMBOLS[label]);observer.CaptureCpuContext(label)
 observer.AddPoint('done_point',SYMBOLS['done_point'])
 rejected('missing-point-rejected',lambda:observer.CaptureCpuContext('missing'))
 rejected('duplicate-context-rejected',lambda:observer.CaptureCpuContext('reset'))
except Exception as error:setup_error=str(error)
'''

RESULT = '''try:
 if setup_error is not None:raise Exception(setup_error)
 rows={}
 for point in observer.Points:
  c=point.Context
  if c is None:
   check('default-context-off',point.Label=='done_point');continue
  rows[str(point.Label)]=dict(pc=int(c.PC),sp=int(c.SP),msp=int(c.MSP),psp=int(c.PSP),control=int(c.Control),xpsr=int(c.Xpsr),vtor=int(c.VectorTableOffset),process_stack_selected=bool(c.ProcessStackSelected))
 check('three-contexts',len(rows)==3)
 for label in rows:
  c=rows[label];check(label+'-pc-vtor',c['pc']==SYMBOLS[label] and c['vtor']==0x438000)
  check(label+'-main-sp',c['msp']==0x2007fb00)
  check(label+'-thread-mode',c['xpsr']&511==0)
 check('reset-active-msp',rows['reset']['sp']==0x2007fb00 and not rows['reset']['process_stack_selected'])
 check('guest-selects-psp',rows['psp_point']['sp']==rows['psp_point']['psp']==0x20001000 and rows['psp_point']['control']&3==2 and rows['psp_point']['process_stack_selected'])
 check('guest-restores-msp',rows['msp_point']['sp']==0x2007fb00 and rows['msp_point']['control']&3==0 and not rows['msp_point']['process_stack_selected'])
 words=[int(m.SystemBus.ReadDoubleWord(0x20000100+i*4)) for i in range(3)]
 check('guest-mrs-agrees',words==[rows['reset']['msp'],rows['psp_point']['psp'],rows['msp_point']['msp']])
 rejected('late-context-rejected',lambda:observer.CaptureCpuContext('done_point'))
 result=dict(passed=True,checks=checks,contexts=rows,guest_mrs=words)
except Exception as error:result=dict(passed=False,checks=checks,error=str(error))
Console.WriteLine('BLACKWALL_OBSERVER_CONTEXT '+json.dumps(result))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--observer', type=Path, default=Path(__file__).with_name('renode-execution-observer.cs'))
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700)
    shutil.copy2(args.observer, out / 'observer.cs')
    (out / 'fixture.S').write_text(ASM)
    (out / 'fixture.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.comment*) } }\n')
    compiler = ['/opt/homebrew/opt/llvm@21/bin/clang', '--target=arm-none-eabi', '-mcpu=cortex-m55', '-mthumb', '-nostdlib', '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld', '-Wl,-T,'+str(out/'fixture.ld'), str(out/'fixture.S'), '-o', str(out/'fixture.elf')]
    execute(compiler, out, 'compiler')
    symbols_text = subprocess.run(['/opt/homebrew/opt/llvm@21/bin/llvm-nm', str(out/'fixture.elf')], capture_output=True, text=True, check=True).stdout
    symbols = {name: int(value, 16) & ~1 for value, name in re.findall(r'(?m)^([0-9a-fA-F]+)\s+[Tt]\s+(\w+)$', symbols_text)}
    (out/'setup.py').write_text('SYMBOLS='+repr(symbols)+'\n'+SETUP)
    (out/'result.py').write_text(RESULT)
    (out/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\n    IRQ -> cpu@0\nmain: Memory.MappedMemory @ sysbus 0x438000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\n')
    (out/'probe.resc').write_text('include @/work/observer.cs\nmach create "observer-context"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/fixture.elf\ncpu VectorTableOffset 0x438000\ninclude @/work/setup.py\nemulation RunFor "0.001"\ninclude @/work/result.py\nquit\n')
    command = ['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly',args.image,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    (out/'launcher.json').write_text(json.dumps(dict(compiler=compiler,command=command),indent=2)+'\n')
    log = execute(command, out, 'renode', timeout=120, stream=True)
    rows = [json.loads(line.split('BLACKWALL_OBSERVER_CONTEXT ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_OBSERVER_CONTEXT ')]
    report = dict(passed=len(rows)==1 and rows[0]['passed'],rows=rows,image_id=args.image,observer_sha256=hashlib.sha256((out/'observer.cs').read_bytes()).hexdigest(),scope='Synthetic M55 guest MRS/MSR test; not original firmware or physical hardware')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],checks=sum(len(r['checks']) for r in rows))))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
