"""Check that ideal sampling never supplies a missing device identity."""
import argparse,json
from pathlib import Path
from verify_mspi1_pio_reset import models
from verify_mspi1_sampling_profile import board
from verify_mspi1_rdid import COMMON
from native_replay import IMAGE
from run_renode_m55_probe import execute
DRIVER=COMMON+"check('ideal-without-identity',q.SamplingProfile=='ideal-sdr' and q.IdentityProfile=='none')\nblocked('sampling-does-not-invent-ID',start)\nConsole.WriteLine('BLACKWALL_SAMPLING_NONE '+json.dumps(dict(passed=True,count=len(checks),checks=checks)))\n"
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);b=board((s/'mspi1-sampling-context-01/stock24/board.repl').read_text());needle='    identityProfile: "mx25u25643g"\n'
 if b.count(needle)!=1:raise ValueError('Unexpected identity owner')
 (o/'board.repl').write_text(b.replace(needle,'    identityProfile: "none"\n'));(o/'strict.cs').write_bytes(models(s));(o/'test.py').write_text(DRIVER);(o/'probe.resc').write_text('include @/work/strict.cs\nmach create "sampling-none"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode');rows=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_SAMPLING_NONE ')]
 if len(rows)!=1:raise ValueError('Missing sampling-none result')
 (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],count=rows[0]['count'])))
if __name__=='__main__':main()
