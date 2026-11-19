import json,time,clr
from System import Console
from System.IO import File
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy,BlackwallSystemControl,BlackwallExecutionObserver
m=monitor.Machine;cpu=m['sysbus.cpu'];bus=m.SystemBus
policy=BlackwallMemoryPolicy(m,cpu,m['sysbus.main'],m['sysbus.itcm'],3700068)
policy.BindBootImage(m['sysbus.boot'],149773)
policy.Attach()
system_control=BlackwallSystemControl(m,cpu,m['sysbus.nvic'],True,True,True)
system_control.Attach()
m['sysbus.guard'].Mspi1Config.AttachRetentionPower(m['sysbus.guard'].Mspi1Power)
observer=BlackwallExecutionObserver(cpu,128)
for label,address in [('boot-reset',0x432cb2),('boot-crt',0x432cd4),('boot-fpu',0x432cf0),('boot-c-init',0x432d14),('boot-data-init',0x432d34),('boot-main',0x41b862),('boot-init-dispatch',0x41fa08),('boot-board-init',0x430536),('boot-manager',0x42e650),('stock-handoff',0x42dfe8),('main-reset',0x5fbe3e)]:
 observer.AddPoint(label,address)

gpu=m['sysbus.guard'].GpuCommandDevice
for label in ('boot-reset','stock-handoff','main-reset'):observer.CaptureCpuContext(label)
for label,address in [('ui-dispatch',0x4456e8),('app1-callback',0x4b7a58),('renderer-entry',0x4439a4)]:observer.AddPoint(label,address)
start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
EmulationManager.Instance.CurrentEmulation.StartAll()
deadline=time.time()+300
while not cpu.IsHalted and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<20000000000 and not (int(gpu.CompleteScreenCaptures)>0 and bool(gpu.CompleteScreenHasDetail)):
 time.sleep(0.01)
reason='halted' if cpu.IsHalted else ('machine-paused' if m.IsPaused else ('first-frame' if int(gpu.CompleteScreenCaptures)>0 and bool(gpu.CompleteScreenHasDetail) else ('host-limit' if time.time()>=deadline else 'virtual-limit')))
m.Pause()

