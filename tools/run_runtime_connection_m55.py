"""Device event -> GPIO59 -> original SPI/HCI/DM; no API caller or register seeding."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import textwrap
from datetime import datetime,timezone
from runtime_event_models import compose, integrate_gaf, imu_span
from run_renode_m55_probe import execute
from native_replay import IMAGE
from run_native_candidate import finish_capture, validate_semantics
from firmware_candidate import candidate_runtime
import runtime_firmware_candidate

ROOT=Path(__file__).resolve().parents[1]
VIRTUAL_BUDGET_MS=20000
EVENT='043e1301004000010011223344556618000000c80000'

def decode(raw,address,length):
    """Retain the byte-decoder API while loading its ARM dependencies on use."""
    from inspect_ambiq_target import decode as arm_decode
    return arm_decode(raw,address,length)

def att_packets(handle=0x842,corrupt_crc=False):
    from probe_tpl_service_ingress import message
    from probe_display_root_ingress import packet
    def acl(pdu):return b'\x02'+struct.pack('<HHHH',0x2040,len(pdu)+4,len(pdu),4)+pdu
    frames=[acl(bytes.fromhex('03f700')),acl(b'\x52'+struct.pack('<H',handle)+packet(128,message(1700000000,16),both=False))]
    if corrupt_crc:
        data=bytearray(frames[1]);data[-1]^=1;frames[1]=bytes(data)
    return [f.hex() for f in frames]



def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def sync_queue(ram,queue):
    def word(address):
        assert 0x20000000<=address<=0x20380000-4
        return struct.unpack_from('<I',ram,address-0x20000000)[0]
    head,write,tail,read=struct.unpack_from('<4I',ram,queue-0x20000000)
    count=word(queue+0x38)
    assert word(queue+0x3c)==150 and word(queue+0x40)==4 and count<=150
    assert 0x20000000<=head<=read<tail<=0x20380000 and head<=write<tail
    packets=[]
    for _ in range(count):
        read+=4
        if read>=tail:read=head
        node=word(read)
        assert 0x20000000<=node<=0x20380000-12
        callback,kind,size,pointer=struct.unpack_from('<IHHI',ram,node-0x20000000)
        assert 0x20000000<=pointer<=0x20380000-size
        packets.append(dict(callback=callback,kind=kind,data=ram[pointer-0x20000000:pointer-0x20000000+size].hex()))
    return dict(count=count,packets=packets)


def opened_contract(raw,dm):
    hits=[]
    for pc in range(dm-0x1000,dm,2):
        code=decode(raw,pc,4)
        if len(code)==2 and code[0].mnemonic=='ldrh' and code[0].op_str=='r0, [r5, #6]' and code[1].mnemonic=='strh' and code[1].op_str=='r0, [r4, #0xc]':hits.append(pc)
    assert len(hits)==1
    entry=hits[0]-0x10;body=decode(raw,entry,0xb0)
    assert body[0].op_str=='{r3, r4, r5, lr}'
    returns=[i.address for i in body if i.mnemonic.startswith('pop') and i.op_str=='{r0, r4, r5, pc}']
    assert len(returns)==1
    return dict(opened=entry,finished=returns[0])


def build(s,out,case,control=False,att_time=False,readonly_control=False,disconnect_reason=None,corrupt_crc=False,disconnect_delay_ms=0,gaf_profile=False,gaf_on_demand_control=False,gaf_control_window_us=1000,firmware_manifest=None,firmware_baseline=None):
    assert not out.exists() and out.resolve().is_relative_to(s.resolve()) and not s.resolve().is_relative_to(ROOT)
    base=s/'tpl-time-native-01'/case;pin=json.loads((s/'tpl-time-research-01/manifest.json').read_text())
    assert sha(base/'capture-files.json')==pin['files'][str((base/'capture-files.json').relative_to(s))]
    files=json.loads((base/'capture-files.json').read_text())['files']
    for name in ['main.bin','strict.cs','board.repl']:assert sha(base/name)==files[name]
    profile=json.loads((base/'sync-profile.json').read_text());template=s/profile['template']
    proof=s/'hci-connection-source-05/report.json';source_pin=json.loads((s/'hci-connection-research-01/manifest.json').read_text())
    assert sha(proof)==source_pin['files'][str(proof.relative_to(s))]
    c=next(x for x in json.loads(proof.read_text())['cases'] if x['case']==case)
    raw=(base/'main.bin').read_bytes();assert sha(base/'main.bin')==c['main_sha256']
    opened=opened_contract(raw,c['contract']['dm_handler'])
    selected=None
    if (firmware_manifest is None)!=(firmware_baseline is None):
        raise ValueError('Candidate selection requires both manifest and registration baseline')
    if firmware_manifest is not None:
        candidate_profile=dict(getter=profile['getter'],gpio=c['contract']['gpio'],att_time=att_time,**opened)
        if att_time:candidate_profile['service']=profile['service']
        if readonly_control or corrupt_crc:
            att_source=json.loads((s/'eus-att-source-04/report.json').read_text())
            write=next(x['contract']['write_processor'] for x in att_source['cases'] if x['case']==case)
            candidate_profile.update(write_processor=write,write_return=next(i.address for i in decode(raw,write,0x350) if i.mnemonic.startswith('pop') and i.op_str.startswith('{r0, r1, r2, r3,')))
        if disconnect_reason is not None:
            close=next(x for x in json.loads((s/'runtime-peer-failure-research-01/close-contract.json').read_text())['cases'] if x['case']==case)
            candidate_profile.update(closed=close['closed'],closed_return=close['closed_return'])
        selected=runtime_firmware_candidate.select(s,firmware_manifest,firmware_baseline,case,raw,candidate_profile)
    out.mkdir(mode=0o700,parents=True);(out/'exports').mkdir()
    for name in ['main.bin','sram-fill.bin','itcm-fill.bin','probe.resc','result.py','activation.cs']:
        shutil.copyfile(template/name,out/name)
    if selected is not None:(out/'main.bin').write_bytes(selected[0])
    model=compose(s,(base/'strict.cs').read_text())
    if gaf_profile:
        model,gaf=integrate_gaf(s,model,gaf_on_demand_control,gaf_control_window_us)
        (out/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
    (out/'strict.cs').write_text(model)
    observer=(ROOT/'tools/renode-runtime-connection-observer.cs').read_bytes()
    (out/'connection-observer.cs').write_bytes(observer)
    with (out/'activation.cs').open('ab') as f:f.write(b'\n'+observer)
    board=(template/'board.repl').read_text();anchor='    gpioInterruptIdle: true\n';assert board.count(anchor)==1
    if not control:board=board.replace(anchor,anchor+'    gpioInterruptController: gpio_runtime\n')
    anchor='spi_header: Miscellaneous.BlackwallEm9305EventPeer @ none\n';assert board.count(anchor)==1
    if not control:
        board=board.replace(anchor,anchor+'    runtimeConnectionEventHex: "'+EVENT+'"\n')
        board+='\ngpio_runtime: Miscellaneous.BlackwallGpioInterruptIdle @ none\n    runtimePin117: true\n    -> nvic@59\nruntime_link: Miscellaneous.BlackwallEm9305RuntimeLink @ none\n    peer: spi_header\n    owner: guard\n'
    if att_time:
        assert not control
        board=board.replace('    runtimeConnectionEventHex:', '    runtimeAttPacketsHex: "'+';'.join(att_packets(0x844 if readonly_control else 0x842,corrupt_crc))+'"\n    runtimeHostAclHex: "02400007000300040002f700"\n    runtimeRandHex: "0102030405060708"\n    runtimeRssi: -42\n    runtimeRemoteFeaturesHex: "0100000000000000"\n    runtimeConnectionEventHex:')
        src=s/'tpl-time-native-01'/case/'sync-profile.json'
        service=json.loads(src.read_text())['service']
        roots=s/'display-root-source-05/report.json';root_pin=json.loads((s/'display-root-research-01/manifest.json').read_text())
        assert sha(roots)==root_pin['files'][str(roots.relative_to(s))]
        sync_queue_address=next(x['contract']['queue'] for x in json.loads(roots.read_text())['cases'] if x['case']==case)
        observer=(ROOT/'tools/renode-tpl-service-observer.cs').read_bytes()
        (out/'att-observer.cs').write_bytes(observer)
        with (out/'activation.cs').open('ab') as f:f.write(b'\n'+observer)
        board=board.replace('    halLowUpperWrites: false\n','    halLowUpperWrites: true\n')
        if readonly_control or corrupt_crc:
            att_source=json.loads((s/'eus-att-source-04/report.json').read_text())
            write=next(x['contract']['write_processor'] for x in att_source['cases'] if x['case']==case)
            returned=next(i.address for i in decode(raw,write,0x350) if i.mnemonic.startswith('pop') and i.op_str.startswith('{r0, r1, r2, r3,'))
            observer=(ROOT/'tools/renode-att-reject-observer.cs').read_bytes();(out/'reject-observer.cs').write_bytes(observer)
            with (out/'activation.cs').open('ab') as f:f.write(b'\n'+observer)

    if disconnect_reason is not None:
        assert att_time and not readonly_control and disconnect_reason in (8,19)
        close_path=s/'runtime-peer-failure-research-01/close-contract.json'
        close=next(x for x in json.loads(close_path.read_text())['cases'] if x['case']==case)
        assert close['dm_global']==c['dm_global'] and decode(raw,close['closed'],2)[0].op_str=='{r3, r4, r5, lr}' and decode(raw,close['closed_return'],2)[0].op_str=='{r0, r4, r5, pc}'
        disconnect_event='040504004000'+format(disconnect_reason,'02x')
        board=board.replace('    runtimeConnectionEventHex:', '    runtimeDisconnectEventHex: "'+disconnect_event+'"\n    runtimeConnectionEventHex:')
        (out/'failure-source.json').write_bytes(close_path.read_bytes())
    if gaf_profile:
        anchor='    profile: \"icm45608-reset-lifecycle\"\n';assert board.count(anchor)==1
        board=board.replace(anchor,anchor+'    gafParametersHex: \"'+gaf['parameters_hex']+'\"\n    gafConfiguration: true\n    gafClockVariationByte: '+str(gaf['clock_variation_byte'])+'\n')
        if gaf_on_demand_control:board=board.replace(anchor,anchor+'    gafOnDemandControl: true\n    gafOnDemandMicroseconds: '+str(gaf_control_window_us)+'\n')
    (out/'board.repl').write_text(board)
    p=dict(case=case,control=control,source_template=profile['template'],getter=profile['getter'],tcb_slot=profile['tcb_slot'],dm_global=c['dm_global'],gpio=c['contract']['gpio'],event=EVENT,main_sha256=sha(out/'main.bin'),model_sha256=sha(out/'strict.cs'),baseline_sram_sha256=sha(template/'exports/sram-full.bin'),virtual_budget_ms=VIRTUAL_BUDGET_MS,**opened)
    if gaf_profile:p.update(gaf_profile=gaf,gaf_profile_sha256=sha(out/'gaf-profile.json'))
    if att_time:p.update(att_time=True,service=service,sync_queue=sync_queue_address,att_packets=att_packets(0x844 if readonly_control else 0x842,corrupt_crc))
    if readonly_control or corrupt_crc:p.update(write_processor=write,write_return=returned)
    if readonly_control:p['readonly_control']=True
    if corrupt_crc:p['att_corrupt_crc']=True
    if disconnect_reason is not None:p.update(disconnect_reason=disconnect_reason,disconnect_event=disconnect_event,closed=close['closed'],closed_return=close['closed_return'],failure_source_sha256=sha(out/'failure-source.json'),disconnect_delay_ms=disconnect_delay_ms)
    if selected is not None:p['firmware_candidate']=runtime_firmware_candidate.snapshot(out,firmware_manifest,firmware_baseline,selected[1],selected[2])
    (out/'connection-profile.json').write_text(json.dumps(p,indent=2)+'\n')
    runtime=(template/'run.py').read_text();anchor='\ntry:\n    import clr,time,json\n';assert runtime.count(anchor)==1
    if selected is not None:runtime=candidate_runtime(runtime,len(raw),len(selected[0]))
    post='''
    try:
        import clr,time,json
        from System.IO import File
        from System import Console
        from Antmicro.Renode.Utilities import TypeManager
        from Antmicro.Renode.Time import TimeInterval
        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRuntimeConnectionObserver').Assembly)
        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeConnectionObserver
        m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];g=m['sysbus.guard'];peer=g.Em9305Reset.HciPeer
        p=json.loads(File.ReadAllText('/work/connection-profile.json'))
        if not m.IsPaused or int(cpu.PC.RawValue)!=p['getter']:raise ValueError('Expected retained original main hold')
        q=g.GpioInterrupts
        def gaf_snapshot():
            if not p.get('gaf_profile'):return None
            imu=m['sysbus.iom4.imu_identity'];v=imu.GafParameters
            result=dict(fixture=str(v.FixtureHex),values=str(v.ValuesHex),fields=int(v.FieldsStarted),read_bytes=int(v.ReadBytes),read_remaining=int(v.ReadRemaining),complete=bool(v.Complete),written_bytes=int(v.WrittenBytes),write_transactions=int(v.WriteTransactions),history=str(v.History),clock_reads=int(v.ClockReads),clock_selections=int(v.ClockSelections),service_completions=int(imu.Service.Completions),service_pending=bool(imu.Service.Pending))
            if p['gaf_profile'].get('on_demand_control'):
                d=imu.OnDemand
                result['on_demand']=dict(phase=str(d.Phase),request=int(d.RequestId),requests=int(d.Requests),reads=int(d.Reads),writes=int(d.Writes),triggers=int(d.Triggers),busy_reads=int(d.BusyReads),pending=bool(d.Pending),observation_ended=bool(d.ObservationEnded),requested_ticks=int(d.RequestedAt),triggered_ticks=int(d.TriggeredAt),deadline_ticks=int(d.DeadlineAt),ended_observed_ticks=int(d.EndedObservedAt),calculation_supported=bool(d.CalculationSupported),completed_calculations=int(d.CompletedCalculations),unsupported_result_requests=int(d.UnsupportedResultRequests),history=str(d.History),last_reject=str(d.LastReject),request_ram=int(imu.Service.RamByte(4)))
            return result
        started_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);ticks_per_ms=int(TimeInterval.TicksPerMillisecond)
        budget_ticks=p['virtual_budget_ms']*ticks_per_ms
        before=dict(pc=int(cpu.PC.RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),counter=int(b.ReadDoubleWord(p['gpio']['counter'])),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),frames=int(peer.Frames),virtual_ticks=started_ticks)
        diag=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['opened'],p['finished'],p['tcb_slot'])
        accepted=bool(peer.TryQueueRuntimeConnection());at_input=dict(irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),ready=int(peer.ReadyLevel),pc=int(cpu.PC.RawValue))
        if not accepted:raise ValueError('Runtime event preconditions not met')
        cpu.IsHalted=False
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
        while not diag.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-started_ticks<budget_ticks:time.sleep(0.01)
        m.Pause()
        att={}
        if p.get('att_time') and diag.Stopped:
            from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallTplServiceObserver
            c=p['service'];app=BlackwallTplServiceObserver(m,cpu,c['ingress'],c['consumer'],c['clock_return'],c['consumer_return'],p['tcb_slot'])
            reject=None
            if p.get('readonly_control') or p.get('att_corrupt_crc'):
                from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallAttRejectObserver
                reject=BlackwallAttRejectObserver(m,cpu,p['write_processor'],p['write_return'],p['tcb_slot'])
            File.WriteAllBytes('/work-output/connected-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            att['workflow_started']=True
            cpu.IsHalted=False
            EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
            while not app.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-started_ticks<budget_ticks:time.sleep(0.01)
            m.Pause()
            if reject is not None:att['reject']=dict(stopped=bool(reject.Stopped),calls=int(reject.Calls),verdict=[int(v) for v in reject.Verdict])
            att.update(stopped=bool(app.Stopped),inputs=[[int(v) for v in row] for row in app.Inputs],consumers=[[int(v) for v in row] for row in app.Consumers],applied=[[int(v) for v in row] for row in app.Applied],returns=[[int(v) for v in row] for row in app.Returns],registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],host_acl=int(peer.RuntimeHostAclConsumed),rand_commands=int(peer.RuntimeRandCommandsAccepted),rand_replies=int(peer.RuntimeRandRepliesConsumed),rssi_commands=int(peer.RuntimeRssiCommandsAccepted),rssi_replies=int(peer.RuntimeRssiRepliesConsumed),remote_commands=int(peer.RuntimeRemoteCommandsAccepted),remote_replies=int(peer.RuntimeRemoteRepliesConsumed),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate),pending=bool(g.Rtc.WritePending),error=str(g.Rtc.LastError)))
        guards=[]
        for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
            v=m['sysbus.'+name];guards.append(dict(name=name,accesses=int(v.AccessCount),address=int(v.LastAddress)))
        result=dict(virtual_time=dict(start_ticks=started_ticks,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),ticks_per_ms=ticks_per_ms,budget_ms=p['virtual_budget_ms']),att=att,stopped=bool(diag.Stopped),pc=int(cpu.PC.RawValue),before=before,input=at_input,accepted=accepted,entry=[int(x) for x in diag.Entry],exit=[int(x) for x in diag.Exit],irq_entries=int(diag.IrqEntries),open_calls=int(diag.OpenCalls),peer=dict(state=str(peer.State),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),frames=int(peer.Frames),runtime_consumed=int(peer.RuntimeEventsConsumed),runtime_pending=bool(peer.RuntimeEventPending)),gpio=dict(pending=bool(q.Pending117),irq=bool(q.IRQ.IsSet),edges=int(q.RisingEdges),clear_requests=[int(x) for x in q.ClearRequests]),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations))
        if p.get('gaf_profile'):result['imu_gaf']=gaf_snapshot()
        File.WriteAllBytes('/work-output/connection-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
        File.WriteAllText('/work-output/connection.json',json.dumps(result));Console.WriteLine('BLACKWALL_RUNTIME_CONNECTION '+json.dumps(result))
        if p.get('disconnect_reason') is not None:
            if not app.Stopped:raise ValueError('Time action must return before disconnect input')
            dticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
            close=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['closed'],p['closed_return'],p['tcb_slot'])
            schedule=None
            dinput=dict(accepted=False,irq=False,pending=False,pc=int(cpu.PC.RawValue),origin_pc=int(cpu.PC.RawValue))
            def enqueue_disconnect():
                accepted=bool(peer.TryQueueRuntimeDisconnect())
                dinput.update(accepted=accepted,irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),pc=int(cpu.PC.RawValue))
                return accepted
            if p.get('disconnect_delay_ms',0):
                from System import Func
                from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRuntimeInputDelay
                schedule=BlackwallRuntimeInputDelay(m,p['disconnect_delay_ms'],Func[bool](enqueue_disconnect))
            elif not enqueue_disconnect():raise ValueError('Disconnect device input preconditions not met')
            cpu.IsHalted=False
            EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
            while not close.Stopped and not m.IsPaused and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-dticks<budget_ticks:time.sleep(0.01)
            m.Pause()
            final_guards=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress)) for x in guards]
            dc=dict(input=dinput,stopped=bool(close.Stopped),pc=int(cpu.PC.RawValue),entry=[int(x) for x in close.Entry],exit=[int(x) for x in close.Exit],calls=int(close.OpenCalls),irq_entries=int(close.IrqEntries),runtime_consumed=int(peer.RuntimeEventsConsumed),runtime_pending=bool(peer.RuntimeEventPending),gpio=dict(irq=bool(q.IRQ.IsSet),pending=bool(q.Pending117),edges=int(q.RisingEdges)),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),guards=final_guards,virtual_time=dict(start_ticks=dticks,end_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),ticks_per_ms=ticks_per_ms,budget_ms=p['virtual_budget_ms']),rtc=dict(commits=int(g.Rtc.Commits),date=str(g.Rtc.VirtualDate),pending=bool(g.Rtc.WritePending),error=str(g.Rtc.LastError)))
            if p.get('gaf_profile'):
                dc['imu_gaf']=gaf_snapshot()
                dc['registers']=[int(cpu.GetRegister(n).RawValue) for n in range(16)]
                iom=m['sysbus.iom4'];dc['iom4']=dict(address=int(iom.LastAddress),value=int(iom.LastValue),operation=str(iom.LastOperation),commands=int(iom.Commands))
            if schedule is not None:dc['delay']=dict(fired=bool(schedule.Fired),accepted=bool(schedule.Accepted),start_ticks=int(schedule.StartedAt),fired_ticks=int(schedule.FiredAt),milliseconds=p['disconnect_delay_ms'])
            File.WriteAllBytes('/work-output/disconnect-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            File.WriteAllText('/work-output/disconnect.json',json.dumps(dc));Console.WriteLine('BLACKWALL_RUNTIME_DISCONNECT '+json.dumps(dc))

    except Exception as error:
        Console.WriteLine('BLACKWALL_RUNTIME_CONNECTION_ERROR '+str(error))
    '''
    if control:
        post='''
        try:
            import json
            from System.IO import File
            from System import Console
            m=monitor.Machine;cpu=m['sysbus.cpu']
            result=dict(paused=bool(m.IsPaused),pc=int(cpu.PC.RawValue),runtime_enabled=bool(m['sysbus.guard'].Em9305Reset.HciPeer.HasRuntimeConnectionScenario))
            File.WriteAllBytes('/work-output/connection-sram.bin',m.SystemBus.ReadBytes(0x20000000,0x380000,True))
            File.WriteAllText('/work-output/control.json',json.dumps(result));Console.WriteLine('BLACKWALL_RUNTIME_CONTROL '+json.dumps(result))
        except Exception as error:
            Console.WriteLine('BLACKWALL_RUNTIME_CONTROL_ERROR '+str(error))
        '''
    (out/'run.py').write_text(runtime.split(anchor)[0]+textwrap.dedent(post))
    (out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    names=['strict.cs','main.bin','sram-fill.bin','itcm-fill.bin','board.repl','run.py','probe.resc','result.py','activation.cs','connection-observer.cs','connection-profile.json','runner-source.py']
    if att_time:names+=['att-observer.cs']
    if readonly_control or corrupt_crc:names+=['reject-observer.cs']
    if disconnect_reason is not None:names+=['failure-source.json']
    if gaf_profile:names+=['gaf-profile.json']
    if selected is not None:names+=['firmware-candidate.json','firmware-runtime-anchors.json']+[str(path.relative_to(out)) for path in sorted((out/'firmware-baseline').rglob('*')) if path.is_file()]
    (out/'connection-inputs.json').write_text(json.dumps({n:sha(out/n) for n in names},indent=2)+'\n')
    return p


def pin_capture(out,origin='runner-after-execution'):
    if origin=='import-after-initial-verification':
        old=json.loads((out/'verification.json').read_text())
        assert old['passed'] and old['observed']==json.loads((out/'exports/connection.json').read_text())
    inputs=json.loads((out/'connection-inputs.json').read_text())
    for n,h in inputs.items():assert sha(out/n)==h
    names=set(inputs)|{'connection-inputs.json','renode.log'}|{str(f.relative_to(out)) for f in (out/'exports').rglob('*') if f.is_file()}
    path=out/'capture-files.json';assert not path.exists()
    path.write_text(json.dumps(dict(origin=origin,files={n:sha(out/n) for n in sorted(names)}),indent=2)+'\n')


def inspect(out,destination=None):
    for n,h in json.loads((out/'capture-files.json').read_text())['files'].items():
        assert (out/n).resolve().is_relative_to(out.resolve()) and sha(out/n)==h
    p=json.loads((out/'connection-profile.json').read_text())
    candidate_checks=runtime_firmware_candidate.inspect(out,p) if 'firmware_candidate' in p else {}
    if 'firmware_candidate' not in p:runtime_firmware_candidate.check_original(out,p)
    if p.get('control'):
        r=json.loads((out/'exports/control.json').read_text())
        checks=dict(stopped=r['paused'] and r['pc']==p['getter'],runtime_disabled=not r['runtime_enabled'],baseline_sram_exact=sha(out/'exports/connection-sram.bin')==p['baseline_sram_sha256'],main_unchanged=sha(out/'main.bin')==p['main_sha256'],model_unchanged=sha(out/'strict.cs')==p['model_sha256'])
        checks.update(candidate_checks)
        spec=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['checks','baseline_sram_exact']]),checks=[dict(path=['checks',k],eq=True) for k in checks],allowed_differences=['New optional model code with runtime event and GPIO IRQ profile off; no resumed execution or event.'],unresolved_differences=['This control covers the retained initial main hold only.'])
        validate_semantics(spec)
        result=dict(schema=2,passed=all(checks.values()),case=p['case'],control=True,checks=checks,observed=r,boundary_kind='bounded-capture',execution_passed=True,selected_observation=dict(events=[dict(pc=r['pc'])],sequence=1,dropped_events=0))
        result=finish_capture(result,dict(checks=dict(main_unchanged=True,model_unchanged=True,baseline_sram_exact=True)),spec);result['contract']=spec
        target=out if destination is None else destination
        if destination is not None:destination.mkdir(mode=0o700,parents=True)
        (target/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
    p=json.loads((out/'connection-profile.json').read_text());r=json.loads((out/'exports/connection.json').read_text());ram=(out/'exports/connection-sram.bin').read_bytes()
    logs=[json.loads(x.split('BLACKWALL_RUNTIME_CONNECTION ',1)[1]) for x in (out/'renode.log').read_text().splitlines() if x.startswith('BLACKWALL_RUNTIME_CONNECTION ')];assert logs==[r]
    slots=[p['dm_global']+48*k for k in range(3)];active=[x for x in slots if ram[x+0x16-0x20000000]!=0]
    task=r['exit'][1] if len(r['exit'])==3 else 0
    task_name=ram[task+52-0x20000000:task+84-0x20000000].split(b'\0')[0].decode(errors='replace') if task else ''
    checks=dict(stopped=r['stopped'] and r['pc']==p['finished'],irq=r['irq_entries']==1 and r['input']['irq'] and r['input']['pending'],no_pc_seed=r['input']['pc']==r['before']['pc']==p['getter'],event_consumed=r['peer']['runtime_consumed']==1 and not r['peer']['runtime_pending'],gpio_cleared=not r['gpio']['pending'] and not r['gpio']['irq'] and r['gpio']['edges']==1 and r['gpio']['clear_requests'][3]&(1<<21)!=0,connection=len(active)==1 and struct.unpack_from('<H',ram,active[0]+12-0x20000000)[0]==64 and ram[active[0]+0x10-0x20000000]==1 and ram[active[0]+0x19-0x20000000]==1,original_task=len(r['entry'])==6 and len(r['exit'])==3 and r['entry'][4]==task and task!=r['before']['tcb'] and r['entry'][5]&511==r['exit'][2]&511==0,no_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,no_unsupported=all(x['accesses']==0 for x in r['guards']),main_unchanged=sha(out/'main.bin')==p['main_sha256'],model_unchanged=sha(out/'strict.cs')==p['model_sha256'])
    checks.update(candidate_checks)
    entry=r['entry'];exit=r['exit'];msg=entry[1] if len(entry)==6 else 0
    connection_ram=(out/'exports/connected-sram.bin').read_bytes() if p.get('att_time') else ram
    decoded=connection_ram[msg-0x20000000:msg-0x20000000+36] if 0x20000000<=msg<0x20380000-36 else b''
    checks.update(original_stack=len(entry)==6 and len(exit)==3 and entry[2]==exit[0]+16 and struct.unpack_from('<I',ram,task+48-0x20000000)[0]<=exit[0]<struct.unpack_from('<I',ram,task+48-0x20000000)[0]+4*struct.unpack_from('<I',ram,task+84-0x20000000)[0],decoded_event=len(decoded)==36 and decoded[4]==0 and struct.unpack_from('<H',decoded,6)[0]==64 and decoded[8:16]==bytes.fromhex('0100112233445566'),startup_counts_preserved=(r['peer']['commands'],r['peer']['replies'])==(r['before']['commands'],r['before']['replies']),gpio_counter=struct.unpack_from('<I',ram,p['gpio']['counter']-0x20000000)[0]==r['before']['counter']+1)
    if p.get('att_time'):
        c=p['service'];a=r['att'];i=a.get('inputs',[]);cons=a.get('consumers',[]);applied=a.get('applied',[]);ret=a.get('returns',[]);rtc=a.get('rtc',{})
        app_task=c['tcb'];app_name=ram[app_task+52-0x20000000:app_task+84-0x20000000].split(b'\0',1)[0].decode()
        checks.update(stopped=a.get('stopped',False) and r['pc']==c['consumer_return'],irq=r['irq_entries']==7 and r['input']['irq'] and r['input']['pending'],event_consumed=r['peer']['runtime_consumed']==3 and not r['peer']['runtime_pending'],gpio_cleared=not r['gpio']['pending'] and not r['gpio']['irq'] and r['gpio']['edges']==7 and r['gpio']['clear_requests'][3]&(1<<21)!=0,gpio_counter=struct.unpack_from('<I',ram,p['gpio']['counter']-0x20000000)[0]==r['before']['counter']+7,
                      runtime_completions=a.get('rand_commands')==a.get('rand_replies')==a.get('host_acl')==a.get('rssi_commands')==a.get('rssi_replies')==a.get('remote_commands')==1 and a.get('remote_replies')==2,
                      original_tpl=len(i)==1 and i[0][0]==0 and i[0][2]==26 and 0x20000000<=i[0][1]<0x20380000 and i[0][5]==task and i[0][6]&511==0,
                      app_original_task=app_name=='ble_msgrx' and len(cons)==len(applied)==len(ret)==1 and all(x[5]==app_task and x[6]&511==0 for x in cons+applied+ret),
                      app_stack=len(cons)==len(ret)==1 and cons[0][3]==ret[0][3],app_state=ram[c['state']-0x20000000:c['state']-0x20000000+5]==struct.pack('<IB',1700000000,16),
                      app_queue_drained=struct.unpack_from('<I',ram,c['queue']+0x38-0x20000000)[0]==0,
                      rtc_commit=rtc.get('commits')==1 and rtc.get('pending') is False and rtc.get('error')=='none',rtc_date=str(rtc.get('date','')).startswith(datetime.fromtimestamp(1700000000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')))
        if 'sync_queue' in p:
            prior_sync=sync_queue(connection_ram,p['sync_queue']);after_sync=sync_queue(ram,p['sync_queue'])
            checks['declared_outbound_queue']=prior_sync['count']==0 and after_sync['count']==(0 if p.get('readonly_control') or p.get('att_corrupt_crc') else 2)
            if not p.get('readonly_control') and not p.get('att_corrupt_crc'):
                checks['declared_outbound_queue']=checks['declared_outbound_queue'] and [x['kind'] for x in after_sync['packets']]==[4,1] and after_sync['packets'][0]['data'].startswith('040c000100001000') and after_sync['packets'][1]['data'].startswith('01090301')
        if p.get('readonly_control') or p.get('att_corrupt_crc'):
            for key in ['runtime_completions','original_tpl','app_original_task','app_stack','app_state','app_queue_drained','rtc_commit','rtc_date']:checks.pop(key)
            verdict=a.get('reject',{}).get('verdict',[])
            checks.update(stopped=a.get('reject',{}).get('stopped',False) and r['pc']==p['write_return'],irq=r['irq_entries']==4 and r['input']['irq'] and r['input']['pending'],gpio_cleared=not r['gpio']['pending'] and not r['gpio']['irq'] and r['gpio']['edges']==4 and r['gpio']['clear_requests'][3]&(1<<21)!=0,gpio_counter=struct.unpack_from('<I',ram,p['gpio']['counter']-0x20000000)[0]==r['before']['counter']+4,
                          write_permission_denied=a.get('reject',{}).get('calls')==1 and len(verdict)==6 and verdict[:3]==[0x52,0x844,3] and verdict[4]==task and verdict[5]&511==0,
                          no_app_ingress=not i and not cons and not applied and not ret,
                          state_unchanged=ram[c['state']-0x20000000:c['state']-0x20000000+5]==connection_ram[c['state']-0x20000000:c['state']-0x20000000+5],
                          rtc_unchanged=rtc.get('commits')==0 and str(rtc.get('date','')).startswith('2000-01-01'),
                          mtu_workflow=a.get('rand_commands')==a.get('rand_replies')==a.get('host_acl')==1)
            if p.get('att_corrupt_crc'):
                checks.pop('write_permission_denied');checks.pop('no_app_ingress')
                checks['att_allowed_tpl_crc_dropped']=a.get('reject',{}).get('calls')==1 and len(verdict)==6 and verdict[:3]==[0x52,0x842,0] and verdict[4]==task and verdict[5]&511==0 and len(i)==1 and i[0][2]==26 and i[0][5]==task and not cons and not applied and not ret
    if 'virtual_budget_ms' in p:
        t=r.get('virtual_time',{});start=t.get('start_ticks');end=t.get('end_ticks');scale=t.get('ticks_per_ms')
        checks['virtual_time_budget']=isinstance(start,int) and isinstance(end,int) and isinstance(scale,int) and scale==1000000 and start==r['before'].get('virtual_ticks') and t.get('budget_ms')==p['virtual_budget_ms']==VIRTUAL_BUDGET_MS and 0<=end-start<=p['virtual_budget_ms']*scale
    if p.get('disconnect_reason') is not None:
        dc=json.loads((out/'exports/disconnect.json').read_text());dr=(out/'exports/disconnect-sram.bin').read_bytes()
        lines=[json.loads(x.split('BLACKWALL_RUNTIME_DISCONNECT ',1)[1]) for x in (out/'renode.log').read_text().splitlines() if x.startswith('BLACKWALL_RUNTIME_DISCONNECT ')];assert lines==[dc]
        dactive=[x for x in slots if dr[x+22-0x20000000]!=0];de=dc['entry'];dx=dc['exit'];dt=dc['virtual_time']
        ptr=de[1] if len(de)==6 else 0
        message=dr[ptr-0x20000000:ptr-0x20000000+9] if 0x20000000<=ptr<=0x20380000-9 else b''
        checks.update(disconnect_endpoint=dc['stopped'] and dc['pc']==p['closed_return'] and dc['calls']==1,
                      disconnect_device_irq=dc['input']['accepted'] and dc['input']['irq'] and dc['input']['pending'] and dc['input']['pc']==c['consumer_return'] and dc['irq_entries']==1,
                      disconnect_consumed=dc['runtime_consumed']==4 and not dc['runtime_pending'],
                      disconnect_gpio_cleared=not dc['gpio']['irq'] and not dc['gpio']['pending'] and dc['gpio']['edges']==8,
                      disconnect_ccb_deallocated=not dactive and all(dr[x+21-0x20000000]==0 for x in slots),
                      disconnect_original_task=len(de)==6 and len(dx)==3 and de[4]==dx[1]==task and de[5]&511==dx[2]&511==0,
                      disconnect_original_stack=len(de)==6 and len(dx)==3 and de[2]==dx[0]+16,
                      disconnect_app_event=len(message)==9 and struct.unpack_from('<H',message)[0]==1 and message[2]==0x28 and message[3]==0 and struct.unpack_from('<H',message,6)[0]==64 and message[8]==p['disconnect_reason'],
                      disconnect_no_fault=dc['cfsr']==dc['hfsr']==dc['memory_violations']==0 and all(x['accesses']==0 for x in dc['guards']),
                      disconnect_virtual_budget=dt['start_ticks']==r['virtual_time']['end_ticks'] and dt['ticks_per_ms']==1000000 and dt['budget_ms']==p['virtual_budget_ms'] and 0<=dt['end_ticks']-dt['start_ticks']<=dt['budget_ms']*1000000,
                      disconnect_rtc_preserved=dc['rtc']['commits']==1 and not dc['rtc']['pending'] and dc['rtc']['error']=='none' and str(dc['rtc']['date']).startswith('2023-11-14T22:13:20'))
        if p.get('disconnect_delay_ms',0):
            delay=dc.get('delay',{})
            checks['disconnect_device_irq']=dc['input']['accepted'] and dc['input']['irq'] and dc['input']['pending'] and dc['input'].get('origin_pc')==c['consumer_return'] and 0x438000<=dc['input']['pc']<0x800000 and dc['irq_entries']==1
            checks['delayed_device_input']=delay.get('fired') is True and delay.get('accepted') is True and delay.get('milliseconds')==p['disconnect_delay_ms'] and delay.get('start_ticks')==dt['start_ticks'] and abs(delay.get('fired_ticks',0)-delay.get('start_ticks',0)-p['disconnect_delay_ms']*1000000)<=1000
    if p.get('gaf_profile'):
        fixture=json.loads((out/'gaf-profile.json').read_text())
        compiled=(out/'strict.cs').read_text();begin,end=imu_span(compiled);actual_imu_sha=hashlib.sha256(compiled[begin:end].encode()).hexdigest()
        initial_gaf=r.get('imu_gaf',{})
        identity_ok=fixture['candidate_sha256']=='3ddefc4c7d372cd5c8bd42da9819bc290e1f52ca898ea865bf3e7e86f5c8c883' and fixture.get('calculation_supported',False) is False
        if fixture.get('on_demand_control'):
            identity_ok=fixture['candidate_sha256']=='c2af9898826af7a903aaa7769ee073208ebc5515f3a6278d96f39c98b456d84e' and fixture.get('parent_component_sha256')=='3ddefc4c7d372cd5c8bd42da9819bc290e1f52ca898ea865bf3e7e86f5c8c883' and fixture.get('control_fragment_sha256')=='4c7afaae0dc6eca1a9d449a354853bc8c02480cda78f9c4bc285062b95cc7306' and fixture.get('calculation_supported') is False
            window=fixture.get('on_demand_observation_microseconds',0)
            identity_ok=identity_ok and 1<=window<=1000000 and (out/'board.repl').read_text().count('    gafOnDemandMicroseconds: '+str(window)+'\n')==1
            d=initial_gaf.get('on_demand',{})
            checks['gaf_calculation_capability_honest']=d.get('calculation_supported') is False and d.get('completed_calculations')==0 and d.get('requests')==0 and d.get('phase')=='unselected'
        checks['pinned_gaf_profile']=sha(out/'gaf-profile.json')==p['gaf_profile_sha256'] and fixture==p['gaf_profile'] and identity_ok and fixture['clock_variation_byte']==133 and (out/'board.repl').read_text().count('    gafConfiguration: true\n')==1 and actual_imu_sha==fixture['candidate_sha256'] and initial_gaf.get('fixture')==fixture['parameters_hex'] and initial_gaf.get('service_completions')==2 and initial_gaf.get('fields')==initial_gaf.get('read_bytes')==initial_gaf.get('written_bytes')==0
    spec=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['checks','main_unchanged'],['checks','model_unchanged']]),checks=[dict(path=['checks',k],eq=True) for k in checks],allowed_differences=['Explicit controller connection event and optional GPIO117 IRQ lifecycle after retained main hold; no API caller/register/TCB seeding.'],unresolved_differences=['Full natural initialization, next controller commands, ATT/application data, physical GPIO/IRQ timing and observer neutrality remain unverified.'])
    if p.get('att_time'):
        spec['allowed_differences']=['Declared virtual phone/controller connection, Rand/RSSI/remote-feature fixtures and MTU exchange; original H4 ACL/ATT/EUS/TPL and actual task/RTC consumption; existing RTC write profile enabled.']
        spec['unresolved_differences']=['Natural main initialization, physical BLE/entropy/RSSI, general controller credit/reconnection behavior, outbound application notification and observer neutrality unverified.']
        if p.get('att_corrupt_crc'):
            spec['allowed_differences']=['Declared virtual connection/MTU with single corrupted TPL CRC; original ATT allowed target then TPL drops packet without app dispatch/RTC mutation.']
    validate_semantics(spec)
    result=dict(schema=2,passed=all(checks.values()),case=p['case'],checks=checks,task_name=task_name,observed=r,api_caller=False,natural_main_complete=False,physical_hardware_access=False,boundary_kind='bounded-capture',execution_passed=True,selected_observation=dict(events=[dict(pc=r['pc'])] if r['stopped'] else [],sequence=int(r['stopped']),dropped_events=0))
    if p.get('sync_queue'):
        result['outbound_sync']=dict(before=prior_sync,after=after_sync,delivered_to_opposite_temple=False)
    if p.get('disconnect_reason') is not None:
        result['disconnect_observed']=dc
        result['disconnect_app_message']=message.hex()
    result=finish_capture(result,dict(checks=dict(main_unchanged=True,model_unchanged=True)),spec);result['contract']=spec
    target=out if destination is None else destination
    if destination is not None:destination.mkdir(mode=0o700,parents=True)
    (target/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result



def comparison_preflight(parser, args):
    if args.compare_baseline is None:
        return
    if not args.comparison_output.resolve().is_relative_to(args.simulator.resolve()):
        parser.error('Comparison output must remain inside the private simulator')
    from compare_runtime_firmware import preflight
    try:
        preflight(args.compare_baseline,args.output,args.comparison_output,args.comparison_expectation)
    except (OSError,ValueError) as error:
        parser.error(str(error))


def finish_runtime_cli(args, result, summary):
    if args.compare_baseline is not None:
        from compare_runtime_firmware import compare
        comparison=compare(args.compare_baseline,args.output,args.comparison_output,args.comparison_expectation)
        summary.update(candidate_passed=result['passed'],comparison_passed=comparison['passed'],comparison_output=str(args.comparison_output))
        summary['passed']=result['passed'] and comparison['passed']
    print(json.dumps(summary))
    if not summary['passed']:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True);p.add_argument('--control',action='store_true');p.add_argument('--gaf-profile',action='store_true');p.add_argument('--gaf-on-demand-control',action='store_true');p.add_argument('--gaf-control-window-us',type=int);p.add_argument('--att-time',action='store_true');p.add_argument('--att-readonly-control',action='store_true');p.add_argument('--att-corrupt-crc',action='store_true');p.add_argument('--disconnect-reason',type=lambda v:int(v,0),choices=[8,19]);p.add_argument('--disconnect-delay-ms',type=int,default=0);p.add_argument('--audit-existing',action='store_true');p.add_argument('--audit-output',type=Path);p.add_argument('--firmware-manifest',type=Path);p.add_argument('--firmware-baseline',type=Path);p.add_argument('--compare-baseline',type=Path);p.add_argument('--comparison-output',type=Path);p.add_argument('--comparison-expectation',type=Path);a=p.parse_args()
    if (a.compare_baseline is None)!=(a.comparison_output is None):p.error('Comparison requires --compare-baseline and --comparison-output together')
    if a.comparison_expectation is not None and a.compare_baseline is None:p.error('Comparison expectation requires --compare-baseline')
    if a.compare_baseline is not None and (a.control or not (a.firmware_manifest is not None or a.audit_existing)):p.error('Comparison requires a registered candidate or its saved audit')
    if a.audit_existing and (a.firmware_manifest is not None or a.firmware_baseline is not None):p.error('Saved audit uses the captured registration snapshot; omit candidate selection')
    if (a.firmware_manifest is None)!=(a.firmware_baseline is None):p.error('Candidate selection requires --firmware-manifest and --firmware-baseline')
    from simulator_cli_readiness import python_packages,native_tools
    python_packages()
    if not a.audit_existing:native_tools()
    if a.audit_existing:
        assert a.audit_output is not None and not a.audit_output.exists() and a.audit_output.resolve().is_relative_to(a.simulator.resolve())
        saved=json.loads((a.output/'connection-profile.json').read_text());assert saved['case']==a.case and saved.get('control',False)==a.control
        if a.gaf_profile:assert saved.get('gaf_profile'), 'Capture does not declare GAF integration'
        if a.gaf_on_demand_control:assert saved.get('gaf_profile',{}).get('on_demand_control'), 'Capture does not declare on-demand control'
        if a.gaf_control_window_us is not None:assert saved.get('gaf_profile',{}).get('on_demand_observation_microseconds')==a.gaf_control_window_us, 'Capture observation window differs'
        comparison_preflight(p,a)
        r=inspect(a.output,a.audit_output)
        finish_runtime_cli(a,r,dict(passed=r['passed'],native_rerun=False))
        return
    if a.att_readonly_control and not a.att_time:p.error('Read-only attribute control needs --att-time')
    if a.disconnect_reason is not None and (not a.att_time or a.att_readonly_control or a.control):p.error('Disconnect requires normal ATT time workflow')
    if a.att_corrupt_crc and (not a.att_time or a.att_readonly_control or a.control or a.disconnect_reason is not None):p.error('Corrupt CRC needs normal ATT time workflow only')
    if not 0<=a.disconnect_delay_ms<=1000 or (a.disconnect_delay_ms and a.disconnect_reason is None):p.error('Delay requires disconnect scenario and 1..1000 virtual ms')
    if a.gaf_on_demand_control and not a.gaf_profile:p.error('On-demand control requires the pinned GAF profile')
    if a.gaf_control_window_us is None:a.gaf_control_window_us=1000
    if not 1<=a.gaf_control_window_us<=1000000 or (not a.gaf_on_demand_control and a.gaf_control_window_us!=1000):p.error('Observation window requires explicit on-demand control and 1..1000000us')
    build(a.simulator,a.output,a.case,a.control,a.att_time,a.att_readonly_control,a.disconnect_reason,a.att_corrupt_crc,a.disconnect_delay_ms,a.gaf_profile,a.gaf_on_demand_control,a.gaf_control_window_us,a.firmware_manifest,a.firmware_baseline)
    comparison_preflight(p,a)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    result=inspect(a.output)
    finish_runtime_cli(a,result,dict(passed=result['passed'],checks=result['checks'],task=result.get('task_name')))


if __name__=='__main__':
    from simulator_cli_readiness import run_cli
    run_cli(main)
