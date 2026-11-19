"""After an original-main halt, isolate the bank's OTP gate while buck remains ready."""
import argparse,json,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,validate_assets
from run_renode_m55_probe import execute

PROOF='''
checks=[]
def proof(n,v):
    if not v:raise Exception(n)
    checks.append(n)
g=m['sysbus.guard'];cp=g.CryptoPower;otp=g.OtpPower
proof('original-prelude-buck-active',str(g.BuckResponsePhase)=='active' and cp.Phase=='on' and otp.Phase=='on')
# Host fault injection after the saved original report. CPU stays halted.
cp.Reset();otp.Reset()
word=g.ReadDoubleWord(0x20004);writes=g.DevicePowerWrites;access=g.AccessCount
proof('only-OTP-precondition-missing',g.BuckResponsePhase=='active' and cp.Phase==otp.Phase=='off' and word==0x400)
try:g.WriteDoubleWord(0x20004,word|0x200000)
except Exception as error:proof('OTP-gate-rejection', 'BLACKWALL unsupported' in str(error))
else:raise Exception('crypto activated without OTP')
proof('rejection-is-atomic',cp.RequestWord==cp.StatusWord==cp.Requests==cp.Responses==0 and g.DevicePowerWrites==writes and g.AccessCount==access+1)
proof('local-OTP-request',otp.TryWrite(0x08000000,True));g.ReadDoubleWord(0x20008)
word=g.ReadDoubleWord(0x20004);g.WriteDoubleWord(0x20004,word|0x200000)
proof('same-bank-accepts-after-OTP-on',cp.Phase=='requested' and cp.RequestWord==0x200000 and cp.StatusWord==0 and otp.Phase=='on')
proof('status-response-preserves-others',g.ReadDoubleWord(0x20008)==0x08200400 and cp.Phase=='on' and cp.Requests==cp.Responses==1)
Console.WriteLine('BLACKWALL_CRYPTO_OTP_GATE '+json.dumps(dict(passed=True,count=len(checks),checks=checks,scope='host fault injection after original CPU halt; not stock recovery or firmware execution of this fault')))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output
    src=s/'crypto-power-main-01/stock24';o.mkdir(mode=0o700)
    validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived'])
    for name in FILES:shutil.copyfile(src/name,o/name)
    (o/'run.py').write_text((src/'run.py').read_text()+PROOF)
    pins={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=pins),indent=2)+'\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=None)
    validate_assets(o,pins)
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_CRYPTO_OTP_GATE ')]
    if len(rows)!=1:raise ValueError('Missing post-halt gate result; inspect preserved log')
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))


if __name__=='__main__':main()
