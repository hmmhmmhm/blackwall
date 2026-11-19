"""Bounded original ring→app→UI-entry runtime; peripheral input only."""

RUNTIME = r'''
try:
    import clr,time,json
    from System.IO import File
    from System import Console,Array,Byte,Func
    from Antmicro.Renode.Utilities import TypeManager
    from Antmicro.Renode.Time import TimeInterval
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallTouchInputObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallTouchInputObserver,BlackwallRuntimeConnectionObserver,BlackwallRuntimeInputDelay,BlackwallWakeRequestObserver,BlackwallWakeRxObserver
    m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];g=m['sysbus.guard'];uart=g.Uarts[0];p=json.loads(File.ReadAllText('/work/ring-profile.json'))
    if not m.IsPaused or int(cpu.PC.RawValue)!=p['getter']:raise ValueError('Expected original main hold')
    trace=BlackwallTouchInputObserver(m,cpu,p['tcb_slot'])
    for tag,key in [(20,'ring_relay'),(21,'ring_enqueue'),(0,'ring_receiver'),(3,'slider'),(5,'ring_caller')]:trace.Watch(tag,p[key])
    if p['hook'] is not None:
        trace.Watch(60,p['hook']);trace.Watch(61,p['fallback'])
    flow=p['flow'];wake=p['wake']
    for tag,key in [(30,'callback'),(31,'helper'),(32,'forward'),(33,'receive'),(34,'reply'),(35,'event_return'),(36,'ui_call')]:trace.Watch(tag,flow[key])
    for tag,address in [(52,wake['request_producer']),(53,wake['wake_gate']),(54,wake['ui_producer']),(55,wake['ui']['call_site']),(56,wake['ui']['callback'])]:trace.Watch(tag,address)
    stop=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),p['ring_receiver'],p['ring_caller'],p['tcb_slot'])
    regs=lambda:[int(cpu.GetRegister(n).RawValue) for n in range(16)]
    before=dict(registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),read=int(uart.RxBytesRead),irq=int(uart.IrqExceptionEntries))
    before['transfers']=int(uart.DmaTx.Transfers.Count)
    File.WriteAllBytes('/work-output/before-input-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    incoming=Array[Byte]([int(p['wire_hex'][i:i+2],16) for i in range(0,len(p['wire_hex']),2)])
    accepted=bool(uart.TryReceive(incoming,g.UartPowers[0].Phase=='on'));injected=dict(accepted=accepted,registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pending=int(uart.RxPending))
    File.WriteAllBytes('/work-output/after-input-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    while not stop.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<100*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
    m.Pause()
    ring_stage=dict(stopped=bool(stop.Stopped),pc=int(cpu.PC.RawValue),entry=[int(v) for v in stop.Entry],exit=[int(v) for v in stop.Exit],ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks))
    if not stop.Stopped:raise ValueError('Original ring handler checkpoint missing')
    ring_stage['report']=[int(v) for v in b.ReadBytes(stop.Entry[0],11,True)]
    File.WriteAllBytes('/work-output/ring-caller-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    app_stop=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),flow['callback'],wake['wake_gate'],p['tcb_slot'])
    def pause_for_send():
        m.Pause();return True
    timer=BlackwallRuntimeInputDelay(m,5,Func[bool](pause_for_send))
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    while not timer.Fired and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<10*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
    m.Pause()
    requests=[]
    for t in list(uart.DmaTx.Transfers)[before['transfers']:]:
        data=[int(v) for v in t.Data]
        if len(data)>=19 and data[5:7]==[0,1] and data[9:13]==[1,9,8,1]:requests.append(data)
    if not timer.Fired or len(requests)!=1:raise ValueError('Unique original ring108 request missing')
    def crc(values):
        value=0
        for byte in values:
            value^=byte
            for unused in range(8):value=(value>>1)^(0xa001 if value&1 else 0)
        return value
    def reply_frame(identifier,payload):
        h=[1,identifier>>8,identifier&255,0,1,0,0];a=crc(h);z=crc([payload]);return h+[a>>8,a&255,payload,z>>8,z&255]
    identifier=(requests[0][1]<<8)|requests[0][2];ack=reply_frame(identifier,10)
    ack_before=dict(registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pending=int(uart.RxPending))
    File.WriteAllBytes('/work-output/before-ack-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    accepted_ack=bool(uart.TryReceive(Array[Byte](ack),g.UartPowers[0].Phase=='on'));ack_after=dict(accepted=accepted_ack,registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pending=int(uart.RxPending))
    File.WriteAllBytes('/work-output/after-ack-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    if not accepted_ack:raise ValueError('Declared ACK rejected by UART')
    EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
    while not app_stop.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<100*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
    m.Pause()
    app_stage=dict(stopped=bool(app_stop.Stopped),pc=int(cpu.PC.RawValue),entry=[int(v) for v in app_stop.Entry],exit=[int(v) for v in app_stop.Exit],requests=requests,ack=ack,before=ack_before,after=ack_after)
    File.WriteAllBytes('/work-output/app-wake-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
    request_stage=None;display_reply=None;timeout_trace=None
    if app_stop.Stopped:
        request=BlackwallWakeRequestObserver(m,cpu,wake['sync_start'],wake['finish_return'],p['tcb_slot'])
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
        while not request.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<100*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
        m.Pause()
        request_stage=dict(stopped=bool(request.Stopped),pc=int(cpu.PC.RawValue),matches=int(request.Matches),context=[int(v) for v in request.Context],exit=[int(v) for v in request.Exit],descriptor=[int(v) for v in request.DescriptorBytes],packet=[int(v) for v in request.PacketBytes])
        File.WriteAllBytes('/work-output/display-send-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
        if request.Stopped:
            descriptor=[int(v) for v in request.DescriptorBytes];display_id=descriptor[0]|descriptor[1]<<8;response=reply_frame(display_id,2)
            timeout_trace=BlackwallWakeRxObserver(m,cpu,uart,p['tcb_slot'])
            state_before=dict(registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pending=int(uart.RxPending))
            File.WriteAllBytes('/work-output/before-display-reply-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            accepted_display=bool(uart.TryReceive(Array[Byte](response),g.UartPowers[0].Phase=='on'));state_after=dict(accepted=accepted_display,registers=regs(),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pending=int(uart.RxPending))
            File.WriteAllBytes('/work-output/after-display-reply-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            if not accepted_display:raise ValueError('Declared display reply rejected by UART')
            ui_dispatch=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),wake['ui_producer'],wake['ui']['call_site'],p['tcb_slot'])
            EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
            while not ui_dispatch.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<100*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
            m.Pause()
            display_reply=dict(id=display_id,bytes=response,before=state_before,after=state_after,ui_dispatch=bool(ui_dispatch.Stopped))
            if ui_dispatch.Stopped:
                callback=BlackwallRuntimeConnectionObserver(m,cpu,int(uart.IrqHandlerAddress),wake['ui']['callback'],wake['ui']['callback'],p['tcb_slot'])
                EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+30;start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                while not callback.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<1000*int(TimeInterval.TicksPerMillisecond):time.sleep(0.01)
                m.Pause();display_reply['callback']=dict(stopped=bool(callback.Stopped),pc=int(cpu.PC.RawValue),entry=[int(v) for v in callback.Entry])
    guards=[]
    for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
        item=m['sysbus.'+name];guards.append(dict(name=name,accesses=int(item.AccessCount),address=int(item.LastAddress),operation=str(item.LastOperation)))
    result=dict(stopped=bool(stop.Stopped),pc=int(cpu.PC.RawValue),entry=[int(v) for v in stop.Entry],exit=[int(v) for v in stop.Exit],before=before,injected=injected,rows=[[int(v) for v in row] for row in trace.Rows],overflow=bool(trace.Overflow),read=int(uart.RxBytesRead),pending=int(uart.RxPending),irq_entries=int(stop.IrqEntries),uart_irq_entries=int(uart.IrqExceptionEntries),uart_active_vector=int(uart.LastActiveVector),uart_isr=int(uart.IrqHandlerAddress),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),guards=guards)
    result['ring_stage']=ring_stage;result['app_stage']=app_stage;result['request_stage']=request_stage;result['display_reply']=display_reply
    result['timeout_trace']=dict(rows=[[int(v) for v in row] for row in timeout_trace.Rows],overflow=bool(timeout_trace.Overflow)) if timeout_trace is not None else None
    result['uart_dma']=[dict(data=[int(v) for v in t.Data]) for t in uart.DmaTx.Transfers]
    result['last_tick']=int(b.ReadDoubleWord(p['last_tick']))
    if stop.Stopped:result['actual_report']=ring_stage['report']
    File.WriteAllBytes('/work-output/ring-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/ring.json',json.dumps(result));Console.WriteLine('BLACKWALL_RING_RUNTIME '+json.dumps(result))
except Exception as error:
    Console.WriteLine('BLACKWALL_RING_RUNTIME_ERROR '+str(error))
'''
