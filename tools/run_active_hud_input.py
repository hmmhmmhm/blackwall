"""Active original HUD: settled no-input control or reusable IOM5 scroll report.
No hardware access, firmware patch, synthetic CPU caller or guest state writes.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_native_candidate import semantic_spec,finish_capture
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
POST='''
try:
    from System.Security.Cryptography import SHA256
    from System import BitConverter
    def input_digest(data):return str(BitConverter.ToString(SHA256.Create().ComputeHash(data))).replace('-','').lower()
    gp=g.GpuCommandDevice;touch_peer=m['sysbus.iom5.iom5_register_probe'];uart=g.Uarts[0]
    spec=json.loads(File.ReadAllText('/work/active-input-profile.json'))
    def run_slice(ms):
        def pause_slice():m.Pause();return True
        clock=BlackwallRuntimeInputDelay(m,ms,Func[bool](pause_slice))
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+60
        while not clock.Accepted and time.time()<deadline:
            if cpu.IsHalted or (m.IsPaused and not clock.Fired):break
            time.sleep(0.002)
        if clock.Fired:
            while not clock.Accepted and time.time()<deadline:time.sleep(0.001)
            if not clock.Accepted:raise ValueError('Owned slice pause did not complete')
        else:
            m.Pause();return False
        return True
    def input_state():
        return dict(pc=int(cpu.PC.RawValue),registers=registers(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions),paused=bool(m.IsPaused),halted=bool(cpu.IsHalted),frames=int(gp.CompleteScreenCaptures),frame_sha256=input_digest(gp.CompleteScreenFrameBytes),frame_bytes=len(gp.CompleteScreenFrameBytes),draws=int(gp.Draws),lists=int(gp.ListsConsumed),gpu_rejections=int(gp.Rejections),gpu_fault=str(gp.Fault),touch_frames=int(touch_peer.EventFramesCompleted),touch_chunks=int(touch_peer.EventReadChunks),reloads=int(touch_peer.EventFrameReloads),gpio_edges=int(q.FallingEdges),gpio_high=bool(q.Pin27High),uart_read=int(uart.RxBytesRead),uart_pending=int(uart.RxPending),uart_transfers=int(uart.DmaTx.Transfers.Count),input_role=int(b.ReadByte(spec['role_slot'])),input_tick=int(b.ReadDoubleWord(spec['tick_slot'])))
    settle_before=input_state()
    for unused in range(80):
        if not run_slice(5):break
    settled=input_state()
    File.WriteAllBytes('/work-output/active-settled-frame.bin',gp.CompleteScreenFrameBytes)
    File.WriteAllBytes('/work-output/active-input-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    event_trace=BlackwallTouchInputObserver(m,cpu,p['tcb_slot'])
    for tag,address in [(200,p['handler']),(201,p['handler_caller_return']),(202,p['slider_dispatch']),(203,spec['ui_callback']),(204,spec['app_callback'])]:event_trace.Watch(tag,address)
    for tag,address in spec.get('consumer_watches',[]):event_trace.Watch(tag,address)
    incoming=Array[Byte]([int(spec['frame_hex'][i:i+2],16) for i in range(0,32,2)])
    reload_accepted=False;edge_accepted=False
    if spec['mode']=='scroll':
        reload_accepted=bool(touch_peer.TryLoadEventFrame(incoming))
        if not reload_accepted:raise ValueError('Touch device refused report reload')
        edge_accepted=bool(q.TrySetPin27(False,int(g.GpioConfig.Values[0x4001006c])==0x53))
        if not edge_accepted:raise ValueError('GPIO27 refused active input')
        def release_active_touch():return bool(q.TrySetPin27(True,int(g.GpioConfig.Values[0x4001006c])==0x53))
        release_active=BlackwallRuntimeInputDelay(m,spec['pulse_microseconds'],Func[bool](release_active_touch),True)
    injected=input_state()
    File.WriteAllBytes('/work-output/active-input-injected-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    seen_tx=int(uart.DmaTx.Transfers.Count);outgoing=[];replies=[];samples=[]
    def crc(values):
        v=0
        for x in values:
            v^=x
            for unused in range(8):v=(v>>1)^(0xa001 if v&1 else 0)
        return v
    def ack_frame(identifier,value):
        header=[1,identifier>>8,identifier&255,0,1,0,0];a=crc(header);z=crc([value]);return header+[a>>8,a&255,value,z>>8,z&255]
    for n in range(40):
        if not run_slice(5):break
        transfers=list(uart.DmaTx.Transfers)
        for transfer in transfers[seen_tx:]:
            data=[int(x) for x in transfer.Data];outgoing.append(data)
            if len(data)<11:raise ValueError('Incomplete UART frame at completed slice')
            length=(data[3]<<8)|data[4];channel=(data[5]<<8)|data[6]
            if len(data)!=length+11 or crc(data[:7])!=((data[7]<<8)|data[8]) or crc(data[9:-2])!=((data[-2]<<8)|data[-1]):raise ValueError('Invalid original UART frame')
            payload=data[9:-2]
            reply_value=None
            if channel==1 and len(payload)>=8 and payload[:2]==[1,9] and (payload[2]|payload[3]<<8) in [0x107,0x108]:reply_value=10
            if spec['input_peer_ack'] and channel==3 and payload==[3,7,1,0,4,0,0,0,167,0,10,0]:reply_value=8
            if spec['display_peer_ack'] and channel==2 and payload==[2,3,1,0,0,0,6,0,0,68,167,0,10,0]:reply_value=spec['display_peer_reply']
            if reply_value is not None:
                reply=ack_frame((data[1]<<8)|data[2],reply_value);before_regs=registers();before_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                accepted=bool(uart.TryReceive(Array[Byte](reply),g.UartPowers[0].Phase=='on'))
                replies.append(dict(bytes=reply,accepted=accepted,before_registers=before_regs,after_registers=registers(),before_ticks=before_ticks,after_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)))
                if not accepted:raise ValueError('Known UART ACK rejected')
        seen_tx=len(transfers)
        current=input_state();samples.append(current)
        File.WriteAllBytes('/work-output/active-frame-%03d.bin'%n,gp.CompleteScreenFrameBytes)
    after=input_state();guards=[]
    for item in result['guards']:
        owner=m['sysbus.'+item['name']];guards.append(dict(name=item['name'],accesses=int(owner.AccessCount),address=int(owner.LastAddress)))
    value=dict(pulse_microseconds=spec['pulse_microseconds'],release=None if spec['mode']=='none' else dict(started=int(release_active.StartedAt),fired_at=int(release_active.FiredAt),accepted=bool(release_active.Accepted)),mode=spec['mode'],settle_before=settle_before,settled=settled,injected=injected,after=after,reload_accepted=reload_accepted,edge_accepted=edge_accepted,rows=[[int(v) for v in row] for row in event_trace.Rows],overflow=bool(event_trace.Overflow),outgoing=outgoing,replies=replies,samples=samples,guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),system_control_violations=int(system_control.Violations),hardware_accessed=False)
    File.WriteAllText('/work-output/active-input.json',json.dumps(value))
    File.WriteAllBytes('/work-output/active-input-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    File.WriteAllBytes('/work-output/active-input-after-frame.bin',gp.CompleteScreenFrameBytes)
except Exception as error:
    File.WriteAllText('/work-output/active-input-error.json',json.dumps(dict(error=str(error))))
    Console.WriteLine('BLACKWALL_ACTIVE_INPUT_ERROR '+str(error))
'''
def derive(o,mode,case,input_peer_ack=False,display_peer_ack=False,display_peer_reply=4):
 manifest=S/'active-reset-manifest.json'
 if sha(manifest)!='e7c16643e89b9000f9f2d9929b2961cdfb7cee20cdae2c307d2e85a16e83fb68':raise ValueError('Changed active board acceptance')
 m=load(manifest);source=S/'active-board-reset-shared-native-01'/case
 if o.exists() or not o.is_relative_to(S):raise ValueError('New private output required')
 o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir(mode=0o700);pins={}
 for p in source.iterdir():
  if p.is_file() and p.suffix in ['.py','.json','.cs','.resc','.repl','.bin'] and p.name!='renode.process.json':
   expected=m['files'][str(p.relative_to(S))]['sha256']
   if sha(p)!=expected:raise ValueError('Changed fixed source '+p.name)
   shutil.copyfile(p,o/p.name);pins[p.name]=expected
 before=S/'touch-repeat-frame-research-01/before-renode-iom-register-probe.cs';after=R/'tools/renode-iom-register-probe.cs'
 if sha(before)!='c504b7e5d9447168ba2555664500dc2833f924942195b953e4da666e0f33d5b7' or sha(after)!='0eea01d156d76d878c94f4298a85e161de77d0cf405d627a45787b4f3eb7d2ac':raise ValueError('Changed accepted reusable touch component')
 model=(o/'strict.cs').read_text()
 if model.count(before.read_text())!=1:raise ValueError('Changed touch component boundary')
 (o/'strict.cs').write_text(model.replace(before.read_text(),after.read_text(),1))
 board=(o/'board.repl').read_text();anchor='    eventPointerProbe: true\n'
 if board.count(anchor)!=1 or board.count('    touchReadBudget: 2\n')!=1:raise ValueError('Changed active touch profile')
 (o/'board.repl').write_text(board.replace(anchor,anchor+'    reusableEventFrames: true\n').replace('    touchReadBudget: 2\n','    touchReadBudget: 4\n'))
 timer_source=R/'tools/renode-runtime-connection-observer.cs';original_timer=timer_source.read_text();activation=(o/'activation.cs').read_text()
 if sha(timer_source)!='0de8e63ac33e993ae04f067ee0898dab59d3fbb922e6b4bb974edf0b728c63ae' or activation.count(original_timer)!=1:raise ValueError('Changed existing input delay component')
 updated_timer=original_timer.replace('public BlackwallRuntimeInputDelay(IMachine machine,uint milliseconds,Func<bool> enqueue)\n        {','public BlackwallRuntimeInputDelay(IMachine machine,uint milliseconds,Func<bool> enqueue) : this(machine,milliseconds,enqueue,false) {}\n        public BlackwallRuntimeInputDelay(IMachine machine,uint milliseconds,Func<bool> enqueue,bool microseconds)\n        {')
 updated_timer=updated_timer.replace('milliseconds>1000 || enqueue==null','milliseconds>(microseconds ? 1000000:1000) || enqueue==null').replace('milliseconds*1000u,Direction.Ascending','(microseconds ? milliseconds:milliseconds*1000u),Direction.Ascending')
 if updated_timer==original_timer:raise ValueError('No explicit microsecond timer overload')
 (o/'activation.cs').write_text(activation.replace(original_timer,updated_timer,1))

 runtime=(o/'run.py').read_text();cut='\ntry:\n    from System.Security.Cryptography import SHA256\n'
 if runtime.count(cut)!=1:raise ValueError('Changed reset phase boundary')
 (o/'run.py').write_text(runtime.split(cut,1)[0]+POST)
 profiles=load(R/'tools/ring-input-profiles.json')['profiles'][case]
 source_main=(o/'main.bin').read_bytes()
 from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
 decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
 if case=='stock24':
  watches=[[205,0x4b7cca],[206,0x53186c],[207,0x469228],[208,0x4694e4],[209,0x445f5c],[210,0x444834]]
  stack_bytes=128
  expectations=[(0x4664bc,'movs','r0, #4'),(0x46971c,'bl','#0x445f5c'),(0x445fd6,'movs','r0, #3'),(0x4692cc,'cmp','r0, #8'),(0x46931e,'bl','#0x446230'),(0x4b7cb2,'bl','#0x53186c')]
 else:
  watches=[[205,0x4ada44],[206,0x500e1c],[207,0x4692e0],[208,0x4695b4],[209,0x445efc],[210,0x44480a]]
  stack_bytes=120
  expectations=[(0x4667ac,'movs','r0, #4'),(0x4697ec,'bl','#0x445efc'),(0x445f76,'movs','r0, #3'),(0x46938c,'cmp','r0, #8'),(0x4693e4,'bl','#0x4461cc'),(0x4ada2c,'bl','#0x500e1c')]
 source_checks=[]
 for address,mnemonic,operands in expectations:
  ins=next(decoder.disasm(source_main[address-0x438000:address-0x438000+4],address),None)
  if ins is None or (ins.mnemonic,ins.op_str)!=(mnemonic,operands):raise ValueError('Changed original input consumer contract '+hex(address))
  source_checks.append(dict(address=address,bytes=source_main[address-0x438000:address-0x438000+ins.size].hex(),mnemonic=mnemonic,operands=operands))
 spec=dict(mode=mode,display_peer_reply=display_peer_reply,consumer_watches=watches,callback_stack_bytes=stack_bytes,source_checks=source_checks,input_peer_ack=input_peer_ack,display_peer_ack=display_peer_ack,pulse_microseconds=250,frame_hex='02400aa73412cdab0180ffff5ac317e9',role_slot=profiles['flow']['role_slot'],tick_slot=profiles['flow']['tick_slot'],app_callback=profiles['flow']['callback'],ui_callback=profiles['wake']['ui']['callback'])
 (o/'active-input-profile.json').write_text(json.dumps(spec,indent=2)+'\n');(o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 checks=['boot_frame','clean_runtime','injection_preserves_cpu_sram','input_consumed','ui_input_callback'] if mode=='scroll' else ['boot_frame','clean_runtime']
 contract=dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['model_sha256'],['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Optional reusable IOM5 report adapter; GPIO touch read budget4; original main unchanged.','80x5ms settling then40x5ms active input window. Both candidate/control use the same pauses and observation.'],unresolved_differences=['Prototype input delivery/UI observation; a changed frame alone may be animation/time and is not full E11 acceptance.'])
 plan=dict(schema=2,id='active-hud-input-prototype-v1',image_id=IMAGE,cases={case:case},source_root=str(source.relative_to(S)),source_input_sha256=pins,input_sha256={p.name:sha(p) for p in o.iterdir() if p.is_file() and p.name not in ['plan.json','runner-source.py']},semantics={case:{'candidate':contract,'control':contract}},main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs'),mode=mode,hardware_accessed=False)
 semantic_spec(plan,case,False);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
def audit(o,out):
 p=load(o/'plan.json');case=next(iter(p['cases']));e=o/'exports'
 if not (e/'active-input.json').exists():
  r=dict(passed=False,execution_passed=False,error=load(e/'active-input-error.json') if (e/'active-input-error.json').exists() else None,full_e11_verified=False);out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return r
 x=load(e/'active-input.json');controls={n:sha(o/n)==digest for n,digest in p['input_sha256'].items()};controls['process_removed']=load(o/'renode.process.json')['status']=='removed'
 input_rows=[r for r in x['rows'] if r[0]==202];ui_rows=[r for r in x['rows'] if r[0]==203 and r[2]==3]
 checks=dict(boot_frame=x['settled']['frame_bytes']==576*288,clean_runtime=x['cfsr']==x['hfsr']==x['memory_violations']==x['system_control_violations']==x['after']['gpu_rejections']==0 and x['after']['gpu_fault']=='' and all(g['accesses']==0 for g in x['guards']) and not x['overflow'],injection_preserves_cpu_sram=x['settled']['registers']==x['injected']['registers'] and x['settled']['ticks']==x['injected']['ticks'] and sha(e/'active-input-before-sram.bin')==sha(e/'active-input-injected-sram.bin'),input_consumed=x['reload_accepted'] and x['edge_accepted'] and x['after']['touch_frames']==x['settled']['touch_frames']+1 and any(r[2:6]==[1,4,10,167] and (r[9]&0x1ff)==0 for r in input_rows),ui_input_callback=bool(ui_rows))
 r=finish_capture(dict(case=case,control=False,boundary_kind='bounded-capture',observed=x['after'],selected_observation={'events':x['rows'],'sequence':len(x['rows']),'dropped_events':int(x['overflow'])},diagnostics=checks,main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs')),{'main_sha256':p['main_sha256'],'model_sha256':p['model_sha256']},semantic_spec(p,case,False))
 r.update(execution_passed=all(controls.values()),execution_checks=controls,input=x,full_e11_verified=False);r['passed']=r['execution_passed'] and r['semantic_validation']['passed'];out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':r['passed'],'checks':checks,'frame_changed':x['after']['frame_sha256']!=x['settled']['frame_sha256'],'rows':x['rows'],'outgoing':x['outgoing']}));return r
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');p.add_argument('--mode',choices=['none','scroll'],default='scroll');p.add_argument('--input-peer-ack',action='store_true');p.add_argument('--display-peer-ack',action='store_true');p.add_argument('--display-peer-reply',type=int,choices=[2,4],default=4);p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);a=p.parse_args();o=a.output.resolve()
 if a.audit_existing:r=audit(o,a.audit_output.resolve())
 else:
  derive(o,a.mode,a.case,a.input_peer_ack,a.display_peer_ack,a.display_peer_reply);execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=780);r=audit(o,o/'audit')
 raise SystemExit(0 if r['passed'] else 1)
