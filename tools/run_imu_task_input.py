"""Original main/active HUD: FIFO device samples and natural sensor-task observation."""
import argparse,hashlib,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from run_native_candidate import semantic_spec,finish_capture
R=Path(__file__).resolve().parents[1];S=Path.home()/'Library/Application Support/Blackwall/simulator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
POST=r'''
try:
    from System import Array,Byte,Func
    from Antmicro.Renode.Utilities import TypeManager
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallImuInt1Gpio').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuInt1Gpio
    spec=json.loads(File.ReadAllText('/work/imu-input-profile.json'))
    transport=m['sysbus.iom4.imu_fifo'];fifo=transport.RawFifo;threshold=transport.Threshold;gpio=g.GpioInterrupts;gp=g.GpuCommandDevice
    sink=BlackwallImuInt1Gpio(m,g,int(transport.StartupPeer.Int1Config2Value));threshold.IRQ.Connect(sink,0)
    trace_sensor=BlackwallTouchInputObserver(m,cpu,p['tcb_slot'])
    for tag,pc in spec['watches']:trace_sensor.Watch(tag,pc)
    def state_sensor():
        return dict(registers=registers(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions),pc=int(cpu.PC.RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),gate=int(b.ReadDoubleWord(spec['gate'])),sample_header=[int(b.ReadDoubleWord(spec['sample_ring']+4*k)) for k in range(3)],frame_bytes=int(fifo.FrameBytes),ready=bool(transport.Configuration.Ready),watermark=int(threshold.WatermarkPackets),interrupt_enabled=bool(threshold.InterruptEnabled),packets=int(fifo.PacketCount),enqueued=int(fifo.PacketsEnqueued),consumed=int(fifo.PacketsConsumed),read_bytes=int(fifo.ReadBytes),completed=int(transport.TransactionsCompleted),threshold_events=int(threshold.EventsRaised),threshold_clears=int(threshold.StatusClears),threshold_pending=bool(threshold.Pending),gpio_edges=int(gpio.Pin38RisingEdges),gpio_pending=bool(gpio.Pending38),gpio_irq=bool(gpio.IRQ38.IsSet),pin_high=bool(sink.PinHigh),source_high=bool(sink.High),pad=int(g.GpioConfig.Values[0x40010098]),int1=int(transport.StartupPeer.Int1Config2Value),accepted_transitions=int(sink.AcceptedTransitions),rejected_transitions=int(sink.RejectedTransitions),frames=int(gp.CompleteScreenCaptures),gpu_fault=str(gp.Fault),gpu_rejections=int(gp.Rejections),halted=bool(cpu.IsHalted))
    before=state_sensor()
    if before['gate']!=1 or not before['ready'] or before['frame_bytes']!=32 or before['watermark']!=10:raise ValueError('Original main did not initialize sensor FIFO')
    File.WriteAllBytes('/work-output/sensor-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    accepted=[]
    if not spec['control']:
        for seed in range(10):
            packet=[0xe0,0x1f]+[(seed+k)&255 for k in range(12)]+list(range(0x11,0x1a))+[0x21,0x22,0x23,0x24,0x25,0x26,0x21,0x34+seed,0x12]
            accepted.append(bool(fifo.TryEnqueueFrame(Array[Byte](packet))))
    injected=state_sensor();File.WriteAllBytes('/work-output/sensor-injected-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    samples=[]
    for n in range(20):
        def pause_sensor():m.Pause();return True
        timer=BlackwallRuntimeInputDelay(m,5,Func[bool](pause_sensor))
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+60
        while not timer.Accepted and time.time()<deadline:
            if cpu.IsHalted or (m.IsPaused and not timer.Fired):break
            time.sleep(0.002)
        if not timer.Accepted:m.Pause();break
        samples.append(state_sensor())
    after=state_sensor();guards=[]
    for item in result['guards']:
        owner=m['sysbus.'+item['name']];guards.append(dict(name=item['name'],accesses=int(owner.AccessCount),address=int(owner.LastAddress)))
    value=dict(before=before,injected=injected,after=after,accepted=accepted,samples=samples,rows=[[int(v) for v in row] for row in trace_sensor.Rows],overflow=bool(trace_sensor.Overflow),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),system_control_violations=int(system_control.Violations),hardware_accessed=False)
    File.WriteAllText('/work-output/sensor-input.json',json.dumps(value));File.WriteAllBytes('/work-output/sensor-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
except Exception as error:
    File.WriteAllText('/work-output/sensor-input-error.json',json.dumps(dict(error=str(error))))
    Console.WriteLine('BLACKWALL_SENSOR_INPUT_ERROR '+str(error))
'''
def derive(o,control,case="stock24"):
 manifest=S/'active-reset-manifest.json'
 if sha(manifest)!='e7c16643e89b9000f9f2d9929b2961cdfb7cee20cdae2c307d2e85a16e83fb68':raise ValueError('Changed functional board manifest')
 if o.exists() or not o.is_relative_to(S) or o.is_relative_to(R):raise ValueError('New private output required')
 source=S/'active-board-reset-shared-native-01'/case;m=load(manifest);o.mkdir(mode=0o700,parents=True);(o/'exports').mkdir(mode=0o700);pins={}
 for p in source.iterdir():
  if p.is_file() and p.suffix in ['.py','.json','.cs','.resc','.repl','.bin'] and p.name!='renode.process.json':
   h=m['files'][str(p.relative_to(S))]['sha256']
   if sha(p)!=h:raise ValueError('Changed fixed source '+p.name)
   shutil.copyfile(p,o/p.name);pins[p.name]=h
 component=R/'tools/renode-imu-int1-gpio.cs'
 if sha(component)!='f9567733b8a6b48bfaff49c4140fc4a8961625fc7e92140cdc80fcfbe22dfebf':raise ValueError('Changed validated pulse component')
 model=(o/'strict.cs').read_text()
 if 'class BlackwallImuInt1Gpio' in model:raise ValueError('Duplicate GPIO sink')
 (o/'strict.cs').write_text(model+'\n'+component.read_text())
 board=(o/'board.repl').read_text();anchor='    runtimePin27: true\n'
 if board.count(anchor)!=1:raise ValueError('Changed existing GPIO attachment')
 (o/'board.repl').write_text(board.replace(anchor,anchor+'    runtimePin38: true\n    IRQ38 -> nvic@57\n',1))
 runtime=(o/'run.py').read_text();cut='\ntry:\n    from System.Security.Cryptography import SHA256\n'
 if runtime.count(cut)!=1:raise ValueError('Changed active-reset phase boundary')
 (o/'run.py').write_text(runtime.split(cut,1)[0]+POST)
 if case=='stock24':
  gate=0x200774f4;sample_ring=0x20066640;watches=[[300,0x4fc90e],[301,0x4c615e],[302,0x4c6196],[303,0x4c38b0],[304,0x4c3ad0],[305,0x4c4c6c],[306,0x4c5fd8],[307,0x4c4908],[308,0x4c4a04],[309,0x555388]]
  checks_source=[(0x4c5fd4,'bl','#0x4c38b0'),(0x4c3acc,'bl','#0x552fa6'),(0x4c3b5a,'bl','#0x4c4908'),(0x4c6192,'bl','#0x4c6040')]
 else:
  gate=0x20077d00;sample_ring=0x20066650;watches=[[300,0x557536],[301,0x4baaa2],[302,0x4baada],[303,0x4b81f4],[304,0x4b8414],[305,0x4b95b0],[306,0x4ba91c],[307,0x4b924c],[308,0x4b9348],[309,0x521530]]
  checks_source=[(0x4ba918,'bl','#0x4b81f4'),(0x4b8410,'bl','#0x51f14e'),(0x4b849e,'bl','#0x4b924c'),(0x4baad6,'bl','#0x4ba984')]
 from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
 decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);raw=(o/'main.bin').read_bytes();proof=[]
 for address,mnemonic,operands in checks_source:
  ins=next(decoder.disasm(raw[address-0x438000:address-0x438000+4],address),None)
  if ins is None or (ins.mnemonic,ins.op_str)!=(mnemonic,operands):raise ValueError('Changed original sensor consumer source '+hex(address))
  proof.append(dict(address=address,bytes=raw[address-0x438000:address-0x438000+ins.size].hex(),mnemonic=mnemonic,operands=operands))
 spec=dict(case=case,control=control,gate=gate,sample_ring=sample_ring,watches=watches,source_checks=proof)
 (o/'imu-input-profile.json').write_text(json.dumps(spec,indent=2)+'\n');(o/'runner-source.py').write_bytes(Path(__file__).read_bytes())
 checks=['original_ready','injection_preserved_state','fault_free','window_completed','control_no_consumption'] if control else ['original_ready','injection_preserved_state','fault_free','window_completed','irq_delivered','fifo_consumed','original_consumer']
 contract=dict(boundary={'kind':'bounded-capture'},comparison={'policy':'bounded-invariants','paths':[['model_sha256'],['main_sha256']]},checks=[{'path':['diagnostics',k],'eq':True} for k in checks],allowed_differences=['Existing opt-in GPIO38/NVIC57 and validated INT1 pulse bridge. Existing main sensor setter owns FIFO configuration.','Only external FIFO sample enqueue; no guest gate/ready/PC/TCB or synthetic caller writes.'],unresolved_differences=['Prototype stock24 natural-task observation, not full E12 or physical/numerical sensor validation.'])
 plan=dict(schema=2,id='imu-natural-task-fifo-v1',cases={case:case},source_root=str(source.relative_to(S)),source_input_sha256=pins,input_sha256={p.name:sha(p) for p in o.iterdir() if p.is_file() and p.name not in ['plan.json','runner-source.py']},main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs'),semantics={case:{'candidate':contract,'control':contract}},control=control)
 semantic_spec(plan,case,control);(o/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
def audit(o,out):
 p=load(o/'plan.json');case=next(iter(p['cases']));e=o/'exports'
 if not (e/'sensor-input.json').exists():
  r=dict(passed=False,error=load(e/'sensor-input-error.json') if (e/'sensor-input-error.json').exists() else None,full_e12_verified=False);out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));return r
 x=load(e/'sensor-input.json');before=x['before'];after=x['after'];controls={n:sha(o/n)==h for n,h in p['input_sha256'].items()};controls['process_removed']=load(o/'renode.process.json')['status']=='removed'
 checks=dict(original_ready=before['gate']==1 and before['ready'] and before['frame_bytes']==32 and before['watermark']==10,injection_preserved_state=all(before[k]==x['injected'][k] for k in ['registers','instructions','ticks']) and sha(e/'sensor-before-sram.bin')==sha(e/'sensor-injected-sram.bin'),fault_free=x['cfsr']==x['hfsr']==x['memory_violations']==x['system_control_violations']==after['gpu_rejections']==0 and not after['gpu_fault'] and all(v['accesses']==0 for v in x['guards']) and not x['overflow'],window_completed=len(x['samples'])==20 and after['ticks']-before['ticks']==100000000,irq_delivered=after['gpio_edges']==before['gpio_edges']+1 and any(v[0]==301 and (v[9]&511)==73 for v in x['rows']),fifo_consumed=len(x['accepted'])==10 and all(x['accepted']) and after['consumed']==before['consumed']+10 and after['packets']==0,original_consumer=any(v[0]==303 and (v[9]&511)==0 for v in x['rows']),control_no_consumption=not x['accepted'] and after['consumed']==before['consumed'] and not any(v[0] in [300,301,303] for v in x['rows']))
 r=finish_capture(dict(case=case,control=p['control'],boundary_kind='bounded-capture',observed=after,selected_observation={'events':x['rows'],'sequence':len(x['rows']),'dropped_events':int(x['overflow'])},diagnostics=checks,main_sha256=sha(o/'main.bin'),model_sha256=sha(o/'strict.cs')),{'main_sha256':p['main_sha256'],'model_sha256':p['model_sha256']},semantic_spec(p,case,p['control']));r.update(execution_passed=all(controls.values()),execution_checks=controls,sensor=x,full_e12_verified=False);r['passed']=r['execution_passed'] and r['semantic_validation']['passed'];out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=r['passed'],checks=checks,before=before,after=after,rows=x['rows'])));return r
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--case',choices=['stock24','stock23','cfw'],default='stock24');parser.add_argument('--control',action='store_true');parser.add_argument('--audit-existing',action='store_true');parser.add_argument('--audit-output',type=Path);a=parser.parse_args();o=a.output.resolve()
 if a.audit_existing:r=audit(o,a.audit_output.resolve())
 else:
  derive(o,a.control,a.case);execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','--mount',f'type=bind,source={o/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=780);r=audit(o,o.parent/(o.name+'-audit'))
 raise SystemExit(0 if r['passed'] else 1)
