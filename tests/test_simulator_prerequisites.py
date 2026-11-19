from pathlib import Path
import subprocess,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import simulator_cli_readiness as readiness

class PrerequisiteTests(unittest.TestCase):
 def test_missing_docker_refused_without_launch(self):
  with patch.object(readiness.shutil,'which',return_value=None),patch.object(readiness.subprocess,'run') as run:
   with self.assertRaisesRegex(readiness.ReadinessError,'Missing simulator executable: docker'):readiness.native_tools()
   run.assert_not_called()
 def test_missing_compiler_refused_before_docker_inspect(self):
  with patch.object(readiness.shutil,'which',return_value='/bin/docker'),patch.object(readiness,'LLVM',{'clang':Path('/missing/clang')}),patch.object(readiness.subprocess,'run') as run:
   with self.assertRaisesRegex(readiness.ReadinessError,'Missing simulator executable'):readiness.native_tools(compiler=True)
   run.assert_not_called()
 def test_missing_image_uses_inspect_only(self):
  with patch.object(readiness.shutil,'which',return_value='/bin/docker'),patch.object(readiness.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','No such image')) as run:
   with self.assertRaisesRegex(readiness.ReadinessError,'Pinned Renode image unavailable'):readiness.native_tools()
   self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[0][:3],['docker','image','inspect'])
 def test_wrong_package_version_is_refused(self):
  with patch.object(readiness.importlib.metadata,'version',return_value='0.0.0'):
   with self.assertRaisesRegex(readiness.ReadinessError,'Python version differs'):readiness.python_packages()
 def test_unrelated_programming_error_is_not_hidden(self):
  def broken():raise ValueError('unexpected implementation bug')
  with self.assertRaisesRegex(ValueError,'unexpected implementation bug'):readiness.run_cli(broken)

if __name__=='__main__':unittest.main()
