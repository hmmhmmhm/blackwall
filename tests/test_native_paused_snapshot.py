import hashlib
import json
import sys
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_native_candidate as runner


class PausedSnapshotTests(unittest.TestCase):
    exports=[dict(name='sram.bin',address=0x20000000,length=4)]
    plan=dict(schema=2,host_capture_seconds=10,memory_export_policy='paused-after-observation',post_stop_memory_exports=exports)

    def test_explicit_policy_requires_finite_observation(self):
        self.assertEqual(runner.memory_exports(self.plan),self.exports)
        for change in [dict(host_capture_seconds=None),dict(host_capture_seconds=True),dict(host_capture_seconds=1),
                       dict(host_capture_seconds=301),dict(schema=1),dict(execution_mode='until-guest-stop'),
                       dict(memory_export_policy='anything'),dict(post_stop_memory_exports=[])]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                runner.memory_exports(dict(self.plan,**change))

    def test_default_exporter_is_unchanged(self):
        self.assertEqual(runner.memory_export_runtime(self.exports),runner.memory_export_runtime(self.exports,'guest-stop'))
        self.assertNotIn('BLACKWALL_MEMORY_SNAPSHOT',runner.memory_export_runtime(self.exports))

    def test_host_snapshot_requires_pause_and_checks_cpu_stability(self):
        code=runner.memory_export_runtime(self.exports,'paused-after-observation')
        self.assertIn('if not m.IsPaused',code)
        self.assertIn('ExecutedInstructions',code)
        self.assertIn('BLACKWALL_MEMORY_SNAPSHOT',code)
        self.assertNotIn('SetRegister',code)
        self.assertNotIn('WriteDoubleWord',code)

    def test_exporter_executes_only_while_paused_and_detects_cpu_change(self):
        for paused,changed in [(True,False),(False,False),(True,True)]:
            with self.subTest(paused=paused,changed=changed):
                cpu=types.SimpleNamespace(PC=types.SimpleNamespace(RawValue=0x500000),ExecutedInstructions=123)
                writes=[];lines=[]
                def read(address,length,only_memory):
                    self.assertEqual((address,length,only_memory),(0x20000000,4,True))
                    if changed:cpu.ExecutedInstructions+=1
                    return b'abcd'
                class Machine:
                    IsPaused=paused
                    SystemBus=types.SimpleNamespace(ReadBytes=read)
                    def __getitem__(self,key):
                        self.assertion=key
                        return cpu
                sha=types.SimpleNamespace(ComputeHash=lambda data:hashlib.sha256(data).digest(),Dispose=lambda:None)
                modules={'clr':types.SimpleNamespace(AddReference=lambda name:None),
                         'System.IO':types.SimpleNamespace(File=types.SimpleNamespace(WriteAllBytes=lambda name,data:writes.append((name,data)))),
                         'System.Security.Cryptography':types.SimpleNamespace(SHA256=types.SimpleNamespace(Create=lambda:sha))}
                env=dict(m=Machine(),blackwall_paused_before_host=False,json=json,
                         Console=types.SimpleNamespace(WriteLine=lines.append))
                with patch.dict(sys.modules,modules):
                    code=textwrap.dedent(runner.memory_export_runtime(self.exports,'paused-after-observation'))
                    if paused and not changed:
                        exec(code,env)
                        self.assertEqual(writes,[('/work-output/sram.bin',b'abcd')])
                        self.assertEqual(runner.read_memory_snapshot('\n'.join(lines),'paused-after-observation',self.observed()),self.snapshot())
                    else:
                        with self.assertRaises(ValueError):exec(code,env)
                        self.assertFalse(any(line.startswith('BLACKWALL_MEMORY_SNAPSHOT ') for line in lines))
                        if not paused:self.assertEqual(writes,[])

    def snapshot(self):
        return dict(origin='host-observation-limit',paused_before=True,paused_after=True,
                    pc_before=0x500000,pc_after=0x500000,instructions_before=123,instructions_after=123)

    def observed(self):
        return dict(machine_paused_before_host=False,pc=0x500000,instructions=123)

    def validate(self,snapshot,observed=None):
        log='BLACKWALL_MEMORY_SNAPSHOT '+json.dumps(snapshot)+'\n'
        return runner.read_memory_snapshot(log,'paused-after-observation',observed or self.observed())

    def test_valid_snapshot_preserves_host_stop_origin(self):
        value=self.snapshot();self.assertEqual(self.validate(value),value)
        value['origin']='guest-stop';self.assertEqual(self.validate(value,dict(self.observed(),machine_paused_before_host=True)),value)

    def test_running_or_changed_cpu_is_rejected(self):
        for change in [dict(paused_before=False),dict(paused_after=False),dict(paused_before=1),
                       dict(pc_after=0x500002),dict(instructions_after=124),dict(origin='guest-stop')]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(dict(self.snapshot(),**change))

    def test_missing_duplicate_or_mismatched_snapshot_rejected(self):
        value=self.snapshot();line='BLACKWALL_MEMORY_SNAPSHOT '+json.dumps(value)+'\n'
        for log in ['',line+line]:
            with self.assertRaises(ValueError):runner.read_memory_snapshot(log,'paused-after-observation',self.observed())
        with self.assertRaises(ValueError):self.validate(value,dict(self.observed(),instructions=124))
        with self.assertRaises(ValueError):self.validate(value,dict(self.observed(),pc=0x500002))
        self.assertIsNone(runner.read_memory_snapshot('','guest-stop',self.observed()))


if __name__=='__main__':unittest.main()
