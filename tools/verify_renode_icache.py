"""Verify strict cache boundaries and optional coherent instruction memory; no devices."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
LINKER='ENTRY(reset)\nSECTIONS { . = 0x438000; .vectors : { KEEP(*(.vectors)) } .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.comment*) } }\n'
CASES={
 'enable':(1,True,None,True,1,[0x20000,0]),
 'without-invalidation':(2,True,('write',0xe000ed14,4),False,0,[0,0]),
 'bad-command':(3,True,('write',0xe000ef50,4),False,0,[0,0]),
 'byte-command':(4,True,('write',0xe000ef50,1),False,0,[0,0]),
 'read-command':(5,True,('read',0xe000ef50,4),False,0,[0,0]),
 'dcache':(6,True,('write',0xe000ed14,4),False,0,[0,0]),
 'rewritten-itcm':(7,True,None,True,2,[7,9]),
 'partial-itcm':(8,True,'memory',True,1,[0,0]),
 'disable':(9,True,None,False,1,[0,0]),
 'repeat-invalidate':(10,True,None,True,2,[0x20000,0]),
 'default-strict':(11,False,('write',0xe000ef50,4),False,0,[0,0]),
 'partial-ccr':(12,True,('write',0xe000ed14,1),False,0,[0,0]),
 'other-ccr-field':(13,True,('write',0xe000ed14,4),False,0,[0,0]),
 'geometry-select':(14,True,('write',0xe000ed84,4),False,0,[0,0]),
 'geometry-read':(15,True,('read',0xe000ed80,4),False,0,[0,0]),
 'dcache-maintenance':(16,True,('write',0xe000ef60,4),False,0,[0,0]),
 'data-full':(100,True,None,True,1,[0xf03fe019,0x30000]),
 'data-bad-select':(102,True,('write',0xe000ed84,4),False,0,[0,0]),
 'data-read-before-select':(103,True,('read',0xe000ed80,4),False,0,[0,0]),
 'data-byte-select':(104,True,('write',0xe000ed84,1),False,0,[0,0]),
 'data-reserved-command':(105,True,('write',0xe000ef60,4),False,0,[0,0]),
 'data-no-sweep':(106,True,('write',0xe000ed14,4),False,0,[0,0]),
 'data-duplicate-sweep':(107,True,('write',0xe000ed14,4),False,0,[0,0]),
 'data-clean-only':(108,True,('write',0xe000ed14,4),False,0,[0,0]),
 'data-reenable':(109,True,('write',0xe000ed14,4),True,1,[0,0]),
 'data-clean-invalidate':(110,True,None,True,1,[0xf03fe019,0x30000]),
 'data-byte-command':(111,True,('write',0xe000ef60,1),False,0,[0,0]),
 'data-read-command':(112,True,('read',0xe000ef60,4),False,0,[0,0]),
 'data-write-geometry':(113,True,('write',0xe000ed80,4),False,0,[0,0]),
 'data-other-ccr':(114,True,('write',0xe000ed14,4),False,0,[0,0]),
 'data-default-strict':(115,True,('write',0xe000ed84,4),False,0,[0,0]),
 'data-write-main':(116,True,'write-main',True,1,[0,0]),
 'data-reserved-set':(117,True,('write',0xe000ef60,4),False,0,[0,0]),
 'data-default-read-command':(118,True,('read',0xe000ef60,4),False,0,[0,0]),
}
DATA_EXPECTED={
 'data-full':dict(enabled=True,initialized_lines=2048,invalidate_set_way=2048,clean_set_way=2048,clean_invalidate_set_way=2048),
 'data-duplicate-sweep':dict(enabled=False,initialized_lines=1,invalidate_set_way=2048),
 'data-clean-only':dict(enabled=False,initialized_lines=0,clean_set_way=2048),
 'data-reenable':dict(enabled=False,initialized_lines=0,invalidate_set_way=2048),
 'data-clean-invalidate':dict(enabled=True,initialized_lines=2048,clean_invalidate_set_way=2048),
 'data-write-main':dict(enabled=True,initialized_lines=2048,invalidate_set_way=2048),
}

def data_cache_enabled(name):
 return name.startswith('data-') and name not in ('data-default-strict','data-default-read-command')

def compile_fixture(directory,mode):
 (directory/'fixture.ld').write_text(LINKER)
 execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu='+('cortex-m4' if mode>=100 else 'cortex-m55'),'-mthumb',
  '-O1','-Wl,--nmagic','-ffreestanding','-fno-builtin','-nostdlib','-DMODE='+str(mode),
  '-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(directory/'fixture.ld'),
  str(ROOT/'tests/fixtures'/('renode-dcache-probe.c' if mode>=100 else 'renode-icache-probe.c')),'-o',str(directory/'fixture.elf')],directory,'compiler')

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('output',type=Path);parser.add_argument('--case',action='append');args=parser.parse_args()
 if args.case and set(args.case)-CASES.keys():raise ValueError('Unknown case')
 output=args.output.resolve();output.mkdir(mode=0o700)
 image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','blackwall-renode:1.17.0-local'],text=True,timeout=15).strip()
 rows={}
 for name,(mode,functional,violation,enabled,invalidations,results) in CASES.items():
  if args.case and name not in args.case:continue
  data_functional=data_cache_enabled(name)
  d=output/name;d.mkdir(mode=0o700);compile_fixture(d,mode)
  shutil.copy2(ROOT/'tests/fixtures/renode-main-minimal.repl',d/'board.repl')
  (d/'strict.cs').write_text('\n'.join((ROOT/'tools'/file).read_text() for file in ['renode-strict-mmio.cs','renode-memory-policy.cs','renode-system-control.cs']))
  (d/'run.py').write_text('''import clr,time,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy,BlackwallSystemControl
m=monitor.Machine
policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],0x1000)
policy.Attach()
control=BlackwallSystemControl(m,m['sysbus.cpu'],m['sysbus.nvic'],%s,%s)
control.Attach()
e=EmulationManager.Instance.CurrentEmulation
e.StartAll()
time.sleep(0.3)
e.PauseAll()
Console.WriteLine('BLACKWALL_CACHE '+json.dumps(dict(enabled=bool(control.ICacheEnabled),invalidations=int(control.Invalidations),
 data=(dict(enabled=bool(control.DataCache.Enabled),initialized_lines=int(control.DataCache.InitializedLines),
 invalidate_set_way=int(control.DataCache.Invalidations),clean_set_way=int(control.DataCache.Cleans),
 clean_invalidate_set_way=int(control.DataCache.CleanInvalidations)) if control.DataCache is not None else None),
 violations=int(control.Violations),operation=str(control.LastOperation),address=int(control.LastAddress),width=int(control.LastWidth),
 value=int(control.LastValue),pc=int(control.LastPC),memory_violations=int(policy.Violations),memory_operation=str(policy.LastOperation),
 words=[int(m.SystemBus.ReadDoubleWord(0x20000000+4*i)) for i in range(3)])))
''' % (str(functional),str(data_functional)))
  (d/'probe.resc').write_text('include @/work/strict.cs\nmach create "blackwall-cache-test"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/fixture.elf\ncpu VectorTableOffset 0x438000\ninclude @/work/run.py\nquit\n')
  log=execute(['docker','run','--rm','--network','none','--memory','512m','--pids-limit','128','--cpus','1','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',image,'--disable-gui','--hide-monitor','-p','/work/probe.resc'],d,'renode')
  records=[line.partition('BLACKWALL_CACHE ')[2] for line in log.splitlines() if line.startswith('BLACKWALL_CACHE ')]
  if len(records)!=1:raise ValueError('Missing cache result; inspect preserved log')
  o=json.loads(records[0]);good=o['enabled']==enabled and o['invalidations']==invalidations and o['words'][1:]==results
  good=good and o['words'][0]==(0x33334444 if violation is None else 0x11112222)
  if isinstance(violation,tuple):good=good and o['violations']==1 and (o['operation'],o['address'],o['width'])==violation and o['memory_violations']==0
  elif violation in ('memory','write-main'):good=good and o['violations']==0 and o['memory_violations']==1 and o['memory_operation']==('write-main' if violation=='write-main' else 'execute-unwritten-itcm')
  else:good=good and o['violations']==o['memory_violations']==0
  if data_functional:
   expected_data=DATA_EXPECTED.get(name,dict(enabled=False,initialized_lines=0))
   good=good and all(o['data'][key]==value for key,value in expected_data.items())
  warnings=[line for line in log.splitlines() if ('[warning]' in line.lower() and 'translation cache size' not in line.lower()) or ('[error]' in line.lower() and not ('this machine has aborted' in line.lower() and violation is not None))]
  good=good and not warnings;rows[name]=dict(passed=good,observed=o,warnings=warnings)
  print(name,'passed' if good else 'FAILED',flush=True)
 report=dict(passed=all(r['passed'] for r in rows.values()),cases=rows,image_id=image,hardware_validated=False,boot_verified=False,installable=False)
 (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 for p in [output,*output.rglob('*')]:p.chmod(0o700 if p.is_dir() else 0o600)
 if not report['passed']:raise ValueError('Cache verification failed; inspect report')

if __name__=='__main__':main()
