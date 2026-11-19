"""Synthetic ARM watchdog request -> synchronized machine reset, never device access."""
import argparse,json,hashlib,shutil
from pathlib import Path
from run_renode_m55_probe import execute
from reset_restart_profiles import RENODE_IMAGE

GUEST=r'''#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define M ((volatile uint32_t *)0x20000000)
void fault(void){M[7]=0xbad;for(;;){}}
void reset(void){
 M[0]++;
 if(M[0]>1){M[1]=R(0x4000885c);M[2]=R(0x40024000);M[3]=R(0x40000000);M[4]=0x600d;}
 else{R(0x40000000)=GATE;R(0x40024000)=0x02000305;}
 for(;;){__asm volatile("wfi");}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[16]={0x20010000,(uintptr_t)reset,(uintptr_t)fault,(uintptr_t)fault};
'''

def run(out,baseline=False,lifecycle=False):
 out.mkdir(mode=0o700,parents=True,exist_ok=False);root=Path(__file__).resolve().parents[1];results=[]
 base=(root/'tools/renode-strict-mmio.cs').read_text()
 for name in ('renode-watchdog.cs','renode-reset-controller.cs'):
  component=(root/'tools'/name).read_text()
  if base.count(component)!=0:raise ValueError('Duplicate shared component '+name)
  base+='\n'+component
 if not baseline:
  from watchdog_reset_delivery_model import compose
  base=compose(base)
 base+='\n'+(root/'tools/renode-reset-aware-nvic.cs').read_text()
 (out/'strict.cs').write_text(base);(out/'guest.c').write_text(GUEST)
 for gate in (2,) if baseline or lifecycle else (0,1,2,3):
  case=out/('gate-'+str(gate));case.mkdir()
  (case/'strict.cs').write_text(base)
  board=(root/'tests/fixtures/m55-minimal.repl').read_text().replace('    cpuType:', '    InitVectorTableOffset: 0\n    cpuType:').replace('IRQControllers.NVIC','Miscellaneous.BlackwallResetAwareNVIC')
  board+='\nrstgen: Miscellaneous.BlackwallResetController @ sysbus 0x40000000\n'+('    mainOnlyWatchdogBootContract: true\n' if not baseline else '')+'\nwdt: Miscellaneous.BlackwallApollo510Watchdog @ sysbus 0x40024000\n    resetController: rstgen\n'+('    propagateSystemReset: true\n' if not baseline else '')
  if not baseline:board+='\nrstgen_status: Miscellaneous.BlackwallVirtualResetBootStatus @ sysbus 0x4000885c\n    resetController: rstgen\n'
  (case/'board.repl').write_text(board)
  execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-O1','-ffreestanding','-fno-builtin','-nostdlib','-DGATE='+str(gate),'-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(root/'tests/fixtures/m55-exceptions-smoke.ld'),str(out/'guest.c'),'-o',str(case/'guest.elf')],case,'compiler')
  (case/'result.py').write_text('''import json
from System import Console
m=monitor.Machine
w=m['sysbus.wdt'];r=m['sysbus.rstgen']
Console.WriteLine('BLACKWALL_WDT_RESET '+json.dumps(dict(words=[int(m.SystemBus.ReadDoubleWord(0x20000000+4*i)) for i in range(8)],cfg=int(w.Configuration),due=bool(w.ResetDue),allowed=bool(w.ResetAllowedByGate),status=int(getattr(r,'VirtualBootStatus',0)),deliveries=int(getattr(r,'WatchdogResetDeliveries',0)),nvic_resets=int(m['sysbus.nvic'].ResetCompletions),accesses=int(w.AccessCount)+int(r.AccessCount))))
''')
  extra='rstgen WriteDoubleWord 0 2\nwdt WriteDoubleWord 0 0x02000305\nstart\npython \"import time; time.sleep(0.8)\"\npause\ninclude @/work/result.py\nmachine Reset\nstart\npython \"import time; time.sleep(0.2)\"\npause\ninclude @/work/result.py\n' if lifecycle else ''
  (case/'probe.resc').write_text('include @/work/strict.cs\nmach create\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/guest.elf\nstart\npython "import time; time.sleep(0.8)"\npause\ninclude @/work/result.py\n'+extra+'quit\n')
  log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={case},target=/work,readonly',RENODE_IMAGE,'--disable-gui','--hide-monitor','-p','/work/probe.resc'],case,'renode',timeout=45)
  rows=[json.loads(l.split('BLACKWALL_WDT_RESET ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_WDT_RESET ')]
  if len(rows)!=(3 if lifecycle else 1):raise ValueError('Missing runtime result')
  r=rows[0];allowed=bool(gate&2)
  checks=dict(boot_count=r['words'][0]==(2 if allowed else 1),no_fault=r['words'][7]==0,strict_clean=r['accesses']==0,request_gate=(r['due'] is False if allowed else r['due'] is True and r['allowed'] is False),delivery_count=r['deliveries']==int(allowed),cause=r['status']==(64 if allowed else 0),fresh_registers=(r['words'][1:5]==[64,0,0,0x600d] and r['cfg']==0) if allowed else r['words'][1:5]==[0,0,0,0])
  if lifecycle:
   checks.update(second_watchdog_epoch=rows[1]['words'][:5]==[3,64,0,0,0x600d] and rows[1]['deliveries']==2 and rows[1]['nvic_resets']==2,unrelated_reset_clears_cause=rows[2]['words'][:5]==[4,0,0,0,0x600d] and rows[2]['status']==0 and rows[2]['deliveries']==2 and rows[2]['nvic_resets']==3,epochs_strict_clean=all(x['accesses']==x['words'][7]==0 for x in rows))
  results.append(dict(gate=gate,checks=checks,observed=r,lifecycle_rows=rows if lifecycle else []));print(json.dumps(results[-1]),flush=True)
 (out/'report.json').write_text(json.dumps(dict(passed=all(all(r['checks'].values()) for r in results),cases=results,original_firmware_executed=False,hardware_accessed=False),indent=2)+'\n')
 if not all(all(r['checks'].values()) for r in results):raise SystemExit(1)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');p.add_argument('--lifecycle',action='store_true');a=p.parse_args();run(a.output,a.baseline,a.lifecycle)
