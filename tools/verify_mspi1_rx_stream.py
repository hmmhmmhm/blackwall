"""Exercise finite RX FIFO backpressure, ordering and aborts in a synthetic NOR range."""
import argparse
import json
import struct
from pathlib import Path
from verify_mspi1_status_byte import SETUP
from verify_mspi1_pio_reset import models
from native_replay import IMAGE
from run_renode_m55_probe import execute


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--length',type=int,choices=[65,172,173,256],default=172)
    p.add_argument('--stuck',action='store_true')
    a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    board=(s/'nvdb-blank-default-main-01/board.repl').read_text()
    board=board.replace('    profile: "idle-nor-reset"\n','    profile: "idle-nor-reset"\n    maxArrayReadBytes: 256\n')
    board=board.replace('    profile: "erased-range"\n','    profile: "synthetic-ramp"\n')
    if a.stuck:board=board.replace('    completeTransactions: true\n','    completeTransactions: false\n')
    (o/'board.repl').write_text(board);(o/'strict.cs').write_bytes(models(s))
    (o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
    setup=SETUP+"""def array_config():
    b.WriteDoubleWord(0x40061084,0x1010861)
    b.WriteDoubleWord(0x40061004,5)
    b.WriteDoubleWord(0x4006100c,0x6c)
def array_start(length=LENGTH,address=0x1fc0001):
    b.WriteDoubleWord(0x40061008,address)
    b.WriteDoubleWord(0x40061000,(length<<16)|0x461)
def take(first,count,total=LENGTH):
    for n in range(first,first+count):
        expected=sum(((1+n*4+k)&255)<<(k*8) for k in range(min(4,total-n*4)))
        check('ordered-word-'+str(n),b.ReadDoubleWord(0x40061014)==expected)
    check('bounded-after-drain-'+str(first),q.RxEntries<=16)
array_config()
check('stream-opt-in',q.MaxArrayReadBytes==256)
for addr,length in [(0x1fc0000,257),(0x1ff7ff0,172),(0xfffffff0,172),(0x1fc0000,0)]:
    blocked('range-or-limit-'+str(addr)+'-'+str(length),lambda addr=addr,length=length:array_start(length,addr))
array_start()
check('no-data-before-timer',q.Busy and q.RxEntries==0 and q.ArrayReadTransfers==0)
""".replace('LENGTH',str(a.length))
    final_words=(a.length+3)//4-40
    steps=[(10,"check('first-FIFO-full-not-complete',q.Busy and q.RxEntries==16 and q.ArrayReadTransfers==0 and (q.Control&2)==0 and i.Status==0)\n"),
           (50,"check('backpressure-no-overflow',q.Busy and q.RxEntries==16 and q.ArrayReadTransfers==0 and i.Status==0)\nblocked('busy-command',array_start)\ncheck('power-off-blocked',not q.CanPowerDown)\ntake(0,8)\ncheck('consume-does-not-instantly-fill',q.RxEntries==8)\n"),
           (10,"check('refill-only-free-eight',q.Busy and q.RxEntries==16 and q.ArrayReadTransfers==0)\ntake(8,16)\ncheck('midstream-empty',q.RxEntries==0 and q.Busy)\n"),
           (10,"check('third-batch-still-busy',q.Busy and q.RxEntries==16 and q.ArrayReadTransfers==0 and i.Status==0)\ntake(24,16)\n"),
           (10,"check('last-batch-completes',not q.Busy and q.RxEntries=="+str(final_words)+" and q.ArrayReadTransfers==1 and q.ArrayBytesRead=="+str(a.length)+" and (q.Control&2)==2 and i.Status==1)\ncheck('unread-prevents-off',not q.CanPowerDown)\ntake(40,"+str(final_words)+")\nblocked('empty-FIFO',lambda:b.ReadDoubleWord(0x40061014))\ncheck('consumed-all',q.RxEntries==0 and q.CanPowerDown)\nb.WriteDoubleWord(0x40061208,1)\narray_start()\n"),
           (10,"check('second-partial',q.Busy and q.RxEntries==16)\ntake(0,1)\ng.WriteDoubleWord(0x3110,0xa4214);g.WriteDoubleWord(0x3110,0xa4234)\n"),
           (10,"check('clock-abort-discards-partial',not q.Busy and q.RxEntries==0 and q.Aborted==1 and q.ArrayReadTransfers==1 and i.Status==0)\narray_start()\n"),
           (10,"check('third-partial-before-reset',q.Busy and q.RxEntries==16)\ng.Reset()\n"),
           (100,"check('reset-no-stale-RX-or-IRQ',not q.Busy and q.RxEntries==q.ArrayReadTransfers==q.ArrayBytesRead==i.Status==0)\nready();array_config();array_start(7)\n"),
           (10,"check('retry-short-completes',not q.Busy and q.ArrayBytesRead==7 and q.RxEntries==2)\ntake(0,2,7)\n")]
    if a.length in [65,256]:
        steps=[]
        total_words=(a.length+3)//4
        for first in range(0,total_words,16):
            count=min(16,total_words-first);done=first+count==total_words
            steps.append((10,"check('boundary-batch-"+str(first)+"',q.RxEntries=="+str(count)+" and q.Busy=="+str(not done)+" and q.ArrayReadTransfers=="+str(int(done))+" and i.Status=="+str(int(done))+")\ntake("+str(first)+','+str(count)+")\n"))
        steps.append((50,"check('boundary-no-replay',not q.Busy and q.RxEntries==0 and q.ArrayReadTransfers==1 and q.ArrayBytesRead=="+str(a.length)+")\n"))
    if a.stuck:
        steps=[(1000,"check('stuck-long-no-data-or-completion',q.Busy and q.RxEntries==q.ArrayReadTransfers==q.ArrayBytesRead==i.Status==0)\ng.Reset()\n"),
               (1000,"check('stuck-reset-no-stale-data',not q.Busy and q.RxEntries==q.ArrayReadTransfers==i.Status==0)\n")]
    (o/'setup.py').write_text(setup)
    resc='include @/work/strict.cs\nmach create "RX-stream"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for n,(us,code) in enumerate(steps):
        (o/f'phase-{n}.py').write_text(code)
        (o/f'advance-{n}.py').write_text('from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nEmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds('+str(us)+'))\n')
        resc+=f'include @/work/advance-{n}.py\ninclude @/work/phase-{n}.py\n'
    (o/'result.py').write_text("Console.WriteLine('BLACKWALL_RX_STREAM '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n")
    (o/'probe.resc').write_text(resc+'include @/work/result.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_RX_STREAM ')]
    if len(rows)!=1:raise ValueError('Missing RX stream result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
