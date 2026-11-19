from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]

class SimulatorCliReadinessTests(unittest.TestCase):
 def test_help_works_without_site_packages(self):
  for script in ['run_display_activation_m55.py','run_runtime_connection_m55.py']:
   with self.subTest(script=script):
    r=subprocess.run([sys.executable,'-S',str(ROOT/'tools'/script),'--help'],capture_output=True,text=True)
    self.assertEqual(r.returncode,0,r.stderr)
 def test_missing_python_package_has_setup_guidance(self):
  with tempfile.TemporaryDirectory() as folder:
   for script in ['run_display_activation_m55.py','run_runtime_connection_m55.py']:
    with self.subTest(script=script):
     r=subprocess.run([sys.executable,'-S',str(ROOT/'tools'/script),folder,folder+'/out','--case','stock24'],capture_output=True,text=True)
     self.assertEqual(r.returncode,2,r.stderr)
     self.assertIn('Missing simulator Python package:',r.stderr)
     self.assertIn('setup_simulator.py',r.stderr)
     self.assertNotIn('Traceback',r.stderr)
     self.assertFalse((Path(folder)/'out').exists())
 def test_missing_capture_has_private_workspace_guidance(self):
  with tempfile.TemporaryDirectory() as folder:
   for script in ['run_display_activation_m55.py','run_runtime_connection_m55.py']:
    with self.subTest(script=script):
     r=subprocess.run([sys.executable,str(ROOT/'tools'/script),folder,folder+'/missing','--case','stock24','--audit-existing','--audit-output',folder+'/audit'],capture_output=True,text=True)
     self.assertEqual(r.returncode,2,r.stderr)
     self.assertIn('Missing simulator asset:',r.stderr)
     self.assertIn('restore_simulator_workspace.py',r.stderr)
     self.assertNotIn('Traceback',r.stderr)
 def test_missing_source_points_to_checkout(self):
  code="import sys;sys.path.insert(0,sys.argv[1]);from simulator_cli_readiness import run_cli;from pathlib import Path;run_cli(lambda:Path(sys.argv[1]+'/missing-reviewed-source.cs').read_text())"
  r=subprocess.run([sys.executable,'-c',code,str(ROOT/'tools')],capture_output=True,text=True)
  self.assertEqual(r.returncode,2);self.assertIn('matching project source checkout',r.stderr);self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__':unittest.main()
