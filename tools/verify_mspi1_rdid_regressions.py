"""Replay frozen PIO and mixed-mode units with current RDID-capable source."""
import argparse,json,shutil
from pathlib import Path
from native_replay import IMAGE,digest
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
CASES=[('mspi1-pio-unit-05','BLACKWALL_MSPI1_PIO_UNIT',26),('mspi1-xip-mixed-unit-02','BLACKWALL_MSPI1_XIP_MIXED_UNIT',63)]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,tag,count in CASES:
  src=a.simulator/name;d=o/name;d.mkdir(mode=0o700);files=[x for x in src.iterdir() if x.name in ['board.repl','probe.resc','spin.bin'] or x.suffix=='.py']
  for f in files:shutil.copyfile(f,d/f.name)
  (d/'strict.cs').write_bytes(models(a.simulator));pins={f.name:digest(d/f.name) for f in files};log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode');found=[json.loads(x.split(tag+' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
  if len(found)!=1 or not found[0]['passed'] or found[0]['count']!=count or any(digest(d/n)!=h for n,h in pins.items()):raise ValueError('Regression failed '+name)
  r=dict(name=name,passed=True,count=count,source_sha256=digest(d/'strict.cs'),fixtures=pins);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');rows.append(r);print(json.dumps(dict(name=name,count=count,passed=True)),flush=True)
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2)+'\n')
if __name__=='__main__':main()
