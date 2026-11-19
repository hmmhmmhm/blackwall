"""Audit saved native draw -> diagnostic GPU -> original IRQ28 captures."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve audit evidence')
    s = args.simulator
    inputs = [(s/'nema-native-irq-final-01'/case,case,'enabled') for case in ['stock24','stock23','cfw']]
    inputs += [(s/'nema-native-irq-disabled-02/stock24','stock24','disabled'),
               (s/'nema-native-irq-default-regression-02/stock24','stock24','default')]
    hashes = dict(stock24='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',
                  stock23='fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5',
                  cfw='4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f')
    checks, captures = [], []
    def check(name, value):
        checks.append(dict(name=name, passed=bool(value)))
        if not value:
            raise ValueError(name)
    for folder, case, mode in inputs:
        name = mode+'-'+case
        report = json.loads((folder/'report.json').read_text())
        actual = report['actual']
        for file, digest in report['input_hashes'].items():
            check(name+'-input-'+file, sha(folder/file) == digest)
        check(name+'-main-pin', sha(folder/'main.bin') == hashes[case])
        check(name+'-runner-checks', report['passed'] and all(report['checks'].values()))
        check(name+'-scope', report['hardware_accessed'] is False and report['full_main_rendered'] is False and report['hardware_gpu_validated'] is False)
        log = (folder/'renode.log').read_text()
        rows = [json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_SUBMIT_M55 ')]
        check(name+'-native-result-log', rows == [actual])
        check(name+'-no-runtime-error', not any(x in log for x in ['Unhandled exception','BLACKWALL_RUNTIME_ERROR','Could not execute']))
        work = (folder/'result/final-work.bin').read_bytes()
        before_work = (folder/'work.bin').read_bytes()
        before_sram = (folder/'sram.bin').read_bytes()
        after_sram = (folder/'result/final-sram.bin').read_bytes()
        check(name+'-output-pins', hashlib.sha256(work).hexdigest() == report['final_work_sha256'] and hashlib.sha256(after_sram).hexdigest() == report['final_sram_sha256'])
        check(name+'-cold-command-input', before_work[0x4000:0x5000] == b'\xa5'*4096)
        check(name+'-frame-actual-guest-memory', work[0xa000:0xa800] == (folder/'expected-frame.bin').read_bytes())
        prior_frame = (s/'nema-live-draw-framebuffer-01'/case/'result/final-work.bin').read_bytes()[0xa000:0xa800]
        check(name+'-same-prior-verified-pixels', work[0xa000:0xa800] == prior_frame)
        check(name+'-oracle-not-loaded', 'expected-frame' not in (folder/'probe.resc').read_text() and 'expected-frame' not in (folder/'setup.py').read_text())
        check(name+'-gpu-frame', actual['reference_gpu']['frames'] == 1 and actual['reference_gpu']['queued_id'] == 8 and actual['reference_gpu']['words'] == 42)
        check(name+'-no-architectural-fault', actual['cfsr'] == actual['hfsr'] == 0)
        if mode != 'default':
            profile = json.loads((folder/'irq-profile.json').read_text())
            source = Path(profile['source'])
            check(name+'-source-capture-pins', all(sha(source/f) == digest for f,digest in profile['source_hashes'].items()))
            state, = json.loads((source/'report.json').read_text())['diagnostics']['records']
            check(name+'-real-captured-semaphore', profile['queue'] == state['handle'] and state['queue_words'][14:17] == [0,1,0] and state['queue_words'][9] == 0)
            check(name+'-captured-queue-bytes', before_sram[profile['queue']-0x20000000:profile['queue']-0x20000000+96] == struct.pack('<24I',*state['queue_words']))
            original_sram = bytearray((s/'nema-submission-contract-02/captures'/case/'sram.bin').read_bytes())
            for region in profile['restored_regions']:
                start = region['address']-0x20000000
                data = before_sram[start:start+region['bytes']]
                check(name+'-restored-region-'+hex(region['address']), hashlib.sha256(data).hexdigest() == region['sha256'])
                original_sram[start:start+len(data)] = data
            check(name+'-only-declared-sram-preparation', bytes(original_sram) == before_sram)
            raw = (folder/'main.bin').read_bytes()
            check(name+'-original-vector', profile['handler'] == struct.unpack_from('<I',raw,44*4)[0]&~1 and profile['pendsv'] == struct.unpack_from('<I',raw,14*4)[0]&~1)
            check(name+'-real-nvic-wiring', 'IRQ -> nvic@28' in (folder/'board.repl').read_text() and '-> cpu@0' in (folder/'board.repl').read_text())
            c = actual['gpu_completion']
            if mode == 'enabled':
                expected = bytearray(before_sram)
                struct.pack_into('<I',expected,profile['last_address']-0x20000000,8)
                struct.pack_into('<I',expected,profile['count_address']-0x20000000,1)
                check(name+'-only-original-publication', bytes(expected) == after_sram)
                check(name+'-irq28', c['irq_entries'] == 1 and c['entry_xpsr']&0x1ff == 44)
                check(name+'-stable-clid-and-ack', c['clid_reads'] == 2 and c['acks'] == 1 and not c['line'])
                check(name+'-original-id-and-count', c['last_id'] == 8 and c['messages'] == 1)
                check(name+'-r3-not-forced-zero', c['entry_r3'] == 0x2100b000)
                check(name+'-actual-pendsv-boundary', c['pendsv_entries'] == 1 and actual['boundary'] == 'rtos-context-required' and actual['registers'][15] == profile['pendsv'])
                check(name+'-first-mrs-not-run', profile['inactive_psp'] == 0x2100d000 and actual['registers'][0] == c['pendsv_entry_r0'] != profile['inactive_psp'])
                check(name+'-draw-returned-submit-interrupted', [p['marker'] for p in actual['live_phases']] == [1,2,3,4,5,0])
            else:
                check(name+'-nvic-disabled-control', c['irq_entries'] == c['pendsv_entries'] == c['clid_reads'] == c['acks'] == 0 and c['line'])
                check(name+'-no-fake-publication', c['last_id'] == 0xffffffff and c['messages'] == 0 and before_sram == after_sram)
                check(name+'-all-calls-returned', actual['boundary'] == 'return' and [p['marker'] for p in actual['live_phases']] == [1,2,3,4,5,6])
        else:
            check(name+'-default-no-completion', report['completion_injected'] is False and before_sram == after_sram and actual['boundary'] == 'return')
            prior = (s/'nema-live-draw-framebuffer-01/stock24/result/final-work.bin').read_bytes()
            check(name+'-default-prior-work-exact', work == prior)
        captures.append(dict(case=case,mode=mode,path=str(folder),report_sha256=sha(folder/'report.json'),log_sha256=sha(folder/'renode.log'),frame_sha256=hashlib.sha256(work[0xa000:0xa800]).hexdigest()))
    args.output.mkdir(parents=True,mode=0o700)
    (args.output/'audit.py').write_bytes(Path(__file__).read_bytes())
    result = dict(passed=True,checks=checks,captures=captures,native_rerun=False,
                  original_irq28_executed=True,full_rtos_context=False,hardware_accessed=False,full_main_rendered=False)
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),captures=len(captures))))


if __name__ == '__main__':
    main()
