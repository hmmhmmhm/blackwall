"""Audit opt-in blank NVdb progress without treating synthetic factory data as real."""
import argparse
import json
from pathlib import Path
from native_replay import parse_log, validate_assets, boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.mkdir(mode=0o700)
    s, checks, cases = a.simulator, [], []
    def check(name, value):
        if not value:
            raise ValueError(name)
        checks.append(name)
    def marker(log, name):
        rows = [json.loads(l.split(' ', 1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        check(name+'-unique', len(rows) == 1)
        return rows[0]
    for key, bundle in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        d = s/'nvdb-blank-main-02'/key
        report = json.loads((d/'report.json').read_text())
        log = (d/'renode.log').read_text()
        observed = parse_log(log)
        validate_assets(d, json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(key+'-native-report', observed == report['observed'])
        check(key+'-current-model', (d/'strict.cs').read_bytes() == models(s))
        _, raw = load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
        check(key+'-original-main', raw == (d/'main.bin').read_bytes())
        obs = marker(log, 'BLACKWALL_OBSERVATION')
        check(key+'-bounded-observation', obs['capacity'] == 4096 and not obs['dropped_events'] and len(obs['events']) == obs['sequence'])
        prior = json.loads((s/'mspi1-program-main-02'/key/'report.json').read_text())
        projected = [dict(e,sequence=i+1) for i,e in enumerate(e for e in obs['events'] if not e['label'].startswith('NVdb-'))]
        check(key+'-KV-prefix-preserved', projected[:len(prior['selected_observation']['events'])] == prior['selected_observation']['events'])
        points = {r['label']:r for r in obs['points']}
        events = {r['label']:r for r in obs['events'] if r['label'].startswith('NVdb-')}
        check(key+'-init-return-zero', points['NVdb-DB-init-return']['hits'] == 1 and events['NVdb-DB-init-return']['r0'] == 0)
        check(key+'-magic-read-four-bytes', points['NVdb-magic-read-return']['hits'] == 1 and events['NVdb-magic-read-return']['r0'] == 4)
        check(key+'-no-magic-rebuild-or-whole-init-return', all(points[n]['hits'] == 0 for n in ['NVdb-magic-rebuild-call','NVdb-magic-rebuild-return','NVdb-initializer-return']))
        table = points['NVdb-initializer-entry']['snapshot']['words'] + points['NVdb-default-tail']['snapshot']['words']
        check(key+'-nine-default-descriptors', len(table) == 27)
        entries = []
        for i in range(9):
            keyptr, valueptr, length = table[i*3:i*3+3]
            check(key+'-default-bounds-'+str(i), 0x438000 <= keyptr < 0x438000+len(raw) and 0x20000000 <= valueptr < 0x20380000 and 0 < length <= 256 and valueptr+length <= 0x20380000)
            end = raw.find(b'\0', keyptr-0x438000, keyptr-0x438000+40)
            check(key+'-key-terminated-'+str(i), end >= 0)
            entries.append(dict(key=raw[keyptr-0x438000:end].decode('ascii'), value_address=valueptr, bytes=length))
        cfg = marker(log,'BLACKWALL_MSPI1_CONFIG')['registers']
        guards = [g for g in observed['guards'] if g['accesses']]
        check(key+'-172-byte-read-still-guarded', len(guards) == 1 and guards[0]['address'] == 0x40061000 and guards[0]['value'] == 0xac0461 and cfg['12'] == 0x6c)
        check(key+'-destination-matches-default', observed['stack_context']['words'][2:4] == [entries[3]['value_address'],172] and entries[3]['bytes'] == 172)
        array = marker(log,'BLACKWALL_NOR_ARRAY')
        check(key+'-explicit-two-partition-window', array['start'] == 0x1fc0000 and array['length'] == 0x40000 and not array['physical_contents_known'] and report['nor_scenario'] == 'synthetic-blank-kvdb-and-nvdb')
        pg, er = marker(log,'BLACKWALL_NOR_PROGRAM'), marker(log,'BLACKWALL_NOR_ERASE')
        check(key+'-program-and-erase-completed', pg['starts'] == pg['completions'] == 242 and er['starts'] == er['completions'] == 128 and not pg['busy'] and not er['busy'])
        nv = marker(log,'BLACKWALL_NVDB_SCENARIO')
        check(key+'-NV-header-and-no-physical-claim', nv['prefix_words'][1] == 0x30424446 and not nv['physical_factory_data_known'] and not report['hardware_validated'] and not report['boot_verified'] and not report['display_verified'])
        cases.append(dict(case=key,program=pg,erase=er,defaults=entries,events=obs['sequence'],next_read_address=hex(cfg['8'])))
    baseline = s/'nvdb-blank-default-main-01'
    r = json.loads((baseline/'report.json').read_text())
    baseline_log = (baseline/'renode.log').read_text()
    validate_assets(baseline, json.loads((baseline/'derived-inputs.json').read_text())['derived'])
    check('default-native-log-report', parse_log(baseline_log) == r['observed'])
    check('default-current-model', (baseline/'strict.cs').read_bytes() == models(s))
    _, original = load_pinned_main((s/'inputs/verified-01/stock-2.4.0.24.bin').read_bytes())
    check('default-original-main', original == (baseline/'main.bin').read_bytes())
    baseline_obs = marker(baseline_log,'BLACKWALL_OBSERVATION')
    check('default-no-drop', not baseline_obs['dropped_events'] and len(baseline_obs['events']) == baseline_obs['sequence'])
    check('default-no-NVdb-hooks', not any(p['label'].startswith('NVdb-') for p in baseline_obs['points']) and 'BLACKWALL_NVDB_SCENARIO ' not in baseline_log)
    old = json.loads((s/'mspi1-program-main-02/stock24/report.json').read_text())
    check('default-KV-boundary-unchanged', boundary_state(r['observed']) == boundary_state(old['observed']) and r['nor_scenario'] == 'synthetic-blank-kvdb')
    check('default-board-unchanged', (baseline/'board.repl').read_bytes() == (s/'mspi1-program-main-02/stock24/board.repl').read_bytes())
    cli = json.loads((s/'nvdb-blank-cli-01/report.json').read_text())
    check('five-missing-prerequisites-rejected', cli['passed'] and cli['count'] == 5 and all(c['rejected_before_output'] and c['exit_code'] == 2 for c in cli['cases']))
    result = dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Synthetic blank NVdb DB-init success and next long-read boundary; whole factory init, real factory data, boot and display unverified')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,count=len(checks))))


if __name__ == '__main__':
    main()
