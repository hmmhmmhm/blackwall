"""The runtime CLI and byte decoder must not require the optional package parser."""
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
GUARD = '''import importlib.abc,sys
sys.path.insert(0,sys.argv[1])
class BlockOptionalPackage(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='blackwall_package':raise RuntimeError('optional-package-read-attempt')
sys.meta_path.insert(0,BlockOptionalPackage())
'''

class RuntimeImportTests(unittest.TestCase):
    def run_child(self,code):
        return subprocess.run([sys.executable,'-c',GUARD+code,str(TOOLS)],capture_output=True,text=True,timeout=15)

    def test_runtime_decoder_without_optional_package(self):
        result=self.run_child("from run_runtime_connection_m55 import decode\nrows=decode(bytes.fromhex('7047'),0x438000,2)\nassert [(x.mnemonic,x.op_str) for x in rows]==[('bx','lr')]\n")
        self.assertEqual(result.returncode,0,result.stderr)

    def test_help_without_firmware_or_optional_package(self):
        result=self.run_child("import run_runtime_connection_m55 as cli\nsys.argv=['run_runtime_connection_m55.py','--help']\ncli.main()\n")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--firmware-manifest',result.stdout)

    def test_real_branch_analysis_still_requires_package(self):
        result=self.run_child("from font_wrapper_contract import BASE,direct_call_candidates\ntry:direct_call_candidates(bytes.fromhex('00f000f8'),BASE+4)\nexcept RuntimeError as error:assert str(error)=='optional-package-read-attempt'\nelse:raise AssertionError('Required parser was bypassed')\n")
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
