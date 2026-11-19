import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import firmware_runner
from firmware_runner import run_main
from verify_renode_icache import CASES,DATA_EXPECTED,compile_fixture,data_cache_enabled

class UnicornICacheTests(unittest.TestCase):
 def test_native_fixture_behaviors_also_hold_in_unicorn(self):
  for name,(mode,functional,violation,enabled,invalidations,results) in CASES.items():
   with self.subTest(name=name):
    with tempfile.TemporaryDirectory() as tmp:
     d=Path(tmp);compile_fixture(d,mode)
     subprocess.run(['/opt/homebrew/opt/llvm@21/bin/llvm-objcopy','-O','binary',str(d/'fixture.elf'),str(d/'fixture.bin')],check=True,capture_output=True)
     instances=[];original=firmware_runner.u.Uc
     def make_cpu(*args):
      cpu=original(*args);instances.append(cpu);return cpu
     with patch.object(firmware_runner.u,'Uc',make_cpu):
      r=run_main((d/'fixture.bin').read_bytes(),200000 if mode>=100 else 2000,cpacr_storage=True,
                 cpu_caches_off=True,itcm=True,coherent_icache_model=functional,coherent_dcache_model=data_cache_enabled(name))
     words=struct.unpack('<III',instances[0].mem_read(0x20000000,12))
    state=r.get('coherent_icache',{})
    data=r.get('coherent_dcache',{})
    if functional:self.assertEqual(int(r['ccr_scenario']['value'],16),state['ccr']|(0x10000 if data.get('enabled') else 0))
    self.assertEqual(bool(state.get('ccr',0)&0x20000),enabled)
    self.assertEqual(state.get('invalidations',0),invalidations)
    if isinstance(violation,tuple):
     self.assertEqual(int(r['access']['address'],16),violation[1]);self.assertEqual(r['access']['bytes'],violation[2])
    elif violation=='memory':self.assertEqual(r['reason'],'uninitialized-itcm-execution')
    elif violation=='write-main':
     self.assertEqual(r['access']['kind'],'write-protected')
     self.assertEqual(int(r['access']['address'],16),0x438000)
    else:
     self.assertEqual(r['reason'],'instruction-limit')
     self.assertEqual(list(words[1:]),results)
     self.assertEqual(words[0],0x33334444)
    if data_cache_enabled(name):
     for key,value in DATA_EXPECTED.get(name,dict(enabled=False,initialized_lines=0)).items():
      self.assertEqual(data[key],value,(name,key))
