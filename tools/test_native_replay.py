"""Small host-side checks for fail-before-run asset validation and boundary comparison."""
import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from native_replay import validate_assets, boundary_state, parse_log

class ReplayChecks(unittest.TestCase):
    def test_valid_python_is_checked_without_running_it(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);data=b'raise RuntimeError("must not execute on host")\n'
            (p/'run.py').write_bytes(data)
            validate_assets(p,{'run.py':hashlib.sha256(data).hexdigest()})

    def test_bad_hash_and_bad_syntax_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);data=b'if :\n';(p/'run.py').write_bytes(data)
            with self.assertRaisesRegex(ValueError,'hash'):validate_assets(p,{'run.py':'0'*64})
            with self.assertRaises(SyntaxError):validate_assets(p,{'run.py':hashlib.sha256(data).hexdigest()})

    def test_traversal_and_external_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'outside').write_text('x');(p/'case').mkdir()
            (p/'case/link').symlink_to(p/'outside')
            for name in ('../outside','/outside','link'):
                with self.assertRaises(ValueError):validate_assets(p/'case',{name:'0'*64})

    def test_boundary_ignores_execution_speed_but_keeps_actual_behavior(self):
        o=dict(pc=12,guards=[dict(name='g',accesses=1,address=16,width=4,operation='read',value=0)],uarts=[],ioms=[],instructions=100)
        a=boundary_state(o);o['instructions']=200
        self.assertEqual(a,boundary_state(o))
        o['guards'][0]['address']=20
        self.assertNotEqual(a,boundary_state(o))

    @staticmethod
    def observed():
        return dict(guards=[dict(accesses=1)],memory_policy=dict(violations=0),
                    system_control=dict(violations=0),machine_paused_before_host=True)

    def test_expected_strict_abort_and_cache_warning_are_accepted(self):
        o=self.observed()
        log='[WARNING] Translation cache size will be clamped\n[ERROR] This machine has aborted\nBLACKWALL_REPORT '+json.dumps(o)
        self.assertEqual(parse_log(log),o)

    def test_missing_or_duplicate_reports_are_rejected(self):
        line='BLACKWALL_REPORT '+json.dumps(self.observed())+'\n'
        for log in ('',line+line):
            with self.subTest(log=log),self.assertRaisesRegex(ValueError,'ambiguous'):
                parse_log(log)

    def test_policy_timeout_and_unexpected_engine_messages_are_rejected(self):
        base=self.observed()
        for field in ('memory_policy','system_control','machine_paused_before_host','zero-guard','double-guard'):
            o=copy.deepcopy(base)
            if field=='machine_paused_before_host':o[field]=False
            elif field=='zero-guard':o['guards'][0]['accesses']=0
            elif field=='double-guard':o['guards'][0]['accesses']=2
            else:o[field]['violations']=1
            with self.subTest(field=field),self.assertRaises(ValueError):
                parse_log('BLACKWALL_REPORT '+json.dumps(o))
        for extra in ('[ERROR] arbitrary failure','[WARNING] unknown status','BLACKWALL_RUNTIME_ERROR exception','could not execute script'):
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'engine message'):
                parse_log('BLACKWALL_REPORT '+json.dumps(base)+'\n'+extra)

if __name__=='__main__':unittest.main()