wire=dict(stages=[],requests=[],replies=[],hardware_accessed=False,guest_writes=False)
try:
 from System import Func,Array,Byte
 clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRuntimeInputDelay').Assembly)
 from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeInputDelay,BlackwallRuntimeConnectionObserver
 g=m['sysbus.guard'];uart=g.Uarts[0];gpio=g.GpioInterrupts
 timers=[]
 def witness():return dict(registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],instructions=int(cpu.ExecutedInstructions),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks))
 def clean():return policy.Violations==0 and system_control.Violations==0 and all(m['sysbus.'+n].AccessCount==0 for n in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'))
 def advance(ms,checkpoint=None):
  def stop_at_deadline():m.Pause();return True
  t=BlackwallRuntimeInputDelay(m,ms,Func[bool](stop_at_deadline));timers.append(t)
  EmulationManager.Instance.CurrentEmulation.StartAll();end=time.time()+60
  while not m.IsPaused and not cpu.IsHalted and time.time()<end:time.sleep(0.001)
  m.Pause();wire['stages'].append(dict(ms=ms,fired=bool(t.Fired),clean=bool(clean()),state=witness()))
  allowed=bool(checkpoint is not None and checkpoint.Stopped)
  if not t.Fired:t.Reset()
  if (not wire['stages'][-1]['fired'] and not allowed) or not clean():raise Exception('unsupported execution boundary before input deadline')
 def crc(data):
  v=0
  for b in data:
   v^=b
   for unused in range(8):v=(v>>1)^(0xa001 if v&1 else 0)
  return v
 def decode(t):
  d=[int(x) for x in t.Data]
  if len(d)<11 or d[0]!=1:raise Exception('unsupported UART frame')
  count=d[3]*256+d[4]
  if len(d)!=11+count or crc(d[:7])!=d[7]*256+d[8] or crc(d[9:-2])!=d[-2]*256+d[-1]:raise Exception('UART frame length/CRC mismatch')
  return dict(data=d,identifier=d[1]*256+d[2],channel=d[6],payload=d[9:-2])
 def reply(request,kind):
  d=request['data'];h=[1,d[1],d[2],0,1,0,0];c=crc(h);tail=crc([kind]);data=h+[c>>8,c&255,kind,tail>>8,tail&255]
  before=witness();accepted=bool(uart.TryReceive(Array[Byte](data),g.UartPowers[0].Phase=='on'));after=witness()
  wire['replies'].append(dict(identifier=request['identifier'],kind=kind,data=data,accepted=accepted,before=before,after=after,guest_state_unchanged=before==after))
  if not accepted or before!=after:raise Exception('UART input rejected or changed guest architectural state')
 if not clean() or g.UartPowers[0].Phase!='on' or g.GpioConfig.Values[0x4001006c]!=0x53:raise Exception('main input readiness missing')
 baseline=int(uart.DmaTx.Transfers.Count);before=witness();accepted=bool(gpio.TrySetPin27(False,True));after=witness()
 wire['touch']=dict(accepted=accepted,before=before,after=after,guest_state_unchanged=before==after,baseline_transfers=baseline)
 if not accepted or before!=after:raise Exception('touch input rejected or changed guest state')
 def release():return bool(gpio.TrySetPin27(True,True))
 pulse=BlackwallRuntimeInputDelay(m,1,Func[bool](release));timers.append(pulse)
 advance(5)
 wire['touch']['released']=bool(pulse.Fired and pulse.Accepted)
 requests=[decode(t) for t in list(uart.DmaTx.Transfers)[baseline:]];wire['requests']+=requests
 if len(requests)!=2:raise Exception('expected two original touch requests')
 for request in requests:reply(request,10)
 baseline=int(uart.DmaTx.Transfers.Count);advance(100)
 requests=[decode(t) for t in list(uart.DmaTx.Transfers)[baseline:]];wire['requests']+=requests
 matching=[q for q in requests if q['channel']==2 and q['payload']==[2,1,1,0,0,0,0,0]]
 if len(matching)!=1:raise Exception('original app1 schedule request not observed on UART')
 gate=BlackwallRuntimeConnectionObserver(m,cpu,5228776,0x445e74,0x4456e8,537359948)
 reply(matching[0],2)
 advance(1000,gate)
 if not gate.Stopped or not m.IsPaused:raise Exception('original UI dispatch checkpoint absent')
 if ((int(g.McuClock.ModeWord)>>3)&3)!=2 or int(cpu.PerformanceInMips)!=10:raise Exception('explicit HP cadence precondition missing')
 before=witness();File.WriteAllBytes('/work-output/cadence-before-sram.bin',bus.ReadBytes(0x20000000,0x380000,True))
 cpu.PerformanceInMips=167
 after=witness();File.WriteAllBytes('/work-output/cadence-after-sram.bin',bus.ReadBytes(0x20000000,0x380000,True))
 wire['cadence']=dict(before=before,after=after,architectural_state_unchanged=before==after,mode_word=int(g.McuClock.ModeWord),mips_before=10,mips_after=int(cpu.PerformanceInMips),profile='existing hal-loop-equivalent-v1 HP functional cadence, not physical performance')
 if before!=after:raise Exception('cadence changed guest architectural state')
 clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallCompleteScreenObserver').Assembly)
 from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallCompleteScreenObserver
 def complete_frame():return bool(gpu.CompleteScreenCaptures>0 and gpu.CompleteScreenHasDetail)
 screen_stop=BlackwallCompleteScreenObserver(m,cpu,0x560f6a,Func[bool](complete_frame))
 advance(500,screen_stop)
 wire['first_complete_stop']=dict(stopped=bool(screen_stop.Stopped),pc=int(screen_stop.PC),checks=int(screen_stop.Checks))
 if not screen_stop.Stopped:raise Exception('complete screen not observed at original post-store boundary')
 wire['completed']=True
except Exception as error:
 wire['completed']=False;wire['error']=str(error)
File.WriteAllText('/work-output/wire-activation.json',json.dumps(wire))
Console.WriteLine('BLACKWALL_BOOT_WIRE '+json.dumps(wire))
reason='wire-complete' if wire['completed'] else 'wire-boundary'

result=dict(pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),instructions=int(cpu.ExecutedInstructions),virtual_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),halted=bool(cpu.IsHalted),policy=dict(violations=int(policy.Violations),operation=str(policy.LastOperation),address=int(policy.LastAddress),pc=int(policy.LastPC),width=int(policy.LastWidth)),cfsr=int(bus.ReadDoubleWord(0xe000ed28)),hfsr=int(bus.ReadDoubleWord(0xe000ed2c)),guard_accesses=int(m['sysbus.guard'].AccessCount))
result['registers']=[int(cpu.GetRegister(i).RawValue) for i in range(16)]
result['itcm40']=[int(v) for v in bus.ReadBytes(0x40,8,True)]
result['stop_reason']=reason
result['vtor']=int(bus.ReadDoubleWord(0xe000ed08))
result['itcm_written_bytes']=int(policy.WrittenBytes)
result['system_control_violations']=int(system_control.Violations)
result['points']=[dict(label=str(p.Label),address=int(p.Address),hits=int(p.Hits),first=int(p.FirstSequence)) for p in observer.Points]
result['events']=[dict(sequence=int(p.Sequence),label=str(p.Label),address=int(p.Address),pc=int(p.PC),r0=int(p.R0),r2=int(p.R2)) for p in observer.Events]
result['events_dropped']=int(observer.DroppedEvents)
result['guards']=[]
for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
 g=m['sysbus.'+name]
 result['guards'].append(dict(name=name,accesses=int(g.AccessCount),address=int(g.LastAddress),value=int(g.LastValue),width=int(g.LastWidth),operation=str(g.LastOperation)))
