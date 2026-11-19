"""Execute pinned recovery watchdog ARM code over strict virtual IOM7 and PMIC; no device access."""
import argparse,hashlib,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
POWER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
using System; using Antmicro.Renode.Peripherals.Bus;
public sealed class BlackwallRecoveryPower:IDoubleWordPeripheral,IKnownSize {
 public BlackwallRecoveryPower(BlackwallPeripheralPower power){Power=power;}
 public BlackwallPeripheralPower Power{get;} public long Size=>16;
 public void Reset(){} public uint ReadDoubleWord(long o){if(o==4)return Power.RequestWord;if(o==8)return Power.ReadStatus();throw new Exception("Unsupported recovery power read");}
 public void WriteDoubleWord(long o,uint v){if(o!=4 || !Power.TryWrite(v,true,Power.CanShutdown()))throw new Exception("Unsupported recovery power write");}
}}
'''
HARNESS='''#include <stdint.h>
#define W(a) (*(volatile uint32_t *)(a))
typedef struct {volatile int held,receiving;} session;
#define TICK W(0x20000040)
#define DELAY(x) ((void)(x))
#include "watchdog.h"
void reset(void){volatile uint32_t *m=(void*)0x20000000;m[0]=0x11112222;m[1]=boot_watchdog_feed();__asm__ volatile("mrs %0,primask":"=r"(m[2]));m[0]=0x600d;for(;;)__asm__ volatile("wfi");}
__attribute__((section(".vectors"))) const uintptr_t vectors[]={0x20010000,(uintptr_t)reset};
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('recovery',type=Path);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh output required')
 o.mkdir(mode=0o700);(o/'runner.py').write_bytes(Path(__file__).read_bytes());header=(a.recovery/'src/watchdog.h').read_bytes()
 if hashlib.sha256(header).hexdigest()!='26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b':raise ValueError('Unreviewed watchdog source')
 # Frozen main snapshot contains the same strict IOM dependency already used by original ARM.
 base=a.simulator/'pmic-timed-main-03'
 strict=(base/'stock24/strict.cs').read_text()
 old=(base/'root.cs').read_text()+'\n'+(base/'timed.cs').read_text()
 if not strict.endswith(old):raise ValueError('PMIC source suffix differs')
 strict=strict[:-len(old)]+(ROOT/'tools/renode-pmic-restore-probe.cs').read_text()+'\n'+(ROOT/'tools/renode-pmic-timed-probe.cs').read_text()
 for name,target,busy in [('match',0x3c00,False),('mismatch',0x3c01,False),('busy',0x3c00,True),('masked',0x3c00,False),('pins',0x3c00,False)]:
  d=o/name;d.mkdir(mode=0o700);(d/'strict.cs').write_text(strict+'\n'+POWER);(d/'watchdog.h').write_bytes(header);(d/'probe.c').write_text(HARNESS.replace('m[0]=0x11112222;', 'm[0]=0x11112222;__asm__ volatile("cpsid i");') if name=='masked' else HARNESS)
  shutil.copyfile(ROOT/'tests/fixtures/m55-exceptions-smoke.ld',d/'link.ld')
  execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-O1','-ffreestanding','-fno-builtin','-nostdlib','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-T,'+str(d/'link.ld'),str(d/'probe.c'),'-o',str(d/'probe.elf')],d,'compiler')
  board=(ROOT/'tests/fixtures/m55-minimal.repl').read_text()+'''\npower: Miscellaneous.BlackwallPeripheralPower
    mask: 256
    profile: 1
    offProfile: 0
powerRegisters: Miscellaneous.BlackwallRecoveryPower @ sysbus 0x40021000
    power: power
iom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40057000
    power: power
    module: 7
pmic: Miscellaneous.BlackwallPmicTimedProbe @ iom 0x6b
    timerProfile: "fast-reset-stopped"
    recoveryReadHoleMock: 0
pins: Memory.MappedMemory @ sysbus 0x40010000
    size: 0x1000
dwtMock: Memory.MappedMemory @ sysbus 0xe0001000
    size: 0x1000
''';(d/'board.repl').write_text(board)
  setup=f'''from System import Array,Byte
m=monitor.Machine;b=m.SystemBus;q=m['sysbus.iom.pmic'];power=m['sysbus.iom'].Power
b.WriteDoubleWord(0x40010058,0x4200);b.WriteDoubleWord(0x4001005c,0x4200)
b.WriteDoubleWord(0xe000edfc,0);b.WriteDoubleWord(0xe0001000,0x40000000)
def send(v):q.Write(Array[Byte](v));q.FinishTransmission()
send([7,5,10]);send([7,8,0,{target>>8},{target&255}]);send([7,3,1]);send([7,0,1])
'''
  if name=='pins':setup+='b.WriteDoubleWord(0x40010058,0)\n'
  if busy:setup+='power.TryWrite(256,True);power.ReadStatus()\n'
  (d/'setup.py').write_text(setup)
  report='''import json
from System import Console
i=m['sysbus.iom'];t=q.Timer
Console.WriteLine('BLACKWALL_RECOVERY_FEED '+json.dumps(dict(mailbox=[int(b.ReadDoubleWord(0x20000000+4*n)) for n in range(3)],kicks=int(t.Kicks),running=bool(t.Running),target=int(t.Target),commands=int(i.Commands),iom_guards=int(i.AccessCount),pmic_guards=int(q.AccessCount),repeated_start_attempts=int(q.RepeatedStarts),timer_reads=int(q.TimerReads),timer_writes=int(q.TimerWrites),power_status_before_settle=int(power.StatusWord),power_request=int(power.RequestWord),power_status=int(power.ReadStatus()),pc=str(m['sysbus.cpu'].PC),last_iom=str(i.LastOperation),last_pmic=str(q.LastOperation),demcr=int(b.ReadDoubleWord(0xe000edfc)),dwt=int(b.ReadDoubleWord(0xe0001000)))))
''';(d/'result.py').write_text(report);(d/'probe.resc').write_text('include @/work/strict.cs\nmach create "recovery-feed"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadELF @/work/probe.elf\ninclude @/work/setup.py\nemulation RunFor "00:00:00.010"\ninclude @/work/result.py\nquit\n')
  log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode')
  rows=[json.loads(x.split('BLACKWALL_RECOVERY_FEED ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RECOVERY_FEED ')]
  bad=[line for line in log.splitlines() if ('[WARNING]' in line and 'Translation cache size 536870912 is larger than maximum allowed 134217728' not in line) or '[ERROR]' in line or 'There was an error' in line]
  if bad:raise ValueError('Unexpected runtime diagnostic: '+str(bad))
  if len(rows)!=1:raise ValueError('Missing feed result; inspect log')
  r=rows[0]
  if r['power_request']!=(256 if busy else 0) or r['power_status_before_settle']!=(0 if name=='pins' else 256) or not r['running'] or r['target']!=target or r['timer_reads']!=(2 if name in ('match','masked','mismatch') else 0) or r['repeated_start_attempts']!=(1 if name in ('match','masked','mismatch') else 0):raise ValueError('Feed state/transport preservation differs')
  (d/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(case=name,**r)),flush=True)
  if r['mailbox']!=[0x600d,int(name in ('match','masked')),int(name=='masked')] or r['kicks']!=int(name in ('match','masked')) or r['commands']!={'match':3,'mismatch':2,'busy':0,'masked':3,'pins':0}[name] or r['iom_guards'] or r['pmic_guards'] or r['power_status']!=(256 if busy else 0) or r['demcr']!=0 or r['dwt']!=0x40000000:raise ValueError('Feed behavior differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=5,scope='pinned compiled feed; synthetic power/pins/frozen DWT/status holes; no scheduler/full boot/hardware'),indent=2)+'\n')
if __name__=='__main__':main()
