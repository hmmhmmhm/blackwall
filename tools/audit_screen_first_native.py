"""Audit the fixed stock24 natural-main first-screen capture and export a local viewer."""
import argparse,hashlib,json,struct,zlib,html,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
S=Path.home()/'Library/Application Support/Blackwall/simulator'
MAIN='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def png(data,w=576,h=288):
 def chunk(tag,payload):return struct.pack('>I',len(payload))+tag+payload+struct.pack('>I',zlib.crc32(tag+payload)&0xffffffff)
 rows=b''.join(b'\0'+data[y*w:(y+1)*w] for y in range(h))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
def audit(capture,out):
 if out.exists() or not out.is_relative_to(S) or out.is_relative_to(R):raise ValueError('New private simulator audit output required')
 out.mkdir(mode=0o700);(out/'auditor.py').write_bytes(Path(__file__).read_bytes());ex=capture/'exports';load=lambda n:json.loads((ex/n).read_text())
 frame=(ex/'screen-complete.bin').read_bytes();meta=load('screen-complete.json');gpu=load('gpu.json');touch=load('touch.json');ui=load('ui-layout.json');gaf=load('gaf-fault-state.json');end=load('after-broadcast.json');profile=json.loads((capture/'functional-profile.json').read_text());process=json.loads((capture/'renode.process.json').read_text())
 baseline=S/'gaf-render-scheduler-native-01/stock24/exports';run=(capture/'run.py').read_text()
 checks=dict(original_main=sha(capture/'main.bin')==MAIN==profile['main_sha256'],model_hash=sha(capture/'strict.cs')==profile['model_sha256'],
  no_cpu_control_patch=not any(re.search(p,run) for p in [r'\.SetRegister\s*\(',r'\.SeedRegister\s*\(',r'\.PC\s*=',r'\.WriteDoubleWord\s*\(',r'\.WriteByte\s*\(']),
  startup_prefix=all((ex/n).read_bytes()==(baseline/n).read_bytes() for n in ['before-input-sram.bin','after-input-sram.bin','before-reply-sram.bin']),
  touch_consumed=touch['event_completed']==1 and touch['handler_calls']==1 and touch['event_chunks']==4,
  original_ui_callbacks=ui['counts']['6']==1 and ui['counts']['8']==1 and ui['counts']['7']>=4,
  all_guards_zero=all(g['accesses']==0 for g in touch['guards']),cpu_faults_zero=touch['cfsr']==touch['hfsr']==touch['memory_violations']==0,
  gpu_accepted=gpu['rejections']==0 and gpu['fault']=='' and gpu['lists']>0 and gpu['draws']>0,
  frame_extent=len(frame)==576*288 and meta['width']==576 and meta['height']==288,
  frame_spatial_detail=bool(frame) and min(frame)<max(frame) and any(frame),
  frame_metadata=meta['has_detail'] and meta['nonzero_pixels']==sum(v!=0 for v in frame) and meta['captures']>=1 and meta['source']=='guest-L8-after-original-packing-completed',
  source_range=0x20000000<=meta['address']<=0x20380000-len(frame),
  frame_stop=end['stopped'] and end['stop_reason']=='frame',
  explicit_functional_model=not profile['numerical_gaf_validated'] and not gaf['calculation_supported'] and gaf['completed_services']==2 and gaf['fifo_ready'],
  owned_process_removed=process['status']=='removed')
 passed=all(checks.values())
 report=dict(passed=passed,first_screen_verified=passed,no_firmware_or_cpu_control_patch=checks['original_main'] and checks['no_cpu_control_patch'],all_runtime_guards_zero=checks['all_guards_zero'] and checks['cpu_faults_zero'] and checks['gpu_accepted'],
  scope='one stock24 natural main/reset/touch/UI frame on explicit functional devices; not physical GPU, whole boot, other firmware, or continuous-frame acceptance',
  frame=dict(width=576,height=288,bytes=len(frame),nonzero_pixels=sum(v!=0 for v in frame),spatial_detail=checks['frame_spatial_detail'],source_address=meta['address'],sha256=hashlib.sha256(frame).hexdigest(),minimum=min(frame) if frame else None,maximum=max(frame) if frame else None),
  original_ui_glyph_calls=ui['counts']['7'],gpu_draws=gpu['draws'],gpu_lists=gpu['lists'],hardware_validated=False,full_boot_verified=False,checks=checks,
  inputs={n:sha(capture/n) for n in ['main.bin','strict.cs','board.repl','run.py','functional-profile.json']},capture=str(capture))
 if passed:
  (out/'screen-raw.png').write_bytes(png(frame));(out/'screen-gain-16.png').write_bytes(png(bytes(min(255,v*16) for v in frame)))
  page='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Blackwall · G2 guest frame</title><style>body{background:#151515;color:#eee;font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}img{width:100%;image-rendering:pixelated;background:black;filter:brightness(16)}p{color:#aaa}a{color:#9bd}input{width:240px}</style><h1>Original G2 UI · 576×288</h1><p>Stock 2.4 ARM · natural reset → touch → UI → GPU → display conversion</p><img id="frame" src="screen-raw.png" alt="Original guest dashboard"><p>Display brightness ×<output id="value">16</output> <input id="gain" type="range" min="1" max="32" value="16"> · guest pixels unchanged</p><p><a href="screen-raw.png">Original pixel PNG</a> · <a href="report.json">Verification record</a></p><p>Virtual device: cold GAF · constant 100 lux · functional reference GPU. Physical optics, GPU fidelity, and full boot verification are separate.</p><script>const g=document.getElementById('gain');g.addEventListener('input',()=>{document.getElementById('value').value=g.value;document.getElementById('frame').style.filter='brightness('+g.value+')';});</script></html>'''
  (out/'index.html').write_text(page)
  report['artifacts']={n:sha(out/n) for n in ['screen-raw.png','screen-gain-16.png','index.html']}
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();d=audit(a.capture.resolve(),a.output.resolve());print(json.dumps(dict(passed=d['passed'],frame=d['frame'],failed=[k for k,v in d['checks'].items() if not v])));raise SystemExit(0 if d['passed'] else 1)
