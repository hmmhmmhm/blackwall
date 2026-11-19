"""Audit bounded, read-only RTOS captures; execute only the original leaf query.

This neither reconstructs a runnable task nor delivers an interrupt. TCB offsets
other than the first saved-SP word remain uninterpreted capture bytes.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_EXEC
import unicorn.arm_const as arm
from inspect_nema_irq_contract import discover_irq
from native_replay import FILES, MAIN_LAYOUT, validate_assets
from run_native_candidate import observe, evaluate_semantics

BASE, SRAM, STOP = 0x438000, 0x20000000, 0x10000000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query_original(raw, contract, values):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    size = (len(raw) + 4095) & ~4095
    u.mem_map(BASE, size)
    u.mem_write(BASE, raw)
    u.mem_protect(BASE, size, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_map(SRAM, 0x80000)
    for address, value in zip(contract['scheduler_slots'], values):
        u.mem_write(address, struct.pack('<I', value))
    u.mem_protect(SRAM, 0x80000, UC_PROT_READ)
    u.mem_map(STOP, 4096)
    u.reg_write(arm.UC_ARM_REG_LR, STOP | 1)
    u.reg_write(arm.UC_ARM_REG_XPSR, 0x01000000)
    u.emu_start(contract['scheduler_query'] | 1, STOP, count=32)
    if u.reg_read(arm.UC_ARM_REG_PC) != STOP:
        raise ValueError('Original scheduler query did not return')
    return u.reg_read(arm.UC_ARM_REG_R0)


def inspect(simulator, captures, plan, case):
    folder = captures / case
    source = simulator / plan['source_root'] / case
    manifest = json.loads((folder / 'derived-inputs.json').read_text())
    validate_assets(folder, manifest['derived'])
    validate_assets(source, manifest['base'])
    report = json.loads((folder / 'report.json').read_text())
    prior = json.loads((source / 'report.json').read_text())
    log = (folder / 'renode.log').read_text()
    observed, kind = observe(log)
    def marker(name):
        rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines()
                if line.startswith(name + ' ')]
        if len(rows) != 1:
            raise ValueError('Missing unique ' + name)
        return rows[0]
    checks = []
    def check(name, value):
        checks.append(dict(name=name, passed=bool(value)))
        if not value:
            raise ValueError(case + ': ' + name)
    check('native-report-matches-log', report['observed'] == observed and report['boundary_kind'] == kind)
    check('diagnostics-match-log', report['diagnostics'] == marker('BLACKWALL_CANDIDATE_' + plan['id']))
    check('events-match-log', report['selected_observation'] == marker('BLACKWALL_OBSERVATION'))
    check('original-execution-unchanged', observed == prior['observed'] and report['selected_observation'] == prior['selected_observation'])
    check('schema2-semantics', evaluate_semantics(report, prior, plan['semantics'][case]['candidate'])['passed'])
    check('no-runtime-or-board-edits', not plan['runtime_edits'] and not plan.get('board_edits') and not plan['components'])
    check('executable-inputs-identical', all(digest(folder / f) == digest(source / f)
          for f in FILES if f not in ('run.py',)))
    check('paused-before-diagnostics', report['diagnostics']['paused'])
    check('captured-plan-identical', json.loads((folder / 'plan.json').read_text()) == plan)
    runtime = (source / 'run.py').read_text()
    anchor = "    Console.WriteLine('BLACKWALL_REPORT "
    insertion = "    Console.WriteLine('BLACKWALL_CANDIDATE_" + plan['id'] + " '+json.dumps(" + plan['diagnostics'] + "))\n"
    check('only-post-stop-runtime-insertion', runtime.count(anchor) == 1 and
          (folder / 'run.py').read_text() == runtime.replace(anchor, insertion + anchor))
    raw = (folder / 'main.bin').read_bytes()
    check('pinned-original-main', hashlib.sha256(raw).hexdigest() == MAIN_LAYOUT[plan['cases'][case]][3])
    contract = discover_irq(raw)
    kernel, = report['diagnostics']['kernel']
    check('source-discovered-kernel-slots', kernel['slots'] == contract['scheduler_slots'] + [contract['current_tcb_slot']])
    check('tcb-pointer-equals-global', kernel['values'][2] == kernel['tcb'])
    check('bounded-tcb', SRAM <= kernel['tcb'] <= 0x20380000 - 512 and kernel['tcb'] % 4 == 0 and len(kernel['tcb_words']) == 128)
    regs = {r['index']: r for r in report['diagnostics']['registers']}
    check('runtime-register-aliases', regs[13]['aliases'] == ['SP', 'R13'] and regs[18]['aliases'] == ['Control'] and regs[22]['aliases'] == ['OtherSP'])
    check('general-registers-match-main', all(regs[i]['value'] == observed['register_context']['r' + str(i)] for i in range(16)))
    check('stack-addresses-from-captured-values', [s['address'] for s in kernel['stacks']] == [regs[13]['value'], regs[22]['value'], kernel['tcb_words'][0]])
    for index, stack in enumerate(kernel['stacks']):
        check('bounded-stack-' + str(index), stack['valid'] and SRAM <= stack['address'] <= 0x20380000 - 512 and stack['address'] % 4 == 0 and len(stack['words']) == 128)
    check('thread-mode', regs[25]['value'] & 0x1ff == 0)
    check('psp-selected', bool(regs[18]['value'] & 2))
    result = query_original(raw, contract, kernel['values'][:2])
    check('original-query-returns-running-code', result == 2 and kernel['values'][:2] == [1, 0])
    check('saved-sp-is-not-current-sp', kernel['tcb_words'][0] != regs[13]['value'])
    return dict(case=case, checks=checks, passed=True,
                kernel_slots=kernel['slots'], kernel_values=kernel['values'], current_tcb=kernel['tcb'],
                saved_sp=kernel['tcb_words'][0], current_psp=regs[13]['value'],
                other_sp_uninterpreted=regs[22]['value'], control=regs[18]['value'],
                xpsr=regs[25]['value'], basepri=regs[19]['value'], primask=regs[28]['value'],
                faultmask=regs[30]['value'], original_scheduler_query_return=result,
                psplim_captured=False, irq_delivered=False, scheduler_executed=False,
                capture_pins={name:digest(folder / name) for name in
                              list(FILES) + ['report.json', 'renode.log', 'derived-inputs.json', 'plan.json']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('captures', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing audit')
    plan = json.loads((args.captures / 'stock24/plan.json').read_text())
    rows = [inspect(args.simulator, args.captures, plan, case) for case in plan['cases']]
    args.output.mkdir(parents=True)
    (args.output / 'inspector.py').write_bytes(Path(__file__).read_bytes())
    answer = dict(passed=all(r['passed'] for r in rows), cases=rows,
                  checks=sum(len(r['checks']) for r in rows), native_rerun=False,
                  hardware_accessed=False, full_main_booted=False, display_completed=False)
    (args.output / 'report.json').write_text(json.dumps(answer, indent=2) + '\n')
    print(json.dumps(dict(passed=answer['passed'], checks=answer['checks'],
                         states=[{k:r[k] for k in ['case','kernel_values','current_psp','saved_sp',
                                                   'other_sp_uninterpreted','original_scheduler_query_return']} for r in rows])))


if __name__ == '__main__':
    main()
