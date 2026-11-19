from pathlib import Path
import re,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from iom_main_adapter import connect_ioms,power_profiles,SUPPORTED
BOARD='''guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40001000
    baseAddress: 0x40001000
guard_high: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40025000
    baseAddress: 0x40025000
    size: 0x1ffdb000
    gpuControlOwner: guard
'''
class Iom6SelectionTests(unittest.TestCase):
 def setUp(self):self.assertIn(6,SUPPORTED,'Explicit IOM6 selection is missing')
 def test_iom6_selection_maps_exact_bank_irq_power(self):
  text=connect_ioms(BOARD,'active','off',(2,4,5,6,7))
  self.assertIn('iom6Power: iom6_power',text)
  self.assertIn('iom6: Miscellaneous.BlackwallStrictIom @ sysbus 0x40056000',text)
  self.assertIn('module: 6\n    IRQ -> nvic@12',text)
  regions=[]
  for name,address,body in re.findall(r'(?m)^((?:guard[_a-z0-9]*|iom[24567])): [^\n]+ @ sysbus (0x[0-9a-f]+)\n((?:[ \t]+[^\n]*\n|\n)*)',text):
   if name=='guard':continue
   begin=int(address,16);size=int(re.search(r'    size: (0x[0-9a-f]+)',body).group(1),16) if name.startswith('guard') else 0x400
   regions.append((begin,begin+size))
  regions.sort();self.assertEqual(regions[0][0],0x40025000);self.assertEqual(regions[-1][1],0x60000000)
  self.assertTrue(all(a[1]==b[0] for a,b in zip(regions,regions[1:])))
 def test_default_and_independent_fault_selection(self):
  self.assertNotIn('iom6Power',connect_ioms(BOARD,'active','off'))
  text=connect_ioms(BOARD,'active','off',(6,),profile_overrides={6:'stuck-off'})
  self.assertIn('mask: 0x80\n    profile: 0',text)
  with self.assertRaises(ValueError):power_profiles((2,),'active',{6:'active'})
if __name__=='__main__':unittest.main()
