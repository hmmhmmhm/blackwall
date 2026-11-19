"""Host stream must accept error RESULT after receive without demanding progress."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from same_board_recovery_peer import HELPER,block,reply

class StreamTests(unittest.TestCase):
 def peer(self,status=0):
  plan=dict(mode='recover16',expect_progress=status==0,expected_return=status,packets=[[]]*19,responses=[[]]*18+[reply(2,0,struct.pack('<I',status))],block_request=block(4,struct.pack('<H',16)),block_input=block(2,b'\x00'*16),block_output=block(1,struct.pack('<I',16)),block_ack=block(3))
  queued=[];ns=dict(RECOVERY_PLAN=plan,peer_stage='recovery',event=lambda *a,**k:None,queue=lambda *x:queued.append(x),request=lambda marker:[1],tick=lambda:3)
  exec(HELPER,ns);ns.update(RECOVERY_INDEX=18,RECOVERY_CURSOR=0)
  return ns,plan,queued
 def test_error_result_requires_input_but_no_progress_ack(self):
  n,p,q=self.peer(7);n['advance_recovery'](p['block_request']);self.assertEqual(q,[('block-input',p['block_input'])]);self.assertTrue(n['RECOVERY_INPUT_SENT'])
  n['advance_recovery'](p['block_request']+p['responses'][-1]);self.assertEqual(n['peer_stage'],'continue');self.assertEqual(n['RECOVERY_INDEX'],19);self.assertFalse(n['RECOVERY_COMPLETED']);self.assertFalse(n['RECOVERY_OUTPUT_ACKED'])
 def test_success_requires_progress_then_result(self):
  n,p,q=self.peer();tx=p['block_request'];n['advance_recovery'](tx);self.assertFalse(n['RECOVERY_COMPLETED']);tx+=p['block_output'];n['advance_recovery'](tx);self.assertEqual(q[-1],('block-ack',p['block_ack']));self.assertFalse(n['RECOVERY_COMPLETED']);n['advance_recovery'](tx+p['responses'][-1]);self.assertTrue(n['RECOVERY_COMPLETED']);self.assertEqual(n['peer_stage'],'continue')
 def test_wrong_progress_is_not_success(self):
  n,p,q=self.peer();tx=p['block_request'];n['advance_recovery'](tx);n['advance_recovery'](tx+block(1,struct.pack('<I',12)));self.assertEqual(n['peer_stage'],'recovery-error');self.assertFalse(n['RECOVERY_COMPLETED']);self.assertFalse(n['RECOVERY_OUTPUT_ACKED'])
if __name__=='__main__':unittest.main()
