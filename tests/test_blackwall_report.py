import importlib.util
import json
import struct
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('blackwall_report', Path(__file__).resolve().parents[1] / 'tools/blackwall_report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

class ReportTests(unittest.TestCase):
    def test_order_and_timed_data_remain_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); exports = root/'capture'/'exports'; exports.mkdir(parents=True)
            audit = root/'audit'; audit.mkdir()
            (audit/'report.json').write_text(json.dumps({'schema':2, 'scenario':'normal', 'boundary_kind':'bounded-capture', 'passed':True, 'execution_passed':True, 'observed':{'virtual_ticks':100000,'events':[{'label':'boot-reset','pc':42,'sequence':1}]},'semantic_validation':{'checks':[]}}))
            (exports/'wire-activation.json').write_text(json.dumps({'replies':[{'before':{'ticks':50000},'data':[1,255],'accepted':True}],'requests':[{'data':[2],'channel':1,'identifier':3}]}))
            model=report.build(root/'capture', audit, root/'out')
            self.assertEqual(model['points'],[{'name':'boot-reset','pc':42,'sequence':1}])
            self.assertEqual(model['replies'][0]['time_us'],50)
            self.assertNotIn('time_us',model['requests'][0])
            self.assertFalse(model['screen'])
            self.assertFalse((root/'out'/'screen.png').exists())

    def test_invalid_observer_timestamps_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); exports=root/'capture'/'exports'; exports.mkdir(parents=True)
            audit=root/'audit'; audit.mkdir()
            result={'schema':2,'scenario':'normal','boundary_kind':'bounded-capture','passed':True,
                    'observed':{'virtual_ticks':100000,'events':[{'label':'a','pc':2,'sequence':1,'ticks':80000}, {'label':'b','pc':4,'sequence':2,'ticks':70000}]},
                    'semantic_validation':{'checks':[]}}
            (audit/'report.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'timestamp ordering'):
                report.build(root/'capture',audit,root/'out')

    def test_uart_line_and_dma_times_preserve_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); exports=root/'capture'/'exports'; exports.mkdir(parents=True)
            audit=root/'audit';audit.mkdir()
            (audit/'report.json').write_text(json.dumps({'schema':2,'scenario':'normal','boundary_kind':'bounded-capture','passed':True,'observed':{'virtual_ticks':100000,'events':[]},'semantic_validation':{'checks':[]}}))
            line=list(b'\x1b[31mhello\x1b[0m\n')
            ports=[{'module':1,'tx':line,'ticks':[2000]*len(line),'dropped':0}, {'module':0,'tx':[1,2],'transfers':[{'ticks':3000,'data':[1,2]}],'dropped':0}]
            (exports/'retry-diagnostic.json').write_text(json.dumps({'uarts':ports}))
            model=report.build(root/'capture',audit,root/'out')
            self.assertEqual(model['firmware_events'],[{'time_us':2,'text':'hello'}])
            self.assertEqual(model['uart_tx'],[{'time_us':3,'data':'01 02'}])
            self.assertTrue(next(q for q in model['trace_quality'] if q['source']=='UART0 DMA')['matches_raw'])
            ports[0]['ticks'].pop()
            (exports/'retry-diagnostic.json').write_text(json.dumps({'uarts':ports}))
            with self.assertRaisesRegex(ValueError,'UART1 timestamp'):
                report.build(root/'capture',audit,root/'bad')

    def test_imu_model_trigger_uses_recorded_time_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);exports=root/'capture'/'exports';exports.mkdir(parents=True)
            audit=root/'audit';audit.mkdir()
            (audit/'report.json').write_text(json.dumps({'schema':2,'scenario':'normal','boundary_kind':'bounded-capture','passed':True,'observed':{'virtual_ticks':100000,'events':[]},'semantic_validation':{'checks':[]}}))
            (exports/'main-input-state.json').write_text(json.dumps({'imu':{'TriggeredAt':25000,'Triggers':2}}))
            model=report.build(root/'capture',audit,root/'out')
            self.assertEqual(model['device_events'][0]['time_us'],25)
            self.assertIn('not sensor data',model['device_events'][0]['text'])
            (exports/'main-input-state.json').write_text(json.dumps({'imu':{'TriggeredAt':100001,'Triggers':2}}))
            with self.assertRaisesRegex(ValueError,'outside capture'):
                report.build(root/'capture',audit,root/'bad')

    def test_soc_highlight_has_dedicated_material(self):
        with tempfile.TemporaryDirectory() as root:
            source=report.ROOT/'web/prototypes/board-model-bw590/g2-temple-assembly.glb'
            target=Path(root)/'board.glb'
            report.isolate_observed_soc(source,target)
            data=target.read_bytes()
            size,kind=struct.unpack_from('<II',data,12)
            model=json.loads(data[20:20+size])
            node=next(n for n in model['nodes'] if n.get('name')=='AP510BFA package')
            index=model['meshes'][node['mesh']]['primitives'][0]['material']
            self.assertEqual(model['materials'][index]['name'],'Blackwall observed SoC')
            uses=sum(primitive.get('material')==index for mesh in model['meshes'] for primitive in mesh['primitives'])
            self.assertEqual(uses,1)
            for name in ('Blackwall observed NOR','Blackwall observed Touch','Blackwall illustrative BLE','Blackwall illustrative Display','Blackwall illustrative IMU'):
                self.assertEqual(sum(m.get('name')==name for m in model['materials']),1)

    def test_host_failure_is_not_boot_failure(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'report'
            report.host_failure(dest,'normal','execution','runner failed')
            self.assertIn('"boundary": "host-error"',(dest/'report-data.js').read_text())

if __name__=='__main__': unittest.main()
