"""Screen-first stock24 natural-main research runner; explicit functional devices.
Requires the pinned private baseline. Never accesses physical glasses.
Usage: python tools/run_screen_first_native.py NEW_PRIVATE_SIMULATOR_OUTPUT
"""
from pathlib import Path
import sys,shutil,json,hashlib
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from run_renode_m55_probe import execute
from native_replay import IMAGE
S=Path.home()/'Library/Application Support/Blackwall/simulator';B=S/'gaf-render-scheduler-native-01/stock24';O=Path(sys.argv[1])
if O.exists() or not O.resolve().is_relative_to(S.resolve()) or O.resolve().is_relative_to(R):raise ValueError('New private output required')
expected={'main.bin': 'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a', 'strict.cs': 'd3af8a6f8dc8a57941c70d7ce0df69515665f1037ea50ce9db85386c1645f51d', 'run.py': '2e703d690907bceaf158a97f7a8c44a4690b0a08905277cf2e6e605cc9d67ceb', 'board.repl': 'cf29c810ffde4462c03d08d41d7641e3e5ce3336d9c6d68cae78b975df852b06'}
for name,digest in expected.items():
 if hashlib.sha256((B/name).read_bytes()).hexdigest()!=digest:raise ValueError('Changed pinned baseline: '+name)
O.mkdir(mode=0o700);(O/'exports').mkdir(mode=0o700)
for p in B.iterdir():
 if p.is_file() and p.suffix in ['.cs','.bin','.json','.py','.resc','.repl'] and p.name!='renode.process.json':shutil.copyfile(p,O/p.name)
(O/'runner-source.py').write_bytes(Path(__file__).read_bytes())
base=(O/'strict.cs').read_text();old=(R/'tools/renode-gaf-frozen-core.cs').read_text();new=(R/'tools/renode-gaf-bootstrap.cs').read_text()
if base.count(old)!=1:raise ValueError('Changed fixed fault component')
model=base.replace(old,new).replace('BlackwallImuGafFrozenCore','BlackwallImuGafBootstrap')
for before,after in [('        internal void GafControlBusy()=>bank.ServiceIdle(false);','        internal void GafControlBusy()=>bank.ServiceIdle(false);\n        internal void GafControlReady()=>bank.ServiceIdle(true);'),('                if(OnDemand.Active)\n                {','                if(OnDemand.Active && (address<0x2000 || OnDemand.OwnsRegister(address)))\n                {')]:
 if model.count(before)!=1:raise ValueError('Changed bootstrap integration anchor')
 model=model.replace(before,after,1)
