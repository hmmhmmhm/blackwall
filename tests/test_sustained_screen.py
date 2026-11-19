import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_sustained_screen import validate_budget, assess, replace_component, validate_observer_scope, POST, extend_startup_render_guard

class SustainedTests(unittest.TestCase):
 def test_only_declared_render_host_deadline_changes(self):
  runtime=b'StartAll();deadline=time.time()+30;render_started=ticks\nvirtual_limit=1000\nwdt=123\n'
  self.assertEqual(extend_startup_render_guard(runtime,300),runtime.replace(b'+30;render_started',b'+300;render_started'))
  for source in [b'unknown deadline',runtime+runtime]:
   with self.assertRaises(ValueError):extend_startup_render_guard(source,300)
  with self.assertRaises(ValueError):extend_startup_render_guard(runtime,600)
  family=b'StartAll();deadline=time.time()+120;started=int(m.ElapsedVirtualTime.TimeElapsed.Ticks)\n                    while not m.IsPaused and not cpu.IsHalted and int(gpu.Rejections)==0 and not gpu.CompleteScreenHasDetail'
  self.assertEqual(extend_startup_render_guard(family,300,'stock23'),family.replace(b'+120;',b'+300;'))
  with self.assertRaises(ValueError):extend_startup_render_guard(runtime,300,'unknown')
 def test_observer_cannot_replace_runtime_peer(self):
  original="peer = 'touch'\n"
  with self.assertRaisesRegex(ValueError,'peer'):
   validate_observer_scope("if True:\n peer = 'controller'\n", original)
  isolated="def capture():\n peer = 'controller'\n return peer\ncapture()\n"
  validate_observer_scope(isolated,original)
  state={};exec(original+isolated,state);self.assertEqual(state['peer'],'touch')
  with self.assertRaisesRegex(ValueError,'outer runtime'):
   validate_observer_scope("def capture():\n global peer\n peer = 'controller'\n",original)
  validate_observer_scope(POST,original)
 def test_single_component_replacement(self):
  self.assertEqual(replace_component(b"left OLD right",b"OLD",b"NEW"),b"left NEW right")
  for original,old in [(b"no component",b"OLD"),(b"OLD OLD",b"OLD"),(b"x",b"")]:
   with self.assertRaises(ValueError):replace_component(original,old,b"NEW")
 def test_budget(self):
  self.assertEqual(validate_budget(100,900)['max_samples'],3)
  self.assertEqual(validate_budget(6000,900),dict(target_ms=6000,host_seconds=900,sample_ms=1000,max_samples=8))
  for value in [0,-1,101,6001]:
   with self.assertRaises(ValueError):validate_budget(value,900)
 def sample(self):
  return dict(target_ms=6000,elapsed_ticks=6000000000,ticks_per_ms=1000000,stop_reason='virtual-limit',before={'instructions':100,'ticks':0,'frames':1},after={'instructions':200,'ticks':6000000000,'frames':10,'gpu_rejections':0,'gpu_fault':'','fifo_ready':True,'imu_wrapper_gate':1},samples=[{'ticks':0,'instructions':100,'frames':1},{'ticks':6000000000,'instructions':200,'frames':10}],wall_seconds=1,signals={'total':600,'counts':[100,100,400],'entered':[50,50],'exited':[50,50],'truncated':True,'samples':[[1]]},faults={'cfsr':0,'hfsr':0,'memory':0,'system':0,'guards':0},first_frame_sha256='5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501')
 def test_complete(self):self.assertTrue(all(assess(self.sample()).values()))
 def test_early_stop_and_wrong_time(self):
  for key,value in [('elapsed_ticks',100000000),('stop_reason','host-limit'),('wall_seconds',0)]:
   x=self.sample();x[key]=value;self.assertFalse(all(assess(x).values()))
 def test_fault_or_stalled(self):
  for key in ['cfsr','hfsr','memory','system','guards']:
   x=self.sample();x['faults'][key]=1;self.assertFalse(all(assess(x).values()))
  x=self.sample();x['after']['instructions']=100;self.assertFalse(all(assess(x).values()))
 def test_signal_samples_are_not_full_history(self):
  x=self.sample();self.assertTrue(assess(x)['bounded_signal_accounting'])
  x['signals']['total']=599;self.assertFalse(assess(x)['bounded_signal_accounting'])

if __name__=='__main__':unittest.main()
