"""CLI comparison selection must be explicit and preserve runtime failure semantics."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class RuntimeComparisonSelectionTests(unittest.TestCase):
 def command(self,args):
  return subprocess.run([sys.executable,str(ROOT/'tools/run_runtime_connection_m55.py'),*args],capture_output=True,text=True,timeout=15)
 def test_comparison_requires_its_output(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.command([folder,folder+'/capture','--case','stock24','--compare-baseline',folder+'/base'])
   self.assertEqual(r.returncode,2)
   self.assertIn('Comparison requires --compare-baseline and --comparison-output together',r.stderr)
   self.assertEqual(list(Path(folder).iterdir()),[])
 def test_expectation_requires_comparison(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.command([folder,folder+'/capture','--case','stock24','--comparison-expectation',folder+'/expect.json'])
   self.assertEqual(r.returncode,2)
   self.assertIn('Comparison expectation requires --compare-baseline',r.stderr)
 def test_live_comparison_requires_registered_candidate(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.command([folder,folder+'/capture','--case','stock24','--compare-baseline',folder+'/base','--comparison-output',folder+'/comparison'])
   self.assertEqual(r.returncode,2)
   self.assertIn('Comparison requires a registered candidate or its saved audit',r.stderr)
 def saved_preflight(self, folder, *, scenario_mismatch=False, model_mismatch=False, nested_output=False):
  root=Path(folder); base=root/'base'; candidate=root/'candidate'
  base.mkdir(); candidate.mkdir()
  profile=dict(case='stock24',main_sha256='a'*64,att_time=True)
  selected=dict(profile,main_sha256='b'*64,firmware_candidate={})
  if scenario_mismatch:selected['att_time']=False
  (base/'connection-profile.json').write_text(json.dumps(profile))
  (candidate/'connection-profile.json').write_text(json.dumps(selected))
  (base/'connection-inputs.json').write_text(json.dumps({'strict.cs':'0'*64}))
  inputs={'strict.cs':('1' if model_mismatch else '0')*64,
          'firmware-candidate.json':'2'*64,'firmware-runtime-anchors.json':'3'*64}
  (candidate/'connection-inputs.json').write_text(json.dumps(inputs))
  comparison=candidate/'comparison' if nested_output else root/'comparison'
  result=self.command([folder,str(candidate),'--case','stock24','--audit-existing',
                       '--audit-output',str(root/'audit'),'--compare-baseline',str(base),
                       '--comparison-output',str(comparison)])
  self.assertEqual(result.returncode,2,result.stderr)
  self.assertFalse((root/'audit').exists())
  self.assertFalse(comparison.exists())
  return result
 def test_different_scenario_rejected_before_saved_audit(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.saved_preflight(folder,scenario_mismatch=True)
   self.assertIn('Different runtime scenario/profile',r.stderr)
 def test_different_model_rejected_before_saved_audit(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.saved_preflight(folder,model_mismatch=True)
   self.assertIn('Different model/board/input/observer bytes',r.stderr)
 def test_comparison_cannot_write_inside_capture(self):
  with tempfile.TemporaryDirectory() as folder:
   r=self.saved_preflight(folder,nested_output=True)
   self.assertIn('Comparison needs a new directory outside both captures',r.stderr)

if __name__=='__main__':unittest.main()
