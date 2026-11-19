"""Cold original main to first frame, then bounded sustained observation; no glasses."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import time
import textwrap

import run_post_screen_lifecycle as baseline
from native_replay import IMAGE
from run_native_candidate import finish_capture, semantic_spec
from run_renode_m55_probe import execute

R = Path(__file__).resolve().parents[1]
S = Path.home() / 'Library/Application Support/Blackwall/simulator'
FIRST = '5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_component(original, old, new):
    if not old or original.count(old) != 1:
        raise ValueError('Exactly one known component required')
    return original.replace(old, new)


def extend_startup_render_guard(runtime, seconds, case='stock24'):
    if seconds != 300:
        raise ValueError('Reviewed render host guard300s required')
    if case == 'stock24':
        before = b'StartAll();deadline=time.time()+30;render_started='
        after = b'StartAll();deadline=time.time()+300;render_started='
    elif case in ['stock23', 'cfw']:
        before = (b'StartAll();deadline=time.time()+120;started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n'
                  b'                    while not m.IsPaused and not cpu.IsHalted and int(gpu.Rejections)==0 and not gpu.CompleteScreenHasDetail')
        after = before.replace(b'+120;', b'+300;', 1)
    else:
        raise ValueError('Known firmware family required')
    return replace_component(runtime, before, after)


def validate_budget(target_ms, host_seconds):
    if target_ms not in [100, 6000, 60000] or not 60 <= host_seconds <= 14400:
        raise ValueError('Reviewed duration and bounded host guard required')
    return dict(target_ms=target_ms, host_seconds=host_seconds, sample_ms=1000,
                max_samples=max(3, target_ms // 1000 + 2))


POST = '''                    if final_draw.Stopped:
                        from System.Diagnostics import Stopwatch
                        from Antmicro.Renode.Utilities import TypeManager
                        clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallSustainedObserver').Assembly)
                        from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallSustainedObserver
                        budget=json.loads(File.ReadAllText('/work/sustained-budget.json'))
                        signal=BlackwallSustainedObserver(m,cpu,m['sysbus.nvic'])
                        wall=Stopwatch.StartNew()
                        def sustained_state():
                            return dict(ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),instructions=int(cpu.ExecutedInstructions),pc=int(cpu.PC.RawValue),registers=registers(),tcb=int(b.ReadDoubleWord(p['tcb_slot'])),frames=int(gpu.CompleteScreenCaptures),nonzero=int(gpu.CompleteScreenNonzero),gpu_rejections=int(gpu.Rejections),gpu_fault=str(gpu.Fault),fifo_ready=bool(m['sysbus.iom4.imu_fifo'].Configuration.Ready),imu_wrapper_gate=int(b.ReadDoubleWord(0x200774f4)))
                        samples=[]
                        def save_checkpoint():
                            state=sustained_state()
                            name='sustained-frame-%03d.bin'%len(samples)
                            File.WriteAllBytes('/work-output/'+name,gpu.CompleteScreenFrameBytes)
                            state['file']=name;state['wall_seconds']=wall.Elapsed.TotalSeconds
                            samples.append(state)
                        File.WriteAllBytes('/work-output/first-screen.bin',gpu.CompleteScreenFrameBytes)
                        File.WriteAllBytes('/work-output/sustained-before-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                        before_sustained=sustained_state();save_checkpoint()
                        started=before_sustained['ticks'];next_sample=started+budget['sample_ms']*int(TimeInterval.TicksPerMillisecond)
                        EmulationManager.Instance.CurrentEmulation.StartAll()
                        while not m.IsPaused and wall.Elapsed.TotalSeconds<budget['host_seconds'] and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-started<budget['target_ms']*int(TimeInterval.TicksPerMillisecond):
                            if bool(cpu.IsHalted) or int(gpu.Rejections)>0:break
                            now=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)
                            if now>=next_sample:
                                if len(samples)>=budget['max_samples']-1:break
                                m.Pause();save_checkpoint()
                                next_sample=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)+budget['sample_ms']*int(TimeInterval.TicksPerMillisecond)
                                EmulationManager.Instance.CurrentEmulation.StartAll()
                            time.sleep(0.02)
                        reason='cpu-halted' if cpu.IsHalted else ('gpu-rejected' if gpu.Rejections else ('machine-paused' if m.IsPaused else ('sample-limit' if len(samples)>=budget['max_samples']-1 else ('host-limit' if wall.Elapsed.TotalSeconds>=budget['host_seconds'] else 'virtual-limit'))))
                        m.Pause();save_checkpoint();wall.Stop()
                        after_sustained=sustained_state()
                        guard_count=0;guard_details=[]
                        for guard_name in ('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail'):
                            guard=m['sysbus.'+guard_name]
                            guard_count+=int(guard.AccessCount)
                            guard_details.append(dict(name=guard_name,accesses=int(guard.AccessCount),address=int(guard.LastAddress),value=int(guard.LastValue),width=int(guard.LastWidth),operation=str(guard.LastOperation)))
                        rtc=g.Rtc
                        rtc_info=dict(accesses=int(rtc.AccessCount),address=int(rtc.LastAddress),value=int(rtc.LastValue),error=str(rtc.LastError),control=int(rtc.Control),writes=int(rtc.Writes),commits=int(rtc.Commits),pending=bool(rtc.WritePending),date=str(rtc.VirtualDate))
                        faults=dict(cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),memory=int(memory_policy.Violations),system=int(system_control.Violations),guards=guard_count,rtc=rtc_info['accesses'])
                        if faults['rtc']:reason='rtc-rejected'
                        observed=dict(target_ms=budget['target_ms'],ticks_per_ms=int(TimeInterval.TicksPerMillisecond),elapsed_ticks=after_sustained['ticks']-started,before=before_sustained,after=after_sustained,samples=samples,stop_reason=reason,wall_seconds=wall.Elapsed.TotalSeconds,faults=faults,signals=dict(counts=[int(v) for v in signal.Counts],total=sum(int(v) for v in signal.Counts),entered=[int(v) for v in signal.Entered],exited=[int(v) for v in signal.Exited],samples=[[int(v) for v in row] for row in signal.Samples],truncated=bool(signal.Truncated)))
                        observed['rtc']=rtc_info
                        observed['guard_details']=guard_details
                        observed['uarts']=[]
                        for module in range(4):
                            uart_adapter=g.Uarts[module];uart_dma=uart_adapter.DmaTx
                            observed['uarts'].append(dict(module=module,control=int(uart_adapter.Control),baud=int(uart_adapter.VirtualBaud),tx_bytes=int(uart_adapter.TxBytes.Count),bounded_tx_capture=bool(getattr(uart_adapter,'BoundedTxCapture',False)),tx_total=int(getattr(uart_adapter,'TxBytesTotal',uart_adapter.TxBytes.Count)),tx_dropped=int(getattr(uart_adapter,'TxBytesDropped',0)),tx_truncated=bool(getattr(uart_adapter,'TxHistoryTruncated',False)),tx_hash=int(uart_adapter.TxBytesHash) if hasattr(uart_adapter,'TxBytesHash') else None,rx_pending=int(uart_adapter.RxPending),power=str(g.UartPowers[module].Phase),power_blocks=int(uart_adapter.PowerBlocks),raw_interrupts=int(uart_adapter.RawInterrupts),masked_interrupts=int(uart_adapter.MaskedInterrupts),dma=None if uart_dma is None else dict(control=int(uart_dma.Control),target=int(uart_dma.Target),count=int(uart_dma.Count),status=int(uart_dma.Status),raw_interrupts=int(uart_dma.RawInterrupts),busy=bool(uart_dma.Busy),starts=int(uart_dma.Starts),completions=int(uart_dma.Completions),transferred_bytes=int(uart_dma.TransferredBytes))))
                        from System.Reflection import BindingFlags
                        reset=g.Em9305Reset;peer=reset.HciPeer
                        flags=BindingFlags.Instance|BindingFlags.NonPublic
                        accepted=peer.GetType().GetField('accepted',flags).GetValue(peer)
                        written=peer.GetType().GetField('written',flags).GetValue(peer)
                        observed['em9305']=dict(pin117_config=int(g.GpioConfig.Values[0x400101d4]) if g.GpioConfig.Values.ContainsKey(0x400101d4) else None,held=bool(reset.Held),released=bool(reset.Released),reset_phase=str(reset.Phase),last_read_pc=int(reset.LastReadPc),write_pc=int(reset.WritePc),confirm_pc=int(reset.WriteConfirmPc),reply_wait_pc=int(reset.ReplyWaitPc),peer_state=str(peer.State),ready=int(peer.ReadyLevel),cs_known=bool(peer.CsKnown),cs_high=bool(peer.CsHigh),commands=int(peer.CommandsAccepted),replies=int(peer.Replies),command_limit=int(peer.CommandLimit),write_headers=int(peer.WriteHeaders),frames=int(peer.Frames),aborts=int(peer.Aborts),accepted=[str(v) for v in accepted],pending_hex=''.join('%02x'%int(v) for v in written))
                        observed['em9305'].update(local_version_commands=int(getattr(peer,'LocalVersionCommands',0)),local_version_replies=int(getattr(peer,'LocalVersionReplies',0)),local_version_limit=int(getattr(peer,'RuntimeLocalVersionLimit',0)),runtime_events_consumed=int(peer.RuntimeEventsConsumed),remote_replies_consumed=int(peer.RuntimeRemoteRepliesConsumed),runtime_pending=bool(peer.RuntimeEventPending))
                        observed['em9305'].update(advertising_disable_commands=int(getattr(peer,'AdvertisingDisableCommands',0)),advertising_disable_replies=int(getattr(peer,'AdvertisingDisableReplies',0)),advertising_disable_limit=int(getattr(peer,'StartupAdvertisingDisableLimit',0)),advertising_stopped=bool(getattr(peer,'AdvertisingStopped',False)))
                        observed['em9305'].update(advertising_procedure_step=int(getattr(peer,'AdvertisingProcedureStep',0)),advertising_parameter_commands=int(getattr(peer,'AdvertisingParameterCommands',0)),advertising_parameter_replies=int(getattr(peer,'AdvertisingParameterReplies',0)),advertising_enable_commands=int(getattr(peer,'AdvertisingEnableCommands',0)),advertising_enable_replies=int(getattr(peer,'AdvertisingEnableReplies',0)))
                        signal.Detach()
                        File.WriteAllBytes('/work-output/sustained-after-sram.bin',b.ReadBytes(0x20000000,0x380000,True))
                        File.WriteAllText('/work-output/sustained.json',json.dumps(observed))
'''


def validate_observer_scope(post, original):
    class Bindings(ast.NodeVisitor):
        def __init__(self):
            self.names = set()
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                self.names.add(node.id)
        def visit_FunctionDef(self, node):
            self.names.add(node.name)
        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef
        def visit_Import(self, node):
            self.names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
        def visit_ImportFrom(self, node):
            self.names.update(alias.asname or alias.name for alias in node.names)
    tree = ast.parse(textwrap.dedent(post))
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        raise ValueError('Observer must not rebind outer runtime state')
    added, prior = Bindings(), Bindings()
    added.visit(tree)
    prior.visit(ast.parse(original))
    if added.names & prior.names:
        raise ValueError('Observer overwrites runtime names: ' + ','.join(sorted(added.names & prior.names)))


_post_lines = POST.splitlines(keepends=True)
POST = (_post_lines[0] + '                        def bw_sustained_capture():\n'
        + ''.join('    ' + line for line in _post_lines[1:])
        + '                        bw_sustained_capture()\n')


def assess(data):
    before, after, samples, signals = (data[k] for k in ['before', 'after', 'samples', 'signals'])
    return dict(
        target_reached=data['stop_reason'] == 'virtual-limit' and data['ticks_per_ms'] == 1000000
        and data['elapsed_ticks'] == after['ticks'] - before['ticks']
        and data['elapsed_ticks'] >= data['target_ms'] * 1000000,
        cpu_progress=after['instructions'] > before['instructions'],
        fault_free=all(v == 0 for v in data['faults'].values()) and after['gpu_rejections'] == 0 and not after['gpu_fault'],
        initialized=after['fifo_ready'] and after['imu_wrapper_gate'] == 1,
        first_frame=data['first_frame_sha256'] == FIRST,
        progressing_samples=len(samples) >= 2 and samples[0]['ticks'] == before['ticks']
        and samples[-1]['ticks'] == after['ticks']
        and all(b['ticks'] > a['ticks'] and b['instructions'] > a['instructions'] and b['frames'] >= a['frames'] for a, b in zip(samples, samples[1:])),
        bounded_signal_accounting=signals['total'] == sum(signals['counts'])
        and all(signals['counts'][k] == signals['entered'][k] + signals['exited'][k] for k in range(2))
        and len(signals['samples']) <= 128,
        sleep_wake=any(signals['entered'][k] > 0 and signals['exited'][k] > 0 for k in range(2)),
        measured_work=data['wall_seconds'] > 0,
    )


def derive(out, case, budget, status_hex=None, rtc_profile=None, controller_version_profile=None, uart_capture_profile=None, startup_command_profile=None, startup_render_host_seconds=None):
    if startup_command_profile is not None and (startup_command_profile not in ['version-and-advertising-stop', 'version-and-advertising-reconfigure'] or controller_version_profile != 'startup-mock'):
        raise ValueError('Startup command selector requires explicit mock identity')
    prior = baseline.POST
    baseline.POST = POST
    try:
        plan = baseline.derive(out, case)
    finally:
        baseline.POST = prior
    if startup_render_host_seconds is not None:
        runtime = out / 'run.py'
        runtime.write_bytes(extend_startup_render_guard(runtime.read_bytes(), startup_render_host_seconds, case))
        original = (S / plan['source_root'] / 'run.py').read_bytes()
        base = extend_startup_render_guard(original, startup_render_host_seconds, case)
        (out / 'host-guard-base.py').write_bytes(base)
        plan['startup_host_guard'] = dict(phase='render-return' if case == 'stock24' else 'family-first-detail-frame', seconds=startup_render_host_seconds,
            original_sha256=hashlib.sha256(original).hexdigest(), base_sha256=sha(out / 'host-guard-base.py'),
            guest_virtual_budget_changed=False, firmware_changed=False)
    if status_hex is not None:
        proof = S / 'jbd-status-integration-verification-01/manifest.json'
        verified = json.loads(proof.read_text())
        component = R / 'tools/renode-mspi1-config.cs'
        old = S / 'display-status-research-01/base-config.cs'
        source = S / 'jbd-status-consumer-source-02/report.json'
        if (status_hex != '5a01' or not verified['passed']
                or sha(component) != verified['model_sha256']
                or sha(source) != verified['source_report_sha256']):
            raise ValueError('Reviewed JBD model and explicit nominal profile required')
        (out / 'strict.cs').write_bytes(replace_component((out / 'strict.cs').read_bytes(), old.read_bytes(), component.read_bytes()))
        (out / 'mspi-before.txt').write_bytes(old.read_bytes())
        (out / 'mspi-after.txt').write_bytes(component.read_bytes())
        board = (out / 'board.repl').read_bytes()
        anchor = b'mspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n'
        (out / 'board.repl').write_bytes(replace_component(board, anchor, anchor + b'    jbdStatusHex: "5a01"\n'))
        plan['status_profile'] = dict(hex=status_hex, proof_sha256=sha(proof), source_sha256=sha(source),
            before_sha256=sha(old), after_sha256=sha(component), board_sha256=sha(out / 'board.repl'))
        plan['source_invariants']['model_sha256'] = sha(out / 'strict.cs')
    if controller_version_profile is not None:
        if controller_version_profile != 'startup-mock':
            raise ValueError('Explicit startup version fixture required')
        from runtime_local_version_model import component
        from verify_runtime_local_version import IDENTITY
        old, new = (value.encode() for value in component(completed_startup=True))
        unit_directory = 'runtime-local-version-startup-max-01'
        required_count = 400
        if startup_command_profile is not None:
            from startup_hci_commands_model import component as command_component
            before, after = (value.encode() for value in command_component())
            if before != new:
                raise ValueError('Changed startup version composition')
            new = after
            unit_directory = 'startup-hci-commands-green-02'
            required_count = 60
            if startup_command_profile == 'version-and-advertising-reconfigure':
                from startup_advertising_procedure_model import component as procedure_component
                before, after = (value.encode() for value in procedure_component())
                if before != new:
                    raise ValueError('Changed startup selector composition')
                new = after
                unit_directory = 'startup-advertising-procedure-green-01'
                required_count = 136
        proof = S / unit_directory / 'report.json'
        verified = json.loads(proof.read_text())
        if (not verified['passed'] or verified['count'] < required_count
                or (verified.get('original_firmware_executed', False) if startup_command_profile else verified['synthetic_att_events'])
                or (S / unit_directory / 'strict.cs').read_bytes().count(new) != 1):
            raise ValueError('Untested startup version component')
        (out / 'controller-before.txt').write_bytes(old)
        (out / 'controller-after.txt').write_bytes(new)
        (out / 'strict.cs').write_bytes(replace_component((out / 'strict.cs').read_bytes(), old, new))
        board = (out / 'board.repl').read_bytes()
        anchor = b'    runtimeConnectionEventHex:'
        addition = ('    runtimeLocalVersionHex: "' + IDENTITY + '"\n    runtimeLocalVersionLimit: 32\n').encode()
        if startup_command_profile is not None:
            addition = b'    startupAdvertisingDisableLimit: 1\n' + addition
        if startup_command_profile == 'version-and-advertising-reconfigure':
            from startup_advertising_procedure_model import PARAMETERS
            addition = ('    startupAdvertisingParametersHex: "' + PARAMETERS + '"\n').encode() + addition
        (out / 'board.repl').write_bytes(replace_component(board, anchor, addition + anchor))
        plan['controller_version_profile'] = dict(name=controller_version_profile, identity=IDENTITY, limit=32,
            physical_identity_verified=False, before_sha256=sha(out / 'controller-before.txt'), after_sha256=sha(out / 'controller-after.txt'),
            unit_report_sha256=sha(proof), unit_model_sha256=sha(S / unit_directory / 'strict.cs'), unit_directory=unit_directory)
        if startup_command_profile is not None:
            plan['controller_version_profile'].update(startup_command_profile=startup_command_profile, advertising_disable_limit=1)
        if startup_command_profile == 'version-and-advertising-reconfigure':
            plan['controller_version_profile']['advertising_parameters_hex'] = PARAMETERS
        plan['source_invariants']['model_sha256'] = sha(out / 'strict.cs')
    if rtc_profile is not None:
        if rtc_profile != 'independent-weekday':
            raise ValueError('Explicit reviewed RTC profile required')
        before = S / 'sustained-matrix-bw492-01/source/tools/renode-rtc.cs'
        component = R / 'tools/renode-rtc.cs'
        proof = S / 'rtc-weekday-green-01/report.json'
        verified = json.loads(proof.read_text())
        if (sha(before) != '5ccd4626bd0c4a21502d8e9daf07135958d04c01a45d4706ec1e6c092d506189'
                or not verified['passed'] or verified['assertion_count'] != 50
                or (S / 'rtc-weekday-green-01/strict.cs').read_bytes().count(component.read_bytes()) != 1):
            raise ValueError('Changed RTC evidence or untested component')
        (out / 'rtc-before.txt').write_bytes(before.read_bytes())
        (out / 'rtc-after.txt').write_bytes(component.read_bytes())
        (out / 'strict.cs').write_bytes(replace_component((out / 'strict.cs').read_bytes(), before.read_bytes(), component.read_bytes()))
        board = (out / 'board.repl').read_bytes()
        (out / 'board.repl').write_bytes(replace_component(board, b'    halLowUpperWrites: false\n', b'    halLowUpperWrites: true\n    independentWeekday: true\n'))
        plan['rtc_profile'] = dict(name=rtc_profile, before_sha256=sha(before), after_sha256=sha(component),
            unit_report_sha256=sha(proof), unit_model_sha256=sha(S / 'rtc-weekday-green-01/strict.cs'))
        plan['source_invariants']['model_sha256'] = sha(out / 'strict.cs')
    if uart_capture_profile is not None:
        if uart_capture_profile != 'bounded-prefix':
            raise ValueError('Explicit bounded UART capture profile required')
        from uart_tx_capture_model import component
        old, new = (value.encode() for value in component())
        proof = S / 'uart-tx-history-green-01/report.json'
        verified = json.loads(proof.read_text())
        if (not verified['passed'] or verified['count'] < 75 or verified['disabled']
                or (S / 'uart-tx-history-green-01/strict.cs').read_bytes().count(new) != 1):
            raise ValueError('Untested UART capture component')
        (out / 'uart-capture-before.txt').write_bytes(old)
        (out / 'uart-capture-after.txt').write_bytes(new)
        (out / 'strict.cs').write_bytes(replace_component((out / 'strict.cs').read_bytes(), old, new))
        anchor = b'uart0_adapter: Miscellaneous.BlackwallUartAdapter\n'
        (out / 'board.repl').write_bytes(replace_component((out / 'board.repl').read_bytes(), anchor, anchor + b'    boundedTxCapture: true\n'))
        plan['uart_capture_profile'] = dict(name=uart_capture_profile, module=0, prefix_capacity=4096,
            before_sha256=sha(out / 'uart-capture-before.txt'), after_sha256=sha(out / 'uart-capture-after.txt'),
            unit_report_sha256=sha(proof), unit_model_sha256=sha(S / 'uart-tx-history-green-01/strict.cs'))
        plan['source_invariants']['model_sha256'] = sha(out / 'strict.cs')
    observer = R / 'tools/renode-sustained-observer.cs'
    activation = out / 'activation.cs'
    activation.write_bytes(activation.read_bytes() + b'\n' + observer.read_bytes())
    (out / 'sustained-budget.json').write_text(json.dumps(budget, indent=2) + '\n')
    checks = list(assess(dict(target_ms=100, elapsed_ticks=0, ticks_per_ms=1000000, stop_reason='',
        before=dict(ticks=0, instructions=0, frames=0), after=dict(ticks=0, instructions=0, frames=0, gpu_rejections=0, gpu_fault='', fifo_ready=False, imu_wrapper_gate=0),
        samples=[], signals=dict(total=0, counts=[0, 0, 0], entered=[0, 0], exited=[0, 0], samples=[]), faults={}, first_frame_sha256='', wall_seconds=0)))
    spec = dict(boundary={'kind': 'bounded-capture'}, comparison={'policy': 'bounded-invariants', 'paths': [['main_sha256'], ['model_sha256']]},
        checks=[dict(path=['diagnostics', k], eq=True) for k in checks],
        allowed_differences=['Original guest control flow plus one isolated post-frame observation; declared host-only render guard and component/board substitutions are pinned in the plan.'],
        unresolved_differences=['Declared virtual sensor/GPU/power models, not exact ROM/fusion/physical timing.', 'Signal/frame checkpoints are sampled, not complete event/frame histories.'])
    plan.update(id='sustained-screen-' + case, observation=budget, telemetry_version=4, semantics={case: {'candidate': spec, 'control': spec}},
        activation_sha256=sha(activation), budget_sha256=sha(out / 'sustained-budget.json'), runner_sha256=sha(Path(__file__)),
        scope='cold main to first frame then sustained execution; not physical stability')
    plan['runtime_edits'][0]['after_sha256'] = sha(out / 'run.py')
    plan['runtime_edits'][0]['change'] = 'bounded sustained post-first-frame observation'
    if 'startup_host_guard' in plan:
        plan['runtime_edits'][0]['change'] += '; declared host-only render deadline to300s'
    original = (S / plan['source_root'] / 'run.py').read_bytes()
    validate_observer_scope(POST, original.decode())
    if 'startup_host_guard' in plan:
        original = extend_startup_render_guard(original, plan['startup_host_guard']['seconds'], case)
    actual = (out / 'run.py').read_bytes()
    offset = next(i for i, (a, b) in enumerate(zip(original, actual)) if a != b)
    added = len(actual) - len(original)
    if added <= 0 or actual[offset + added:] != original[offset:]:
        raise ValueError('Observation must be one insertion into the preserved runtime')
    (out / 'post-observation.py').write_bytes(actual[offset:offset + added])
    plan['runtime_insertion'] = dict(offset=offset, bytes=added, sha256=sha(out / 'post-observation.py'))
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    (out / 'runner-source.py').write_bytes(Path(__file__).read_bytes())
    return plan


def audit(folder, out):
    if out.exists():
        raise ValueError('Preserve prior audits')
    plan = json.loads((folder / 'plan.json').read_text())
    case = next(iter(plan['cases']))
    ex = folder / 'exports'
    log = (folder / 'renode.log').read_text()
    data = json.loads((ex / 'sustained.json').read_text()) if (ex / 'sustained.json').exists() else None
    integrity = dict(
        runtime=sha(folder / 'run.py') == plan['runtime_edits'][0]['after_sha256'],
        activation=sha(folder / 'activation.cs') == plan['activation_sha256'],
        budget=sha(folder / 'sustained-budget.json') == plan['budget_sha256'],
        removed=json.loads((folder / 'renode.process.json').read_text())['status'] == 'removed',
        no_runtime_error='RUNTIME_ERROR' not in log and 'There was an error executing' not in log,
        no_cpu_control=not any(re.search(x, (folder / 'run.py').read_text()) for x in [r'\.SetRegister\s*\(', r'\.SeedRegister\s*\(', r'\.PC\s*=', r'\.WriteDoubleWord\s*\(', r'\.WriteByte\s*\(']),
    )
    for name, digest in plan['input_sha256'].items():
        integrity['source:' + name] = sha(S / plan['source_root'] / name) == digest
        changed = ['strict.cs', 'board.repl'] if any(k in plan for k in ['status_profile', 'rtc_profile', 'controller_version_profile', 'uart_capture_profile']) else []
        if name not in ['activation.cs', 'run.py', 'runner-source.py', 'plan.json'] + changed:
            integrity['input:' + name] = sha(folder / name) == digest
    if 'status_profile' in plan:
        status = plan['status_profile']
        source = S / plan['source_root']
        old, new = folder / 'mspi-before.txt', folder / 'mspi-after.txt'
        expected_model = replace_component((source / 'strict.cs').read_bytes(), old.read_bytes(), new.read_bytes())
        anchor = b'mspi0_tx: Miscellaneous.BlackwallMspi0Tx @ none\n'
        expected_board = replace_component((source / 'board.repl').read_bytes(), anchor, anchor + b'    jbdStatusHex: "5a01"\n')
        integrity['mspi_component_pins'] = sha(old) == status['before_sha256'] and sha(new) == status['after_sha256']
        integrity['status_evidence'] = (sha(S / 'jbd-status-integration-verification-01/manifest.json') == status['proof_sha256']
            and sha(S / 'jbd-status-consumer-source-02/report.json') == status['source_sha256'])
    else:
        expected_model = (S / plan['source_root'] / 'strict.cs').read_bytes()
        expected_board = (S / plan['source_root'] / 'board.repl').read_bytes()
    if 'rtc_profile' in plan:
        rtc = plan['rtc_profile']
        old, new = folder / 'rtc-before.txt', folder / 'rtc-after.txt'
        integrity['rtc_component_pins'] = sha(old) == rtc['before_sha256'] and sha(new) == rtc['after_sha256']
        expected_model = replace_component(expected_model, old.read_bytes(), new.read_bytes())
        expected_board = replace_component(expected_board, b'    halLowUpperWrites: false\n', b'    halLowUpperWrites: true\n    independentWeekday: true\n')
        integrity['rtc_evidence'] = sha(S / 'rtc-weekday-green-01/report.json') == rtc['unit_report_sha256'] and sha(S / 'rtc-weekday-green-01/strict.cs') == rtc['unit_model_sha256']
    if 'controller_version_profile' in plan:
        profile = plan['controller_version_profile']
        old, new = folder / 'controller-before.txt', folder / 'controller-after.txt'
        integrity['controller_component_pins'] = sha(old) == profile['before_sha256'] and sha(new) == profile['after_sha256']
        expected_model = replace_component(expected_model, old.read_bytes(), new.read_bytes())
        anchor = b'    runtimeConnectionEventHex:'
        addition = ('    runtimeLocalVersionHex: "' + profile['identity'] + '"\n    runtimeLocalVersionLimit: 32\n').encode()
        command_profile = profile.get('startup_command_profile')
        directory = ('startup-advertising-procedure-green-01' if command_profile == 'version-and-advertising-reconfigure'
                     else 'startup-hci-commands-green-02' if command_profile else 'runtime-local-version-startup-max-01')
        if command_profile is not None:
            integrity['startup_command_profile'] = command_profile in ['version-and-advertising-stop', 'version-and-advertising-reconfigure'] and profile['advertising_disable_limit'] == 1
            addition = b'    startupAdvertisingDisableLimit: 1\n' + addition
        if command_profile == 'version-and-advertising-reconfigure':
            parameters = profile['advertising_parameters_hex']
            integrity['advertising_parameters_profile'] = parameters == '0106200f400640060001000000000000000700'
            addition = ('    startupAdvertisingParametersHex: "' + parameters + '"\n').encode() + addition
        expected_board = replace_component(expected_board, anchor, addition + anchor)
        integrity['controller_fixture'] = profile['name'] == 'startup-mock' and profile['identity'] == '0d34120d5a007856' and profile['limit'] == 32 and profile['physical_identity_verified'] is False
        integrity['controller_evidence'] = profile.get('unit_directory', directory) == directory and sha(S / directory / 'report.json') == profile['unit_report_sha256'] and sha(S / directory / 'strict.cs') == profile['unit_model_sha256']
    if 'uart_capture_profile' in plan:
        profile = plan['uart_capture_profile']
        old, new = folder / 'uart-capture-before.txt', folder / 'uart-capture-after.txt'
        integrity['uart_capture_pins'] = sha(old) == profile['before_sha256'] and sha(new) == profile['after_sha256']
        integrity['uart_capture_profile'] = profile['name'] == 'bounded-prefix' and profile['module'] == 0 and profile['prefix_capacity'] == 4096
        expected_model = replace_component(expected_model, old.read_bytes(), new.read_bytes())
        anchor = b'uart0_adapter: Miscellaneous.BlackwallUartAdapter\n'
        expected_board = replace_component(expected_board, anchor, anchor + b'    boundedTxCapture: true\n')
        integrity['uart_capture_evidence'] = sha(S / 'uart-tx-history-green-01/report.json') == profile['unit_report_sha256'] and sha(S / 'uart-tx-history-green-01/strict.cs') == profile['unit_model_sha256']
    integrity['only_declared_model_changes'] = (folder / 'strict.cs').read_bytes() == expected_model
    integrity['only_declared_board_changes'] = (folder / 'board.repl').read_bytes() == expected_board
    for name, digest in plan['prefix_sha256'].items():
        integrity['prefix:' + name] = sha(ex / name) == digest
    if 'runtime_insertion' in plan:
        insertion = plan['runtime_insertion']
        original = (S / plan['source_root'] / 'run.py').read_bytes()
        if 'startup_host_guard' in plan:
            guard = plan['startup_host_guard']
            integrity['declared_render_host_guard'] = (guard['phase'] == ('render-return' if case == 'stock24' else 'family-first-detail-frame') and guard['seconds'] == 300
                and guard['guest_virtual_budget_changed'] is False and guard['firmware_changed'] is False
                and hashlib.sha256(original).hexdigest() == guard['original_sha256'])
            original = extend_startup_render_guard(original, guard['seconds'], case)
            integrity['host_guard_only_literal_edit'] = ((folder / 'host-guard-base.py').read_bytes() == original
                and sha(folder / 'host-guard-base.py') == guard['base_sha256'])
        post = (folder / 'post-observation.py').read_bytes()
        offset = insertion['offset']
        integrity['original_runtime_preserved'] = (sha(folder / 'post-observation.py') == insertion['sha256']
            and len(post) == insertion['bytes']
            and (folder / 'run.py').read_bytes() == original[:offset] + post + original[offset:])
    checks = dict(capture_present=data is not None)
    if data is not None:
        data['first_frame_sha256'] = sha(ex / 'first-screen.bin')
        checks = assess(data)
        integrity['requested_duration'] = data['target_ms'] == plan['observation']['target_ms']
        if plan.get('telemetry_version', 0) >= 2:
            integrity['rtc_telemetry'] = data['faults'].get('rtc') == data['rtc']['accesses']
        if plan.get('telemetry_version', 0) >= 3:
            integrity['em9305_telemetry'] = 'em9305' in data
        if plan.get('telemetry_version', 0) >= 4:
            integrity['guard_details'] = sum(row['accesses'] for row in data['guard_details']) == data['faults']['guards']
            integrity['uart_telemetry'] = [row['module'] for row in data['uarts']] == list(range(4))
        if 'controller_version_profile' in plan:
            peer = data['em9305']
            integrity['controller_telemetry'] = peer['local_version_limit'] == 32 and 0 <= peer['local_version_replies'] <= peer['local_version_commands'] <= 32 and peer['runtime_events_consumed'] == peer['remote_replies_consumed'] == 0
            if plan['controller_version_profile'].get('startup_command_profile'):
                enable_commands = peer['advertising_enable_commands'] if plan['controller_version_profile']['startup_command_profile'] == 'version-and-advertising-reconfigure' else 0
                integrity['advertising_telemetry'] = peer['advertising_disable_limit'] == 1 and 0 <= peer['advertising_disable_replies'] <= peer['advertising_disable_commands'] <= 1 and peer['advertising_stopped'] == (peer['advertising_disable_commands'] > enable_commands)
                if plan['controller_version_profile']['startup_command_profile'] == 'version-and-advertising-reconfigure':
                    integrity['advertising_procedure_telemetry'] = (0 <= peer['advertising_parameter_replies'] <= peer['advertising_parameter_commands'] <= peer['advertising_disable_replies']
                        and 0 <= peer['advertising_enable_replies'] <= peer['advertising_enable_commands'] <= peer['advertising_parameter_replies']
                        and peer['advertising_procedure_step'] == peer['advertising_disable_replies'] + peer['advertising_parameter_replies'] + peer['advertising_enable_replies'])
        if 'uart_capture_profile' in plan:
            uart = data['uarts'][0]
            integrity['uart_capture_telemetry'] = uart['bounded_tx_capture'] and 0 <= uart['tx_bytes'] <= 4096 and uart['tx_total'] >= uart['tx_bytes'] and uart['tx_dropped'] == uart['tx_total'] - uart['tx_bytes'] and uart['tx_truncated'] == (uart['tx_dropped'] > 0) and type(uart['tx_hash']) is int and 0 <= uart['tx_hash'] < 2**64
        integrity['samples'] = len(data['samples']) <= plan['observation']['max_samples']
        integrity['frames'] = all((ex / row['file']).stat().st_size == 576 * 288 for row in data['samples'])
    result = dict(case=case, control=False, boundary_kind='bounded-capture', main_sha256=sha(folder / 'main.bin'),
        model_sha256=sha(folder / 'strict.cs'), observed=data, diagnostics=checks,
        selected_observation=dict(events=data['samples'] if data else [], sequence=len(data['samples']) if data else 0,
                                  dropped_events=0, scope='bounded checkpoints; not all frames or IRQ events'))
    result = finish_capture(result, plan['source_invariants'], semantic_spec(plan, case, False))
    result.update(execution_passed=all(integrity.values()), execution_checks=integrity,
                  hardware_accessed=False, complete_frame_history=False)
    result['startup_trace_truncated'] = json.loads((ex / 'touch.json').read_text())['overflow'] if (ex / 'touch.json').exists() else None
    result['passed'] = result['execution_passed'] and result['semantic_validation']['passed']
    result['capture_hashes'] = {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file() and 'audit' not in p.relative_to(folder).parts}
    out.mkdir(mode=0o700, parents=True)
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], failures=[k for k, v in checks.items() if not v],
        execution_failures=[k for k, v in integrity.items() if not v],
        elapsed_ms=data['elapsed_ticks'] / 1e6 if data else None, wall_seconds=data['wall_seconds'] if data else None)))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--case', choices=['stock24', 'stock23', 'cfw'], default='stock24')
    p.add_argument('--duration-ms', type=int, choices=[100, 6000, 60000], default=6000)
    p.add_argument('--host-seconds', type=int, default=3600)
    p.add_argument('--jbd-status-hex', choices=['5a01'])
    p.add_argument('--rtc-profile', choices=['independent-weekday'])
    p.add_argument('--controller-version-profile', choices=['startup-mock'])
    p.add_argument('--uart-capture-profile', choices=['bounded-prefix'])
    p.add_argument('--startup-command-profile', choices=['version-and-advertising-stop', 'version-and-advertising-reconfigure'])
    p.add_argument('--startup-render-host-seconds', type=int, choices=[300])
    p.add_argument('--audit-existing', action='store_true')
    p.add_argument('--audit-output', type=Path)
    args = p.parse_args()
    out = args.output.resolve()
    if args.audit_existing:
        if args.audit_output is None:
            p.error('Separate audit output required')
        result = audit(out, args.audit_output.resolve())
    else:
        budget = validate_budget(args.duration_ms, args.host_seconds)
        derive(out, args.case, budget, args.jbd_status_hex, args.rtc_profile, args.controller_version_profile, args.uart_capture_profile, args.startup_command_profile, args.startup_render_host_seconds)
        started = time.monotonic()
        execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', '--mount', f'type=bind,source={out/"exports"},target=/work-output', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], out, 'renode', timeout=args.host_seconds + 300, stream=True)
        (out / 'host-measurement.json').write_text(json.dumps(dict(docker_wall_seconds=time.monotonic() - started, includes_compile_and_cold_boot=True), indent=2) + '\n')
        result = audit(out, out / 'audit')
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
