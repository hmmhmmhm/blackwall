import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_native_candidate as runner


class SemanticContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(runner, 'evaluate_semantics', None)),
                        'The runner must evaluate a semantic contract separately from capture success')
        self.prior = dict(selected_observation=dict(events=[{'event': 1}], sequence=1, dropped_events=0),
                          diagnostics=dict(tx_bytes=[1, 2], irq_entries=8))
        self.result = dict(boundary_kind='strict-mmio', observed=dict(pc=0x488e90, guards=[
            dict(accesses=1, address=0x40021004, operation='write', width=4, value=0x8e80)]),
            selected_observation=dict(events=[{'event': 1}, {'event': 2}], sequence=2, dropped_events=0),
            diagnostics=dict(tx_bytes=[1, 2], irq_entries=8, no_ops=2))
        self.spec = dict(boundary=dict(kind='strict-mmio', pc=0x488e90, address=0x40021004,
                                      operation='write', width=4, value=0x8e80),
                         comparison=dict(policy='prefix', path=['selected_observation', 'events']),
                         checks=[dict(path=['diagnostics', 'no_ops'], eq=2),
                                 dict(path=['diagnostics', 'tx_bytes'], eq_source=['diagnostics', 'tx_bytes']),
                                 dict(path=['diagnostics', 'irq_entries'], eq_source=['diagnostics', 'irq_entries'])],
                         allowed_differences=['The candidate extends the prior event prefix'],
                         unresolved_differences=['Physical timing is not verified'])

    def evaluate(self):
        return runner.evaluate_semantics(self.result, self.prior, self.spec)

    def test_saved_state_satisfies_contract(self):
        answer = self.evaluate()
        self.assertTrue(answer['passed'], answer)
        self.assertEqual(answer['unresolved_differences'], self.spec['unresolved_differences'])

    def test_wrong_frontier_value_fails_even_at_same_pc(self):
        self.result['observed']['guards'][0]['value'] = 0xe80
        self.assertFalse(self.evaluate()['passed'])

    def test_prefix_change_fails(self):
        self.result['selected_observation']['events'][0]['event'] = 99
        self.assertFalse(self.evaluate()['passed'])

    def test_lost_events_fail(self):
        self.result['selected_observation']['dropped_events'] = 1
        self.assertFalse(self.evaluate()['passed'])

    def test_irq_or_bytes_changed_fails(self):
        for name, value in [('irq_entries', 9), ('tx_bytes', [1, 3])]:
            with self.subTest(name=name):
                old = self.result['diagnostics'][name]
                self.result['diagnostics'][name] = value
                self.assertFalse(self.evaluate()['passed'])
                self.result['diagnostics'][name] = old

    def test_missing_path_and_type_confusion_fail(self):
        self.spec['checks'][0]['eq'] = True
        self.result['diagnostics']['no_ops'] = 1
        self.assertFalse(self.evaluate()['passed'])
        del self.result['diagnostics']['no_ops']
        self.assertFalse(self.evaluate()['passed'])

    def test_subsequence_accepts_ordered_insertions_and_rejects_reorder(self):
        self.spec['comparison']['policy'] = 'subsequence'
        self.prior['selected_observation']['events'] = [1, 2]
        self.result['selected_observation']['events'] = [0, 1, 3, 2]
        self.result['selected_observation']['sequence'] = 4
        self.assertTrue(self.evaluate()['passed'])
        self.result['selected_observation']['events'] = [2, 0, 3, 1]
        self.assertFalse(self.evaluate()['passed'])

    def test_exact_and_bounded_invariants(self):
        self.spec['comparison'] = dict(policy='exact', path=['selected_observation'])
        self.assertFalse(self.evaluate()['passed'])
        self.result['selected_observation'] = copy.deepcopy(self.prior['selected_observation'])
        self.assertTrue(self.evaluate()['passed'])
        self.spec['comparison'] = dict(policy='bounded-invariants', paths=[['diagnostics', 'tx_bytes']])
        self.assertTrue(self.evaluate()['passed'])
        self.result['diagnostics']['tx_bytes'].append(9)
        self.assertFalse(self.evaluate()['passed'])

    def test_capture_pass_cannot_hide_semantic_failure(self):
        self.assertTrue(callable(getattr(runner, 'finish_capture', None)))
        self.result['observed']['guards'][0]['value'] = 0xe80
        answer = runner.finish_capture(self.result, self.prior, self.spec)
        self.assertTrue(answer['execution_passed'])
        self.assertFalse(answer['semantic_validation']['passed'])
        self.assertFalse(answer['passed'])

    def test_schema_two_requires_candidate_and_control_for_every_case(self):
        self.assertTrue(callable(getattr(runner, 'semantic_spec', None)))
        plan = dict(schema=2, cases=dict(stock23='stock_base'))
        with self.assertRaises(ValueError):
            runner.semantic_spec(plan, 'stock23', False)
        plan['semantics'] = dict(stock23=dict(candidate=self.spec, control=self.spec))
        self.assertEqual(runner.semantic_spec(plan, 'stock23', False), self.spec)
        legacy = runner.finish_capture(self.result, self.prior, None)
        self.assertTrue(legacy['execution_passed'])
        self.assertIsNone(legacy['semantic_validation']['passed'])

    def test_named_guard_reason_is_an_exact_frontier_operation(self):
        self.spec['boundary']['operation'] = 'cq-external-flags-unknown'
        self.result['observed']['guards'][0]['operation'] = 'cq-external-flags-unknown'
        self.assertTrue(self.evaluate()['passed'])
        self.spec['boundary']['operation'] = 'read'
        self.assertFalse(self.evaluate()['passed'])

    def test_reviewed_capture_source_has_an_explicit_acceptance_gate(self):
        self.assertTrue(callable(getattr(runner, 'source_acceptance', None)),
                        'A frozen semantic-failure capture needs hash-pinned review acceptance before reuse')
        with self.assertRaises(ValueError):
            runner.source_acceptance(Path('/unused'), Path('/unused/capture'), {'passed': False}, {}, 'stock24')
        self.assertIsNone(runner.source_acceptance(Path('/unused'), Path('/unused/capture'), {'passed': True}, {}, 'stock24'))

    def test_unknown_or_vacuous_contract_rejected(self):
        for change in [dict(comparison=dict(policy='anything')), dict(checks=[]), dict(boundary={})]:
            with self.subTest(change=change):
                spec = dict(self.spec, **change)
                with self.assertRaises(ValueError):
                    runner.evaluate_semantics(self.result, self.prior, spec)


if __name__ == '__main__':
    unittest.main()
