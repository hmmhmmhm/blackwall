"""Derive a frozen original-main experiment with one explicit pointer-only virtual I2C peer."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from native_replay import FILES,IMAGE,digest,validate_assets,parse_log
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Use a fresh evidence directory')
 prior=s/'iom7-request-observation-02';o.mkdir(mode=0o700);peer=(ROOT/'tools/renode-i2c-pointer-probe.cs').read_bytes();(o/'peer.cs').write_bytes(peer);(o/'runner.py').write_bytes(Path(__file__).read_bytes());rows=[]
 for name in ('stock24','stock23','cfw'):
  source=prior/name;reference=json.loads((source/'report.json').read_text());old=parse_log((source/'renode.log').read_text())
  if old!=reference['observed'] or reference['image_id']!=IMAGE or old['pc'] not in (0x58236c,0x57b014):raise ValueError('Unexpected frozen base')
  launch=json.loads((prior/(name+'-launcher.json')).read_text());_,raw=load_pinned_main(Path(launch['command'][2]).read_bytes())
  if raw!=(source/'main.bin').read_bytes():raise ValueError('Pinned main differs')
  base={f:digest(source/f) for f in FILES};d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(source/f,d/f)
  validate_assets(d,base)
  (d/'strict.cs').write_bytes((d/'strict.cs').read_bytes()+b'\n'+peer)
  (d/'board.repl').write_text((d/'board.repl').read_text()+'\npointerProbe: Miscellaneous.BlackwallI2cPointerProbe @ iom7 0x6b\n')
  # Add one explicit guard node to the existing reporting path, without changing guest execution.
  for file in ('run.py','result.py'):
   text=(d/file).read_text();needle="for name in ('rstgen', "
   if text.count(needle)!=1:raise ValueError('Reporting guard catalog differs')
   text=text.replace(needle,"for name in ('iom7.pointerProbe', 'rstgen', ")
   text=text.replace("peer_attached=False","peer_attached=(int(w.Module)==7)")
   if file=='run.py':
    marker="except Exception as error:\n"
    if text.count(marker)!=1:raise ValueError('Runtime error boundary differs')
    extra="    peer=m['sysbus.iom7.pointerProbe']\n    Console.WriteLine('BLACKWALL_POINTER '+json.dumps(dict(pointer=int(peer.Pointer),writes=int(peer.Writes),finishes=int(peer.Finishes),read_attempts=int(peer.ReadAttempts),blocked=int(peer.AccessCount),operation=str(peer.LastOperation),requested_length=int(peer.LastWidth))))\n"
    text=text.replace(marker,extra+marker)
   compile(text,file,'exec');(d/file).write_text(text)
  derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=base,derived=derived,peer_sha256=hashlib.sha256(peer).hexdigest(),base_report_sha256=digest(source/'report.json'),profile='explicit-synthetic-pointer-0509-no-read-response'),indent=2)+'\n')
  command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(command,indent=2)+'\n')
  log=execute(command,d,'renode');v=parse_log(log);validate_assets(d,derived)
  probes=[json.loads(line.split('BLACKWALL_POINTER ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_POINTER ')]
  if len(probes)!=1:raise ValueError('Missing peer result')
  state=probes[0];guard=[g for g in v['guards'] if g['accesses']];iom=next(i for i in v['ioms'] if i['module']==7)
  report=dict(name=name,observed=v,pointer_probe=state,image_id=IMAGE,raw_main_sha256=hashlib.sha256(raw).hexdigest(),reset_vector=hex(struct.unpack_from('<I',raw,4)[0]),selected_hypotheses=reference['selected_hypotheses'],additional_hypothesis='only 05 09 pointer accepted at IOM7 address6b, every read blocked; not a PMIC model',boot_verified=False,hardware_validated=False,installable=False)
  (d/'report.json').write_text(json.dumps(report,indent=2)+'\n')
  if state!=dict(pointer=0x509,writes=1,finishes=1,read_attempts=1,blocked=1,operation='peer-read-unknown',requested_length=1):raise ValueError('Unexpected original next request; inspect saved report')
  if len(guard)!=1 or guard[0]['name']!='iom7.pointerProbe' or not iom['peer_attached'] or iom['commands']!=2:raise ValueError('Unexpected IOM transfer boundary')
  row=dict(name=name,pc=hex(v['pc']),peer=state,guard=guard,iom7_commands=iom['commands']);rows.append(row);print(json.dumps(row),flush=True)
 for f in ('board.repl','strict.cs','probe.resc','result.py'):
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW model differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs beyond main length')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='explicit virtual pointer allows original next read request; no data response, physical device or full boot'),indent=2)+'\n')
if __name__=='__main__':main()
