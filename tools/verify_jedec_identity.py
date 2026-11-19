"""Verify an explicitly synthetic JEDEC personality and shared PPB owner; no physical IDs."""
import argparse,json
from pathlib import Path
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallChipIdentity').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallChipIdentity
m=monitor.Machine;b=m.SystemBus;g=m['sysbus.guard'];p=m['sysbus.ppb'];u=m['sysbus.unknown'];checks=[]
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
def state():return [(int(a),int(g.ChipInfo.GetValue(a)),int(g.ChipInfo.GetReads(a))) for a in g.ChipInfo.Addresses]
def blocked(name,node,action):
    before=state();count=int(node.AccessCount)
    try:action()
    except Exception:pass
    else:raise Exception(name+' accepted')
    check(name,state()==before and node.AccessCount==count+1)
addresses=[0xe00fefe0,0xe00fefe4,0xe00fefe8,0xe00fefec,0xe00feff0,0xe00feff4,0xe00feff8,0xe00feffc]
values=[0x23,0xb1,0x29,0x30,0x0d,0x10,0x05,0xb1]
check('owner-reference',p.ChipInfo is None and p.ChipInfoOwner==g and g.ChipInfo.JedecMockPart==0x123 and g.ChipInfo.JedecMockCid==0xb105100d)
for index,address in enumerate(addresses):
    check('mock-read-'+str(index),b.ReadDoubleWord(address)==values[index] and g.ChipInfo.GetReads(address)==1)
    blocked('readonly-'+str(index),p,lambda:b.WriteDoubleWord(address,values[index]))
check('reconstructed-part',((values[1]&15)<<8)|values[0]==0x123)
check('reconstructed-manufacturer',(values[2]&15)<<4|(values[1]>>4)==0x9b)
check('reconstructed-shared-revision',(values[2]>>4)<<4|(values[3]>>4)==g.ChipRevision==0x23)
before=state();p.Reset();check('owner-not-reset-by-delegate',state()==before)
for address in (0xe00fefdc,0xe00feffd,0xe0100000):blocked('unknown-'+str(address),p,lambda:b.ReadDoubleWord(address))
blocked('byte-width',p,lambda:b.ReadByte(0xe00fefe0))
blocked('word-width',p,lambda:b.WriteWord(0xe00fefe0,0))
blocked('quad-width',p,lambda:b.ReadQuadWord(0xe00fefe0))
blocked('default-unknown',u,lambda:u.ReadDoubleWord(0xefe0))
for revision,part,cid in [(0x23,-1,0),(0x23,0,-1),(0x23,4096,0),(0x23,0,0x100000000),(0x20,0,0)]:
    try:BlackwallChipIdentity(revision,part,cid)
    except Exception as e:check('invalid-constructor-'+str(part)+'-'+str(cid)+'-'+str(revision),'JEDEC mock' in str(e) or 'synthetic revision' in str(e))
    else:raise Exception('invalid identity accepted')
g.Reset();check('owner-reset-all-counts',all(g.ChipInfo.GetReads(a)==0 for a in g.ChipInfo.Addresses))
check('default6-preserved',not BlackwallChipIdentity(0x23).JedecMockEnabled and len(list(BlackwallChipIdentity(0x23).Addresses))==6)
Console.WriteLine('BLACKWALL_JEDEC '+json.dumps(dict(passed=True,checks=checks,assertion_count=len(checks),part_is_mock=True,cid_is_mock=True,hardware_validated=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
    if o.exists():raise ValueError('Use a new evidence directory')
    o.mkdir(mode=0o700);(o/'strict.cs').write_bytes((ROOT/'tools/renode-strict-mmio.cs').read_bytes());compile(DRIVER,'test.py','exec');(o/'test.py').write_text(DRIVER)
    (o/'board.repl').write_text('guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40000000\n    baseAddress: 0x40000000\n    size: 0x30000\n    chipRevision: 0x23\n    chipInfo: true\n    jedecMockPart: 0x123\n    jedecMockCid: 0xb105100d\nppb: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0xe0010000\n    baseAddress: 0xe0010000\n    size: 0x100000\n    chipInfoOwner: guard\nunknown: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0xe1000000\n    baseAddress: 0xe00f0000\n    size: 0x10000\n')
    (o/'probe.resc').write_text('include @/work/strict.cs\nmach create "jedec-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    rows=[json.loads(x.split('BLACKWALL_JEDEC ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_JEDEC ')];assert len(rows)==1
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(rows[0]))

if __name__=='__main__':main()
