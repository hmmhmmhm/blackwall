"""Verify a pointer-only diagnostic I2C peer; unknown reads must stop rather than synthesize IDs."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from iom_engine_source import load_engine
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import json
from System import Console,Array,Byte
m=monitor.Machine;i=m['sysbus.iom'];p=m['sysbus.iom.peer'];b=m.SystemBus;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(o,v):b.WriteDoubleWord(0x40055000+o,v)
def r(o):return b.ReadDoubleWord(0x40055000+o)
def blocked(n,fn,op):
    old=i.AccessCount
    try:fn()
    except Exception as e:
        if 'Blackwall unsupported IOM' not in str(e):raise
    else:raise Exception(n+' accepted')
    check(n,i.AccessCount==old+1 and i.LastOperation==op)
check('initial-peer',not p.PointerSelected and p.PointerWrites==p.ReadAttempts==p.Finishes==0)
check('power',i.Power.TryWrite(64,True) and i.Power.ReadStatus()==64)
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xd);w(0x10c,1)
blocked('unregistered-target',lambda:w(0x120,0x101),'write')
check('unregistered-no-command',i.Commands==0 and p.PointerWrites==0)
w(0x2c4,0xc);w(0x200,1);w(0x120,0x101)
check('pointer-byte-consumed',p.PointerSelected and p.Pointer==1 and p.PointerWrites==1 and p.Finishes==1)
check('write-completed',i.Commands==1 and r(0x12c)&31==0 and r(0x204)&1 and i.IRQ.IsSet)
w(0x208,0x7fff)
check('clear-completion',not i.IRQ.IsSet and r(0x204)==0)
blocked('unknown-read',lambda:w(0x120,0x102),'peer-read')
check('read-diagnostic-only',p.ReadAttempts==1 and p.LastReadCount==1 and p.LastReadPointer==1 and p.PointerWrites==1 and p.Finishes==1)
check('no-fabricated-read-completion',r(0x204)&1==0 and not i.IRQ.IsSet and r(0x100)&0x00ff0000==0)
i.ResetThroughInterface()
check('controller-reset-preserves-peer',p.PointerSelected and p.Pointer==1 and p.PointerWrites==1)
p.Reset()
check('peer-reset',not p.PointerSelected and p.PointerWrites==p.ReadAttempts==p.Finishes==0)
blocked('empty-pointer',lambda:p.Write(Array[Byte]([])),'peer-write')
blocked('unknown-register',lambda:p.Write(Array[Byte]([2])),'peer-write')
blocked('data-write',lambda:p.Write(Array[Byte]([1,12])),'peer-write')
check('rejected-writes-unchanged',not p.PointerSelected and p.PointerWrites==0)
blocked('unselected-read',lambda:p.Read(1),'peer-read')
check('unselected-read-recorded',p.ReadAttempts==1 and p.LastReadPointer==-1)
Console.WriteLine('BLACKWALL_IOM_PROBE '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='synthetic pointer ACK only, all reads rejected; no sensor identity/data/physical bus proof')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--package-version',action='store_true');p.add_argument('--startup-threshold',type=int);p.add_argument('--event-probe',action='store_true');p.add_argument('--event-frame-hex');p.add_argument('--reusable-events',action='store_true');a=p.parse_args()
 if a.event_probe and a.startup_threshold is None:p.error('--event-probe requires --startup-threshold')
 if a.reusable_events and a.event_frame_hex is None:p.error('--reusable-events requires --event-frame-hex')
 if a.event_frame_hex is not None and (not a.event_probe or len(a.event_frame_hex)!=32):p.error('--event-frame-hex requires --event-probe and exactly16bytes')
 o=a.output;o.mkdir(mode=0o700)
 source=(ROOT/'tools/renode-strict-mmio.cs').read_text()+'\n'+load_engine()+'\n'+(ROOT/'tools/renode-iom-command-queue.cs').read_text()+'\n'+(ROOT/'tools/renode-iom.cs').read_text()
 addon=ROOT/'tools/renode-iom-register-probe.cs'
 if addon.exists():source+='\n'+addon.read_text()
 (o/'strict.cs').write_text(source);(o/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 64\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40055000\n    power: power\n    module: 5\npeer: Miscellaneous.BlackwallIomRegisterProbe @ iom 0xc\n    owner: iom\n    profile: "pointer-01-only"\n')
 driver=DRIVER
 if a.package_version or a.startup_threshold is not None:
  (o/'board.repl').write_text((o/'board.repl').read_text().replace('"pointer-01-only"','"package-version-only"'))
  extra='''
i.ResetThroughInterface();p.Reset()
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xc);w(0x200,1);w(0x10c,1);w(0x120,0x101);w(0x208,0x7fff)
w(0x120,0x402)
check('version-wire-bytes',r(0x108)==0x00090202 and p.VersionReads==1 and p.ReturnedBytes==4)
check('version-read-completes',r(0x12c)&31==0 and r(0x204)&1 and i.IRQ.IsSet and p.Finishes==2)
blocked('no-assumed-pointer-auto-increment',lambda:p.Read(4),'peer-read')
check('repeat-does-not-return-data',p.VersionReads==1 and p.ReturnedBytes==4)
p.Write(Array[Byte]([1]))
blocked('wrong-version-length',lambda:p.Read(8),'peer-read')
check('wrong-length-preserves-response',p.VersionReads==1 and p.ReturnedBytes==4)
value=p.Read(4)
check('fresh-pointer-reread',list(value)==[2,2,9,0] and p.VersionReads==2 and p.ReturnedBytes==8)
'''
  driver=driver.replace("Console.WriteLine('BLACKWALL_IOM_PROBE",extra+"Console.WriteLine('BLACKWALL_IOM_PROBE").replace('synthetic pointer ACK only, all reads rejected; no sensor identity/data/physical bus proof','synthetic package-match version response only; no physical version, other register or touch event proof')
 if a.startup_threshold is not None:
  (o/'board.repl').write_text((o/'board.repl').read_text().replace('"package-version-only"','"touch-startup-config"\n    initialGestureThreshold: '+str(a.startup_threshold)))
  extra='''
i.ResetThroughInterface();p.Reset()
check('explicit-initial-threshold',p.GestureThreshold==INITIAL_THRESHOLD and p.GestureReads==p.ConfigWrites==p.StatusReads==0 and not p.ConfigReplyPending)
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xc)
w(0x10c,8);w(0x120,0x101);w(0x120,0x202)
check('gesture-read-little-endian',r(0x108)==INITIAL_THRESHOLD and p.GestureReads==1)
w(0x10c,0x00032007);w(0x120,0x301)
check('gesture-write-state',p.GestureThreshold==800 and p.ConfigWrites==1 and p.ConfigReplyPending)
blocked('pending-command-overlap',lambda:p.Write(Array[Byte]([7,1,0])),'peer-write')
check('overlap-preserves',p.GestureThreshold==800 and p.ConfigWrites==1)
blocked('wrong-status-length',lambda:p.Read(4),'peer-read')
check('wrong-status-length-preserves-pending',p.ConfigReplyPending and p.StatusReads==0)
w(0x120,0x302)
check('command-status-frame',r(0x108)==0x170007 and p.StatusReads==1 and not p.ConfigReplyPending)
w(0x10c,8);w(0x120,0x101);w(0x120,0x202)
check('gesture-readback',r(0x108)==800 and p.GestureReads==2)
before=p.ReturnedBytes
blocked('zero-config-rejected',lambda:p.Write(Array[Byte]([7,0,0])),'peer-write')
blocked('unknown-event-register',lambda:p.Write(Array[Byte]([3])),'peer-write')
blocked('status-without-command',lambda:p.Read(3),'peer-read')
check('rejections-preserve-config',p.GestureThreshold==800 and p.ConfigWrites==1 and p.StatusReads==1 and p.ReturnedBytes==before)
p.Write(Array[Byte]([8]))
blocked('gesture-is-not-version',lambda:p.Read(4),'peer-read')
check('correct-gesture-read-after-rejection',list(p.Read(2))==[0x20,3] and p.GestureReads==3 and p.VersionReads==0)
p.Reset()
check('reset-restores-explicit-scenario',p.GestureThreshold==INITIAL_THRESHOLD and not p.ConfigReplyPending and p.ConfigWrites==p.GestureReads==p.StatusReads==0)
'''.replace('INITIAL_THRESHOLD',str(a.startup_threshold))
  driver=driver.replace("Console.WriteLine('BLACKWALL_IOM_PROBE",extra+"Console.WriteLine('BLACKWALL_IOM_PROBE").replace('synthetic package-match version response only; no physical version, other register or touch event proof','synthetic startup version/gesture config and immediate command status; no physical defaults, events or DFU proof')
 if a.event_probe:
  (o/'board.repl').write_text((o/'board.repl').read_text()+'    eventPointerProbe: true\n')
  driver=driver.replace("blocked('unknown-event-register',lambda:p.Write(Array[Byte]([3])),'peer-write')","blocked('unknown-event-register',lambda:p.Write(Array[Byte]([255])),'peer-write')")
  extra='''
p.Write(Array[Byte]([3]))
check('explicit-event-pointer',p.EventPointerProbe and p.PointerSelected and p.Pointer==3)
before=p.ReturnedBytes
blocked('event-bytes-unknown',lambda:p.Read(16),'peer-read')
check('event-request-recorded-no-response',p.LastReadPointer==3 and p.LastReadCount==16 and p.ReturnedBytes==before)
'''
  if a.event_frame_hex is not None:
   (o/'board.repl').write_text((o/'board.repl').read_text()+'    eventFrameHex: "'+a.event_frame_hex+'"\n')
   extra='''
import clr
clr.AddReference(p.GetType().Assembly)
from System import ArgumentException
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallIomRegisterProbe
def bad_frame(n,probe,frame):
    try:BlackwallIomRegisterProbe(i,'touch-startup-config',800,probe,frame)
    except ArgumentException:check(n,True)
    else:raise Exception(n+' accepted')
bad_frame('event-needs-explicit-profile',False,'00'*16)
bad_frame('event-short-frame',True,'00'*15)
bad_frame('event-long-frame',True,'00'*17)
bad_frame('event-nonhex-frame',True,'gg'*16)
i.ResetThroughInterface();p.Reset()
check('event-explicit-initial',p.EventFrameEnabled and p.EventReadOffset==p.EventReadChunks==p.EventFramesCompleted==0)
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xc)
w(0x10c,3);w(0x120,0x101);w(0x208,0x7fff)
before=(p.EventReadOffset,p.ReturnedBytes,p.EventReadChunks,p.EventFramesCompleted)
blocked('event-outside-command',lambda:p.Read(4),'peer-read')
check('outside-command-no-consumption',before==(p.EventReadOffset,p.ReturnedBytes,p.EventReadChunks,p.EventFramesCompleted))
blocked('event-length-eight',lambda:w(0x120,0x802),'peer-read')
check('wrong-total-no-consumption',before==(p.EventReadOffset,p.ReturnedBytes,p.EventReadChunks,p.EventFramesCompleted) and not i.IRQ.IsSet and p.Finishes==1)
i.ResetThroughInterface()
w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xc)
w(0x200,1)
w(0x120,0x1002)
words=[r(0x108) for _ in range(4)]
check('event-wire-four-words',words==EXPECTED_WORDS)
check('event-complete-once',p.EventReadOffset==16 and p.EventReadChunks==4 and p.EventFramesCompleted==1 and p.ReturnedBytes==16 and p.Finishes==2)
check('event-iom-completion',r(0x12c)&31==0 and r(0x204)&1 and i.IRQ.IsSet)
before=(p.EventReadOffset,p.ReturnedBytes,p.EventReadChunks,p.EventFramesCompleted,p.PointerWrites)
blocked('event-repeated-read',lambda:p.Read(4),'peer-read')
blocked('event-repeated-pointer',lambda:p.Write(Array[Byte]([3])),'peer-write')
check('event-budget-preserved',before==(p.EventReadOffset,p.ReturnedBytes,p.EventReadChunks,p.EventFramesCompleted,p.PointerWrites))
i.ResetThroughInterface()
check('iom-reset-does-not-rearm-event',p.EventFramesCompleted==1 and p.EventReadOffset==16)
p.Write(Array[Byte]([8]));check('event-does-not-break-config',list(p.Read(2))==[INITIAL_THRESHOLD&255,INITIAL_THRESHOLD>>8])
p.Reset()
check('peer-reset-rearms-declared-input',p.EventReadOffset==p.EventReadChunks==p.EventFramesCompleted==p.ReturnedBytes==0)
'''.replace('INITIAL_THRESHOLD',str(a.startup_threshold)).replace('EXPECTED_WORDS',repr([int.from_bytes(bytes.fromhex(a.event_frame_hex)[k:k+4],'little') for k in range(0,16,4)]))
  driver=driver.replace("Console.WriteLine('BLACKWALL_IOM_PROBE",extra+"Console.WriteLine('BLACKWALL_IOM_PROBE")
 if a.reusable_events:
  (o/'board.repl').write_text((o/'board.repl').read_text()+'    reusableEventFrames: true\n')
  extra='''
from System import Array,Byte,ArgumentException
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallIomRegisterProbe
frame2=[2,64,10,167,52,18,205,171,1,128,255,255,90,195,23,233]
def state():return (p.EventReadOffset,p.EventReadChunks,p.EventFramesCompleted,p.EventFrameReloads,p.ReturnedBytes,p.PointerWrites,p.ConfigReplyPending)
def setup():
    w(0x118,1);w(0x11c,0x10);w(0x2c0,0x3f270);w(0x2c4,0xc);w(0x200,1)
def start_report():
    w(0x10c,3);w(0x120,0x101);w(0x208,0x7fff);w(0x120,0x1002)
def idle():
    w(0x208,0x7fff);w(0x11c,0);check('bus-quiescent',i.Quiescent)
def payload():return sum(([int((v>>(8*k))&255) for k in range(4)] for v in [r(0x108) for _ in range(4)]),[])
i.ResetThroughInterface();p.Reset()
check('reusable-selected',p.ReusableEventFrames and p.EventFrameReloads==0)
old=state();check('unconsumed-frame-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
off=BlackwallIomRegisterProbe(i,'touch-startup-config',800,True,'00'*16)
check('reusable-default-off',not off.ReusableEventFrames and not off.TryLoadEventFrame(Array[Byte](frame2)))
try:BlackwallIomRegisterProbe(i,'touch-startup-config',800,True,None,True)
except ArgumentException:check('reusable-requires-initial-frame',True)
else:raise Exception('reusable accepted absent initial frame')
setup();start_report();old=state()
check('active-transfer-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
words=[r(0x108) for _ in range(3)];old=state()
check('unread-fifo-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
words.append(r(0x108));check('first-frame-still-exact',words==EXPECTED_WORDS)
old=state();check('completion-irq-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
w(0x208,0x7fff);old=state();check('enabled-bus-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
idle();old=state()
for label,value in [('null',None),('short',Array[Byte]([1]*15)),('long',Array[Byte]([1]*17))]:check('reject-'+label,not p.TryLoadEventFrame(value) and state()==old)
p.Write(Array[Byte]([7,32,3]));old=state();check('pending-config-cannot-be-overwritten',not p.TryLoadEventFrame(Array[Byte](frame2)) and state()==old)
check('pending-config-preserved',list(p.Read(3))==[7,0,23])
loaded=Array[Byte](frame2);check('load-next-explicit-report',p.TryLoadEventFrame(loaded) and p.EventFrameReloads==1 and p.EventFramesCompleted==1 and p.EventReadOffset==0)
loaded[0]=255;old=state();check('duplicate-load-rejected',not p.TryLoadEventFrame(Array[Byte]([9]*16)) and state()==old)
blocked('new-frame-requires-fresh-pointer',lambda:p.Read(4),'peer-read')
setup();start_report();check('second-frame-exact-and-caller-alias-isolated',payload()==frame2)
check('two-report-counters',p.EventFramesCompleted==2 and p.EventReadChunks==8 and p.EventFrameReloads==1)
idle();check('load-third-report',p.TryLoadEventFrame(Array[Byte]([0x5a]*16)))
i.ResetThroughInterface();check('controller-reset-preserves-loaded-report',p.EventFrameReloads==2 and p.EventFramesCompleted==2 and p.EventReadOffset==0)
setup();start_report();check('third-frame-after-controller-reset',payload()==[0x5a]*16)
idle();p.Reset();check('peer-reset-clears-reload-lifetime',p.EventFrameReloads==p.EventFramesCompleted==p.EventReadChunks==p.EventReadOffset==0)
setup();start_report();check('peer-reset-restores-original-declared-report',[r(0x108) for _ in range(4)]==EXPECTED_WORDS)
'''.replace('EXPECTED_WORDS',repr([int.from_bytes(bytes.fromhex(a.event_frame_hex)[k:k+4],'little') for k in range(0,16,4)]))
  driver=driver.replace("Console.WriteLine('BLACKWALL_IOM_PROBE",extra+"Console.WriteLine('BLACKWALL_IOM_PROBE")
 (o/'test.py').write_text(driver);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "iom-register-probe"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_IOM_PROBE ')]
 if len(rows)!=1:raise ValueError('Missing IOM probe unit result; inspect preserved log')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
if __name__=='__main__':main()
