"""Exercise strict IOM MMIO and polling I2C with a synthetic peer; never physical devices."""
import argparse,json,shutil
from pathlib import Path
from run_renode_m55_probe import execute
from iom_engine_source import load_engine
ROOT=Path(__file__).resolve().parents[1]
PEER='''namespace Antmicro.Renode.Peripherals.Miscellaneous {
using Antmicro.Renode.Peripherals.I2C;
public sealed class BlackwallIomTestPeer:II2CPeripheral {
public System.Collections.Generic.List<byte> Bytes {get;}=new System.Collections.Generic.List<byte>();
public int ReadBytes {get;private set;} public int Finishes {get;private set;}
public void Reset(){Bytes.Clear();ReadBytes=Finishes=0;}
public void Write(byte[] data){Bytes.AddRange(data);}
public byte[] Read(int count=1){var r=new byte[count];for(int j=0;j<count;j++)r[j]=(byte)(0xa0+ReadBytes++);return r;}
public void FinishTransmission(){Finishes++;}
}}
'''
DRIVER='''import json
from System import Console
m=monitor.Machine;i=m['sysbus.iom'];p=m['sysbus.iom.peer'];other=m['sysbus.iom.other'];wide=m['sysbus.iom.wide'];power=i.Power;b=m.SystemBus
checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def read(off):return b.ReadDoubleWord(0x40052000+off)
def write(off,v):b.WriteDoubleWord(0x40052000+off,v)
def blocked(name,fn,width=4):
    before=int(i.AccessCount);writes=int(i.Writes);commands=int(i.Commands)
    try:fn()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,i.AccessCount==before+1 and i.LastWidth==width and i.Writes==writes and i.Commands==commands)
blocked('power-off-read',lambda:read(0x118))
blocked('power-off-write',lambda:write(0x118,1))
check('power-unready',not power.TryWrite(8,False))
check('power-request-not-on',power.TryWrite(8,True) and power.StatusWord==0)
blocked('power-request-read',lambda:read(0x118))
check('power-on',power.ReadStatus()==8)
check('reset-shadows',read(0x118)==0 and read(0x110)==2 and read(0x11c)==0x20)
check('idle-hypothesis',read(0x248)==4 and read(0x100)==0x20002000)
write(0x118,0xffff3f01)
check('apollo510-clock-bits',read(0x118)==0xffff3f01)
blocked('clock-reserved',lambda:write(0x118,2))
for width in (1,2,8):
    fn={1:b.WriteByte,2:b.WriteWord,8:b.WriteQuadWord}[width]
    blocked('native-width-write-'+str(width),lambda:fn(0x40052118,1),width)
    fn={1:b.ReadByte,2:b.ReadWord,8:b.ReadQuadWord}[width]
    blocked('native-width-read-'+str(width),lambda:fn(0x40052118),width)
for off in (0x40,0x11d,0x300,0x304,0x308,0x384):blocked('undefined-'+hex(off),lambda:write(off,0))
blocked('both-submodules',lambda:write(0x11c,0x11))
for off in (0x218,0x21c,0x220):
    write(off,0);check('disabled-zero-'+hex(off),read(off)==0)
    blocked('unsupported-nonzero-'+hex(off),lambda:write(off,4 if off==0x22c else 1))
blocked('fifo-input-ro',lambda:write(0x20,1))
blocked('status-ro',lambda:write(0x248,0))
blocked('lsb',lambda:write(0x2c0,2))
before=(int(i.ClockConfiguration),int(i.FifoControl),int(i.Commands),int(i.PowerDowns))
write(0x2c0,0x40)
check('unused-mi2crst-no-reset',before==(int(i.ClockConfiguration),int(i.FifoControl),int(i.Commands),int(i.PowerDowns)))
write(0x2c0,0x3f270)
check('i2c-timing-config-storage',read(0x2c0)==0x3f270 and i.LastI2CConfiguration==0x3f270)
blocked('i2c-config-reserved',lambda:write(0x2c0,8))
write(0x2c0,0)
blocked('spi-full-duplex',lambda:write(0x280,0x200004))
blocked('device-truncation',lambda:write(0x2c4,0x148))
write(0x118,1);write(0x11c,0x10);write(0x2c0,1);write(0x2c4,0x148);write(0x2c0,0);write(0x10c,0x04030201)
blocked('address-width-recheck',lambda:write(0x120,0x401))
check('address-width-rejection-preserves',wide.Bytes.Count==0 and read(0x2c4)==0x148 and read(0x100)&255==4 and read(0x12c)&31==0)
write(0x2c0,1);write(0x120,0x401)
check('ten-bit-transfer',list(wide.Bytes)==[1,2,3,4])
i.ResetThroughInterface()
write(0x118,1);write(0x11c,0x10);write(0x2c4,0x4a)
blocked('unknown-peer',lambda:write(0x120,0x401))
write(0x2c4,0x48);write(0x118,0)
blocked('clock-disabled',lambda:write(0x120,0x401))
write(0x118,1);write(0x110,0)
blocked('fifo-in-reset',lambda:write(0x120,0x401))
write(0x110,2);write(0x11c,1)
blocked('spi-command',lambda:write(0x120,0x401))
write(0x11c,0x10);write(0x200,1)
write(0x2c0,4)
blocked('arbitration-unmodeled',lambda:write(0x120,0x401))
write(0x2c0,0)
blocked('empty-write-command',lambda:write(0x120,0x401))
write(0x10c,0x04030201);write(0x120,0x401)
check('peer-write',list(p.Bytes)==[1,2,3,4] and p.Finishes==1 and i.Commands==1)
check('completion-irq',i.IRQ.IsSet and read(0x204)&1==1)
write(0x208,0xffffffff)
check('clear-all',not i.IRQ.IsSet and read(0x204)==0)
write(0x120,0x602)
check('peer-read',p.ReadBytes==6 and read(0x108)==0xa3a2a1a0 and read(0x108)==0xa5a4)
write(0x208,0xffffffff);write(0x10c,0x04030201)
write(0x120,0x801)
check('streaming-inflight',read(0x12c)&31==1 and list(p.Bytes)==[1,2,3,4,1,2,3,4])
blocked('streaming-overlap',lambda:write(0x120,0x602))
check('streaming-busy-off',not power.CanShutdown())
write(0x10c,0x08070605)
check('streaming-tx-exact',read(0x12c)&31==0 and list(p.Bytes)==[1,2,3,4,1,2,3,4,5,6,7,8] and i.Commands==3)
for length in (1,3,4,5,31,32,33,65,257):
    before=len(list(p.Bytes));write(0x10c,0x03020100);write(0x120,(length<<8)|1)
    sent=4
    while sent<length:
        value=sum(((sent+j)&255)<<(8*j) for j in range(4));write(0x10c,value);sent+=4
    check('streaming-length-'+str(length),[int(x) for x in list(p.Bytes)[before:]]==[x&255 for x in range(length)] and read(0x12c)&31==0)
write(0x208,0xffffffff)
write(0x120,0x2402)
check('long-read-inflight',read(0x12c)&31==2 and i.Commands==13)
blocked('overlap-command',lambda:write(0x120,0x401))
blocked('active-submodule-reset-unmodeled',lambda:write(0x11c,0))
blocked('active-i2c-reconfigure-unmodeled',lambda:write(0x2c0,1))
blocked('active-device-reroute',lambda:write(0x2c4,0x49))
check('address-routing-preserved',read(0x2c4)==0x48 and other.ReadBytes==0 and other.Bytes.Count==0)
write(0x2c4,0x48)
check('same-active-address',read(0x2c4)==0x48)
command_before=int(read(0x12c));write(0x2c0,0x40)
check('unused-mi2crst-preserves-inflight',int(read(0x12c))==command_before)
write(0x2c0,0)
check('busy-off-block',not power.CanShutdown() and not power.TryWrite(0,True,power.CanShutdown()))
words=[int(read(0x108)) for _ in range(9)]
expected=[sum((0xa6+4*n+j)<<(8*j) for j in range(4)) for n in range(9)]
check('long-read-finishes',words==expected and read(0x12c)&31==0 and p.ReadBytes==42)
check('active-config-not-quiescent',not i.Quiescent and not power.CanShutdown())
write(0x208,0xffffffff);write(0x11c,0)
check('quiescent',i.Quiescent and power.CanShutdown())
check('off-request',power.TryWrite(0,True,power.CanShutdown()) and i.PowerDowns==0)
blocked('off-request-mmio',lambda:read(0x118))
check('off-response-reset',power.ReadStatus()==0 and i.PowerDowns==1 and power.PowerCycles==1)
power.ReadStatus();check('off-callback-once',i.PowerDowns==1)
check('reenable',power.TryWrite(8,True) and power.ReadStatus()==8)
check('reset-after-off',read(0x118)==0 and read(0x110)==2 and read(0x11c)==0x20 and not i.IRQ.IsSet and i.Commands==13)
i.ResetThroughInterface()
check('cold-reset-interface',i.Commands==0 and i.Writes==0 and i.PowerDowns==0 and read(0x118)==0)
Console.WriteLine('BLACKWALL_IOM '+json.dumps(dict(passed=True,assertion_count=len(checks),checks=checks,scope='synthetic peer and direct MMIO; no original main, physical bus, DMA/CQ or timing proof')))
'''
NAK_DRIVER = """import json
from System import Console
m=monitor.Machine;i=m['sysbus.iom'];p=m['sysbus.iom.peer'];b=m.SystemBus;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def w(o,v):b.WriteDoubleWord(0x40054000+o,v)
def r(o):return b.ReadDoubleWord(0x40054000+o)
def blocked(n,fn):
    old=(i.Writes,i.Commands,i.NakInjected,p.Bytes.Count,p.Finishes)
    try:fn()
    except Exception:pass
    else:raise Exception(n+' accepted')
    check(n,old==(i.Writes,i.Commands,i.NakInjected,p.Bytes.Count,p.Finishes))
check('power',i.Power.TryWrite(32,True) and i.Power.ReadStatus()==32)
w(0x118,1);w(0x11c,0x10);w(0x2c4,0x48)
check('default-clock',r(0x388)==0)
reads=i.Reads
check('passive-clock-diagnostic',i.RecoveryClockValue==0 and i.Reads==reads)
w(0x10c,0x04030201);w(0x120,0x401)
check('normal-first',i.Commands==1 and p.Bytes.Count==4 and p.Finishes==1 and i.NakInjected==0)
w(0x208,0x7fff);w(0x200,0x10);w(0x10c,0x08070605)
w(0x120,0x401)
check('nak-only',r(0x204)==0x10 and i.IRQ.IsSet and i.NakInjected==1 and i.Commands==2)
check('no-peer-side-effect',p.Bytes.Count==4 and p.Finishes==1)
check('idle-and-fifo-retained',r(0x248)==4 and r(0x12c)&31==0 and r(0x100)&255==4)
blocked('clock-active-submodule',lambda:w(0x388,2))
w(0x200,0);check('irq-mask',not i.IRQ.IsSet and r(0x204)==0x10)
w(0x11c,0);blocked('clock-fifo-not-reset',lambda:w(0x388,2))
w(0x110,0);check('fifo-reset',r(0x100)&0xff00ff==0)
blocked('debug-other-bits',lambda:w(0x388,4))
w(0x388,2);check('clock-forced',r(0x388)==2)
w(0x388,0);w(0x110,2);w(0x11c,0x10);w(0x208,0x7fff);w(0x200,0x10)
check('cleanup-restored',r(0x388)==0 and r(0x204)==0 and not i.IRQ.IsSet)
w(0x10c,0x0c0b0a09);w(0x120,0x401)
check('next-transfer',i.Commands==3 and i.NakInjected==1 and list(p.Bytes)==[1,2,3,4,9,10,11,12] and p.Finishes==2)
check('normal-irq-mask',not i.IRQ.IsSet and r(0x204)&1==1)
i.ResetThroughInterface();check('host-reset',i.Commands==0 and i.NakInjected==0 and r(0x388)==0)
Console.WriteLine('BLACKWALL_IOM '+json.dumps(dict(passed=True,assertion_count=len(checks),checks=checks,scope='Declared single-command address NAK fault and recovery clock storage; no original main or physical timing')))
"""

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--nak-profile',action='store_true');a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    (o/'strict.cs').write_text((ROOT/'tools/renode-strict-mmio.cs').read_text()+'\n'+load_engine()+'\n'+(ROOT/'tools/renode-iom-command-queue.cs').read_text()+'\n'+(ROOT/'tools/renode-iom.cs').read_text()+'\n'+PEER)
    (o/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 8\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40052000\n    power: power\n    module: 2\npeer: Miscellaneous.BlackwallIomTestPeer @ iom 0x48\nother: Miscellaneous.BlackwallIomTestPeer @ iom 0x49\nwide: Miscellaneous.BlackwallIomTestPeer @ iom 0x148\n')
    if a.nak_profile:
        board=(o/'board.repl').read_text().replace('mask: 8','mask: 32').replace('0x40052000','0x40054000').replace('module: 2','module: 4\n    i2cNakCommand: 2\n    i2cRecoveryClock: true')
        (o/'board.repl').write_text(board)
    (o/'test.py').write_text(NAK_DRIVER if a.nak_profile else DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "iom-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','blackwall-renode:1.17.0-local','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_IOM ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_IOM ')];assert len(rows)==1
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
