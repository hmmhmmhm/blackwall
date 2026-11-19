"""Check explicit synthetic pointer-only peer state and strict rejection, without devices."""
import argparse,json
from pathlib import Path
from run_renode_m55_probe import execute
from native_replay import IMAGE
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console,Array,Byte
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallI2cPointerProbe').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallI2cPointerProbe
p=BlackwallI2cPointerProbe();checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def write(values):p.Write(Array[Byte](values))
def state():return (p.Pointer,p.Writes,p.Finishes)
def blocked(name,fn):
    old=state();n=p.AccessCount
    try:fn()
    except Exception as e:
        if 'pointer probe unsupported' not in str(e):raise
    else:raise Exception(name+' accepted')
    check(name,state()==old and p.AccessCount==n+1)
check('initial',p.Pointer==-1 and p.Writes==0 and p.ReadAttempts==0)
blocked('unknown-initial-read',lambda:p.Read(1))
blocked('finish-without-write',lambda:p.FinishTransmission())
for index,data in enumerate([[],[5],[5,8],[9,5],[5,9,0],[0,0]]):blocked('invalid-write-'+str(index),lambda:write(data))
blocked('null-write',lambda:p.Write(None))
write([5,9]);check('pointer-accepted',p.Pointer==0x509 and p.Writes==1 and p.Finishes==0)
blocked('pending-overlap',lambda:write([5,9]))
p.FinishTransmission();check('finish-retains-pointer',p.Pointer==0x509 and p.Finishes==1)
for count in [1,2,0,-1,33]:blocked('read-unknown-'+str(count),lambda:p.Read(count))
write([5,9]);p.FinishTransmission();check('explicit-repeat',p.Writes==2 and p.Finishes==2)
p.Reset();check('reset',p.Pointer==-1 and p.Writes==0 and p.Finishes==0 and p.ReadAttempts==0 and p.AccessCount==0)
for initial in range(4):
    q=BlackwallI2cPointerProbe(initial)
    check('explicit-initial-'+str(initial),q.InitialAdcConfig==initial)
    try:q.Read(1)
    except Exception:pass
    else:raise Exception('unselected pointer read accepted')
    q.Write(Array[Byte]([5,9]));q.FinishTransmission()
    try:q.Read(2)
    except Exception:check('explicit-wrong-length-'+str(initial),q.ReturnedReads==0 and q.Pointer==0x509)
    else:raise Exception('Wrong length returned data')
    check('explicit-read-'+str(initial),list(q.Read(1))==[initial] and q.ReturnedReads==1)
    q.FinishTransmission();check('read-finish-'+str(initial),q.Finishes==2)
    q.Reset();check('reset-explicit-'+str(initial),q.InitialAdcConfig==initial and q.Pointer==-1 and q.ReturnedReads==0)
for initial in [-2,4,255]:
    try:BlackwallI2cPointerProbe(initial)
    except Exception as e:check('invalid-initial-'+str(initial),'Explicit ADC config' in str(e))
    else:raise Exception('Invalid config accepted')
Console.WriteLine('BLACKWALL_POINTER_UNIT '+json.dumps(dict(passed=True,checks=checks,count=len(checks),scope='synthetic pointer and optional two-bit config response, not a PMIC model or original main')))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
 if o.exists():raise ValueError('Use a new evidence directory')
 o.mkdir(mode=0o700);(o/'peer.cs').write_bytes((ROOT/'tools/renode-i2c-pointer-probe.cs').read_bytes());(o/'test.py').write_text(DRIVER);compile(DRIVER,'test.py','exec')
 (o/'probe.resc').write_text('include @/work/peer.cs\nmach create "pointer-only"\ninclude @/work/test.py\nquit\n')
 log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
 rows=[json.loads(x.split('BLACKWALL_POINTER_UNIT ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_POINTER_UNIT ')]
 if len(rows)!=1:raise ValueError('Missing pointer unit result')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))
if __name__=='__main__':main()
