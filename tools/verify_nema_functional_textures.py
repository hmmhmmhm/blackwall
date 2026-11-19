"""Verify declared packing/texture reference policies; no physical GPU or ARM CPU."""
import argparse,json,hashlib
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve()
s=Path.home()/'Library/Application Support/Blackwall/simulator'
if o.exists() or not o.is_relative_to(s) or o.is_relative_to(R):p.error('New private simulator output required')
o.mkdir(mode=0o700)
inputs={}
for name,path in [('consumer.cs',R/'tools/nema-ring-consumer.cs'),('packing.cs',R/'tests/nema-functional-packing-tests.cs'),('texture.cs',R/'tests/nema-functional-texture-tests.cs')]:
 data=path.read_bytes();(o/name).write_bytes(data);inputs[str(path.relative_to(R))]=hashlib.sha256(data).hexdigest()
(o/'test.py').write_text('from System import AppDomain\nfor name in ["PackingTests","TextureTests"]:\n for asm in AppDomain.CurrentDomain.GetAssemblies():\n  t=asm.GetType(name)\n  if t is not None:t.GetMethod("Run").Invoke(None,None)\n')
(o/'probe.resc').write_text('include @/work/consumer.cs\ninclude @/work/packing.cs\ninclude @/work/texture.cs\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=90)
counts={}
for tag in ['PACKING','TEXTURE']:
 rows=[x for x in log.splitlines() if x.startswith('BLACKWALL_'+tag+'_CHECKS ')]
 if len(rows)!=1:raise ValueError('Missing '+tag+' result; inspect log')
 counts[tag.lower()]=int(rows[0].split()[-1])
report=dict(passed=True,checks=counts,source_sha256=inputs,hardware_validated=False)
(o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
