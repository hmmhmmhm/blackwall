"""Run a synthetic M55 guest through UART1 IRQ16 twice; never load G2 firmware."""
import argparse
import json
import re
from pathlib import Path
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
GUEST = r'''
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
static volatile uint32_t *const result=(void*)0x20000000;
void irq(void) {
    uint32_t cause=R(0x4003a040), active;
    __asm__ volatile("mrs %0, ipsr":"=r"(active));
    result[1]|=cause; result[3]=active;
    R(0x4003a044)=cause;
    result[0]++;
}
void reset(void) {
    __asm__ volatile("cpsid i":::"memory");
    for(int i=0;i<4;i++) result[i]=0;
    R(0x4003a02c)=0x70; R(0x4003a030)=0x319;
    R(0xe000e100)=1u<<16;
    R(0x4003a038)=0x20;
    __asm__ volatile("cpsie i":::"memory");
    while(result[0]!=1) {}
    R(0x4003a038)=1; R(0x4003a000)='Z';
    while(result[0]!=2) {}
    result[2]=0x1234;
    for(;;) __asm__ volatile("wfi");
}
__attribute__((section(".vectors"),used)) const void *vectors[33]={
    [0]=(void*)0x2007f000,[1]=reset,[32]=irq
};
'''
DRIVER='''import time,json
from Antmicro.Renode.Core import EmulationManager
from System import Console
m=monitor.Machine
g=m['sysbus.guard'];u=g.Uarts[1]
g.UartPowers[1].TryWrite(0x400,True);g.UartPowers[1].ReadStatus()
address=int(m.SystemBus.ReadDoubleWord(0x438080))&~1
u.AttachIrqProbe(m['sysbus.cpu'],address,m)
e=EmulationManager.Instance.CurrentEmulation;e.StartAll();time.sleep(1);e.PauseAll()
Console.WriteLine('BLACKWALL_CPU_IRQ '+json.dumps(dict(words=[int(m.SystemBus.ReadDoubleWord(0x20000000+4*i)) for i in range(4)],tx=[int(b) for b in u.TxBytes],entries=int(u.IrqHandlerEntries),exceptions=int(u.IrqExceptionEntries),active=int(u.LastActiveVector),irq=bool(u.IRQ.IsSet),assertions=int(u.IRQAssertions))))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--module',type=int,default=1,choices=range(4))
    args=parser.parse_args()
    board=args.board.read_text().replace('BlackwallUart1Adapter','BlackwallUartAdapter')
    module=args.module
    if '    uart%s: uart%s_adapter'%(module,module) not in board:raise ValueError('Selected UART not enabled in input board')
    match=re.search(r'(?m)^uart%s_adapter: [^\n]+\n(?:[ \t]+[^\n]*\n|\n)*'%module,board)
    if not match:raise ValueError('Selected UART adapter missing')
    block=re.sub(r'(?m)^    (?:interrupts:.*|IRQ -> .*)\n','',match.group())
    block+='    interrupts: true\n    IRQ -> nvic@%s\n'%(15+module)
    board=board[:match.start()]+block+board[match.end():]
    guest=GUEST.replace('0x4003a','0x400%02x'%(0x39+module)).replace('1u<<16','1u<<%s'%(15+module)).replace('vectors[33]','vectors[%s]'%(32+module)).replace('[32]=irq','[%s]=irq'%(31+module))
    driver=DRIVER.replace('g.Uarts[1]','g.Uarts[%s]'%module).replace('g.UartPowers[1]','g.UartPowers[%s]'%module).replace('0x400,True','%s,True'%(0x200<<module)).replace('0x438080',hex(0x438000+(31+module)*4))
    out=args.output.resolve();out.mkdir(mode=0o700)
    names=['renode-strict-mmio.cs','renode-memory-policy.cs','renode-system-control.cs','renode-reset-controller.cs','renode-watchdog.cs']
    (out/'strict.cs').write_text('\n'.join((ROOT/'tools'/n).read_text() for n in names))
    (out/'board.repl').write_text(board);(out/'guest.c').write_text(guest)
    (out/'guest.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) } }\n')
    execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-mfloat-abi=soft','-nostdlib','-ffreestanding','-O1','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(out/'guest.ld'),str(out/'guest.c'),'-o',str(out/'guest.elf')],out,'compile')
    (out/'run.py').write_text(driver)
    (out/'probe.resc').write_text('include @/work/strict.cs\nmach create "uart-irq-cpu"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/guest.elf\ncpu VectorTableOffset 0x438000\ninclude @/work/run.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode')
    rows=[json.loads(x.split('BLACKWALL_CPU_IRQ ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_CPU_IRQ ')]
    assert len(rows)==1
    expected=dict(words=[2,0x21,0x1234,31+module],tx=[90],entries=2,exceptions=2,active=31+module,irq=False,assertions=2)
    report=dict(observed=rows[0],expected=expected,passed=rows[0]==expected,scope='synthetic guest and seeded UART power; not actual main or physical UART')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    assert report['passed']


if __name__=='__main__':main()
