"""Exercise guest stores and instruction execution against the Renode memory policy."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--unguarded-control', action='store_true')
    parser.add_argument('--case', action='append')
    parser.add_argument('--image', default='blackwall-renode:1.17.0-local')
    args = parser.parse_args()
    selections = {
        'main-write-byte': (1, 'write-main', 0),
        'main-write-word': (2, 'write-main', 0),
        'main-write-dword': (3, 'write-main', 0),
        'unwritten-itcm': (4, 'execute-unwritten-itcm', 2),
        'guest-written-itcm': (5, None, 0),
        'partial-itcm-instruction': (6, 'execute-unwritten-itcm', 4),
        'main-padding-read': (7, 'read-main-padding', 4),
        'main-padding-execute': (8, 'execute-outside-code', 2),
        'rewritten-itcm': (10, None, 0),
        'rewrite-expands-instruction': (11, 'execute-unwritten-itcm', 4),
        'sram-execute': (9, 'execute-outside-code', 2),
        'boot-code-execute': (12, None, 0),
        'boot-write-byte': (13, 'write-boot', 0),
        'boot-padding-read': (14, 'read-boot-padding', 4),
        'boot-padding-execute': (15, 'execute-outside-code', 2),
        'boot-partial-instruction': (16, 'execute-outside-code', 4),
    }
    if args.case:
        if set(args.case)-selections.keys():
            raise ValueError('Unknown case')
        selections = {k:v for k,v in selections.items() if k in args.case}
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    image_id = subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',
        args.image],text=True,timeout=15).strip()
    cases = {}
    for name,(mode,operation,width) in selections.items():
        directory = output/name
        directory.mkdir(mode=0o700)
        boot_case = mode >= 12
        shutil.copy2(ROOT/'tests/fixtures/renode-main-minimal.repl',directory/'board.repl')
        if boot_case:
            with (directory/'board.repl').open('a') as f:
                f.write('\nboot: Memory.MappedMemory @ sysbus 0x410000\n    size: 0x28000\n')
        shutil.copy2(ROOT/'tools/renode-strict-mmio.cs',directory/'strict.cs')
        if not args.unguarded_control:
            with (directory/'strict.cs').open('a') as f:
                f.write('\n'+(ROOT/'tools/renode-memory-policy.cs').read_text())
        (directory/'fixture.c').write_text('''#include <stdint.h>
void reset(void) {
 volatile uint32_t *sentinel=(volatile uint32_t*)0x20000000;
 volatile uint32_t *result=(volatile uint32_t*)0x20000004;
 *sentinel=0x11112222;
#if MODE == 1
 *(volatile uint8_t*)0x438800=0x5a;
#elif MODE == 2
 *(volatile uint16_t*)0x438800=0x5a5a;
#elif MODE == 3
 *(volatile uint32_t*)0x438800=0x5a5a5a5a;
#elif MODE == 4
 *result=((uint32_t(*)(void))0x101)();
#elif MODE == 5
 *(volatile uint32_t*)0x100=0x47702007;
 *result=((uint32_t(*)(void))0x101)();
#elif MODE == 6
 *(volatile uint16_t*)0x100=0xf240;
 *result=((uint32_t(*)(void))0x101)();
#elif MODE == 7
 *result=*(volatile uint32_t*)0x439000;
#elif MODE == 8
 ((void(*)(void))0x439001)();
#elif MODE == 10
 *(volatile uint32_t*)0x100=0x47702007;
 ((uint32_t(*)(void))0x101)();
 *(volatile uint8_t*)0x100=9;
 *result=((uint32_t(*)(void))0x101)();
#elif MODE == 11
 *(volatile uint16_t*)0x100=0x4770;
 ((void(*)(void))0x101)();
 *(volatile uint16_t*)0x100=0xf240;
 ((void(*)(void))0x101)();
#elif MODE == 9
 ((void(*)(void))0x20010001)();
#elif MODE == 12
 *result=((uint32_t(*)(void))0x410101)();
#elif MODE == 13
 *(volatile uint8_t*)0x410800=0x5a;
#elif MODE == 14
 *result=*(volatile uint32_t*)0x411000;
#elif MODE == 15
 ((void(*)(void))0x411001)();
#elif MODE == 16
 ((void(*)(void))0x410fff)();
#endif
 *sentinel=0x33334444;
 for(;;){}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[]={0x2007fb00,(uintptr_t)reset};
''')
        (directory/'fixture.ld').write_text('ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.comment*) } }\n')
        execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb',
            '-O1','-Wl,--nmagic','-ffreestanding','-fno-builtin','-nostdlib','-DMODE='+str(mode),
            '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(directory/'fixture.ld'),
            str(directory/'fixture.c'),'-o',str(directory/'fixture.elf')],directory,'compiler')
        (directory/'itcm-seed.bin').write_bytes(bytes.fromhex('07207047'))
        if boot_case:
            boot = bytearray(0x1000)
            boot[0x100:0x104] = bytes.fromhex('07207047')
            boot[-2:] = bytes.fromhex('40f2')
            (directory/'boot-seed.bin').write_bytes(boot)
        (directory/'result.py').write_text('''import json
from System import Console
m=monitor.Machine
policy=None
if %s:
    p=memory_policy
    policy=dict(violations=int(p.Violations),operation=str(p.LastOperation),address=int(p.LastAddress),
        width=int(p.LastWidth),pc=int(p.LastPC),written_bytes=int(p.WrittenBytes))
Console.WriteLine('BLACKWALL_MEMORY '+json.dumps(dict(policy=policy,
    sentinel=int(m.SystemBus.ReadDoubleWord(0x20000000)),result=int(m.SystemBus.ReadDoubleWord(0x20000004)),
    main_word=int(m.SystemBus.ReadDoubleWord(0x438800)),
    boot_word=int(m.SystemBus.ReadDoubleWord(0x410800)) if %s else None)))
''' % (not args.unguarded_control, boot_case))
        result_script=(directory/'result.py').read_text()
        setup="""import time
