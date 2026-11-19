"""Test an explicit ideal SDR phase abstraction and fixed-capture control."""
import argparse,json,struct
from pathlib import Path
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_rdid import COMMON as BASE_COMMON,ACTIVE as BASE_ACTIVE,PHASES as BASE_PHASES

def board(text,ideal=True):
 needle='    profile: "idle-nor-reset"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected PIO profile')
 text=text.replace(needle,needle+'    samplingProfile: "'+('ideal-sdr' if ideal else 'fixed-capture')+'"\n')
 return text
COMMON=BASE_COMMON.replace('q.Writes,i.Status,i.Writes)','q.Writes,i.Status,i.Writes,q.CompletedSamplingMask)')
ACTIVE=BASE_ACTIVE

def phases(ideal):
 if not ideal:return BASE_PHASES+[(1,"check('default-fixed-profile',q.SamplingProfile=='fixed-capture' and q.CompletedSamplingMask==0)\nready()\nb.WriteDoubleWord(0x40061084,0x3410861)\nblocked('fixed-does-not-accept-next-capture',start)\n")]
 result=BASE_PHASES+[(1,"check('ideal-explicit',q.SamplingProfile=='ideal-sdr' and q.CompletedSamplingMask==0)\nready()\nb.WriteDoubleWord(0x40061084,0x2010861)\nstart()\n")]
 for phase in range(8):
  code="check('phase-ready-"+str(phase)+"',q.RxEntries==1 and not q.Busy)\ncheck('phase-ID-"+str(phase)+"',b.ReadDoubleWord(0x40061014)==0x3925c2 and q.CompletedSamplingMask=="+str((1<<(phase+1))-1)+")\n"
  if phase<7:code+='b.WriteDoubleWord(0x40061084,'+str(0x2010861|((phase+1)<<22))+')\nstart()\n'
  else:code+="b.WriteDoubleWord(0x40061084,0x1010861)\nblocked('other-config-still-strict',start)\ncheck('eight-completed-phase-settings',q.CompletedSamplingMask==255 and q.ReadIdTransfers==8)\ng.Reset()\ncheck('phase-mask-owner-reset',q.CompletedSamplingMask==0)\n"
  result.append((10,code))
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--fixed',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(models(s));(o/'board.repl').write_text(board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text(),not a.fixed));(o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
 setup=COMMON+ACTIVE;steps=phases(not a.fixed);(o/'setup.py').write_text(setup);resc='include @/work/strict.cs\nmach create "mspi-rdid"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
 for n,(us,phase) in enumerate(steps):
  (o/f'phase-{n}.py').write_text(phase);(o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n');resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
 (o/'result.py').write_text("Console.WriteLine('BLACKWALL_MSPI1_SAMPLING_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='explicit ideal digital sampling or fixed capture; no physical timing window, identity or backing proof')))\n");(o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split('BLACKWALL_MSPI1_SAMPLING_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI1_SAMPLING_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing RDID result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
