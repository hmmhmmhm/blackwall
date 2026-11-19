import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import run_native_candidate as runner
from run_renode_m55_probe import execute


class ObservationPolicyTests(unittest.TestCase):
    runtime = '    live_seconds=0\n    while not m.IsPaused and live_seconds<45:\n        time.sleep(1.0)\n        live_seconds+=1\n    blackwall_paused_before_host=bool(m.IsPaused)\n'

    def test_explicit_guest_stop_removes_inherited_host_deadline(self):
        result=runner.observation_runtime(self.runtime,dict(schema=2,execution_mode='until-guest-stop'))
        self.assertIn('while not m.IsPaused:\n',result)
        self.assertNotIn('live_seconds<',result)
        self.assertIn('blackwall_paused_before_host=bool(m.IsPaused)',result)

    def test_legacy_runtime_is_unchanged(self):
        self.assertEqual(runner.observation_runtime(self.runtime,dict(schema=2)),self.runtime)

    def test_already_unbounded_is_idempotent(self):
        runtime=self.runtime.replace(' and live_seconds<45','')
        self.assertEqual(runner.observation_runtime(runtime,dict(schema=2,execution_mode='until-guest-stop')),runtime)

    def test_observation_deadline_does_not_end_guest_stop_mode(self):
        def execute_loop(runtime):
            state={}
            class Machine:
                @property
                def IsPaused(self):return state.get('live_seconds',0)>=47
            class Clock:
                def sleep(self,seconds):pass
            state.update(m=Machine(),time=Clock())
            exec('if True:\n'+runtime,state)
            return state['live_seconds'],state['blackwall_paused_before_host']
        self.assertEqual(execute_loop(self.runtime),(45,False))
        runtime=runner.observation_runtime(self.runtime,dict(schema=2,execution_mode='until-guest-stop'))
        self.assertEqual(execute_loop(runtime),(47,True))

    def test_invalid_or_conflicting_policy_rejected(self):
        for plan in [dict(schema=1,execution_mode='until-guest-stop'),dict(schema=2,execution_mode='retry'),dict(schema=2,execution_mode='until-guest-stop',host_capture_seconds=45)]:
            with self.subTest(plan=plan),self.assertRaises(ValueError):
                runner.observation_runtime(self.runtime,plan)

    def test_missing_duplicate_or_unknown_loop_rejected(self):
        unknown=self.runtime.replace('live_seconds<45','live_seconds<unknown')
        for runtime in ['',self.runtime+self.runtime,unknown,self.runtime+unknown]:
            with self.subTest(runtime=runtime),self.assertRaises(ValueError):
                runner.observation_runtime(runtime,dict(schema=2,execution_mode='until-guest-stop'))


class StreamingExecutionTests(unittest.TestCase):
    def test_running_child_log_is_visible_and_same_child_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);release=root/'release';answers=[];errors=[]
            code="import os,pathlib,time;print('READY '+str(os.getpid()),flush=True);p=pathlib.Path(__import__('sys').argv[1]);\nwhile not p.exists(): time.sleep(.01)\nprint('FINISHED',flush=True)"
            def worker():
                try:answers.append(execute([sys.executable,'-u','-c',code,str(release)],root,'live',timeout=None,stream=True))
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start()
            try:
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    log=(root/'live.log').read_text() if (root/'live.log').exists() else ''
                    if log.startswith('READY '):break
                    time.sleep(.01)
                self.assertTrue(log.startswith('READY '),errors)
                pid=int(log.split()[1]);self.assertTrue(thread.is_alive());__import__('os').kill(pid,0)
                self.assertNotIn('FINISHED',log)
            finally:
                release.touch();thread.join(5)
            self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)
            self.assertEqual(answers,[(root/'live.log').read_text()])
            self.assertEqual(answers[0].splitlines(),['READY '+str(pid),'FINISHED'])

    def test_nonzero_exit_retains_both_output_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            with self.assertRaises(RuntimeError):
                execute([sys.executable,'-u','-c',"import sys;print('out');print('err',file=sys.stderr);sys.exit(7)"],root,'failed',timeout=None,stream=True)
            text=(root/'failed.log').read_text();self.assertIn('out',text);self.assertIn('err',text)


if __name__=='__main__':unittest.main()
