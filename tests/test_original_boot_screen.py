import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_original_boot_screen import assess, checked_asset, checked_path, valid_frame, decode_frame, scenario_component, validate_runtime, derive, PROFILE, render_preview

FIXTURE=Path(__file__).parent/'fixtures/original-boot-screen-observation.json'

class OriginalBootScreenTests(unittest.TestCase):
    def fixture(self):return json.loads(FIXTURE.read_text())
    def passed(self,value):return all(assess(value).values())
    def test_real_record_shape(self):self.assertTrue(self.passed(self.fixture()))
    def test_boot_and_main_must_both_execute_in_order(self):
        for label in ['boot-reset','stock-handoff','main-reset','ui-dispatch','app1-callback','renderer-entry']:
            value=self.fixture();next(p for p in value['native']['points'] if p['label']==label)['hits']=0
            self.assertFalse(self.passed(value),label)
        value=self.fixture();value['native']['points'][0]['first']=100
        self.assertFalse(self.passed(value))
    def test_every_fault_and_overflow_rejects(self):
        for name in ['cfsr','hfsr','system_control_violations','events_dropped']:
            value=self.fixture();value['native'][name]=1;self.assertFalse(self.passed(value),name)
        for name in ['rtc_accesses','post_observer_unchanged']:
            value=self.fixture();value['delegated'][name]=1 if name=='rtc_accesses' else False
            self.assertFalse(self.passed(value),name)
        value=self.fixture();value['native']['guards'][0]['accesses']=1
        self.assertFalse(self.passed(value))
        value=self.fixture();value['native']['policy']['violations']=1
        self.assertFalse(self.passed(value))
    def test_bool_is_not_integer_fault_zero(self):
        value=self.fixture();value['native']['cfsr']=False
        self.assertFalse(self.passed(value))
    def test_original_stack_banks_are_preserved(self):
        value=self.fixture();value['context']['contexts'][-1]['msp']=0x2007fb00
        self.assertFalse(self.passed(value))
        value=self.fixture();value['context']['contexts'][-1]['vtor']=0x410000
        self.assertFalse(self.passed(value))
    def test_pending_or_incomplete_wire_is_not_success(self):
        for name in ['completed']:
            value=self.fixture();value['wire'][name]=False;self.assertFalse(self.passed(value))
        value=self.fixture();value['wire']['replies'][-1]['identifier']^=1
        self.assertFalse(self.passed(value))
        value=self.fixture();value['wire']['replies'][-1]['data'][-1]^=1
        self.assertFalse(self.passed(value))
        value=self.fixture();value['wire']['replies'][-1]['after']['instructions']+=1
        self.assertFalse(self.passed(value))
    def test_same_time_cadence_frame_and_original_images_required(self):
        for key in ['image_equal','cadence_equal','frame_equal']:
            value=self.fixture();value[key]=False;self.assertFalse(self.passed(value),key)
        value=self.fixture();value['wire']['cadence']['after']['ticks']+=1
        self.assertFalse(self.passed(value))
        value=self.fixture();value['screen']['captures']=0
        self.assertFalse(self.passed(value))
        value=self.fixture();value['wire']['first_complete_stop']['pc']+=2
        self.assertFalse(self.passed(value))
    def test_frame_comparison_rejects_reused_buffer(self):
        raw=bytes([0,7])*(576*288//2);ram=b'\0'*32+raw
        screen=dict(width=576,height=288,bytes=len(raw),address=0x20000020,nonzero=len(raw)//2,has_detail=True)
        self.assertTrue(valid_frame(screen,raw,ram))
        self.assertFalse(valid_frame(screen,raw,ram[:-1]+b'\0'))
        self.assertFalse(valid_frame(screen,raw,ram[:32]))
        self.assertFalse(valid_frame(dict(screen,address=0x1fffffff),raw,ram))
    def test_asset_hash_size_and_vectors_before_execution(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'boot.bin';data=struct.pack('<II',0x2007fb00,0x432cb3)+b'\x5a'*24;p.write_bytes(data)
            spec=dict(path='boot.bin',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),sp=0x2007fb00,reset=0x432cb3)
            self.assertEqual(checked_asset(Path(d),spec),p.resolve())
            p.write_bytes(data[:-1]);self.assertRaises(ValueError,checked_asset,Path(d),spec)
            p.write_bytes(data[:-1]+b'\x00');self.assertRaises(ValueError,checked_asset,Path(d),spec)
            p.write_bytes(data);self.assertRaises(ValueError,checked_asset,Path(d),dict(spec,reset=0x5fbe3f))
            self.assertRaises(ValueError,checked_path,Path(d),'../elsewhere')
    def test_unknown_marker_changes_only_the_declared_profile(self):
        board=b'ota_marker: Miscellaneous.BlackwallOtaMarkerRead @ none\n    profile: "cleared"\n    bootReadPc: 4384130\n'
        changed=scenario_component('board.repl',board,'unknown-boot-marker')
        self.assertEqual(changed,board.replace(b'"cleared"',b'"unknown"'))
        self.assertEqual(scenario_component('run.py',board,'unknown-boot-marker'),board)
        self.assertRaises(ValueError,scenario_component,'board.repl',board+board,'unknown-boot-marker')
    def test_forced_execution_and_guest_memory_writes_are_rejected(self):
        for source in ['cpu.PC=1','cpu.SetRegister(0,1)','bus.WriteBytes(data,addr)','cpu.IsHalted=False']:
            self.assertRaises(ValueError,validate_runtime,source)
        validate_runtime('cpu.PerformanceInMips=167\nx=cpu.GetRegister(13)')
    def test_corrupt_image_leaves_no_output_or_runtime_job(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bad=root/'bad.bin';bad.write_bytes(b'corrupt');out=root/'output'
            self.assertRaises(ValueError,derive,PROFILE,root,out,'normal',bad)
            self.assertFalse(out.exists())
    def test_preview_is_lossless_and_contrast_is_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);e=folder/'exports';e.mkdir();raw=bytes([0,7])*(576*288//2);(e/'complete-screen.bin').write_bytes(raw)
            render_preview(folder)
            self.assertEqual((e/'complete-screen.bin').read_bytes(),raw)
            for name,expected in [('complete-screen.png',b'\0\x07'),('contrast-preview.png',b'\0\xff')]:
                data=(e/name).read_bytes();self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n');pos=8;packed=b''
                while pos<len(data):
                    n=struct.unpack_from('>I',data,pos)[0];tag=data[pos+4:pos+8];payload=data[pos+8:pos+8+n]
                    self.assertEqual(zlib.crc32(tag+payload)&0xffffffff,struct.unpack_from('>I',data,pos+8+n)[0])
                    if tag==b'IDAT':packed+=payload
                    pos+=12+n
                rows=zlib.decompress(packed);self.assertEqual(len(rows),577*288);self.assertEqual(rows[1:3],expected)
    def test_declared_actual_request_decodes(self):
        value=self.fixture();request=value['wire']['requests'][-1]
        self.assertEqual(decode_frame(request['data'])['identifier'],request['identifier'])
        bad=copy.deepcopy(request['data']);bad[8]^=1
        self.assertRaises(ValueError,decode_frame,bad)

if __name__=='__main__':unittest.main()