model=model.replace('GafParameters!=null && PowerSave.Complete && !IregPending','GafParameters!=null && (!GafParameters.Complete || (data.Length==3 && data[1]==0xa2 && data[2]==0xa2)) && PowerSave.Complete && !IregPending')
model=model.replace('data.Length==3 && address==0x5bc && OnDemand.BeginRamRead(address)','data.Length==3 && address<0x2000 && OnDemand.BeginRamRead(address)')
model=model.replace('        public bool Complete=>index==addresses.Length;','        public int DeclaredFieldLength(int address) {for(int k=0;k<addresses.Length;k++)if(address==addresses[k])return lengths[k];return 0;}\n        public bool Complete=>index==addresses.Length;')
model=model.replace('            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)','            if(OnDemand!=null && OnDemand.GuestReadActive && !IregPending && !pending && data.Length>=3 && data[0]==0x7c)\n            {OnDemand.EndGuestRead();IregReady=false;}\n            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)')
model=model.replace('new BlackwallImuGafBootstrap(machine,Service,GafParameters,gafOnDemandMicroseconds)', 'new BlackwallImuGafBootstrap(machine,Service,GafParameters,gafOnDemandMicroseconds,Odr)')
model=model.replace('if(address==0x2a)return bank.Enable1;', 'if(address==0x29)return bank.Enable0;\n            if(address==0x2a)return bank.Enable1;').replace('if(address==0x2a)bank.ServiceWrite(address,value);','if(address==0x29 || address==0x2a)bank.ServiceWrite(address,value);')
model=model.replace('TryWriteInterrupt(byte first,byte second)', 'TryWriteInterrupt(byte first,byte second,bool fifoMask=false)').replace('if(!interruptRead || first!=Interrupt0 || (second&0x80)!=0 || (second&0x5f)!=(Interrupt1&0x5f))return false;', 'if((second&0x80)!=0 || (!fifoMask && (!interruptRead || first!=Interrupt0 || (second&0x5f)!=(Interrupt1&0x5f))))return false;').replace('Auxiliary.TryWriteInterrupt(data[1],data[2])', 'Auxiliary.TryWriteInterrupt(data[1],data[2],OnDemand!=null && OnDemand.Phase=="disabled")')
model=model.replace('            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))','            if(OnDemand!=null && data!=null && data.Length>0 && OnDemand.MaskRegister(data[0]))\n            {\n                if(data.Length==1){Pointer=data[0];PointerWrites++;pending=true;return;}\n                var values=new byte[data.Length-1];Array.Copy(data,1,values,0,values.Length);\n                if(OnDemand.TryWriteMask(data[0],values)){Pointer=data[0];pending=false;return;}\n                owner.RejectDiagnosticPeerAccess("apex-mask-write",(uint)data.Length);return;\n            }\n            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))').replace('            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))','            if(OnDemand!=null && pending && OnDemand.MaskRegister(Pointer))\n            {\n                var values=OnDemand.ReadMask(Pointer,count);\n                if(values==null){owner.RejectDiagnosticPeerAccess("apex-mask-read",(uint)count);return new byte[0];}\n                pending=false;ReturnedBytes+=values.Length;return values;\n            }\n            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))')
from importlib.machinery import SourceFileLoader
compose_gpu=SourceFileLoader('screen_gpu',str(Path(__file__).with_name('screen_native_gpu.py'))).load_module()
model,core_changes=compose_gpu.compose(model,(R/'tools/renode-strict-mmio.cs').read_text())
for name in ['nema-ring-consumer.cs','renode-nema-ring-device.cs','renode-opt3007-bootstrap.cs']:model+='\n'+(R/'tools'/name).read_text()
(O/'core-changes.json').write_text(json.dumps(core_changes,indent=2)+'\n')
fifo=SourceFileLoader('screen_fifo',str(Path(__file__).with_name('screen_native_fifo.py'))).load_module()
model=fifo.compose(model,R)
from cpu_retention_staging_model import compose as compose_retention
from retention_preparation_models import compose_timer_controls,compose_inactive_audio,compose_retention_flush
model=compose_retention_flush(compose_inactive_audio(compose_timer_controls(compose_retention(model))))
(O/'strict.cs').write_text(model)
board=(O/'board.repl').read_text();anchor='    gpuOffSequenceStorage: true\n'
if board.count(anchor)!=1:raise ValueError('Changed GPU power configuration')
board=board.replace(anchor,anchor+'    gpuRuntimeWakeResponse: 1\n')
board+='\ngpuRing: Miscellaneous.BlackwallNemaRingDevice @ none\n    cpu: cpu\n    owner: guard\n    referenceCoverage: true\n    packingReference: true\n    textureReference: true\n    IRQ -> nvic@28\n'
board=fifo.board_transform(board)
board+='\nopt3007: Miscellaneous.BlackwallOpt3007Bootstrap @ iom2 0x45\n    owner: iom2\n    resultWord: 13538\n'
board=board.replace('cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n', 'cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n    retentionStorePc: 0x4956e2\n    retentionReturnPc: 0x44df60\n    inactiveAudioStatus: true\n    retentionFlush: true\n')
board=board.replace('Miscellaneous.BlackwallTimer14 @ none\n', 'Miscellaneous.BlackwallTimer14 @ none\n    idleChannelControls: true\n')
(O/'board.repl').write_text(board)
run=(O/'run.py').read_text().replace("['sysbus.iom4.imu_identity']","['sysbus.iom4.imu_fifo'].StartupPeer");before='-refresh_started<20*int(TimeInterval.TicksPerMillisecond)';after='-refresh_started<500*int(TimeInterval.TicksPerMillisecond)'
if run.count(before)!=1:raise ValueError('Changed post-broadcast budget')
run=run.replace(before,after,1)
# Replace this fixed diagnostic stop with observation of a guest-rendered surface.
lines=run.splitlines();pos=next(i for i,l in enumerate(lines) if 'final_draw=BlackwallRuntimeConnectionObserver' in l)
lines[pos]='                    class FrameStop: Stopped=False;Entry=[];Exit=[]\n                    final_draw=FrameStop();gpu=g.GpuCommandDevice'
loop=next(i for i,l in enumerate(lines) if 'while not final_draw.Stopped' in l)
lines[loop]='                    while not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-refresh_started<500*int(TimeInterval.TicksPerMillisecond):\n                        if bool(cpu.IsHalted) or int(gpu.Rejections)>0:break\n                        if gpu.CompleteScreenHasDetail:final_draw.Stopped=True;break\n                        time.sleep(0.02)'
run='\n'.join(lines)+'\n'
run=run.replace('                    m.Pause()\n                    after_broadcast=', '                    stop_reason="frame" if final_draw.Stopped else ("cpu-halted" if cpu.IsHalted else ("gpu-rejected" if gpu.Rejections else ("machine-paused" if m.IsPaused else ("host-limit" if time.time()>=deadline else "virtual-limit"))))\n                    m.Pause()\n                    after_broadcast=')
run=run.replace('after_broadcast=dict(stopped=', 'after_broadcast=dict(stop_reason=stop_reason,stopped=')
run=run.replace('StartAll();deadline=time.time()+30;refresh_started=', 'StartAll();deadline=time.time()+90;refresh_started=')
anchor="    File.WriteAllText('/work-output/touch.json',json.dumps(result))"
insert="    gpu=g.GpuCommandDevice\n    File.WriteAllBytes('/work-output/gpu-last-frame.bin',gpu.FrameBytes)\n    File.WriteAllText('/work-output/gpu.json',json.dumps(dict(width=int(gpu.FrameWidth),height=int(gpu.FrameHeight),stride=int(gpu.FrameStride),address=int(gpu.FrameAddress),nonzero_pixels=int(gpu.NonzeroPixels),epochs=int(gpu.Epochs),pixels_written=int(gpu.PixelsWritten),draws=int(gpu.Draws),lists=int(gpu.ListsConsumed),fault=str(gpu.Fault),rejections=int(gpu.Rejections))))\n"
insert+="    File.WriteAllBytes('/work-output/screen-frame.bin',gpu.ScreenFrameBytes)\n    File.WriteAllText('/work-output/screen.json',json.dumps(dict(width=576,height=288,address=int(gpu.ScreenFrameAddress),source_stride=int(gpu.ScreenSourceStride),captures=int(gpu.ScreenCaptures),nonzero_pixels=int(gpu.ScreenNonzeroPixels),has_detail=bool(gpu.ScreenHasDetail))))\n"
insert+="    File.WriteAllBytes('/work-output/screen-complete.bin',gpu.CompleteScreenFrameBytes)\n    File.WriteAllText('/work-output/screen-complete.json',json.dumps(dict(width=576,height=288,address=int(gpu.CompleteScreenAddress),captures=int(gpu.CompleteScreenCaptures),nonzero_pixels=int(gpu.CompleteScreenNonzero),has_detail=bool(gpu.CompleteScreenHasDetail),source='guest-L8-after-original-packing-completed')))\n"
if run.count(anchor)!=1:raise ValueError('Changed output boundary')
run=run.replace(anchor,insert+anchor,1)
run=run.replace("fault_state=dict(fault_injected=", "fault_state=dict(functional_profile=str(fault.FunctionalProfile),completed_services=int(fault.CompletedServices),accuracy_assumed=bool(fault.AccuracyAssumed),last_peer_write=str(imu.LastWriteHex),fault_injected=")
run=run.replace("fault_state=dict(functional_profile=", "fault_state=dict(aux_interrupt=[int(imu.Auxiliary.Interrupt0),int(imu.Auxiliary.Interrupt1)],fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),odr_hex=str(imu.Odr.ValuesHex),ireg_ready=bool(imu.IregReady),ireg_pending=bool(imu.IregPending),ram_read_remaining=int(fault.RamReadRemaining),functional_profile=")
(O/'run.py').write_text(run)
(O/'functional-profile.json').write_text(json.dumps(dict(profile='cold-bootstrap-v1',numerical_gaf_validated=False,cold_accuracy_assumed=0,main_sha256=hashlib.sha256((O/'main.bin').read_bytes()).hexdigest(),base_model_sha256=hashlib.sha256(base.encode()).hexdigest(),model_sha256=hashlib.sha256(model.encode()).hexdigest(),firmware_patched=False,cpu_tcb_or_branch_forced=False,packing_profile='center-msb-alpha-high-reference-v1',texture_profile='nominal-identity-translation-point-v1',readiness='functional-service-not-sensor-rom',ambient_light_profile='constant-100-lux-instant-conversion',cpu_retention_profile='bw416-417-context-qualified-retention-native-wfi'),indent=2)+'\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={O},target=/work,readonly','--mount',f'type=bind,source={O/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],O,'renode',timeout=240)
for name in ['gaf-fault-state.json','after-broadcast.json','ui-layout.json','touch.json']:
 p=O/'exports'/name
 if p.exists():
  d=json.loads(p.read_text());print(name,json.dumps({k:v for k,v in d.items() if k in ['phase','completed_services','last_reject','last_peer_write','pc','stopped','counts','guards','memory_violations','cfsr','hfsr']}))
