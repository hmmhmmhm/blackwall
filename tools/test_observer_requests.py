import unittest
from execution_observer import requests,instrument

class RequestsTest(unittest.TestCase):
    def test_valid_and_generated_syntax(self):
        p,c=requests(['entry:0x438000','return:0x438010'],['return:0x20000000:16'],64)
        code=instrument('try:\n    e.StartAll()\nexcept Exception:\n    pass\n',p,c)
        compile(code,'generated','exec')
        self.assertIn("observer.CaptureSram(m,'return',536870912,16)",code)
    def test_invalid_points(self):
        cases=[['entry'],['bad label:0x438000'],['a:0x438001'],['a:0x437ffe'],['a:0x438040'],['a:0x438000','a:0x438002'],['a:0x438000','b:0x438000']]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):requests(case,[],64)
        with self.assertRaises(ValueError):requests([f'p{i}:{hex(0x438000+2*i)}' for i in range(129)],[],4096)
    def test_invalid_snapshots(self):
        cases=[['unknown:0x20000000:1'],['a:0x40000000:1'],['a:0x20000001:1'],['a:0x20000000:0'],['a:0x20000000:17'],['a:0x20380000:1'],['a:0x20000000:1','a:0x20000004:1']]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):requests(['a:0x438000'],case,64)

if __name__=='__main__':unittest.main()
