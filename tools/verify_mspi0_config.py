"""Verify shared clock fields and isolated MSPI0 configuration without bus engines."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallG2StartupFixture').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMspi1ClockStorage,BlackwallMspi1ConfigStorage
m=monitor.Machine;g=m['sysbus.guard'];c=g.Mspi0Config;old=g.Mspi1Config;k=g.Mspi1Clock;checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
def read(address,ready=True):return tuple(c.TryRead(address,ready))
check('isolated-addresses',c.Owns(0x40060000) and not c.Owns(0x40061000) and old.Owns(0x40061000) and not old.Owns(0x40060000))
check('power-required',read(0x40060090,False)==(False,0) and not c.TryWrite(0x40060090,0,False))
check('reset-xip-disabled',read(0x40060090)==(True,0))
old_before=list(old.Values)
for address,value in [(0x40060090,0),(0x4006009c,0),(0x40060080,0),(0x40060030,0xc00000f1)]:
    check('write-'+str(address),c.TryWrite(address,value,True) and read(address)==(True,value))
check('mspi1-preserved',old_before==list(old.Values))
for address,value in [(0x40061090,0),(0x40060090,1),(0x4006009c,0x80000000),(0x40060100,1),(0x40060000,1),(0x40060030,0)]:
    before=(c.Reads,c.Writes,list(c.Values));check('blocked-write-'+str(address)+'-'+str(value),not c.TryWrite(address,value,True) and before==(c.Reads,c.Writes,list(c.Values)))
for address in [0x40060018,0x40060000,0x40060200,0x400602a0,0x40061090]:check('unknown-read-'+str(address),read(address)==(False,0))
for selection in [7,8,9,10]:
    previous=k.Value;value=(previous&~0x1f)|(selection<<1)|1
    check('clock-module0-'+str(selection),k.TryWrite(value) and k.Mspi0Enabled and k.Mspi0Selection==selection and (k.Value&~0x1f)==(previous&~0x1f))
for value in [(k.Value&~0x1e)|(6<<1),k.Value^0x100000,((k.Value&~0x1e)|(9<<1))^0x20]:
    before=(k.Value,k.Reads,k.Writes);check('clock-invalid-'+str(value),not k.TryWrite(value) and before==(k.Value,k.Reads,k.Writes))
legacy=BlackwallMspi1ClockStorage('source-reset-storage');check('legacy-clock-default',not legacy.TryWrite(0xa4210) and legacy.Value==0xa4214)
legacy_config=BlackwallMspi1ConfigStorage('source-reset-config');check('legacy-config-default',legacy_config.Owns(0x40061000) and not legacy_config.Owns(0x40060000))
for kwargs in [dict(commandQueueInit=True),dict(xipTurnaroundStorage=True),dict(xipMixedStorage=True)]:
    try:BlackwallMspi1ConfigStorage('source-reset-config',baseAddress=0x40060000,**kwargs)
    except Exception as error:check('advanced-module0-rejected-'+str(kwargs),'MSPI0 supports configuration storage only' in str(error))
    else:raise Exception('advanced module0 accepted')
try:BlackwallMspi1ConfigStorage('source-reset-config',baseAddress=0x40062000)
except Exception as error:check('wrong-base-rejected','Explicit MSPI0/1 configuration base' in str(error))
else:raise Exception('unknown base accepted')
g.Reset();check('reset-bank',c.Reads==c.Writes==0 and c.Values[0x30]==0xc00000f0 and k.Value==0xa4214)
Console.WriteLine('BLACKWALL_MSPI0_CONFIG_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output
    if o.exists():raise ValueError('Fresh output required')
    base=s/'mspi0-power-main-01/stock24';research=s/'mspi0-config-peer-research-01';model=(base/'strict.cs').read_bytes()
    for n in ['renode-strict-mmio.cs','renode-mspi1-clock.cs','renode-mspi1-config.cs']:
        before=(research/('base-'+n)).read_bytes()
        if model.count(before)!=1:raise ValueError('Changed source component')
        model=model.replace(before,(ROOT/'tools'/n).read_bytes())
    board=(base/'board.repl').read_text().replace('    mspi0Power: mspi0_power\n','    mspi0Power: mspi0_power\n    mspi0Config: mspi0_config\n')
    board=board.replace('mspi1_clock: Miscellaneous.BlackwallMspi1ClockStorage @ none\n','mspi1_clock: Miscellaneous.BlackwallMspi1ClockStorage @ none\n    mspi0Storage: true\n')
    board+='\nmspi0_config: Miscellaneous.BlackwallMspi1ConfigStorage @ none\n    profile: "source-reset-config"\n    baseAddress: 0x40060000\n'
    o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(model);(o/'board.repl').write_text(board);(o/'test.py').write_text(DRIVER)
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "mspi0-config"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_MSPI0_CONFIG_UNIT ')]
    if len(rows)!=1:raise ValueError('Missing MSPI0 config result; inspect saved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
