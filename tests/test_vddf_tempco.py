import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from simulator_vddf_tempco import VddfTempcoStorage


class VddfTests(unittest.TestCase):
    def make(self,trim=64):
        report={'models':[],'buck_response':{'phase':'active'},'memldo_setup_storage':{'steps_completed':2}}
        fixture=SimpleNamespace(registers={0x4002004c:dict(value=hex(0x1fef80|trim),reads=2,writes=0)})
        return VddfTempcoStorage(report,fixture),report,fixture

    def test_saturation_preserves_other_bits_and_allows_one_write(self):
        for trim in (0,1,9,10,11,64,127):
            model,report,fixture=self.make(trim);expected=0x1fef80|max(trim-10,0)
            self.assertTrue(model.write(0x4002004c,4,expected))
            self.assertFalse(model.write(0x4002004c,4,expected))
            self.assertEqual(fixture.registers[0x4002004c]['writes'],1)
            self.assertEqual(int(fixture.registers[0x4002004c]['value'],16),expected)

    def test_phase_read_witness_width_address_and_value_guards(self):
        for field in ('phase','setup','reads','changed','width','address','value'):
            model,report,fixture=self.make();address=0x4002004c;size=4;value=0x1fefb6
            if field=='phase':report['buck_response']['phase']='requested'
            if field=='setup':report['memldo_setup_storage']['steps_completed']=1
            if field=='reads':fixture.registers[address]['reads']=1
            if field=='changed':fixture.registers[address]['value']='0x1fefc1'
            if field=='width':size=1
            if field=='address':address+=4
            if field=='value':value^=0x80
            self.assertFalse(model.write(address,size,value),field)


if __name__=='__main__':unittest.main()
