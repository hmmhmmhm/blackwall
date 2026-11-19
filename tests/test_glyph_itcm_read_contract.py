import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_glyph_itcm_read import read_contract

SIM=Path.home()/'Library/Application Support/Blackwall/simulator'


@unittest.skipUnless((SIM/'builtin-font-memory-main-01/stock24/main.bin').is_file(),'Pinned private firmware required')
class RawBitmapReadContractTests(unittest.TestCase):
    def source(self,case='stock24'):
        folder=SIM/'builtin-font-memory-main-01'/case
        report=json.loads((folder/'report.json').read_text())
        font=next(v for v in report['fonts'].values() if v[6])
        return (folder/'main.bin').read_bytes(),font[1]&~1

    def test_three_pinned_callbacks_restore_the_unused_loaded_register(self):
        for case in ['stock24','stock23','cfw']:
            raw,entry=self.source(case);proof=read_contract(raw,entry)
            self.assertTrue(proof['access_must_complete'])
            self.assertTrue(proof['saved_register_restored'])
            self.assertFalse(proof['loaded_word_read_before_return'])

    def test_changed_raw_path_condition_is_rejected(self):
        raw,entry=self.source();changed=bytearray(raw)
        # The raw path's BPL must not silently become a different condition.
        changed[entry+0x29-0x438000]^=1
        with self.assertRaises(AssertionError):read_contract(bytes(changed),entry)

    def test_epilogue_without_register_restoration_is_rejected(self):
        raw,entry=self.source();proof=read_contract(raw,entry);changed=bytearray(raw)
        offset=proof['raw_path'][-1]['pc']-0x438000
        changed[offset:offset+4]=bytes.fromhex('00bf00bf')
        with self.assertRaises(AssertionError):read_contract(bytes(changed),entry)

    def test_wrong_function_entry_is_rejected(self):
        raw,entry=self.source()
        with self.assertRaises(AssertionError):read_contract(raw,entry+2)


if __name__=='__main__':unittest.main()
