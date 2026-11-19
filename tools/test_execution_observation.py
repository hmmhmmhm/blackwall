"""Host rejection checks for bounded PC observation records and generated-script syntax."""
import copy,json,unittest
from observe_native_profile import audit_observation,runtime

class ObservationChecks(unittest.TestCase):
    def setUp(self):
        self.points=[dict(label='control-reset',address=16),dict(label='control-stop',address=32)]
        self.record=dict(sequence=2,dropped_events=0,capacity=128,points=[dict(p,hits=1,first_sequence=i+1) for i,p in enumerate(self.points)],events=[dict(p,sequence=i+1,pc=p['address'],r2=0) for i,p in enumerate(self.points)])

    @staticmethod
    def log(record):return 'BLACKWALL_OBSERVATION '+json.dumps(record)+'\n'

    def test_valid_observation(self):self.assertEqual(audit_observation(self.log(self.record),self.points),self.record)

    def test_missing_duplicate_or_invalid_records(self):
        for log in ('',self.log(self.record)*2):
            with self.subTest(log=log),self.assertRaises(ValueError):audit_observation(log,self.points)
        for kind in ('point','count','capacity','order','pc','control'):
            r=copy.deepcopy(self.record)
            if kind=='point':r['points'][0]['address']=18
            elif kind=='count':r['points'][0]['hits']=2
            elif kind=='capacity':r['capacity']=4096
            elif kind=='order':r['events'][0]['sequence']=2
            elif kind=='pc':r['events'][0]['pc']=18
            else:r['points'][0]['hits']=0
            with self.subTest(kind=kind),self.assertRaises(ValueError):audit_observation(self.log(r),self.points)

    def test_injection_preserves_try_block_syntax_and_requires_one_start(self):
        base='try:\n    e.StartAll()\nexcept Exception:\n    pass\n'
        compile(runtime(base,self.points),'generated','exec')
        for bad in ('e.StartAll()\n',base+base):
            with self.subTest(bad=bad),self.assertRaises(ValueError):runtime(bad,self.points)

if __name__=='__main__':unittest.main()