from System import Console
m=monitor.Machine
"""
        if not args.unguarded_control:
            setup+="""import clr
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy
memory_policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],0x1000)
"""
            if boot_case:
                setup+="memory_policy.BindBootImage(m['sysbus.boot'],0x1000)\n"
            setup+="memory_policy.Attach()\n"
        setup+="from Antmicro.Renode.Core import EmulationManager\ne=EmulationManager.Instance.CurrentEmulation\ne.StartAll()\ntime.sleep(0.3)\ne.PauseAll()\n"+result_script
        (directory/'run.py').write_text("try:\n"+''.join('    '+line+'\n' for line in setup.splitlines())+
            "except Exception as e:\n    from System import Console\n    Console.WriteLine('POLICY_ERROR '+str(e))\n")
        (directory/'probe.resc').write_text("""include @/work/strict.cs
mach create "blackwall-memory-test"
machine LoadPlatformDescription @/work/board.repl
sysbus LoadELF @/work/fixture.elf
sysbus LoadBinary @/work/itcm-seed.bin 0x100
%s
cpu VectorTableOffset 0x438000
include @/work/run.py
quit
""" % ('sysbus LoadBinary @/work/boot-seed.bin 0x410000' if boot_case else ''))
        log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--mount',
            f'type=bind,source={directory},target=/work,readonly',image_id,
            '--disable-gui','--hide-monitor','-p','/work/probe.resc'],directory,'renode')
        lines=[line.partition('BLACKWALL_MEMORY ')[2] for line in log.splitlines() if line.startswith('BLACKWALL_MEMORY ')]
        if len(lines)!=1:
            raise ValueError('Missing result: '+name)
        observed=json.loads(lines[0]); p=observed['policy']
        passed=(p is not None and p['violations']==(1 if operation else 0)
            and p['operation']==(operation or 'none') and p['width']==width
            and observed['main_word']==0 and observed['sentinel']==(0x11112222 if operation else 0x33334444)
            and observed['result']==(0 if operation else 9 if mode==10 else 7))
        if boot_case:
            passed=passed and observed['boot_word']==0
        if passed and mode in (5,10):
            passed=p['written_bytes']==4
        if passed and mode in (6,11):
            passed=p['written_bytes']==2
        if passed and operation:
            expected_address=(0x438800 if mode in (1,2,3) else 0x100 if mode in (4,6,11)
                              else 0x439000 if mode in (7,8) else 0x410800 if mode==13
                              else 0x411000 if mode in (14,15) else 0x410ffe if mode==16
                              else 0x20010000)
            passed=p['address']==expected_address and p['pc']!=0
        unexpected=[]
        for line in log.splitlines():
            lower=line.lower()
            if (('[warning]' in lower and 'translation cache size' not in lower)
                or ('[error]' in lower and not (p is not None and p['violations']==1 and 'this machine has aborted' in lower))
                or 'policy_error' in lower):
                unexpected.append(line)
        passed=passed and not unexpected
        cases[name]=dict(passed=passed,observed=observed,unmodeled_engine_messages=unexpected)
        print(name,'passed' if passed else 'FAILED',flush=True)
    report=dict(cases=cases,passed=all(c['passed'] for c in cases.values()),image_id=image_id,
        unguarded_control=args.unguarded_control,hardware_validated=False)
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
