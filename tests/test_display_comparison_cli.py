"""Display comparison requires explicit candidate and output selection."""
from pathlib import Path
import subprocess,sys,tempfile,unittest
RUNNER=Path(__file__).resolve().parents[1]/'tools/run_display_activation_m55.py'

class DisplayComparisonCliTests(unittest.TestCase):
 def call(self,*extra):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   result=subprocess.run([sys.executable,str(RUNNER),folder,str(root/'capture'),
     '--case','stock24',*extra],capture_output=True,text=True,timeout=15)
   self.assertEqual(result.returncode,2,result.stderr)
   self.assertEqual(list(root.iterdir()),[])
   return result.stderr
 def test_output_required(self):
  self.assertIn('Comparison requires --compare-baseline and --comparison-output together',
    self.call('--compare-baseline','missing'))
 def test_expectation_needs_comparison(self):
  self.assertIn('Comparison expectation requires --compare-baseline',
    self.call('--comparison-expectation','missing'))
 def test_live_comparison_needs_registered_candidate(self):
  self.assertIn('Comparison requires a registered candidate or its saved audit',
    self.call('--compare-baseline','missing','--comparison-output','comparison'))

if __name__=='__main__':unittest.main()
