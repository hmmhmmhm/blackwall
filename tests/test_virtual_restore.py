import importlib.util
from pathlib import Path
import unittest

class VirtualRestoreTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[1]/'tools/check_virtual_restore.py'
        self.assertTrue(path.is_file(),'Component-aware restoration checker is required')
        spec=importlib.util.spec_from_file_location('virtual_restore',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.stock={'boot':'a'*64,'main':'b'*64,'nor':'c'*64}

    def test_main_only_does_not_mean_full_stock(self):
        d=self.m.assess(self.stock,dict(self.stock,boot='d'*64),['boot','main'],True)
        self.assertTrue(d['stock_application_bytes']);self.assertFalse(d['full_stock_bytes'])
        self.assertFalse(d['reboot_verified']);self.assertFalse(d['hardware_validated'])

    def test_unknown_inventory_cannot_mean_full_stock(self):
        self.assertFalse(self.m.assess(self.stock,self.stock,['boot','main'],False)['full_stock_bytes'])

    def test_missing_component_and_wrong_hash_not_accepted(self):
        d=self.m.assess(self.stock,{'main':'b'*64},['boot','main'],True)
        self.assertEqual(d['missing'],['boot']);self.assertFalse(d['full_stock_bytes'])
        with self.assertRaises(ValueError):self.m.assess({'main':'bad'},self.stock,['main'],True)

    def test_all_components_still_only_byte_verification(self):
        extents={'boot':{'space':'mram','address':0x410000,'bytes':0x28000},'main':{'space':'mram','address':0x438000,'bytes':3700068},'nor':{'space':'nor','address':0,'bytes':4096}}
        changes=[{'space':'mram','address':0x434910,'bytes':6116},{'space':'nor','address':0,'bytes':256}]
        d=self.m.assess(self.stock,self.stock,['boot','main','nor'],True,stock_extents=extents,modified_regions=changes)
        self.assertTrue(d['full_stock_bytes']);self.assertFalse(d['reboot_verified'])
        self.assertFalse(d['installable'])

    def test_hash_only_cannot_prove_modified_byte_coverage(self):
        self.assertFalse(self.m.assess(self.stock,self.stock,['boot','main'],True)['full_stock_bytes'])

    def test_stock_boot_prefix_does_not_cover_appended_patch(self):
        extents={'boot':{'space':'mram','address':0x410000,'bytes':149773},'main':{'space':'mram','address':0x438000,'bytes':3700068}}
        changes=[{'space':'mram','address':0x434910,'bytes':6116}]
        d=self.m.assess(self.stock,self.stock,['boot','main'],True,stock_extents=extents,modified_regions=changes)
        self.assertFalse(d['full_stock_bytes']);self.assertTrue(d['uncovered_modified_regions'])

    def test_other_address_space_cannot_cover_boot(self):
        extents={'boot':{'space':'other-device','address':0x410000,'bytes':0x28000},'main':{'space':'mram','address':0x438000,'bytes':3700068}}
        d=self.m.assess(self.stock,self.stock,['boot','main'],True,stock_extents=extents,modified_regions=[{'space':'mram','address':0x434910,'bytes':6116}])
        self.assertFalse(d['full_stock_bytes'])

    def test_tail_backup_can_complete_known_modified_coverage(self):
        stock=dict(self.stock,boot_tail='d'*64)
        extents={'boot':{'space':'mram','address':0x410000,'bytes':149773},'main':{'space':'mram','address':0x438000,'bytes':3700068},'boot_tail':{'space':'mram','address':0x43490d,'bytes':9971}}
        changes=[{'space':'mram','address':0x410000,'bytes':159744}]
        d=self.m.assess(stock,stock,['boot','main','boot_tail'],True,stock_extents=extents,modified_regions=changes)
        self.assertTrue(d['full_stock_bytes']);self.assertFalse(d['reboot_verified'])
        extents['boot_tail']={'space':'mram','address':0x43490e,'bytes':9970}
        d=self.m.assess(stock,stock,['boot','main','boot_tail'],True,stock_extents=extents,modified_regions=changes)
        self.assertFalse(d['full_stock_bytes'])
        self.assertEqual(d['uncovered_modified_regions'],[{'space':'mram','address':0x43490d,'bytes':1}])

    def test_invalid_byte_extents_are_rejected(self):
        for bad in [{'space':'mram','address':True,'bytes':16},{'space':'mram','address':0,'bytes':0},{'space':'mram','address':2**64-1,'bytes':2}]:
            with self.assertRaises(ValueError):
                self.m.assess(self.stock,self.stock,['boot','main'],True,stock_extents={'boot':bad},modified_regions=[{'space':'mram','address':0,'bytes':16}])

    def test_empty_or_duplicate_component_inventory_rejected(self):
        for inv in ([],['main','main']):
            with self.assertRaises(ValueError):self.m.assess(self.stock,self.stock,inv,True)

if __name__=='__main__':unittest.main()
