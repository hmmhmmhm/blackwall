from pathlib import Path
import hashlib,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from restore_simulator_workspace import restore

class WorkspaceRestoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.source=self.root/'source';self.source.mkdir();(self.source/'a.bin').write_bytes(b'abc');self.index=self.root/'index.json';self.output=self.root/'restored'
  self.data=dict(schema='blackwall-simulator-workspace/1',files={'a.bin':dict(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())})
  self.index.write_text(json.dumps(self.data))
 def test_exact_restore_and_completion_marker(self):
  r=restore(self.index,self.source,self.output);self.assertEqual((self.output/'a.bin').read_bytes(),b'abc');self.assertTrue(r['passed']);self.assertTrue((self.output/'blackwall-workspace.json').exists())
 def test_corrupt_source_refused_before_output(self):
  (self.source/'a.bin').write_bytes(b'bad')
  with self.assertRaisesRegex(ValueError,'Workspace asset hash differs'):restore(self.index,self.source,self.output)
  self.assertFalse(self.output.exists())
 def test_missing_source_names_the_asset(self):
  (self.source/'a.bin').unlink()
  with self.assertRaisesRegex(ValueError,'Missing workspace asset: a.bin'):restore(self.index,self.source,self.output)
  self.assertFalse(self.output.exists())
 def test_escape_and_symlink_refused(self):
  for name in ['../escape','/tmp/escape']:
   self.data['files']={name:dict(bytes=3,sha256='0'*64)};self.index.write_text(json.dumps(self.data))
   with self.assertRaisesRegex(ValueError,'Workspace path escapes'):restore(self.index,self.source,self.output)
  (self.root/'outside.bin').write_bytes(b'abc');(self.source/'link.bin').symlink_to(self.root/'outside.bin');self.data['files']={'link.bin':dict(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())};self.index.write_text(json.dumps(self.data))
  with self.assertRaisesRegex(ValueError,'Workspace path escapes'):restore(self.index,self.source,self.output)
 def test_existing_output_and_git_output_preserved(self):
  self.output.mkdir();(self.output/'keep').write_text('keep')
  with self.assertRaisesRegex(ValueError,'Output exists'):restore(self.index,self.source,self.output)
  self.assertEqual((self.output/'keep').read_text(),'keep')
  repo=self.root/'repository';repo.mkdir();(repo/'.git').mkdir()
  with self.assertRaisesRegex(ValueError,'outside Git'):restore(self.index,self.source,repo/'new')
 def test_aliased_completion_marker_cannot_be_an_asset(self):
  (self.source/'blackwall-workspace.json').write_bytes(b'abc')
  self.data['files']={'./blackwall-workspace.json':dict(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())};self.index.write_text(json.dumps(self.data))
  with self.assertRaisesRegex(ValueError,'Workspace path escapes or is reserved'):restore(self.index,self.source,self.output)
  self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
