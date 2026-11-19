"""Observe original CQFLAGS retention snapshot under explicit mock peer input levels."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute
PLANS=[('stock24','stock24',0),('stock23','stock23',0),('cfw','cfw',0),('stock24-input3','stock24',3),('stock24-unknown','stock24',None)]
FLAGS_MARKER="    c=m['sysbus.guard'].Mspi1Config\n    Console.WriteLine('BLACKWALL_CQ_FLAGS '+json.dumps(dict(input_levels=int(c.CqInputLevels),full_reads=int(c.CqFlagReads),last_value=int(c.LastCqFlags))))\n"
def board(text,levels):
 if levels is None:return text
 needle='    profile: "source-reset-config"\n'
 if text.count(needle)!=1:raise ValueError('Unexpected CQ owner')
 return text.replace(needle,needle+'    cqInputLevels: '+str(levels)+'\n')
def instrument(runtime,raw,prior,key):
 delta=0 if key=='stock24' else 0xd3d4;entry=0x4e8f8c-delta;load=0x4e92dc-delta;hook=load+8;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);c={x.address:(x.mnemonic,x.op_str) for x in md.disasm(raw[entry-0x438000:hook+2-0x438000],entry)}
 if c.get(entry)!=('push','{r4, r5, r6, lr}') or c.get(load)!=('ldr.w','r1, [r1, #0x2b0]') or c.get(load+4)!=('str.w','r1, [r5, #0x8b8]') or c.get(hook)!=('ldr','r1, [r5, #4]'):raise ValueError('Original flags snapshot path differs')
 state=prior['observed']['register_context']['r5'];snapshot=state+0x8b8
 if snapshot%4 or not 0x20000000<=snapshot<=0x20380000-4:raise ValueError('Snapshot not bounded SRAM')
 extra="    observer.AddPoint('CQFLAGS-saved',"+str(hook)+")\n    observer.CaptureSram(m,'CQFLAGS-saved',"+str(snapshot)+",1)\n"
 if runtime.count('    e.StartAll()\n')!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Runtime insertion differs')
 return runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n').replace('except Exception as error:\n',FLAGS_MARKER+'except Exception as error:\n'),dict(entry=entry,load=load,hook=hook,snapshot=snapshot)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,levels in PLANS:
  src=s/'mspi1-write-disable-main-01'/key;prior=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text())
  if v0!=prior['observed']:raise ValueError('Base report differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
  d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),levels));runtime,meta=instrument((src/'run.py').read_text(),raw,prior,key);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,cq_input_levels=levels,observation=meta),indent=2)+'\n');log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  flags=marker('BLACKWALL_CQ_FLAGS');ob=marker('BLACKWALL_OBSERVATION');q=marker('BLACKWALL_MSPI1_SAMPLING');points={x['label']:x for x in ob['points']}
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Selected event loss')
  if levels is None and boundary_state(v)!=boundary_state(v0):raise ValueError('Unknown flags changed base boundary')
  r=dict(passed=True,name=name,observed=v,cq_flags=flags,sampling=q,selected_observation=ob,observation=meta,selected_hypotheses=prior['selected_hypotheses'],additional_hypotheses=prior['additional_hypotheses']+[dict(mock_selected_peer_buffer_levels=levels,paired_buffer_XOR_XNOR_assumed=True,physical_handshake_verified=False)],CQ_execution_verified=False,array_addressing_verified=False,boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),cq_flags=flags,saved=points['CQFLAGS-saved']['snapshot'],events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW dependency differs')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='explicit mock flag inputs and original retention snapshot; no physical links, CQ/DMA execution or full boot/display proof'),indent=2)+'\n')
if __name__=='__main__':main()
