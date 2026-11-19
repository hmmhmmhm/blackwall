"""Compare all bytes even when the human-readable difference list is bounded."""
from pathlib import Path
import hashlib,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compare_display_firmware import byte_changes,canonical_sha256,load_expectation

class DisplayComparisonBytesTests(unittest.TestCase):
 def test_late_difference_is_hashed_and_counted(self):
  before=bytes(100);after=bytes([1]*70+[0]*29+[2])
  result=byte_changes(before,after)
  self.assertEqual(result['changed_bytes'],71)
  self.assertEqual(len(result['first_changes']),64)
  self.assertTrue(result['changes_truncated'])
  self.assertEqual(result['after_sha256'],hashlib.sha256(after).hexdigest())
  self.assertNotEqual(result['before_sha256'],result['after_sha256'])
 def test_unequal_lengths_are_refused(self):
  with self.assertRaisesRegex(ValueError,'Different byte capture lengths'):byte_changes(b'',b'1')
 def test_canonical_trace_ignores_key_order_only(self):
  self.assertEqual(canonical_sha256(dict(a=1,b=[2,3])),canonical_sha256(dict(b=[2,3],a=1)))
  self.assertNotEqual(canonical_sha256(dict(a=1,b=[2,3])),canonical_sha256(dict(b=[3,2],a=1)))
 def test_expectation_is_complete_and_typed(self):
  good=dict(schema=1,candidate_passed=True,failed_checks=[],surface_sha256='0'*64,
            final_sram_sha256='1'*64,trace_sha256='2'*64)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'expect.json';p.write_text(json.dumps(good));self.assertEqual(load_expectation(p),good)
   for bad in [dict(good,schema=True),dict(good,candidate_passed=1),dict(good,surface_sha256='x'*64),
               dict(good,failed_checks=['a','a']),dict(good,extra=True),{k:v for k,v in good.items() if k!='trace_sha256'}]:
    with self.subTest(bad=bad):
     p.write_text(json.dumps(bad))
     with self.assertRaisesRegex(ValueError,'Unsupported display comparison expectation'):load_expectation(p)

if __name__=='__main__':unittest.main()
