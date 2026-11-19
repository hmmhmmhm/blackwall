"""Original sync APIs on the existing M55 board; explicit API diagnostic, no hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import textwrap
from run_renode_m55_probe import execute
from native_replay import IMAGE
from run_display_activation_m55 import prepare_context
from sync_peer_roundtrip import frame
from inspect_nema_blocking_wait import SRAM
from run_native_candidate import validate_assets, validate_semantics, finish_capture

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = dict(stock24='display-activation-cli-01', stock23='display-activation-cli-stock23-01', cfw='display-activation-cli-cfw-01')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(s, output, case, scenario='send', jbd_status_hex=''):
    if jbd_status_hex and (scenario not in ('uart-rx-crc-then-valid','uart-rx-crc-pair') or len(jbd_status_hex)!=4 or any(c not in '0123456789abcdef' for c in jbd_status_hex)):
        raise ValueError('Explicit two-byte JBD status requires RX stream scenario')
    if output.exists() or not output.resolve().is_relative_to(s.resolve()) or s.resolve().is_relative_to(ROOT):
        raise ValueError('Fresh private simulator output required')
    template = s/TEMPLATES[case]
    prior = json.loads((template/'verification/report.json').read_text())
    assert prior['passed'] and prior['case'] == case
    base = s/'imu-powersave-main-01'/case
    meta=json.loads((base/'derived-inputs.json').read_text());validate_assets(base,meta['derived'])
    for name in ('sram-fill.bin','itcm-fill.bin'):
        assert (template/name).read_bytes()==(base/name).read_bytes()
    assert (template/'strict.cs').read_bytes() == (base/'strict.cs').read_bytes()
    assert (template/'main.bin').read_bytes() == (base/'main.bin').read_bytes()
    proof = s/'sync-request-parser-source-04/report.json'
    pin = json.loads((s/'sync-request-parser-research-01/manifest.json').read_text())
    assert pin['passed'] and sha(proof) == pin['files'][str(proof.relative_to(s))]
    row = next(x for x in json.loads(proof.read_text())['cases'] if x['case'] == case)
    assert sha(template/'main.bin') == row['raw_sha256']
    c = row['sync_roundtrip']['contract']
    old_proof = s/'ui-peer-reply-contract-04/report.json'
    old_pin = json.loads((s/'ui-peer-reply-research-01/manifest.json').read_text())
    assert sha(old_proof) == old_pin['files'][str(old_proof.relative_to(s))]
    sync = next(x['sync_ingress']['contract'] for x in json.loads(old_proof.read_text())['cases'] if x['case'] == case)
    ctx = prepare_context(s, case, 2)
    output.mkdir(mode=0o700, parents=True)
    (output/'exports').mkdir(mode=0o700)
    for name in ('strict.cs', 'main.bin', 'sram-fill.bin', 'itcm-fill.bin', 'board.repl', 'probe.resc', 'result.py', 'activation.cs'):
        shutil.copyfile(template/name, output/name)
    current_uart = scenario in ('send-current-uart', 'uart-rx-crc-then-valid', 'uart-rx-crc-pair')
    rx_device = scenario in ('uart-rx-crc-then-valid', 'uart-rx-crc-pair')
    component = None
    if current_uart:
        start = '    public sealed class BlackwallUartAdapter : IPeripheral\n'
        end = '\n    public sealed class BlackwallAdcPower\n'
        old = (output/'strict.cs').read_text()
        new = (ROOT/'tools/renode-strict-mmio.cs').read_text()
        assert old.count(start)==new.count(start)==1 and old.count(end)==new.count(end)==1
        before = start+old.split(start)[1].split(end)[0]
        after = start+new.split(start)[1].split(end)[0]
        (output/'uart-before.txt').write_text(before);(output/'uart-after.txt').write_text(after)
        (output/'strict.cs').write_text(old.replace(before,after))
        component = dict(before_sha256=sha(output/'uart-before.txt'),after_sha256=sha(output/'uart-after.txt'),base_sha256=sha(template/'strict.cs'),derived_sha256=sha(output/'strict.cs'))
    if rx_device:
        board=(output/'board.repl').read_text();anchor='uart0_adapter: Miscellaneous.BlackwallUartAdapter\n    module: 0\n'
        assert board.count(anchor)==1
        (output/'board.repl').write_text(board.replace(anchor,anchor+'    receiveFifo: true\n'))
        observer=(output/'activation.cs').read_text()
        anchor='    public void Watch(uint pc)'
        assert observer.count(anchor)==1
        method='    public List<uint[]> Receives {get;}=new List<uint[]>();\n    public void WatchReceive(uint pc,IMachine machine,uint slot) { cpu.AddHook(pc,(c,a)=>{if(Receives.Count<8)Receives.Add(new uint[]{(uint)cpu.GetRegister(0).RawValue,(uint)cpu.GetRegister(1).RawValue,(uint)cpu.GetRegister(13).RawValue,(uint)cpu.GetRegister(14).RawValue,machine.SystemBus.ReadDoubleWord(slot),(uint)cpu.GetRegister(25).RawValue});}); }\n'
        if jbd_status_hex:
            method += '    public List<uint[]> UiMessages {get;}=new List<uint[]>();\n    public void WatchUi(uint pc,IMachine machine,uint slot) { cpu.AddHook(pc,(c,a)=>{if(UiMessages.Count<8)UiMessages.Add(new uint[]{(uint)cpu.GetRegister(0).RawValue,(uint)cpu.GetRegister(1).RawValue,(uint)cpu.GetRegister(2).RawValue,(uint)cpu.GetRegister(13).RawValue,machine.SystemBus.ReadDoubleWord(slot),(uint)cpu.GetRegister(25).RawValue});}); }\n'
        (output/'activation.cs').write_text(observer.replace(anchor,method+anchor))
    mspi_component=None
    if jbd_status_hex:
        proof=s/'jbd-status-integration-verification-01/manifest.json'
        previous=json.loads(proof.read_text());candidate=ROOT/'tools/renode-mspi1-config.cs'
        source=s/'jbd-status-consumer-source-02/report.json'
        assert previous['passed'] and sha(candidate)==previous['model_sha256'] and sha(source)==previous['source_report_sha256']
        old=(s/'display-status-research-01/base-config.cs').read_text();model=(output/'strict.cs').read_text()
        assert model.count(old)==1
        (output/'mspi-before.txt').write_text(old);(output/'mspi-after.txt').write_bytes(candidate.read_bytes())
        (output/'strict.cs').write_text(model.replace(old,candidate.read_text()))
        board=(output/'board.repl').read_text();anchor='mspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n'
        assert board.count(anchor)==1
        (output/'board.repl').write_text(board.replace(anchor,anchor+'    jbdStatusHex: "'+jbd_status_hex+'"\n'))
        shutil.copyfile(source,output/'mspi-source.json')
        mspi_component=dict(before_sha256=sha(output/'mspi-before.txt'),after_sha256=sha(output/'mspi-after.txt'),derived_sha256=sha(output/'strict.cs'),source_sha256=sha(output/'mspi-source.json'),prior_manifest_sha256=sha(proof))
    service_profile=None
    if scenario=='tpl-service-time':
        from tpl_service_native import prepare
        service_profile=prepare(s,output,case)
    root_profile=None
    if scenario=='tpl-request-send':
        from sync_root_native import prepare
        root_profile=prepare(s,output,case,(output/'main.bin').read_bytes(),c)
    code = ['.syntax unified' , '.cpu cortex-m55', '.thumb', '.section .text', '.global entry', '.thumb_func', 'entry:']
    def load(reg, value): code.append('ldr '+reg+', =0x%x'%value)
    def call(address): load('r12', address | 1);code.append('blx r12')
    def record(offset, reg='r0'): load('r12', 0x21000080);code.append('str '+reg+', [r12, #%d]'%offset)
    load('r12', 0x21000048)
    for k, reg in enumerate(('psp','msp','control','psplim','msplim','primask','basepri','ipsr')):
        code += ['mrs r1, '+reg, 'str r1, [r12, #%d]'%(4*k)]
    if service_profile:
        from tpl_service_native import harness
        harness(code,load,call,record,service_profile,ctx)
    elif root_profile:
        from sync_root_native import harness
        harness(code,load,call,record,c,ctx,root_profile)
    else:
        load('r0', 12);call(c['allocator']);code.append('mov r5, r0');record(0)
        load('r0', 8);call(c['allocator']);code.append('mov r6, r0');record(4)
        code += ['movs r0, #0', 'str r0, [r5]', 'str r0, [r5, #4]', 'str r6, [r5, #8]', 'str r0, [r6, #4]']
        load('r0', 0x010b0100);code.append('str r0, [r6]')
        load('r7', 0x21000300)
        code += ['movs r0, #0', 'str r0, [r7]', 'str r0, [r7, #8]', 'str r0, [r7, #20]', 'movs r0, #2', 'str r0, [r7, #4]', 'movs r0, #8', 'str r0, [r7, #12]', 'str r5, [r7, #16]']
        load('r4', sync['context_slot']);code.append('ldr r4, [r4]')
        code += ['mov r0, r4', 'mov r1, r7', 'sub sp, #8', 'movs r2, #50', 'str r2, [sp]']
        load('r2', sync['master_reply'] | 1);load('r3', c['timeout_callback'] | 1);call(c['start']);code.append('add sp, #8');record(8)
        code += ['mov r0, r4', 'mov r1, r6', 'movs r2, #8'];call(c['chunk']);record(12)
        code.append('mov r0, r4');call(c['finish']);record(16)
        load('r0', 0xc0ff3300);record(20)
        if scenario=='bad-header-crc' or rx_device:
            code += ['.global sent', 'sent:', 'nop']
            if rx_device:
                load('r0',1);load('r1',4);load('r2',0);call(ctx['queue_new']);code.append('mov r4, r0')
                load('r1',0x21000200);load('r2',0);load('r3',0xffffffff);call(ctx['ui']['get'])
            else:
                load('r0',0x21002000);load('r1',12);call(c['receive']);record(24)
                load('r0',0xc0ff3301);record(28)
    code += ['.global done', 'done:', 'wfi', 'b done', '.balign 4', '.ltorg']
    (output/'harness.s').write_text('\n'.join(code)+'\n')
    llvm = Path('/opt/homebrew/opt/llvm@21/bin')
    execute([str(llvm/'clang'),'--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-mfloat-abi=hard','-nostdlib','-fuse-ld=/opt/homebrew/opt/lld@21/bin/ld.lld','-Wl,-Ttext=0x3fe00','-Wl,-e,entry',str(output/'harness.s'),'-o',str(output/'harness.elf')],output,'compiler')
    execute([str(llvm/'llvm-objcopy'),'-O','binary',str(output/'harness.elf'),str(output/'harness.bin')],output,'objcopy')
    symbols = execute([str(llvm/'llvm-nm'),'--defined-only',str(output/'harness.elf')],output,'symbols')
    done = [int(line.split()[0],16) for line in symbols.splitlines() if line.split()[-1:] == ['done']]
    assert len(done) == 1 and 0 < (output/'harness.bin').stat().st_size <= 512
    sent=[int(line.split()[0],16) for line in symbols.splitlines() if line.split()[-1:]==['sent']]
    if scenario=='bad-header-crc':
        from inspect_ambiq_target import decode
        branch=decode((output/'main.bin').read_bytes(),c['byte_parser']+0x15e,2)[0]
        assert branch.mnemonic=='beq' and len(sent)==1
    profile = dict(schema=2, scenario=scenario, send_stop=sent[0] if sent else done[0], error_branch=c['byte_parser']+0x160, case=case, contract=c, sync=sync, ui=ctx['ui'], copy=ctx['copy'], getter=ctx['getter'], tcb_slot=ctx['tcb_slot'], stop=done[0], template=TEMPLATES[case], source_audit_sha256=sha(template/'verification/report.json'), main_sha256=sha(template/'main.bin'), model_sha256=sha(template/'strict.cs'), synthetic_api_stimulus=True, natural_main_complete=False)
    if service_profile:profile['service']=service_profile
    if mspi_component:
        profile['mspi_component']=mspi_component
        profile['jbd_status_hex']=jbd_status_hex
    if current_uart:
        profile['uart_component']=component
        profile['model_sha256']=sha(output/'strict.cs')
    if rx_device:
        from inspect_ambiq_target import decode
        returns=[i.address for i in decode((output/'main.bin').read_bytes(),c['receive'],0x80) if i.mnemonic.startswith('pop') and 'pc' in i.op_str]
        assert len(returns)==1
        profile['stop']=returns[0]
        first=decode((output/'main.bin').read_bytes(),c['receive'],2)[0]
        assert first.mnemonic=='push'
        profile['receive_stack_bytes']=4*len(first.operands)
    if root_profile:
        input_done=[int(line.split()[0],16) for line in symbols.splitlines() if line.split()[-1:]==['input_done']]
        assert len(input_done)==1
        root_profile['input_stop']=input_done[0]
        profile['root']=root_profile
        profile['harness_stop']=root_profile['input_stop']
        profile['stop']=root_profile['finish_return']
    (output/'sync-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    runtime = (template/'run.py').read_text()
    anchor = '\ntry:\n    import clr,time,json\n'
    assert runtime.count(anchor) == 1
    runtime = runtime.split(anchor)[0]
    post = '''
    try:
        import clr,time,json
        from System.IO import File
        from System import Console
        from Antmicro.Renode.Utilities import TypeManager
        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallUiActivationDiagnostic').Assembly)
        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallUiActivationDiagnostic
        m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu']
        p=json.loads(File.ReadAllText('/work/sync-profile.json'))
        if not m.IsPaused or int(cpu.PC.RawValue)!=p['getter']:raise ValueError('Expected original normal main hold')
        prior_time=str(m.ElapsedVirtualTime.TimeElapsed);time.sleep(0.2)
        if str(m.ElapsedVirtualTime.TimeElapsed)!=prior_time:raise ValueError('Machine advanced while paused')
        if any(int(v)!=0xa5 for v in b.ReadBytes(0x3fe00,512,True)):raise ValueError('Occupied ITCM')
        uart=m['sysbus.guard'].Uarts[0];dma=uart.DmaTx
        before=dict(transfers=int(dma.Transfers.Count),completions=int(dma.Completions),irq_entries=int(uart.IrqExceptionEntries),current_tcb=int(b.ReadDoubleWord(p['tcb_slot'])),sp=int(cpu.GetRegister(13).RawValue))
        data=File.ReadAllBytes('/work/harness.bin')
        for n in range(data.Length):b.WriteByte(0x2100e000+n,data[n])
        service_diag=None;service_before={}
        if p.get('service'):
            from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallTplServiceObserver
            c=p['service'];service_diag=BlackwallTplServiceObserver(m,cpu,c['ingress'],c['consumer'],c['clock_return'],c['consumer_return'],p['tcb_slot'])
            for index,value in enumerate(bytearray.fromhex(c['serialized'])):b.WriteByte(0x21002000+index,value)
            rtc=m['sysbus.guard'].Rtc
            service_before=dict(commits=int(rtc.Commits),date=str(rtc.VirtualDate))
        root_diag=None
        if p.get('root'):
            from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallSyncRootObserver
            root_diag=BlackwallSyncRootObserver(m,cpu,p['root']['ingress'],p['root']['both'],p['contract']['start'],p['root']['finish_return'],p['tcb_slot'])
            for index,value in enumerate(bytearray.fromhex(p['root']['serialized'])):b.WriteByte(0x21002000+index,value)
        diag=BlackwallUiActivationDiagnostic(m,cpu,p.get('harness_stop',p.get('send_stop',p['stop'])))
        diag.Seed(0,0x3fe00);diag.Seed(1,0x2100e000);diag.Seed(2,data.Length);diag.Seed(14,0x3fe01);diag.Seed(15,p['copy']|1)
        cpu.IsHalted=False
        EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
        while not diag.Stopped and not (service_diag is not None and service_diag.Stopped) and not (root_diag is not None and root_diag.Stopped) and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
        m.Pause()
        root_points=[]
        if root_diag is not None:
            for phase in range(2):
                pc=int(cpu.PC.RawValue)
                kind='request-finished' if root_diag.Stopped and pc==p['root']['finish_return'] else 'input-returned' if diag.Stopped and pc==p['root']['input_stop'] else 'unexpected'
                root_points.append(dict(kind=kind,pc=pc,sp=int(cpu.GetRegister(13).RawValue),tcb=int(b.ReadDoubleWord(p['tcb_slot']))))
                if kind=='unexpected' or (root_diag.Stopped and diag.Stopped):break
                EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
                while not (root_diag.Stopped and diag.Stopped) and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
                m.Pause()
        error_events=[];reply=[];rx={}
        send_stopped=bool(diag.Stopped)
        if p.get('scenario')=='bad-header-crc' and send_stopped:
            File.WriteAllBytes('/work-output/sync-send-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            identifier=int(b.ReadWord(0x21000300))
            def crc(values):
                v=0
                for x in values:
                    v^=x
                    for unused in range(8):v=(v>>1)^(0xa001 if v&1 else 0)
                return v
            header=[1,(identifier>>8)&255,identifier&255,0,1,0,2];h=crc(header);tail=crc([2])
            reply=header+[h>>8,(h&255)^1,2,tail>>8,tail&255]
            for index,value in enumerate(reply):b.WriteByte(0x21002000+index,value)
            next_diag=BlackwallUiActivationDiagnostic(m,cpu,p['stop']);next_diag.Watch(p['error_branch'])
            EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
            while not next_diag.Stopped and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
            m.Pause();diag=next_diag;error_events=[int(value) for value in diag.Events]
        if p.get('scenario') in ('uart-rx-crc-then-valid','uart-rx-crc-pair') and send_stopped:
            from System import Array,Byte
            File.WriteAllBytes('/work-output/sync-send-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
            identifier=int(b.ReadWord(0x21000300))
            def crc(values):
                v=0
                for x in values:
                    v^=x
                    for unused in range(8):v=(v>>1)^(0xa001 if v&1 else 0)
                return v
            header=[1,(identifier>>8)&255,identifier&255,0,1,0,2];h=crc(header);tail=crc([2])
            valid=header+[h>>8,h&255,2,tail>>8,tail&255]
            invalid=list(valid);invalid[8]^=1;reply=invalid+(invalid if p['scenario']=='uart-rx-crc-pair' else valid)
            rx=dict(control=int(uart.Control),level=int(uart.ReceiveLevelSelection),mask=int(uart.InterruptMask),before_entries=int(uart.IrqExceptionEntries),send_tcb=int(b.ReadDoubleWord(p['tcb_slot'])),send_sp=int(cpu.GetRegister(13).RawValue))
            next_diag=BlackwallUiActivationDiagnostic(m,cpu,p['stop']);next_diag.Watch(p['error_branch']);next_diag.WatchReceive(p['contract']['receive'],m,p['tcb_slot'])
            if p.get('jbd_status_hex'):next_diag.WatchUi(p['ui']['ui_producer'],m,p['tcb_slot'])
            rx['accepted']=bool(uart.TryReceive(Array[Byte](reply),m['sysbus.guard'].UartPowers[0].Phase=='on'))
            rx['pending_at_injection']=int(uart.RxPending);rx['irq_at_injection']=bool(uart.IRQ.IsSet)
            EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+45
            while not next_diag.Stopped and not m.IsPaused and time.time()<deadline:time.sleep(0.01)
            m.Pause();diag=next_diag;error_events=[int(value) for value in diag.Events]
            rx.update(pending=int(uart.RxPending),injected=int(uart.RxBytesInjected),read=int(uart.RxBytesRead),read_hash=int(uart.RxReadHash),receives=[[int(v) for v in row] for row in diag.Receives])
        transfers=[dict(target=int(t.Target),data=''.join('%02x'%int(v) for v in t.Data)) for t in dma.Transfers]
        guards=[]
        for name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
            g=m['sysbus.'+name];guards.append(dict(name=name,accesses=int(g.AccessCount),address=int(g.LastAddress),operation=str(g.LastOperation)))
        if p.get('jbd_status_hex'):rx['ui_calls']=[[int(v) for v in row] for row in diag.UiMessages]
        mspi={}
        if p.get('jbd_status_hex'):
            pio=m['sysbus.guard'].Mspi0Config.Pio
            mspi=dict(profile=p['jbd_status_hex'],rx_starts=int(pio.RxStarts),rx_completions=int(pio.RxCompletions),rx_reads=int(pio.RxReads),rx_bytes=int(pio.RxBytesDelivered),rx_frames=[dict(control=int(t.Control),instruction=int(t.Instruction),data=str(t.PayloadHex)) for t in pio.ReceiveFrames])
        service={}
        if service_diag is not None:
            rtc=m['sysbus.guard'].Rtc
            service=dict(stopped=bool(service_diag.Stopped),inputs=[[int(v) for v in row] for row in service_diag.Inputs],consumers=[[int(v) for v in row] for row in service_diag.Consumers],applied=[[int(v) for v in row] for row in service_diag.Applied],returns=[[int(v) for v in row] for row in service_diag.Returns],rtc_before=service_before,rtc=dict(commits=int(rtc.Commits),reads=int(rtc.Reads),writes=int(rtc.Writes),pending=bool(rtc.WritePending),date=str(rtc.VirtualDate),error=str(rtc.LastError)))
        root={}
        if root_diag is not None:
            root=dict(stopped=bool(root_diag.Stopped),matches=int(root_diag.Matches),requests_seen=int(root_diag.RequestsSeen),context=[int(v) for v in root_diag.Context],inputs=[[int(v) for v in row] for row in root_diag.Inputs],producers=[[int(v) for v in row] for row in root_diag.Producers],descriptor=[int(v) for v in root_diag.DescriptorBytes],packet=[int(v) for v in root_diag.PacketBytes],finish_context=[int(v) for v in root_diag.FinishContext],points=root_points)
        result=dict(stopped=bool(diag.Stopped),pc=int(cpu.PC.RawValue),before=before,mailbox=[int(b.ReadDoubleWord(0x21000080+4*k)) for k in range(8)],send_stopped=send_stopped,rx=rx,mspi=mspi,service=service,root=root,error_events=error_events,reply=reply,bootstrap=[int(b.ReadDoubleWord(0x21000048+4*k)) for k in range(8)],descriptor=[int(v) for v in b.ReadBytes(0x21000300,24,True)],dma=dict(transfers=transfers,completions=int(dma.Completions),phase=str(dma.Phase),raw_interrupts=int(dma.RawInterrupts)),uart_irq_entries=int(uart.IrqExceptionEntries),uart_irq_vector=int(uart.LastActiveVector),guards=guards,cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory_violations=int(memory_policy.Violations),current_tcb=int(b.ReadDoubleWord(p['tcb_slot'])),sp=int(cpu.GetRegister(13).RawValue),xpsr=int(cpu.GetRegister(25).RawValue),ui_messages=int(b.ReadDoubleWord(p['ui']['queue']+0x38)))
        File.WriteAllBytes('/work-output/sync-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
        File.WriteAllText('/work-output/sync.json',json.dumps(result));Console.WriteLine('BLACKWALL_SYNC_NATIVE '+json.dumps(result))
    except Exception as error:
        Console.WriteLine('BLACKWALL_SYNC_NATIVE_ERROR '+str(error))
    '''
    (output/'run.py').write_text(runtime+textwrap.dedent(post))
    (output/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    names=('strict.cs','main.bin','sram-fill.bin','itcm-fill.bin','board.repl','probe.resc','result.py','activation.cs','run.py','sync-profile.json','harness.s','harness.elf','harness.bin','runner-source.py')
    if service_profile:names+=('service-observer.cs','service-source.json','service-root-source.json')
    if root_profile:names+=('root-observer.cs','tpl-source.json')
    if current_uart:names+=('uart-before.txt','uart-after.txt')
    if mspi_component:names+=('mspi-before.txt','mspi-after.txt','mspi-source.json')
    (output/'sync-inputs.json').write_text(json.dumps({name:sha(output/name) for name in names},indent=2)+'\n')
    return profile



def pin_capture(output, origin='runner-after-execution'):
    target=output/'capture-files.json'
    if target.exists():raise ValueError('Capture pins already exist')
    inputs=json.loads((output/'sync-inputs.json').read_text())
    for name,pin in inputs.items():assert sha(output/name)==pin,name
    raw=json.loads((output/'exports/sync.json').read_text())
    rows=[json.loads(line.split('BLACKWALL_SYNC_NATIVE ',1)[1]) for line in (output/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_SYNC_NATIVE ')]
    assert rows==[raw]
    if origin=='import-after-original-verification':
        previous=json.loads((output/'verification.json').read_text());assert previous['passed'] and previous['observed']==raw
    names=set(inputs)|{'sync-inputs.json','renode.log'}
    names.update(str(p.relative_to(output)) for p in (output/'exports').rglob('*') if p.is_file())
    target.write_text(json.dumps(dict(schema=1,origin=origin,files={name:sha(output/name) for name in sorted(names)}),indent=2)+'\n')

def inspect(s, output, destination=None):
    if destination is not None and (destination.exists() or not destination.resolve().is_relative_to(s.resolve())):
        raise ValueError('Fresh private audit output required')
    captured=json.loads((output/'capture-files.json').read_text())
    for name,pin in captured['files'].items():
        path=output/name
        assert path.resolve().is_relative_to(output.resolve()) and sha(path)==pin,name
    pins=json.loads((output/'sync-inputs.json').read_text())
    for name,pin in pins.items():assert sha(output/name)==pin,name
    p=json.loads((output/'sync-profile.json').read_text());r=json.loads((output/'exports/sync.json').read_text());ram=(output/'exports/sync-after-sram.bin').read_bytes()
    logs=[json.loads(line.split('BLACKWALL_SYNC_NATIVE ',1)[1]) for line in (output/'renode.log').read_text().splitlines() if line.startswith('BLACKWALL_SYNC_NATIVE ')]
    assert logs==[r]
    base=s/'imu-powersave-main-01'/p['case'];meta=json.loads((base/'derived-inputs.json').read_text());validate_assets(base,meta['derived'])
    initial_same=all((output/name).read_bytes()==(base/name).read_bytes() for name in ('main.bin','sram-fill.bin','itcm-fill.bin'))
    if p.get('uart_component'):
        component=p['uart_component'];old=(base/'strict.cs').read_text();before=(output/'uart-before.txt').read_text();after=(output/'uart-after.txt').read_text()
        initial_same=initial_same and sha(base/'strict.cs')==component['base_sha256'] and sha(output/'uart-before.txt')==component['before_sha256'] and sha(output/'uart-after.txt')==component['after_sha256'] and old.count(before)==1
        expected_model=old.replace(before,after)
        initial_same=initial_same and hashlib.sha256(expected_model.encode()).hexdigest()==component['derived_sha256']
        if p.get('mspi_component'):
            m=p['mspi_component'];old_mspi=(output/'mspi-before.txt').read_text();new_mspi=(output/'mspi-after.txt').read_text()
            initial_same=initial_same and expected_model.count(old_mspi)==1 and sha(output/'mspi-before.txt')==m['before_sha256'] and sha(output/'mspi-after.txt')==m['after_sha256'] and sha(output/'mspi-source.json')==m['source_sha256']
            expected_model=expected_model.replace(old_mspi,new_mspi)
            initial_same=initial_same and sha(output/'strict.cs')==m['derived_sha256']
        initial_same=initial_same and (output/'strict.cs').read_text()==expected_model
    else:initial_same=initial_same and (output/'strict.cs').read_bytes()==(base/'strict.cs').read_bytes()
    if p.get('service'):
        from tpl_service_native import inspect as inspect_service
        return inspect_service(output,p,r,ram,initial_same,destination)
    if p.get('root'):
        from sync_root_native import inspect_root
        return inspect_root(s,output,p,r,ram,initial_same,destination)
    desc=bytes(r['descriptor']);identifier=struct.unpack_from('<H',desc)[0]
    expected=frame(identifier,2,struct.pack('<4H',0x100,0x10b,0,0)).hex()
    before=r['before'];new=r['dma']['transfers'][before['transfers']:]
    owner=r['current_tcb'];name=ram[owner+52-SRAM:owner+84-SRAM].split(b'\0',1)[0].decode()
    checks=dict(initial_assets_unchanged=initial_same,stopped=r['stopped'] and r['pc']==p['stop'],caller_finished=r['mailbox'][5]==0xc0ff3300,start_return=r['mailbox'][2]==1,original_sensor_thread=owner==before['current_tcb'] and name=='sensor_hub' and r['xpsr']&0x1ff==0,preserved_stack=r['sp']==before['sp'],irq_context=r['bootstrap'][5:]==[0,0,0],dma_payload=len(new)==1 and new[0]['data']==expected,dma_completed=r['dma']['completions']==before['completions']+1,uart_irq=r['uart_irq_entries']>before['irq_entries'] and r['uart_irq_vector']==31,no_fault=r['cfsr']==r['hfsr']==r['memory_violations']==0,no_unsupported=all(g['accesses']==0 for g in r['guards']),no_ui_input=r['ui_messages']==0,main_unchanged=sha(output/'main.bin')==p['main_sha256'],model_unchanged=sha(output/'strict.cs')==p['model_sha256'])
    if p.get('scenario')=='bad-header-crc':
        context=struct.unpack_from('<I',ram,p['sync']['context_slot']-SRAM)[0]
        count=ram[context+0x7158-SRAM]
        records=[context+0x6430+24*k for k in range(count)]
        matching=[address for address in records if struct.unpack_from('<H',ram,address-SRAM)[0]==identifier]
        wanted=bytearray(frame(identifier,2,b'\x02'));wanted[8]^=1
        checks.update(reply_bytes=bytes(r['reply'])==bytes(wanted),send_checkpoint=r['send_stopped'],receive_return=r['mailbox'][7]==0xc0ff3301,crc_error_branch=r['error_events'].count(p['error_branch'])==1,parser_reset=ram[context+0x10-SRAM]==0,pending_request_preserved=len(matching)==1 and struct.unpack_from('<I',ram,matching[0]+4-SRAM)[0]==p['sync']['master_reply']|1)
    if p.get('scenario') in ('uart-rx-crc-then-valid','uart-rx-crc-pair'):
        rx=r['rx'];wanted=frame(identifier,2,b'\x02');bad=bytearray(wanted);bad[8]^=1;stream=bytes(bad)+(bytes(bad) if p['scenario']=='uart-rx-crc-pair' else wanted)
        digest=14695981039346656037
        for value in stream:digest=((digest^value)*1099511628211)&((1<<64)-1)
        receives=rx.get('receives',[])
        checks['original_sensor_thread']=rx['send_tcb']==before['current_tcb'] and name=='uart_sync_thread' and r['xpsr']&0x1ff==0
        checks['preserved_stack']=rx['send_sp']==before['sp'] and len(receives)==1 and r['sp']+p['receive_stack_bytes']==receives[0][2]
        checks['no_ui_input']=r['ui_messages']==(0 if p['scenario']=='uart-rx-crc-pair' else 1)
        checks.update(rx_accepted=rx['accepted'],rx_config=rx['level']==2 and rx['control']&0x209==0x209,rx_stream=bytes(r['reply'])==stream,rx_irq=rx['irq_at_injection'] and r['uart_irq_entries']>rx['before_entries'],rx_bytes=rx['injected']==rx['read']==24 and rx['pending']==0 and rx['read_hash']==digest,rx_original_task=len(receives)==1 and receives[0][4]==owner and receives[0][5]&0x1ff==0,rx_buffer=len(receives)==1 and SRAM<=receives[0][0]<SRAM+len(ram) and receives[0][1]==24 and ram[receives[0][0]-SRAM:receives[0][0]-SRAM+24]==stream,crc_error=r['error_events'].count(p['error_branch'])==(2 if p['scenario']=='uart-rx-crc-pair' else 1))
    if p.get('scenario')=='uart-rx-crc-pair':
        context=struct.unpack_from('<I',ram,p['sync']['context_slot']-SRAM)[0]
        count=ram[context+0x7158-SRAM]
        records=[context+0x6430+24*k for k in range(count)]
        matching=[address for address in records if struct.unpack_from('<H',ram,address-SRAM)[0]==identifier]
        checks.update(parser_reset=ram[context+0x10-SRAM]==0,pending_request_preserved=len(matching)==1 and struct.unpack_from('<I',ram,matching[0]+4-SRAM)[0]==p['sync']['master_reply']|1)
    if p.get('jbd_status_hex'):
        m=r['mspi'];values=bytes.fromhex(p['jbd_status_hex']);frames=m['rx_frames']
        status_frames=[f for f in frames if f['instruction'] in (5,0x35)]
        calls=r['rx'].get('ui_calls',[])
        if p['scenario']=='uart-rx-crc-then-valid':
            checks.pop('no_ui_input')
            checks['ui_request_forwarded']=len(calls)==1 and calls[0][0]==0x10b and calls[0][1]==r['mailbox'][1]+8 and calls[0][2]==0 and calls[0][4]==r['rx']['receives'][0][4] and calls[0][5]&0x1ff==0
            context=struct.unpack_from('<I',ram,p['sync']['context_slot']-SRAM)[0];count=ram[context+0x7158-SRAM]
            records=[context+0x6430+24*k for k in range(count)]
            checks['request_retired']=all(struct.unpack_from('<H',ram,address-SRAM)[0]!=identifier for address in records)
            checks['parser_reset']=ram[context+0x10-SRAM]==0
            if p['jbd_status_hex']=='5a01':
                checks['mspi_status_sequence']=len(status_frames)>=2 and len(status_frames)%2==0 and [f['instruction'] for f in status_frames]==[5,0x35]*(len(status_frames)//2)
        else:
            checks['no_ui_producer']=not calls

        checks.update(mspi_profile=m['profile']==p['jbd_status_hex'],mspi_status_read=(len(status_frames)>=1 if p['scenario']=='uart-rx-crc-then-valid' else len(status_frames)==0) and all(f['control']==0x10441 and f['data']==values[0 if f['instruction']==5 else 1:1 if f['instruction']==5 else 2].hex() for f in status_frames),mspi_reads=m['rx_completions']==m['rx_reads'] and m['rx_bytes']>=len(status_frames))
    result=dict(passed=all(checks.values()),case=p['case'],checks=checks,expected_frame=expected,observed_new_transfers=new,synthetic_api_stimulus=True,physical_transport=False,natural_main_complete=False,receive_tested=False)
    result['rx_device_input_tested']=p.get('scenario') in ('uart-rx-crc-then-valid','uart-rx-crc-pair') and all(checks.values())
    if p.get('scenario') in ('uart-rx-crc-then-valid','uart-rx-crc-pair'):result['receive_tested']=result['rx_device_input_tested']
    spec=dict(boundary=dict(kind='bounded-capture'),comparison=dict(policy='bounded-invariants',paths=[['checks','main_unchanged'],['checks','model_unchanged'],['checks','initial_assets_unchanged']]),checks=[dict(path=['checks',key],eq=True) for key in checks],allowed_differences=['Explicit API caller after normal main hold; original Sensor Thread/IRQ/stack preserved, UI stimulus absent.'],unresolved_differences=['No original main completion, RX device input or peer error cleanup. Observer neutrality unproven.'])
    if p.get('uart_component'):spec['allowed_differences'].append('The saved before/after source and hashes define each declared component replacement.')
    if p.get('scenario') in ('uart-rx-crc-then-valid','uart-rx-crc-pair'):
        spec['allowed_differences']=['Explicit send API caller, then original blocking queue API permits normal scheduling; RX bytes enter only the optional device FIFO. Original receive Thread and stack verified.']
        spec['unresolved_differences']=['No original main completion, single short-frame timeout or physical timing validation. Normal reply path may wake unsupported display initialization. Observer neutrality unproven.']
    if p.get('mspi_component'):
        spec['allowed_differences'].append('The pinned existing MSPI0 status component and explicit virtual JBD profile are reused; no physical reset/status claim.')
        spec['unresolved_differences']=['No natural main completion, original root request producer, full frame or short-frame timeout/physical timing validation. Observer neutrality unproven.']
    validate_semantics(spec)
    result.update(observed=r,boundary_kind='bounded-capture',execution_passed=True,selected_observation=dict(events=[dict(pc=r['pc'])] if r['stopped'] else [],sequence=1 if r['stopped'] else 0,dropped_events=0),schema=2)
    result=finish_capture(result,dict(checks=dict(main_unchanged=True,model_unchanged=True,initial_assets_unchanged=True)),spec)
    result['contract']=spec
    target=output if destination is None else destination
    if destination is not None:destination.mkdir(mode=0o700,parents=True)
    (target/'verification.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('simulator',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--case',choices=TEMPLATES,required=True);parser.add_argument('--scenario',choices=['send','bad-header-crc','send-current-uart','uart-rx-crc-then-valid','uart-rx-crc-pair','tpl-request-send','tpl-service-time'],default='send');parser.add_argument('--jbd-status-hex',default='');parser.add_argument('--audit-existing',action='store_true');parser.add_argument('--audit-output',type=Path);a=parser.parse_args()
    if a.audit_existing:
        if a.audit_output is None:parser.error('Saved audit needs --audit-output')
        saved=json.loads((a.output/'sync-profile.json').read_text());assert saved['case']==a.case and saved.get('scenario','send')==a.scenario and saved.get('jbd_status_hex','')==a.jbd_status_hex
        result=inspect(a.simulator,a.output,a.audit_output);print(json.dumps(dict(passed=result['passed'],native_rerun=False)))
        if not result['passed']:raise SystemExit(1)
        return
    if a.audit_output is not None:parser.error('--audit-output requires --audit-existing')
    build(a.simulator,a.output,a.case,a.scenario,a.jbd_status_hex)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+str(a.output)+',target=/work,readonly','--mount','type=bind,source='+str(a.output/'exports')+',target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=240,stream=False)
    pin_capture(a.output)
    r=inspect(a.simulator,a.output);print(json.dumps(dict(passed=r['passed'],case=r['case'],checks=len(r['checks']),expected_frame=r['expected_frame'],synthetic_api_stimulus=True,natural_main_complete=False)));
    if not r['passed']:raise SystemExit(1)


if __name__=='__main__':
    main()