File.WriteAllBytes('/work-output/boot-globals.bin',bus.ReadBytes(0x20000000,0x28000,True))
File.WriteAllBytes('/work-output/guest-boot.bin',bus.ReadBytes(0x410000,149773,True))
File.WriteAllText('/work-output/boot-reset.json',json.dumps(result))
Console.WriteLine('BLACKWALL_BOOT_RESET '+json.dumps(result))

try:
    from System.IO import File
    from System import Console
    m=monitor.Machine;g=m['sysbus.guard'];cpu=m['sysbus.cpu']
    def power(v):return dict(mask=int(v.Mask),request=int(v.RequestWord),status=int(v.StatusWord),phase=str(v.Phase),profile=int(v.Profile),off_profile=int(v.OffProfile),generation=int(v.Generation),requests=int(v.Requests),responses=int(v.Responses))
    uarts=[]
    for pair in g.UartPowers:
        a=g.Uarts[pair.Key];v=power(pair.Value);v.update(module=int(pair.Key),quiescent=bool(a.Quiescent),control=int(a.Control),raw_interrupts=int(a.RawInterrupts),interrupt_mask=int(a.InterruptMask),irq=bool(a.IRQ.IsSet),dma=None if a.DmaTx is None else dict(control=int(a.DmaTx.Control),busy=bool(a.DmaTx.Busy)))
        uarts.append(v)
    ioms=[]
    for pair in g.IomPowers:
        v=power(pair.Value);v.update(module=int(pair.Key));ioms.append(v)
    extras={}
    for name in ('Mspi0Power','Mspi1Power','OtpPower','CryptoPower'):
        v=getattr(g,name);extras[name]=None if v is None else power(v)
    masks=uarts+ioms+[v for v in extras.values() if v is not None]
    request=int(g.GpuPower.RequestWord)|int(g.AdcPower.RequestWord)
    for v in masks:request|=v['request']
    proposed=int(cpu.GetRegister(1).RawValue)
    value=dict(paused=bool(m.IsPaused),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],request_before=request,proposed=proposed,changed_mask=request^proposed,buck_phase=str(g.BuckResponsePhase),shared_uart_gate=bool(g.UartHcpaGate),uarts=uarts,ioms=ioms,extras=extras,gpu_request=int(g.GpuPower.RequestWord),adc_request=int(g.AdcPower.RequestWord),hardware_accessed=False)
    value['adc']=dict(phase=str(g.AdcPower.Phase),request=int(g.AdcPower.RequestWord),status=int(g.AdcPower.StatusWord),requests=int(g.AdcPower.Requests),responses=int(g.AdcPower.Responses),calibration_word=int(g.AdcCalibrationControl.Value),calibration_reads=int(g.AdcCalibrationControl.Reads),calibration_writes=int(g.AdcCalibrationControl.Writes))
    value['buck']=dict(phase=str(g.BuckResponsePhase),reads=int(g.BuckResponseReads),transitions=int(g.BuckResponseTransitions),override_step=int(g.BuckOverrideStep),override_complete=bool(g.BuckOverrideComplete),enable_requested=bool(g.BuckStart.EnableRequested))
    File.WriteAllText('/work-output/boot-power-owner.json',json.dumps(value));Console.WriteLine('BLACKWALL_BOOT_POWER_OWNER '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_BOOT_POWER_OWNER_ERROR '+str(error))

c=m['sysbus.guard'].Mspi1Config
q=c.Pio
state=dict(configuration=dict((hex(int(v.Key)),int(v.Value)) for v in c.Values),queue=dict((hex(int(v.Key)),int(v.Value)) for v in c.CqValues),command_queue_init=bool(c.CommandQueueInit),controller_power_downs=int(c.ControllerPowerDowns),xip_accesses=(None if c.XipGuard is None else int(c.XipGuard.AccessCount)),pio=None if q is None else dict(busy=bool(q.Busy),recovering=bool(q.Recovering),rx_entries=int(q.RxEntries),tx_entries=int(q.TxEntries),control=int(q.Control),starts=int(q.Starts),completions=int(q.Completions),erase_busy=bool(q.EraseBusy),program_busy=bool(q.ProgramBusy)))
state['post_registers']=[int(cpu.GetRegister(i).RawValue) for i in range(16)]
state['post_instructions']=int(cpu.ExecutedInstructions)
File.WriteAllText('/work-output/mspi1-off-state.json',json.dumps(state))
Console.WriteLine('BLACKWALL_MSPI1_OFF_STATE '+json.dumps(state))

g=m['sysbus.guard'];q=g.Mspi1Config.Pio
v=dict(uarts=[dict(module=int(p.Key),tx=[int(b) for b in p.Value.TxBytes],writes=int(p.Value.Writes)) for p in g.Uarts],nor=dict(sampling_profile=str(q.SamplingProfile),completed_sampling_mask=int(q.CompletedSamplingMask),read_id_transfers=int(q.ReadIdTransfers),status_reads=int(q.StatusReadTransfers),configuration_reads=int(q.ConfigurationReadTransfers),array_reads=int(q.ArrayReadTransfers),array_bytes=int(q.ArrayBytesRead),last_array_address=int(q.LastArrayAddress),status_byte=int(q.CurrentStatusByte),configuration_byte=int(q.CurrentConfigurationByte),four_byte_mode=bool(q.FourByteAddressMode),array_profile=str(q.ArrayBacking.Profile),array_start=int(q.ArrayBacking.Start),array_length=int(q.ArrayBacking.Length)))
sp=int(cpu.GetRegister(13).RawValue)
if 0x20000000<=sp<0x20380000 and sp%4==0:
 length=min(0x800,0x20380000-sp)
 File.WriteAllBytes('/work-output/stopped-stack.bin',bus.ReadBytes(sp,length,True))
 v['stack_length']=length
else:v['stack_error']='SP outside mapped aligned SRAM'
v['stack_address']=sp
v['post_registers']=[int(cpu.GetRegister(i).RawValue) for i in range(16)]
v['post_instructions']=int(cpu.ExecutedInstructions)
File.WriteAllText('/work-output/retry-diagnostic.json',json.dumps(v))
Console.WriteLine('BLACKWALL_BOOT_DIAGNOSTIC '+json.dumps(v))

screen=dict(captures=int(gpu.CompleteScreenCaptures),nonzero=int(gpu.CompleteScreenNonzero),has_detail=bool(gpu.CompleteScreenHasDetail),address=int(gpu.CompleteScreenAddress),bytes=int(gpu.CompleteScreenFrameBytes.Length),rejections=int(gpu.Rejections),fault=str(gpu.Fault),width=576,height=288)
if screen['bytes']>0:File.WriteAllBytes('/work-output/complete-screen.bin',gpu.CompleteScreenFrameBytes)
File.WriteAllText('/work-output/screen.json',json.dumps(screen))
Console.WriteLine('BLACKWALL_BOOT_SCREEN '+json.dumps(screen))

marker=m['sysbus.guard_mram_tail'].OtaMarker
marker_state=dict(profile=str(marker.Profile),boot_read_pc=int(marker.BootReadPc),reads=int(marker.Reads),boot_reads=int(marker.BootReads),startup_reads=int(marker.StartupReads),setter_reads=int(marker.SetterReads),last_read_pc=int(marker.LastReadPc))
File.WriteAllText('/work-output/marker.json',json.dumps(marker_state))
Console.WriteLine('BLACKWALL_BOOT_MARKER '+json.dumps(marker_state))

contexts=[]
for point in observer.Points:
 c=point.Context
 if c is not None:contexts.append(dict(label=str(point.Label),sequence=int(c.Sequence),pc=int(c.PC),sp=int(c.SP),msp=int(c.MSP),psp=int(c.PSP),control=int(c.Control),xpsr=int(c.Xpsr),vtor=int(c.VectorTableOffset),process_stack_selected=bool(c.ProcessStackSelected)))
g=m['sysbus.guard']
vr=dict(before=int(g.VrctrlValue),proposed=int(g.LastValue),changed_mask=int(g.VrctrlValue)^int(g.LastValue),last_address=int(g.LastAddress),last_operation=str(g.LastOperation),writes=int(g.VrctrlWrites),reads=int(g.VrctrlReads),override_step=int(g.BuckOverrideStep),override_complete=bool(g.BuckOverrideComplete),buck_phase=str(g.BuckResponsePhase),mode_word=int(g.McuClock.ModeWord))
if vr['last_address']!=0x40020060 or vr['last_operation']!='write':vr['proposed']=None;vr['changed_mask']=None
File.WriteAllText('/work-output/handoff-context.json',json.dumps(dict(contexts=contexts,vrctrl=vr)))
File.WriteAllBytes('/work-output/guest-main.bin',bus.ReadBytes(0x438000,3700068,True))
Console.WriteLine('BLACKWALL_HANDOFF_CONTEXT '+json.dumps(dict(contexts=contexts,vrctrl=vr)))

r=g.HalStorage.Registers[0x4002004c]
v=dict(before=int(r.Value),reads=int(r.Reads),writes=int(r.Writes),initial=int(r.InitialValue),applied=bool(g.VddfTempco.Applied),original_word=int(g.VddfTempco.OriginalWord),reduced_trim=int(g.VddfTempco.ReducedTrim),mem_steps=int(g.MemLdo.StepsCompleted),buck_phase=str(g.BuckResponsePhase),last_address=int(g.LastAddress),proposed=int(g.LastValue),changed_mask=int(r.Value)^int(g.LastValue),guest_cached_trim=int(bus.ReadDoubleWord(0x20076c34)))
if v['last_address']!=0x4002004c or str(g.LastOperation)!='write':v['proposed']=None;v['changed_mask']=None
File.WriteAllText('/work-output/vddf-state.json',json.dumps(v))
Console.WriteLine('BLACKWALL_VDDF_STATE '+json.dumps(v))

adc=dict(phase=str(g.AdcPower.Phase),request=int(g.AdcPower.RequestWord),status=int(g.AdcPower.StatusWord),requests=int(g.AdcPower.Requests),responses=int(g.AdcPower.Responses),off_requests=int(g.AdcPower.OffRequests),retired=bool(g.AdcPower.EpochRetired),enabled=bool(g.AdcDisabledConfig.Enabled),config=[dict(address=int(v.Key),value=int(v.Value)) for v in g.AdcDisabledConfig.Values],fifo_count=int(g.AdcScan.Count),timer_phase=str(g.AdcInternalTrigger.Phase),timer_starts=int(g.AdcInternalTrigger.StartRequests),timer_events=int(g.AdcInternalTrigger.TriggerEvents),trigger_word=int(g.AdcTriggerConfig.Value))
File.WriteAllText('/work-output/adc-cycle-state.json',json.dumps(adc))
Console.WriteLine('BLACKWALL_ADC_CYCLE '+json.dumps(adc))

regs_before=[int(cpu.GetRegister(n).RawValue) for n in range(16)]
insn_before=int(cpu.ExecutedInstructions)
g=m['sysbus.guard'];hci=g.Em9305Reset.HciPeer;imu=m['sysbus.iom4.imu_fifo'].StartupPeer;touch=m['sysbus.iom5.iom5_register_probe'];gpio=g.GpioInterrupts
def scalar(obj,name):
 v=getattr(obj,name,None)
 if v is None:return None
 if isinstance(v,bool):return bool(v)
 try:return int(v)
 except:return str(v)
state=dict(hci=dict((n,scalar(hci,n)) for n in ['CommandsAccepted','RuntimeEventPending','RuntimeEventsConsumed','RuntimeRemoteRepliesConsumed','AdvertisingStopped','AdvertisingProcedureStep','LocalVersionCommands','LastReject']),imu=dict((n,scalar(imu.OnDemand,n)) for n in ['Phase','CompletedServices','Pending','Requests','Triggers','CompletedCalculations','LastReject']),imu_fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),touch=dict((n,scalar(touch,n)) for n in ['Profile','EventFramesCompleted','EventReadChunks','EventReplyPending','ConfigReplyPending','FrameCount']),gpio=dict(enable=[int(v) for v in gpio.EnableWords],pin27=scalar(gpio,'Pin27High'),pin117=scalar(gpio,'Pin117High'),pad27=int(g.GpioConfig.Values[0x4001006c]) if g.GpioConfig.Values.ContainsKey(0x4001006c) else None,pad117=int(g.GpioConfig.Values[0x400101d4]) if g.GpioConfig.Values.ContainsKey(0x400101d4) else None),uart0=dict(phase=str(g.UartPowers[0].Phase),transfers=int(g.Uarts[0].DmaTx.Transfers.Count),pending=int(g.Uarts[0].RxPending),bytes_read=int(g.Uarts[0].RxBytesRead)),gpu=dict(phase=str(g.GpuPower.Phase),captures=int(g.GpuCommandDevice.CompleteScreenCaptures)))
state['sram_globals']=dict((hex(a),int(bus.ReadDoubleWord(a))) for a in [537359948,537358196,537354940,537341304])
File.WriteAllBytes('/work-output/main-state-sram.bin',bus.ReadBytes(0x20000000,0x380000,True))
state['post_read_observer_unchanged']=regs_before==[int(cpu.GetRegister(n).RawValue) for n in range(16)] and insn_before==int(cpu.ExecutedInstructions) and bool(m.IsPaused)
File.WriteAllText('/work-output/main-input-state.json',json.dumps(state))
Console.WriteLine('BLACKWALL_MAIN_INPUT_STATE '+json.dumps(state))

# Read-only delegated guard accounting; diagnostic reads do not touch MMIO.
delegated=dict(rtc_accesses=int(g.Rtc.AccessCount),post_observer_unchanged=bool(state['post_read_observer_unchanged']))
File.WriteAllText('/work-output/delegated-guards.json',json.dumps(delegated))
Console.WriteLine('BLACKWALL_DELEGATED_GUARDS '+json.dumps(delegated))
