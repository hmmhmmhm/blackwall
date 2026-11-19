"""Continue a validated recovery-worker RAM call in Renode M55; host memory only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import argparse
import importlib.util
import unicorn.arm_const as registers
from emulate_recovery_worker import RecoveryWorker, RamInvocationBoundary
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_write(path, data):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as stream:
        stream.write(data)


def is_git_output(path):
    return path.is_relative_to(ROOT) or any((parent / '.git').exists() for parent in [path, *path.parents])


def validate_write_scope(destination,length,full_main_restore,*,boot_restore=False):
    if type(destination) is not int or type(length) is not int or type(full_main_restore) is not bool or type(boot_restore) is not bool or full_main_restore and boot_restore:
        raise ValueError('Explicit integer range and boolean restore mode required')
    allowed=((destination==0x438010 and length==3700064) or (destination==0x438000 and length==16)) if full_main_restore else (destination==0x438010 and 0<length<=4096 and length%16==0)
    if boot_restore:allowed=(destination,length) in ((0x410000,149776),(0x434910,9968),(0x410000,159744))
    if not allowed:raise ValueError('Outside declared virtual write scope')


def prepare_capture(candidate, output, data, *, destination=0x438010, full_main_restore=False, mram_before=None, boot_restore=False):
    output = Path(output).resolve()
    validate_write_scope(destination,len(data),full_main_restore,boot_restore=boot_restore)
    if is_git_output(output):
        raise ValueError('Use aligned bounded data and a private output')
    worker = RecoveryWorker(candidate)
    if mram_before is not None:
        before=Path(mram_before).read_bytes()
        original=bytes(worker.cpu.mem_read(0x400000,0x400000))
        allowed_boot=before[0x10000:0x37000]==original[0x10000:0x37000]
        if boot_restore and not allowed_boot:
            stock=(Path.home()/'Library/Application Support/Blackwall/recovery/boot-2-4-analysis/boot-2.4.0.24.bin').read_bytes()
            if sha(stock)!='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665':raise ValueError('Pinned stock boot required')
            prefix_restored=bytearray(original[0x10000:0x37000]);prefix_restored[:149776]=stock+bytes(3)
            allowed_boot=before[0x10000:0x37000]==prefix_restored
        if not (full_main_restore or boot_restore) or len(before)!=0x400000 or not allowed_boot:
            raise ValueError('Restore snapshot must retain a reviewed recovery boot state')
        worker.cpu.mem_write(0x400000,before)
    worker.claim()
    writer = (Path(candidate) / 'source/build/recover.bin').read_bytes()
    if sha(writer) != '9abc30c98bec432981d0c40ded3159085f273700e6c3b54716e37360df8cb8b2':
        raise ValueError('Unreviewed recovery writer')
    worker.client.upload(writer, arg0=destination, arg1=len(data))
    try:
        worker.client.execute(source=lambda n: data[:n])
    except RamInvocationBoundary:
        pass
    else:
        raise ValueError('No compiled RAM invocation boundary')
    names = ['R' + str(n) for n in range(13)] + ['SP', 'LR', 'PC', 'CONTROL', 'BASEPRI', 'PRIMASK', 'FAULTMASK', 'XPSR', 'MSP', 'PSP']
    state = {name: worker.cpu.reg_read(getattr(registers, 'UC_ARM_REG_' + name)) for name in names}
    manifest = dict(schema=1, destination=destination, full_main_restore=full_main_restore, boot_restore=boot_restore, registers=state, worker=worker.report(), tick=worker.ticks,
                    functions=worker.functions, payload_bytes=len(data), payload_sha256=sha(data),
                    initial_boot_sha256=sha(bytes(worker.cpu.mem_read(0x410000,0x27000))),hardware_accessed=False, extension_profile='M55 FPU access on; limits zero; S-register patterns, VPR=ffff; unobserved by Unicorn')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in [('sram.bin', bytes(worker.cpu.mem_read(0x20000000, 0x80000))),
                           ('mram.bin', bytes(worker.cpu.mem_read(0x400000, 0x400000))), ('payload.bin', data)]:
        private_write(output / name, content)
    private_write(output / 'protocol.py', Path(worker.protocol.__file__).read_bytes())
    private_write(output / 'worker-source.py', (ROOT / 'tools/emulate_recovery_worker.py').read_bytes())
    if not (full_main_restore or boot_restore) and (output / 'mram.bin').read_bytes()[0x38000:0x38010] != bytes(16):
        raise ValueError('Corrupt-main fixture vector differs')
    manifest['sha256'] = {name: sha((output / name).read_bytes()) for name in ['sram.bin', 'mram.bin', 'payload.bin', 'protocol.py', 'worker-source.py']}
    private_write(output / 'snapshot.json', (json.dumps(manifest, indent=2) + '\n').encode())
    return manifest


def run_case(capture, output, rom_status=0, corrupt=False, interrupt_after_words=-1,*,allow_incomplete=False):
    capture, output = Path(capture), Path(output).resolve()
    if is_git_output(output) or type(rom_status) is not int or not 0 <= rom_status <= 255 or type(corrupt) is not bool:
        raise ValueError('Private output and explicit bounded fault configuration required')
    if type(interrupt_after_words) is not int or interrupt_after_words < -1 or interrupt_after_words>=0 and (rom_status or corrupt):
        raise ValueError('Explicit independent word interruption required')
    manifest = json.loads((capture / 'snapshot.json').read_text())
    destination=manifest.get('destination',0x438010);full=manifest.get('full_main_restore',False)
    boot_restore=manifest.get('boot_restore',False);compact=full or boot_restore
    validate_write_scope(destination,manifest['payload_bytes'],full,boot_restore=boot_restore)
    if type(allow_incomplete) is not bool or allow_incomplete and not boot_restore:raise ValueError('Incomplete result capture is only for the explicit boot experiment')
    if interrupt_after_words>manifest['payload_bytes']//4:
        raise ValueError('Interruption outside bounded payload')
    for name, expected in manifest['sha256'].items():
        if sha((capture / name).read_bytes()) != expected:
            raise ValueError('Captured memory changed')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output/'exports').mkdir(mode=0o700)
    for name in ['snapshot.json', *manifest['sha256']]:
        private_write(output / name, (capture / name).read_bytes())
    fixture = (ROOT / 'tools/renode-recovery-writer-fixture.cs').read_bytes()
    private_write(output / 'fixture.cs', fixture)
    private_write(output / 'runner-source.py', Path(__file__).read_bytes())
    state, functions = manifest['registers'], manifest['functions']
    board = '''cpu: CPU.CortexM @ sysbus
    cpuType: "cortex-m55"
    nvic: nvic
    PerformanceInMips: 10
nvic: IRQControllers.NVIC @ sysbus 0xe000e000
    systickFrequency: 1000000
mram: Miscellaneous.BlackwallProtectedMram @ sysbus 0x400000
    size: 0x400000
sram: Memory.MappedMemory @ sysbus 0x20000000
    size: 0x80000
rom: Memory.MappedMemory @ sysbus 0x0200f000
    size: 0x1000
mram_control: Miscellaneous.BlackwallRecoveryMramControl @ sysbus 0x40014000
uart: Miscellaneous.BlackwallRecoveryWriterFixture @ sysbus 0x4003b000
    cpu: cpu
    nvic: nvic
    initialTick: {tick}
    returnPc: {return_pc}
    writerPc: {writer_pc}
    recvPc: {recv_pc}
    sendPc: {send_pc}
    destination: {destination}
    fullMainRestore: {full}
    bootRestore: {boot_restore}
    length: {length}
    romStatus: {rom_status}
    corruptReadback: {corrupt}
    interruptAfterWords: {interrupt_words}
'''.format(destination=destination,full=str(full).lower(),boot_restore=str(boot_restore).lower(),tick=manifest['tick'], return_pc=state['LR'] & ~1, writer_pc=manifest['worker']['boundary']['entry'] & ~1,
           recv_pc=functions['recv_input'], send_pc=functions['send_output'], length=manifest['payload_bytes'], rom_status=rom_status, corrupt=str(corrupt).lower(), interrupt_words=interrupt_after_words)
    private_write(output / 'board.repl', board.encode())
    # Replay requests only; expected responses are checked against actual ARM UART output.
    spec = importlib.util.spec_from_file_location('frozen_recovery_protocol', capture / 'protocol.py')
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    data = (capture / 'payload.bin').read_bytes()
    incoming = bytearray()
    expected = []
    for offset in range(0, len(data), 256):
        chunk = data[offset:offset + 256]
        expected.append(protocol.block(protocol.BLOCK_REQUEST, struct.pack('<H', len(chunk))))
        incoming.extend(protocol.block(protocol.BLOCK_INPUT, chunk))
        if rom_status or corrupt:
            break
        expected.append(protocol.block(protocol.BLOCK_OUTPUT, struct.pack('<I', offset + len(chunk))))
        incoming.extend(protocol.block(protocol.BLOCK_ACK))
    result = (rom_status | 0x08000100) if rom_status else 3 if corrupt else 0
    expected.append(protocol.reply(protocol.RESULT, data=struct.pack('<I', result)))
    private_write(output / 'uart-input.bin', incoming)
    setup = '''import json
from System.IO import File
m=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];uart=m['sysbus.uart']
snapshot=json.loads(File.ReadAllText('/work/snapshot.json'));r=snapshot['registers']
m['sysbus.mram'].Arm()
uart.AttachCache()
cpu.FpuEnabled=True
for n in range(13):uart.SeedRegister(n,r['R'+str(n)])
uart.SeedRegister(13,r['SP']);uart.SeedRegister(14,r['LR'])
for index,name in [(18,'CONTROL'),(19,'BASEPRI'),(25,'XPSR'),(28,'PRIMASK'),(30,'FAULTMASK')]:uart.SeedRegister(index,r[name]|4 if name=='CONTROL' else r[name])
uart.SeedRegister(22,r['PSP']);uart.SeedRegister(27,0xf00000);uart.SeedRegister(31,0xffff);uart.SeedRegister(74,0)
for n in range(32):uart.SeedRegister(75+n,0x3f800000+n*100)
initial_regs=[int(cpu.GetRegister(n).RawValue) for n in range(15)]
initial_special=dict((str(n),int(cpu.GetRegister(n).RawValue)) for n in [18,19,25,28,30,31,74])
initial_float=[int(cpu.GetRegister(75+n).RawValue) for n in range(32)]
uart.Enqueue(File.ReadAllBytes('/work/uart-input.bin'))
uart.SeedRegister(15,r['PC']|1)
'''
    private_write(output / 'setup.py', setup.encode())
    report_script = '''import json
from System import Console
from System.IO import File
answer=dict(host_limit_reached=runner_host_limit_reached,cpu_halted=bool(cpu.IsHalted),code_invalidations=int(uart.CodeInvalidations),changed_code_fetches=int(uart.ChangedCodeFetches),first_changed_code_pc=int(uart.FirstChangedCodePc),original_code_word=int(uart.OriginalCodeWord),updated_code_word=int(uart.UpdatedCodeWord),power_interrupted=bool(uart.PowerInterrupted),result_seen=bool(uart.ResultSeen),violations=int(uart.Violations),context_entries=int(uart.ContextEntries),context_returns=int(uart.ContextReturns),writer_entries=int(uart.WriterEntries),stock_mram_entries=int(uart.StockMramEntries),rom_calls=int(uart.RomCalls),programmed_bytes=int(uart.ProgrammedBytes),receive_calls=int(uart.ReceiveCalls),send_calls=int(uart.SendCalls),frames=[[int(v) for v in frame] for frame in uart.Frames],body=[int(b.ReadByte(0x438010+n)) for n in range(snapshot['payload_bytes'])],vectors=[int(b.ReadByte(0x438000+n)) for n in range(16)],destinations=[int(v) for v in uart.ProgramDestinations],lengths=[int(v) for v in uart.ProgramLengths],initial_regs=initial_regs,return_regs=[int(v) for v in uart.ReturnRegisters],initial_special=initial_special,return_special=dict((str(n),int(uart.ReturnSpecial[n])) for n in uart.ReturnSpecial.Keys),initial_float=initial_float,return_float=[int(v) for v in uart.ReturnFloat],pc=int(cpu.PC.RawValue),mram_control_writes=int(m['sysbus.mram_control'].Writes))
File.WriteAllBytes('/work-output/final-mram.bin',b.ReadBytes(0x400000,0x400000,True))
Console.WriteLine('BLACKWALL_RECOVERY_WRITER '+json.dumps(answer))
Console.WriteLine('BLACKWALL_RECOVERY_CACHE '+json.dumps([int(v) for v in uart.CacheLines]))
Console.WriteLine('BLACKWALL_RECOVERY_FAILURE '+json.dumps(dict(reason=str(uart.Failure),address=int(uart.FailureAddress))))
Console.WriteLine('BLACKWALL_RECOVERY_DIAGNOSTIC '+json.dumps(dict(halted=bool(cpu.IsHalted),blocks=int(uart.Blocks),last_block=int(uart.LastBlock),registers=dict((str(n),int(cpu.GetRegister(n).RawValue)) for n in list(range(16))+[18,19,25,27,28,30,31,32,74]),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),fpccr=int(b.ReadDoubleWord(0xe000ef34)))))
'''
    if compact:
        report_script=report_script.replace("frames=[[int(v) for v in frame] for frame in uart.Frames]", "frames=[]")
        report_script=report_script.replace("body=[int(b.ReadByte(0x438010+n)) for n in range(snapshot['payload_bytes'])]", "body=[]")
        report_script="from System.IO import MemoryStream\nstream=MemoryStream()\nfor frame in uart.Frames:stream.Write(frame,0,frame.Length)\nFile.WriteAllBytes('/work-output/frames.bin',stream.ToArray())\n"+report_script
        # File is imported by setup.py in the same runtime before this script.
    private_write(output / 'result.py', report_script.encode())
    setup += '''
import time
from Antmicro.Renode.Core import EmulationManager
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not m.IsPaused and not cpu.IsHalted and not uart.ResultSeen and not uart.PowerInterrupted and time.time()<deadline:time.sleep(0.001)
runner_host_limit_reached=time.time()>=deadline
m.Pause()
'''
    if compact:
        setup=setup.replace('deadline=time.time()+5','deadline=time.time()+'+('120' if boot_restore else '540')+';next_progress=time.time()+5')
        setup=setup.replace('time.sleep(0.001)', '''
 if time.time()>=next_progress:
  File.WriteAllText('/work-output/progress.json',json.dumps(dict(programmed_bytes=int(uart.ProgrammedBytes),rom_calls=int(uart.RomCalls),pc=int(cpu.PC.RawValue),result=bool(uart.ResultSeen))))
  next_progress=time.time()+5
 time.sleep(0.001)''')
    (output / 'setup.py').write_text(setup)
    private_write(output / 'probe.resc', b'include @/work/fixture.cs\nmach create "recovery-writer"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/mram.bin 0x400000\nsysbus LoadBinary @/work/sram.bin 0x20000000\ninclude @/work/setup.py\ninclude @/work/result.py\nquit\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={output},target=/work,readonly', '--mount', f'type=bind,source={output / "exports"},target=/work-output', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], output, 'renode', timeout=180 if boot_restore else 600 if full else 45,stream=compact)
    rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_RECOVERY_WRITER ')]
    if len(rows) != 1:
        raise ValueError('Missing writer result; inspect frozen log')
    actual = rows[0]
    final=(output/'exports/final-mram.bin').read_bytes()
    before=(output/'mram.bin').read_bytes()
    if compact:
        actual['body']=final[destination-0x400000:destination-0x400000+len(data)]
        actual['frames_match']=(output/'exports/frames.bin').read_bytes()==b''.join(expected)
    bad = [line for line in log.splitlines() if (('[WARNING]' in line and 'Translation cache size' not in line) or '[ERROR]' in line or 'There was an error' in line)]
    expected_body = bytearray(before[destination-0x400000:destination-0x400000+len(data)])
    if not rom_status:
        written = min(256, len(data)) if corrupt else len(data)
        expected_body[:written] = data[:written]
        if corrupt:
            expected_body[0] ^= 1
    checks = dict(no_runtime_diagnostics=not bad, result=actual['result_seen'], guard=actual['violations'] == 0,
                  context=actual['context_entries'] == actual['context_returns'] == actual['writer_entries'] == 1,
                  registers=actual['initial_regs'] == actual['return_regs'], special=actual['initial_special'] == actual['return_special'],
                  floating=actual['initial_float'] == actual['return_float'], frames=actual['frames_match'] if compact else [bytes(frame) for frame in actual['frames']] == expected,
                  vectors=bytes(actual['vectors']) == (bytes(expected_body) if destination==0x438000 else before[0x38000:0x38010]),
                  body=bytes(actual['body']) == bytes(expected_body))
    expected_mram=bytearray(before)
    expected_mram[destination-0x400000:destination-0x400000+len(expected_body)]=expected_body
    if interrupt_after_words>=0:
        written=interrupt_after_words*4
        expected_mram=bytearray(before);expected_mram[destination-0x400000:destination-0x400000+written]=data[:written]
        # A cut at a block boundary occurs before that block's progress report.
        complete_before_cut=max(0,(written-1)//256)
        prefix=[]
        for i in range(complete_before_cut+1):
            size=min(256,len(data)-i*256)
            if size<=0:break
            prefix.append(protocol.block(protocol.BLOCK_REQUEST,struct.pack('<H',size)))
            if i<complete_before_cut:prefix.append(protocol.block(protocol.BLOCK_OUTPUT,struct.pack('<I',(i+1)*256)))
        checks=dict(no_runtime_diagnostics=not bad,interrupted=actual['power_interrupted'] is True,
                    no_result=not actual['result_seen'],no_context_return=actual['context_returns']==0,
                    guard=actual['violations']==0,writer=actual['writer_entries']==actual['context_entries']==1,
                    programmed_prefix=actual['programmed_bytes']==written,
                    vectors=bytes(actual['vectors'])==before[0x38000:0x38010],
                    frames=(output/'exports/frames.bin').read_bytes()==b''.join(prefix) if compact else [bytes(frame) for frame in actual['frames']]==prefix)
    checks['whole_mram_expected']=final==bytes(expected_mram)
    if compact:
        actual['body_sha256']=sha(bytes(actual.pop('body')))
        actual['uart_frames_sha256']=sha((output/'exports/frames.bin').read_bytes())
    report = dict(destination=destination,full_main_restore=full,boot_restore=boot_restore,interrupt_after_words=interrupt_after_words,final_mram_sha256=sha(final),passed=all(checks.values()), checks=checks, observed=actual, diagnostics=bad,
                  rom_programming_modeled=True, hardware_accessed=False, full_boot_verified=False, recovery_verified=False,
                  assumptions=['Unicorn GPR/control/SRAM/MRAM bridge; M55 extension seed explicit', 'prequeued UART input replay, no physical timing', 'ROM programming and stock GPIO/time/power/IRQ helpers modeled'],
                  extension_seed=dict(fpu_enabled=True, control_fpca=True, vpr=0xffff, s_register_pattern=True, limits_zero=True),
                  sha256={name: sha((output / name).read_bytes()) for name in ['snapshot.json', 'sram.bin', 'mram.bin', 'payload.bin', 'fixture.cs', 'runner-source.py', 'board.repl', 'uart-input.bin', 'setup.py', 'result.py', 'probe.resc', 'renode.log']})
    private_write(output / 'report.json', (json.dumps(report, indent=2) + '\n').encode())
    if not report['passed'] and not allow_incomplete:
        raise ValueError('Writer contract failed: ' + str(checks) + ' ' + str(bad))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    manifest = prepare_capture(args.candidate, args.output / 'capture', bytes(range(256)) * 2)
    for name, status, corrupt in [('success', 0, False), ('rom-failure', 7, False), ('readback-mismatch', 0, True)]:
        report = run_case(args.output / 'capture', args.output / name, status, corrupt)
        print(json.dumps(dict(case=name, passed=report['passed'], rom_calls=report['observed']['rom_calls'])), flush=True)


if __name__ == '__main__':
    main()
