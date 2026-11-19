"""Check the bounded TI register policy; no real light sensor or ARM firmware runs."""
import argparse,json,hashlib
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
if o.exists() or not o.is_relative_to(S) or o.is_relative_to(R):p.error('New private simulator output required')
o.mkdir(mode=0o700)
b=S/'gaf-render-scheduler-native-01/stock24/strict.cs';core=b.read_bytes();device=(R/'tools/renode-opt3007-bootstrap.cs').read_bytes();(o/'model.cs').write_bytes(core+b'\n'+device)
(o/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 8\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40052000\n    power: power\n    module: 2\nopt: Miscellaneous.BlackwallOpt3007Bootstrap @ iom 0x45\n    owner: iom\n    resultWord: 0\n')
(o/'test.py').write_text('''import clr,json
from System import Array,Byte,Console
c=monitor.Machine['sysbus.iom.opt'];checks=[]
def check(n,b):
 if not b:raise Exception(n)
 checks.append(n)
def read(reg):
 check('pointer-'+str(reg),c.TryWrite(Array[Byte]([reg])))
 ok,data=c.TryRead(2);check('read-'+str(reg),ok);c.FinishTransmission();return list(data)
check('profile',c.FunctionalProfile=='constant-light-instant-conversion-v1')
check('manufacturer',read(0x7e)==[0x54,0x49]);check('device',read(0x7f)==[0x30,1])
check('reset-config',read(1)==[0xc8,0x10]);check('low',read(2)==[0xc0,0]);check('high',read(3)==[0xbf,0xff]);check('declared-dark',read(0)==[0,0])
check('continuous',c.TryWrite(Array[Byte]([1,0xcc,0x10])) and read(1)==[0xcc,0x90])
check('readonly',not c.TryWrite(Array[Byte]([0x7e,0,0])) and read(0x7e)==[0x54,0x49])
check('unknown',not c.TryWrite(Array[Byte]([4])))
check('length',not c.TryWrite(Array[Byte]([1,2])))
c.TryWrite(Array[Byte]([0x7e]));ok,a=c.TryRead(1);ok2,b=c.TryRead(1);check('split-msb',ok and ok2 and list(a)+list(b)==[0x54,0x49])
check('overrun',not c.TryRead(1)[0]);c.FinishTransmission();check('repeat',list(c.TryRead(2)[1])==[0x54,0x49])
c.Reset();check('reset',read(1)==[0xc8,0x10])
Console.WriteLine('BLACKWALL_OPT3007 '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_validated=False)))
''')
(o/'probe.resc').write_text('include @/work/model.cs\nmach create "opt3007-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=90)
rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_OPT3007 ')]
if len(rows)!=1:raise ValueError('Inspect saved OPT3007 log')
d=rows[0];d['baseline_sha256']=hashlib.sha256(core).hexdigest();d['device_sha256']=hashlib.sha256(device).hexdigest();(o/'report.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(dict(passed=True,count=d['count'])))
