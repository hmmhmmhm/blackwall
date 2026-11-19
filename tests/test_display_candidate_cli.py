"""Candidate selection errors must stop before a display machine is created."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER=Path(__file__).resolve().parents[1]/'tools/run_display_activation_m55.py'

class DisplayCandidateCliTests(unittest.TestCase):
 def command(self,root,*extra):
  return subprocess.run([sys.executable,str(RUNNER),str(root),str(root/'capture'),
                         '--case','stock24',*extra],capture_output=True,text=True,timeout=15)
 def test_incomplete_selection_stops_before_preparation(self):
  for flag in ['--firmware-manifest','--firmware-baseline']:
   with self.subTest(flag=flag),tempfile.TemporaryDirectory() as folder:
    root=Path(folder);result=self.command(root,flag,str(root/'missing'))
    self.assertEqual(result.returncode,2)
    self.assertIn('Candidate selection requires --firmware-manifest and --firmware-baseline',result.stderr)
    self.assertEqual(list(root.iterdir()),[])
 def test_saved_audit_uses_snapshot(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);result=self.command(root,'--audit-existing','--audit-output',str(root/'audit'),
      '--firmware-manifest',str(root/'manifest'),'--firmware-baseline',str(root/'baseline'))
   self.assertEqual(result.returncode,2)
   self.assertIn('Saved audit uses the captured registration snapshot',result.stderr)
   self.assertEqual(list(root.iterdir()),[])

if __name__=='__main__':unittest.main()
