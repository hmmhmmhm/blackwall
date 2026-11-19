"""Compare original main with explicit immutable idle/busy bytes and unknown-status control."""
import argparse,json,shutil,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
PLANS=[('stock24-idle','stock24',64),('stock23-idle','stock23',64),('cfw-idle','cfw',64),('stock24-busy','stock24',65),('stock24-unknown','stock24',None)]
STATUS_MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    Console.WriteLine('BLACKWALL_NOR_STATUS '+json.dumps(dict(status_byte=int(q.StatusByte),reads_completed=int(q.StatusReadTransfers))))\n"
def instrument(runtime,raw,prior,key,compact=False):
 removed=[]
 for line in runtime.splitlines(True):
  if ('observer.AddPoint(' in line or 'observer.CaptureSram(' in line) and any("'"+label+"'" in line for label in ['rdid-fifo-return','classifier-input','classifier-result']):removed.append(line)
 if len(removed)!=4:raise ValueError('Unexpected repetitive RDID observations')
 for line in removed:runtime=runtime.replace(line,'')
 delta=0 if key=='stock24' else 0x4d18;entry=0x47b750-delta;poll=0x47b7e0-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[entry-0x438000:entry+0x7c-0x438000],entry)}
 expected={0:('push','{r0, r1, r2, r3, r4, lr}'),0x6a:('ldrb.w','r0, [sp, #8]'),0x6e:('lsls','r0, r0, #0x1f'),0x70:('bpl','#'+hex(entry+0x76)),0x72:('movs','r0, #1'),0x76:('movs','r0, #0'),0x78:('add','sp, #0x10'),0x7a:('pop','{r4, pc}')}
 if any(code.get(entry+n)!=pair for n,pair in expected.items()):raise ValueError('Original status branch differs')
 poll_code={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[poll-0x438000:poll+0x52-0x438000],poll)}
 if poll_code.get(poll)!=('push','{r3, r4, r5, lr}') or poll_code.get(poll+0x50)!=('pop','{r1, r4, r5, pc}'):raise ValueError('Original poll return differs')
 st=prior['observed']['stack_context'];buf=struct.pack('<32I',*st['words']);off=prior['observed']['register_context']['r1']-st['base'];buffer=struct.unpack_from('<I',buf,off+20)[0]
 if off!=36 or not 0x20000000<=buffer<=0x20380000-4 or buffer%4:raise ValueError('Saved status buffer differs')
 extra=''
 for label,address in ([('status-result',entry+0x78),('status-poll-return',poll+0x50)] if compact else [('status-byte',entry+0x6e),('status-result',entry+0x78),('status-poll-return',poll+0x50)]):extra+="    observer.AddPoint('"+label+"',"+str(address)+")\n"
 extra+="    observer.CaptureSram(m,'"+('status-result' if compact else 'status-byte')+"',"+str(buffer)+",1)\n"
 if runtime.count('    e.StartAll()\n')!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Runtime insertion point differs')
 meta=dict(status_entry=entry,poll_entry=poll,first_buffer=buffer,removed_points=['rdid-fifo-return','classifier-input','classifier-result'])
 if compact:meta['compact_results_only']=True
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n').replace('except Exception as error:\n',STATUS_MARKER+'except Exception as error:\n'),meta
def board(text,status):
 if status is None:return text
 needle='    profile: "idle-nor-reset"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected NOR owner')
 return text.replace(needle,needle+'    statusByte: '+str(status)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--remaining',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,status in PLANS:
  if a.remaining and status==64:continue
  src=s/'mspi1-zero-main-01'/key;prior=json.loads((src/'report.json').read_text());check=parse_log((src/'renode.log').read_text())
  if check!=prior['observed']:raise ValueError('Saved base report differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
  d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),status));runtime,meta=instrument((src/'run.py').read_text(),raw,prior,key,status==65);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,status_byte=status,observation=meta),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  ob=marker('BLACKWALL_OBSERVATION');st=marker('BLACKWALL_NOR_STATUS');q=marker('BLACKWALL_MSPI1_SAMPLING')
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Observation overflow; inspect retained evidence')
  if status is None and boundary_state(v)!=boundary_state(check):raise ValueError('Unknown status changed prior boundary')
  r=dict(passed=True,name=name,observed=v,nor_status=st,sampling=q,selected_observation=ob,observation=meta,selected_hypotheses=prior['selected_hypotheses'],additional_hypotheses=prior['additional_hypotheses']+[dict(immutable_status_byte=status,physical_state_known=False)],boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),nor_status=st,sampling=q,events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 if not a.remaining:
  for f in ['strict.cs','board.repl','result.py','probe.resc']:
   if (o/'stock23-idle'/f).read_bytes()!=(o/'cfw-idle'/f).read_bytes():raise ValueError('Stock/CFW dependency differs')
  if (o/'stock23-idle/run.py').read_text().replace('3758688','3829832')!=(o/'cfw-idle/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='immutable status-byte scenarios in original ARM main; no physical state, NV writes, full boot or display proof'),indent=2)+'\n')
if __name__=='__main__':main()
