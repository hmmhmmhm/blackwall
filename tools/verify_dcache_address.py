"""Native coherent SRAM MVA behavior and default rejection; no firmware/device."""
import argparse,json
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from dcache_address_models import assemble

DRIVER='''import clr,json
from System import Console
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallCoherentDataCache').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCoherentDataCache,BlackwallSystemControl
checks=[]
def check(n,v):
    if not v:raise Exception(n)
    checks.append(n)
c=BlackwallCoherentDataCache() if BASELINE else BlackwallCoherentDataCache(True)
check('SRAM-clean-line-supported',c.TryWrite(0xf68,4,0x2035cc60))
check('live-line-counter',c.AddressCleans==1 and c.LastAddressLine==0x2035cc60)
check('SRAM-clean-to-PoU',c.TryWrite(0xf64,4,0x2001bb00))
for off,name in [(0xf5c,'invalidate'),(0xf64,'clean-pou'),(0xf68,'clean'),(0xf70,'both')]:
    for value in [0x20000000,0x20000003,0x2037ffff]:
        check(name+'-'+hex(value),c.TryWrite(off,4,value) and c.LastAddressLine==value&~31)
    for width in [1,2,8]:check('width-'+name+str(width),not c.TryWrite(off,width,0x20000000))
    for value in [0,0x1fffffff,0x20380000,0x438000,0x80100000,0x40039000,0x100000000]:check('range-'+name+hex(value),not c.TryWrite(off,4,value))
check('address-ops-do-not-initialize-cache',c.InitializedLines==0 and not c.CanSetEnabled(True))
check('separate-counters',c.AddressInvalidations==3 and c.AddressCleans==4 and c.AddressCleanInvalidations==3 and c.AddressUnificationCleans==4 and c.Invalidations==c.Cleans==c.CleanInvalidations==0)
for off in [0xf5c,0xf64,0xf68,0xf70]:check('default-still-strict-'+hex(off),not BlackwallCoherentDataCache().TryWrite(off,4,0x20000000))
check('selector',c.TryWrite(0xd84,4,0))
for i in range(512):
    for way in range(4):
        if not c.TryWrite(0xf60,4,(way<<30)|(i<<5)):raise Exception('setway sweep')
check('setway-initialization-preserved',c.InitializedLines==2048 and c.Invalidations==2048 and c.CanSetEnabled(True))
c.SetEnabled(True);check('enabled-address-operation',c.TryWrite(0xf68,4,0x20377740) and c.Enabled)
c.SetEnabled(False);check('disable-keeps-address-profile',c.InitializedLines==0 and c.TryWrite(0xf68,4,0x20377743) and c.LastAddressLine==0x20377740)
try:BlackwallSystemControl(monitor.Machine,None,None,True,False,True)
except Exception as e:check('address-profile-needs-coherent-data','SRAM address maintenance requires coherent data cache' in str(e))
else:raise Exception('invalid cache profile accepted')
Console.WriteLine('BLACKWALL_DCACHE_ADDRESS '+json.dumps(dict(passed=True,count=len(checks),checks=checks,hardware_accessed=False,physical_cache_verified=False)))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700)
    candidate,manifest=assemble(s);(o/'strict.cs').write_bytes(candidate);(o/'model-components.json').write_text(json.dumps(manifest,indent=2)+'\n');(o/'test.py').write_text(DRIVER.replace('BASELINE',str(a.baseline)));(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "SRAM-cache-address"\ninclude @/work/test.py\nquit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_DCACHE_ADDRESS ')]
    if len(rows)!=1:raise ValueError('Missing cache address marker; inspect native log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))

if __name__=='__main__':main()
