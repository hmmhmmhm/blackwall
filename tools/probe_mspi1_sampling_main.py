"""Replay original scan under explicit ideal phase abstraction, with a fixed-profile control."""
import argparse,json,shutil,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,parse_log,validate_assets,boundary_state,digest
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
from verify_mspi1_sampling_profile import board
MARKER="    q=m['sysbus.guard'].Mspi1Config.Pio\n    sampling_state=dict(profile=str(q.SamplingProfile),completed_mask=int(q.CompletedSamplingMask),starts=int(q.Starts),completions=int(q.Completions),id_frames=int(q.ReadIdTransfers),fifo_reads=int(q.FifoReads),pending=int(q.RxEntries),busy=bool(q.Busy),control=int(q.Control))\n    Console.WriteLine('BLACKWALL_MSPI1_SAMPLING '+json.dumps(sampling_state))\n"
LIVE_WAIT="    import json\n    from System import Console\n    live_cpu=m['sysbus.cpu']\n    live_seconds=0\n    while not m.IsPaused:\n        time.sleep(1.0)\n        live_seconds+=1\n        if live_seconds%5==0:\n            Console.WriteLine('BLACKWALL_LIVE '+json.dumps(dict(seconds=live_seconds,pc=int(live_cpu.PC.RawValue),r0=int(live_cpu.GetRegister(0).RawValue),instructions=int(live_cpu.ExecutedInstructions),paused=bool(m.IsPaused))))\n            Console.Out.Flush()\n"
PLANS=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-fixed','stock24',False)]
def observation(runtime,raw,meta,base_observation,wait_mode="until-paused"):
 entries=[x for x in base_observation['events'] if x['label']=='scan-table-0']
 if len(entries)!=1:raise ValueError('Missing scan input')
 output=entries[0]['r0'];matrix=output-0xcc;scan=meta['scan'];delta=0x47ab18-scan;ret=0x47ad9a-delta;md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 code={x.address:x for x in md.disasm(raw[scan-0x438000:scan-0x438000+0x270],scan)}
 if any(scan+off not in code for off in [0xaa,0xac,0xae]):raise ValueError('Matrix hooks must be instruction boundaries')
 expected={0xc:('movs','r2, #0x90'),0x10:('add','r0, sp, #0x2c'),0x4c:('add','r0, sp, #0x2c'),0x58:('str.w','r1, [r0, r6, lsl #2]'),0x68:('cmp','r6, r5'),0x6a:('bhs','#'+hex(scan+0xaa)),0xaa:('movs','r6, #0'),0xac:('movs','r7, #0'),0xae:('movs','r0, #0'),0xb6:('add','r0, sp, #0x2c'),0xb8:('add.w','r0, r0, r8, lsl #2'),0x1da:('add','r0, sp, #0x2c'),0x1dc:('add.w','r0, r0, r6, lsl #2')}
 if any(scan+off not in code or (code[scan+off].mnemonic,code[scan+off].op_str)!=pair for off,pair in expected.items()):raise ValueError('Final pass matrix and selection pointer derivation differ')

 if (code[scan].mnemonic,code[scan].op_str)!=('push.w','{r3, r4, r5, r6, r7, r8, lr}') or (code[scan+4].mnemonic,code[scan+4].op_str)!=('sub','sp, #0xbc'):raise ValueError('Scan stack frame differs')
 wrapper=list(md.disasm(raw[ret-0x14-0x438000:ret-0x438000],ret-0x14));wm={x.address:(x.mnemonic,x.op_str) for x in wrapper}
 if wm.get(ret-0x14)!=('push','{r4, lr}') or wm.get(ret-0x12)!=('sub','sp, #0x28') or wm.get(ret-6)!=('add','r0, sp, #0x20'):raise ValueError('Scan output/stack derivation differs')

 caller=list(md.disasm(raw[ret-4-0x438000:ret-0x438000],ret-4))
 if len(caller)!=1 or caller[0].mnemonic!='bl' or caller[0].op_str!='#'+hex(scan):raise ValueError('Scan return differs')
 if output%4 or matrix%4 or not 0x20000000<=matrix<output<=0x20380000-8:raise ValueError('Output/matrix must be bounded SRAM')
 extra=''
 for n,(off,words) in enumerate([(0xaa,16),(0xac,16),(0xae,4)]):extra+="    observer.AddPoint('scan-matrix-"+str(n)+"',"+str(scan+off)+")\n    observer.CaptureSram(m,'scan-matrix-"+str(n)+"',"+str(matrix+n*64)+','+str(words)+')\n'
 extra+="    observer.AddPoint('scan-return',"+str(ret)+")\n    observer.CaptureSram(m,'scan-return',"+str(output)+",2)\n"
 needle='    e.StartAll()\n'
 if runtime.count(needle)!=1 or runtime.count('except Exception as error:\n')!=1:raise ValueError('Unexpected observation runtime')
 runtime=runtime.replace(needle,extra+needle).replace('except Exception as error:\n',MARKER+'except Exception as error:\n')
 if wait_mode=='until-paused':
  old='    time.sleep(15.0)\n'
  if runtime.count(old)!=1:raise ValueError('Unexpected legacy observation window')
  live=LIVE_WAIT
  runtime=runtime.replace(old,live)
 elif wait_mode!='legacy':raise ValueError('Unknown observation wait mode')
 return runtime,dict(output=output,matrix=matrix,return_point=ret)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--remaining',action='store_true');a=p.parse_args();s=a.simulator;o=a.output;o.mkdir(mode=0o700);rows=[]
 for name,key,ideal in PLANS:
  if a.remaining and name=='stock24':continue
  src=s/'mspi1-sampling-context-01'/key;r=json.loads((src/'report.json').read_text());prior=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or prior!=r['observed']:raise ValueError('Frozen source differs')
  validate_assets(src,json.loads((src/'derived-inputs.json').read_text())['derived']);d=o/name;d.mkdir(mode=0o700)
  for f in FILES:shutil.copyfile(src/f,d/f)
  (d/'strict.cs').write_bytes(models(s));(d/'board.repl').write_text(board((src/'board.repl').read_text(),ideal));runtime,capture=observation((src/'run.py').read_text(),raw,r['metadata'],r['selected_observation']);compile(runtime,'run.py','exec');(d/'run.py').write_text(runtime);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base={f:digest(src/f) for f in FILES},derived=derived,ideal_sampling=ideal,capture=capture,wait_mode="until-paused"),indent=2)+'\n')
  log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode',timeout=None);v=parse_log(log);validate_assets(d,derived)
  def marker(tag):
   z=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith(tag+' ')]
   if len(z)!=1:raise ValueError(tag)
   return z[0]
  state=marker('BLACKWALL_MSPI1_SAMPLING');ob=marker('BLACKWALL_OBSERVATION');points={x['label']:x for x in ob['points']}
  if ob['dropped_events'] or len(ob['events'])!=ob['sequence']:raise ValueError('Selected event stream overflow; inspect retained evidence')
  if not ideal and boundary_state(v)!=boundary_state(prior):raise ValueError('Default boundary changed')
  masks=[]
  for n in range(3):
   pnt=points['scan-matrix-'+str(n)]
   if pnt['snapshot'] is not None:masks+=pnt['snapshot']['words']
  output=points['scan-return']['snapshot'];selection=None if output is None else struct.pack('<2I',*output['words'])[:6].hex();baseline=json.loads((s/'mspi1-rdid-main-01'/key/'report.json').read_text())
  report=dict(passed=True,name=name,observed=v,sampling=state,selected_observation=ob,capture=capture,pass_masks=masks,selection=selection,selected_hypotheses=baseline['selected_hypotheses'],additional_hypotheses=baseline['additional_hypotheses']+[dict(sampling_profile=state['profile'],physical_signal_margin=False)],boot_verified=False,hardware_validated=False,installable=False);(d/'report.json').write_text(json.dumps(report,indent=2)+'\n');row=dict(name=name,pc=hex(v['pc']),sampling=state,scan_return_hits=points['scan-return']['hits'],selection=selection,matrix_words=len(masks),selected_events=ob['sequence'],guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 for f in ['strict.cs','board.repl','result.py','probe.resc']:
  if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
 if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='explicit ideal digital phase abstraction only; no physical timing margin or full boot/display proof'),indent=2)+'\n')
if __name__=='__main__':main()
