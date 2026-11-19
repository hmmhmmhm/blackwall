from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_process_recovery as recovery

class NativeProcessRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.path,self.job=recovery.create_job(self.root,'renode')
 def info(self):
  return dict(Id='a'*64,Name='/'+self.job['container'],Config=dict(Labels={
    recovery.TOKEN_LABEL:self.job['token'],recovery.DIRECTORY_LABEL:str(self.root.resolve())}))
 def result(self,code=0,stdout='',stderr=''):return subprocess.CompletedProcess([],code,stdout,stderr)
 def test_live_owner_is_refused_before_docker(self):
  with patch.object(recovery,'docker') as docker:
   with self.assertRaisesRegex(recovery.RecoveryError,'Owner process is still running'):recovery.recover(self.path)
   docker.assert_not_called()
 def test_identity_mismatch_never_removes_container(self):
  info=self.info();info['Config']['Labels'][recovery.TOKEN_LABEL]='wrong'
  with patch.object(recovery,'owner_is_alive',return_value=False),patch.object(recovery,'docker',return_value=self.result(stdout=json.dumps([info]))) as docker:
   with self.assertRaisesRegex(recovery.RecoveryError,'Container ownership differs'):recovery.recover(self.path)
   self.assertEqual(docker.call_count,1)
 def test_removal_uses_verified_immutable_id(self):
  with patch.object(recovery,'owner_is_alive',return_value=False),patch.object(recovery,'docker',side_effect=[self.result(stdout=json.dumps([self.info()])),self.result()]) as docker:
   result=recovery.recover(self.path)
   self.assertTrue(result['removed']);self.assertEqual(docker.call_args_list[1].args[0],['rm','--force','a'*64])
   self.assertEqual(json.loads(self.path.read_text())['status'],'removed')
 def test_terminal_absence_does_not_rewrite_sealed_journal(self):
  self.job['status']='removed';self.path.write_text(json.dumps(self.job));before=self.path.read_bytes()
  with patch.object(recovery,'docker',return_value=self.result(1,stderr='No such container')):
   self.assertTrue(recovery.recover(self.path)['already_absent'])
  self.assertEqual(self.path.read_bytes(),before)
 def test_daemon_failure_remains_recoverable(self):
  with patch.object(recovery,'owner_is_alive',return_value=False),patch.object(recovery,'docker',return_value=self.result(1,stderr='Cannot connect to Docker daemon')):
   with self.assertRaisesRegex(recovery.RecoveryError,'Cannot connect'):recovery.recover(self.path)
  self.assertEqual(json.loads(self.path.read_text())['status'],'cleanup-failed')
 def test_copied_journal_is_refused_before_docker(self):
  destination=self.root/'copy';destination.mkdir();copy=destination/self.path.name;copy.write_bytes(self.path.read_bytes())
  with patch.object(recovery,'docker') as docker:
   with self.assertRaisesRegex(recovery.RecoveryError,'Journal directory differs'):recovery.recover(copy)
   docker.assert_not_called()
 def test_new_job_preserves_old_journal(self):
  before=self.path.read_bytes();other,job=recovery.create_job(self.root,'renode')
  self.assertNotEqual(other,self.path);self.assertNotEqual(job['token'],self.job['token'])
  self.assertEqual(self.path.read_bytes(),before)
 def test_other_host_is_refused_before_docker(self):
  self.job['owner_host']='different-test-host';self.path.write_text(json.dumps(self.job))
  with patch.object(recovery,'docker') as docker:
   with self.assertRaisesRegex(recovery.RecoveryError,'another host'):recovery.recover(self.path)
   docker.assert_not_called()
 def test_malformed_identity_is_refused_before_docker(self):
  for changes in [dict(schema=True),dict(owner_pid=0),dict(owner_pid=True),dict(token='../escape')]:
   with self.subTest(changes=changes),patch.object(recovery,'docker') as docker:
    self.path.write_text(json.dumps(dict(self.job,**changes)))
    with self.assertRaisesRegex(recovery.RecoveryError,'Unsupported native process journal'):recovery.recover(self.path)
    docker.assert_not_called()

if __name__=='__main__':unittest.main()
