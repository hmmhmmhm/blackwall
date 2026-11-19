"""Pinned old-family natural reset/touch/UI experiment with frozen screen devices.
No hardware access. Version-specific board properties remain from bw452.
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from native_replay import IMAGE
from reset_restart_profiles import profile
from run_renode_m55_probe import execute
from run_native_candidate import semantic_spec,finish_capture
R=Path(__file__).resolve().parents[1]
S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def pinned_manifest(name,digest):
 p=S/name
 if sha(p)!=digest:raise ValueError('Changed source manifest '+name)
 return load(p)
def frozen_file(p,m):
 entries=m['files']
 if isinstance(entries,list):expected=next(x['sha256'] for x in entries if x['path']==str(p))
 else:expected=entries[str(p.relative_to(S))]['sha256']
 if sha(p)!=expected:raise ValueError('Changed frozen source '+str(p))
 return expected
POST='''                # Callback return is taken from this image's checked registry contract.
                if not m.IsPaused or int(cpu.PC.RawValue)!=wake['ui']['call_site']:raise ValueError('Missing UI dispatch')
                if int(cpu.PerformanceInMips)!=10 or ((int(g.McuClock.ModeWord)>>3)&3)!=2:raise ValueError('Unverified HP rate boundary')
                rate_before=dict(registers=registers(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions))
                File.WriteAllBytes('/work-output/rate-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                cpu.PerformanceInMips=167
                rate_after=dict(registers=registers(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions))
                File.WriteAllBytes('/work-output/rate-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                if rate_before!=rate_after:raise ValueError('Rate input changed paused state')
                callback_end=BlackwallRuntimeConnectionObserver(m,cpu,p['isr'],wake['ui']['callback'],wake['ui']['return_site'],p['tcb_slot'])
                EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+60;started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                while not callback_end.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-started<1000*int(TimeInterval.TicksPerMillisecond):time.sleep(0.02)
                m.Pause()
                gpu=g.GpuCommandDevice
                callback=dict(stopped=bool(callback_end.Stopped),pc=int(cpu.PC.RawValue),entry=[int(v) for v in callback_end.Entry],exit=[int(v) for v in callback_end.Exit])
                if callback_end.Stopped:
                    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+120;started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                    while not m.IsPaused and not cpu.IsHalted and int(gpu.Rejections)==0 and not gpu.CompleteScreenHasDetail and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-started<1000*int(TimeInterval.TicksPerMillisecond):time.sleep(0.02)
                    m.Pause()
                boot=dict(callback=callback,rate_before=rate_before,rate_after=rate_after,pc=int(cpu.PC.RawValue),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions),frame=bool(gpu.CompleteScreenHasDetail),frame_serial=int(gpu.CompleteScreenCaptures),nonzero=int(gpu.CompleteScreenNonzero),gpu_rejections=int(gpu.Rejections),gpu_fault=str(gpu.Fault),gpu_lists=int(gpu.ListsConsumed),gpu_draws=int(gpu.Draws),fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),retention_stages=int(g.CpuNormalSleep.RetentionStages))
                imu=m['sysbus.iom4.imu_fifo'].StartupPeer
                boot['sensor']=dict(phase=str(imu.OnDemand.Phase),services=int(imu.OnDemand.CompletedServices),last_write=str(imu.LastWriteHex))
                File.WriteAllBytes('/work-output/family-screen.bin',gpu.CompleteScreenFrameBytes)
                File.WriteAllText('/work-output/family-boot.json',json.dumps(boot))
'''
def derive(case,o):
 screen=pinned_manifest('screen-first-functional-manifest.json','0ba154614177b0620b5204aaecaec5167ffdfd64e3ef16034eabcb41e1a10d22')
 family=load(S/'touch-wake-families-manifest.json')
 # Pin the root as well as the individual files, rather than trust a mutable list.
 if sha(S/'touch-wake-families-manifest.json')!=FAMILY_PIN:raise ValueError('Changed family acceptance')
 b=S/'touch-wake-families-native-01'/case;f=S/'screen-first-native-23'
 pins={}
 o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir(mode=0o700)
 for p in b.iterdir():
  if p.is_file() and p.suffix in ['.cs','.bin','.json','.py','.resc','.repl'] and p.name!='renode.process.json':
   pins[str(p.relative_to(S))]=frozen_file(p,family);shutil.copyfile(p,o/p.name)
 for name in ['strict.cs','board.repl']:
  pins[str((f/name).relative_to(S))]=frozen_file(f/name,screen)
 shutil.copyfile(f/'strict.cs',o/'strict.cs')
 # Reuse the common chip model; retain every firmware-qualified property in old board.
 board=(b/'board.repl').read_text();new=(f/'board.repl').read_text()
 for old,add in [('    gpuOffSequenceStorage: true\n','    gpuRuntimeWakeResponse: 1\n'),('timer14: Miscellaneous.BlackwallTimer14 @ none\n','    idleChannelControls: true\n')]:
  if board.count(old)!=1:raise ValueError('Changed device boundary')
  board=board.replace(old,old+add,1)
 rp=profile(S,case,(o/'main.bin').read_bytes())
 board=board.replace('cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n','cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n    retentionStorePc: 0x%x\n    retentionReturnPc: 0x%x\n    inactiveAudioStatus: true\n    retentionFlush: true\n'%(rp['retention_store'],rp['retention_return']))
 board=board.replace('imu_identity: Miscellaneous.BlackwallImuIdentity @ iom4 0x69\n','imu_identity: Miscellaneous.BlackwallImuIdentity @ none\n    gafOnDemandControl: true\n    gafOnDemandMicroseconds: 1000\n')
 board+='\ngpuRing:'+new.split('\ngpuRing:',1)[1]
 (o/'board.repl').write_text(board)
 runtime=(b/'run.py').read_text().replace("m['sysbus.iom4.imu_identity']","m['sysbus.iom4.imu_fifo'].StartupPeer")
 start=runtime.index('                callback_end=BlackwallRuntimeConnectionObserver',runtime.index('if end.Stopped:'))
 end=runtime.index('\n    guards=[]',start)
 runtime=runtime[:start]+POST+runtime[end:]
 (o/'run.py').write_text(runtime)
 (o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 checks=['callback_returned','screen_present','fault_free','paused_rate_invariant','main_unmodified','common_model_unmodified','startup_prefix_exact']
 contract=dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['model_sha256'],['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Old-family original main/PC-qualified board and hooks are pinned from bw452.','The bw479 functional device model is reused byte-for-byte; initial10 MIPS becomes167 at original UI dispatch.'],unresolved_differences=['Cold sensor numerical results and GPU reference packing are not physical validation.','This capture alone does not prove all service initialization, sustained lifecycle or E05.'])
 plan=dict(schema=2,id='boot-family-functional-v1',image_id=IMAGE,cases={case:case},input_sha256=pins,components={'model':sha(o/'strict.cs'),'runner':sha(o/'runner-source.py')},runtime_sha256=sha(o/'run.py'),board_sha256=sha(o/'board.repl'),retention_contract=rp,source_invariants={'model_sha256':sha(o/'strict.cs'),'main_sha256':sha(o/'main.bin')},semantics={case:{'candidate':contract,'control':contract}},budgets={'host_seconds':360,'post_callback_virtual_ms':1000})
 semantic_spec(plan,case,False);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 return plan

def audit(o,out):
 plan=load(o/'plan.json');case=next(iter(plan['cases']));ex=o/'exports'
 logs=(o/'renode.log').read_text()
 errors=[l[:900] for l in logs.splitlines() if 'RUNTIME_ERROR' in l or 'There was an error executing' in l]
 checks={};boot=load(ex/'family-boot.json') if (ex/'family-boot.json').exists() else {}
 touch=load(ex/'touch.json') if (ex/'touch.json').exists() else {}
 checks.update(callback_returned=bool(boot.get('callback',{}).get('stopped')) and boot['callback']['pc']==load(o/'touch-profile.json')['wake']['ui']['return_site'],screen_present=bool(boot.get('frame')) and (ex/'family-screen.bin').stat().st_size==576*288 and boot.get('nonzero',0)>0 and sum(v!=0 for v in (ex/'family-screen.bin').read_bytes())==boot['nonzero'],fault_free=bool(touch) and touch['cfsr']==touch['hfsr']==touch['memory_violations']==boot.get('gpu_rejections')==0 and boot.get('gpu_fault')=='' and all(x['accesses']==0 for x in touch['guards']),paused_rate_invariant=bool(boot) and boot['rate_before']==boot['rate_after'] and (ex/'rate-before-sram.bin').read_bytes()==(ex/'rate-after-sram.bin').read_bytes(),main_unmodified=sha(o/'main.bin')==plan['source_invariants']['main_sha256'],common_model_unmodified=sha(o/'strict.cs')==plan['source_invariants']['model_sha256'])
 prefix_names=['before-input-sram.bin','after-input-sram.bin','before-reply-sram.bin','after-reply-sram.bin','app-request-sram.bin','ui-dispatch-sram.bin']
 fm=pinned_manifest('touch-wake-families-manifest.json',FAMILY_PIN)
 prefix_pins={name:frozen_file(S/'touch-wake-families-native-01'/case/'exports'/name,fm) for name in prefix_names}
 checks['startup_prefix_exact']=all((ex/name).exists() and sha(ex/name)==digest for name,digest in prefix_pins.items())
 pin_checks={name:sha(S/name)==digest for name,digest in plan['input_sha256'].items()}
 pin_checks.update(runtime=sha(o/'run.py')==plan['runtime_sha256'],board=sha(o/'board.repl')==plan['board_sha256'],runner=sha(o/'runner-source.py')==plan['components']['runner'],removed=load(o/'renode.process.json')['status']=='removed',no_runtime_errors=not errors,no_cpu_control_writes=not any(re.search(x,(o/'run.py').read_text()) for x in [r'\.SetRegister\s*\(',r'\.SeedRegister\s*\(',r'\.PC\s*=',r'\.WriteDoubleWord\s*\(',r'\.WriteByte\s*\(']))
 for name,digest in plan['input_sha256'].items():
  if name.startswith('touch-wake-families-native-01/') and Path(name).name not in ['run.py','board.repl','strict.cs','runner-source.py']:
   pin_checks['copied:'+Path(name).name]=sha(o/Path(name).name)==digest
 result=finish_capture(dict(case=case,control=False,boundary_kind='bounded-capture',observed=boot,selected_observation={'events':[],'sequence':0,'dropped_events':0},diagnostics=checks,**plan['source_invariants']),plan['source_invariants'],semantic_spec(plan,case,False))
 result.update(execution_passed=all(pin_checks.values()),execution_checks=pin_checks,runtime_errors=errors,full_e05_verified=False,hardware_accessed=False)
 result['passed']=result['execution_passed'] and result['semantic_validation']['passed']
 result['capture_sha256']={str(p.relative_to(o)):sha(p) for p in ex.iterdir() if p.is_file()}
 out.mkdir(mode=0o700);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'case':case,'passed':result['passed'],'execution_passed':result['execution_passed'],'checks':checks,'errors':errors,'observed':boot}),flush=True)
 return result

FAMILY_PIN='1213c819551739187842b4c37467aff4a0623e488c097e21ae5593f50208fc44'
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('case',choices=['stock23','cfw']);p.add_argument('output',type=Path);p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args();o=a.output.resolve()
 if not o.is_relative_to(S) or o.is_relative_to(R):raise ValueError('Private simulator output required')
 if a.audit_existing:
  if a.audit_output is None:p.error('Separate audit output required')
  result=audit(o,a.audit_output.resolve())
 else:
  if o.exists():raise ValueError('New output required')
  derive(a.case,o)
  execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=360)
  result=audit(o,o/'audit')
 raise SystemExit(0 if result['passed'] else 1)
