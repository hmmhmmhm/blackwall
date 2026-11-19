import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_same_board_uart2 import finalized_nonzero_repair,MAIN
class RepairScopeTests(unittest.TestCase):
 def fixture(self):
  return dict(recovery_command=dict(mode='recover16',completed=True,input_sent=True,output_acked=True,failure=None),bounded_main_rom=dict(validated=True,status=0,programmed_bytes=16,calls=1,violation=False),images_unchanged=True,classification='main-entered',guards=[],policy=0,system_control_violations=0,events_dropped=0),dict(bounded_main_rom=True,corrupt_main16=True,initial_main_sha256='corrupt')
 def test_actual_repair_is_accepted(self):
  d,m=self.fixture();self.assertTrue(finalized_nonzero_repair(d,m))
 def test_diagnostic_no_change_error_and_incomplete_are_not_repair(self):
  for group,key,value in [('manifest','bounded_main_rom',False),('manifest','corrupt_main16',False),('manifest','initial_main_sha256',MAIN),('result','images_unchanged',False),('result','events_dropped',1),('result','policy',1),('result','machine_aborted',True),('command','completed',False),('command','mode','checksum'),('command','output_acked',False),('rom','status',7),('rom','programmed_bytes',0),('rom','violation',True)]:
   d,m=self.fixture();target={'manifest':m,'result':d,'command':d['recovery_command'],'rom':d['bounded_main_rom']}[group];target[key]=value
   with self.subTest(group=group,key=key):self.assertFalse(finalized_nonzero_repair(d,m))
if __name__=='__main__':unittest.main()
