import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from project_progress import evaluate,start_task,finish_task,read_ledger,render,record_progress,resolve


class ProjectProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'repo';self.root.mkdir();(self.root/'docs').mkdir()
        self.private=Path(self.tmp.name)/'private';self.private.mkdir()
        (self.root/'input.txt').write_text('one')
        self.proof=self.private/'proof.json';self.proof.write_text('{"passed":true}')
        self.evidence={'path':'private:proof.json','sha256':hashlib.sha256(self.proof.read_bytes()).hexdigest(),
                       'checks':[{'path':['passed'],'eq':True}]}
        self.scope={'version':1,'metric':'verified-criteria-ratio','groups':{'S':'simulator'},
                    'criteria':[{'id':'S1','group':'S','title':'verified','status':'done','evidence':[self.evidence]},
                                {'id':'S2','group':'S','title':'unfinished','status':'partial','evidence':[]}]}

    def test_moved_document_resolves_historic_ledger_path(self):
        target=self.root/'docs'/'research'/'old.md'
        target.parent.mkdir();target.write_text('record')
        (self.root/'docs'/'document-path-map.json').write_text(json.dumps({'paths': {'docs/old.md':'docs/research/old.md'}}))
        self.assertEqual(resolve('docs/old.md',self.root,self.private),target.resolve())
        self.scope.update(objective='goal')
        self.scope['criteria'][0]['document']='docs/old.md'
        text=render(self.scope,evaluate(self.scope,self.root,self.private),[],{'docs/old.md':'docs/research/old.md'})
        self.assertIn('(research/old.md)',text)

    def start(self,repeat=None):
        return start_task(self.root,self.private,'same-work','work','verification',['input.txt'],['S1'],repeat)

    def test_only_verified_complete_criteria_count_and_stale_evidence_drops_score(self):
        score=evaluate(self.scope,self.root,self.private)
        self.assertEqual((score.get('completed'),score.get('total'),score.get('percent')),(1,2,50.0))
        self.proof.unlink()
        score=evaluate(self.scope,self.root,self.private)
        self.assertEqual(score.get('completed'),0)
        self.assertEqual(score['criteria'][0]['effective_status'],'stale')

    def test_false_or_changed_evidence_never_counts_complete(self):
        self.proof.write_text('{"passed":false}')
        self.assertEqual(evaluate(self.scope,self.root,self.private).get('completed'),0)

    def test_same_active_and_completed_inputs_are_refused_without_new_task(self):
        task=self.start();self.assertEqual(task,'bw-0001')
        with self.assertRaisesRegex(ValueError,'Existing task'):self.start()
        finish_task(self.root,self.private,task,'done',['private:proof.json'],'evidence checked')
        with self.assertRaisesRegex(ValueError,'Existing task'):self.start()
        self.assertEqual({r['phase'] for r in read_ledger(self.root)},{task})

    def test_changed_inputs_allow_new_work_and_history_is_append_only(self):
        task=self.start();finish_task(self.root,self.private,task,'done',['private:proof.json'],'verification')
        previous=(self.root/'docs/work-log.tsv').read_bytes()
        (self.root/'input.txt').write_text('two')
        self.assertEqual(self.start(),'bw-0002')
        self.assertTrue((self.root/'docs/work-log.tsv').read_bytes().startswith(previous))

    def test_progress_preserves_scope_identity_and_append_only_history(self):
        task=self.start();before=(self.root/'docs/work-log.tsv').read_bytes()
        start=read_ledger(self.root)[0]
        record_progress(self.root,self.private,task,'running','actual process checked',['private:proof.json'])
        row=read_ledger(self.root)[-1]
        self.assertEqual(row['event'],'progress')
        self.assertEqual(row['scope_ids'],'S1')
        for key in ('phase','task_key','input_sha256','inputs','result'):
            self.assertEqual(row[key],start[key])
        self.assertTrue((self.root/'docs/work-log.tsv').read_bytes().startswith(before))
        with self.assertRaisesRegex(ValueError,'Existing task'):self.start()
        finish_task(self.root,self.private,task,'done',['private:proof.json'],'verification')

    def test_progress_after_completion_is_rejected_without_appending(self):
        task=self.start();finish_task(self.root,self.private,task,'done',['private:proof.json'],'complete')
        before=(self.root/'docs/work-log.tsv').read_bytes()
        with self.assertRaisesRegex(ValueError,'in-progress'):
            record_progress(self.root,self.private,task,'invalid resume','verification',[])
        self.assertEqual((self.root/'docs/work-log.tsv').read_bytes(),before)

    def test_progress_missing_evidence_is_rejected_without_appending(self):
        task=self.start();before=(self.root/'docs/work-log.tsv').read_bytes()
        with self.assertRaisesRegex(ValueError,'Evidence file not found'):
            record_progress(self.root,self.private,task,'progress','verification',['missing.json'])
        self.assertEqual((self.root/'docs/work-log.tsv').read_bytes(),before)

    def test_explicit_repeat_reason_is_recorded(self):
        task=self.start();finish_task(self.root,self.private,task,'done',['private:proof.json'],'verification')
        self.assertEqual(self.start('reverify after external conditions changed'),'bw-0002')
        self.assertIn('external conditions',read_ledger(self.root)[-1]['why'])

    def test_completion_without_evidence_is_rejected_and_deferred_work_resumes(self):
        task=self.start()
        with self.assertRaises(ValueError):finish_task(self.root,self.private,task,'done',[],'none')
        finish_task(self.root,self.private,task,'deferred',[],'prerequisite')
        self.assertEqual(self.start(),task)

    def test_duplicate_criteria_and_path_escape_are_rejected(self):
        self.scope['criteria'].append(self.scope['criteria'][0])
        with self.assertRaises(ValueError):evaluate(self.scope,self.root,self.private)
        with self.assertRaises(ValueError):start_task(self.root,self.private,'bad','bad','bad',['../outside'],['S1'])

    def test_reverted_inputs_reuse_earlier_completed_work_not_only_latest(self):
        first=self.start();finish_task(self.root,self.private,first,'done',['private:proof.json'],'A verification')
        (self.root/'input.txt').write_text('two')
        second=self.start();finish_task(self.root,self.private,second,'done',['private:proof.json'],'B verification')
        (self.root/'input.txt').write_text('one')
        with self.assertRaisesRegex(ValueError,first):self.start()

    def test_scope_ids_must_exist_in_catalog_before_work_is_logged(self):
        (self.root/'docs/project-scope.json').write_text(json.dumps(self.scope))
        with self.assertRaisesRegex(ValueError,'scope'):
            start_task(self.root,self.private,'bad-scope','bad','bad',['input.txt'],['S99'])
        self.assertEqual(read_ledger(self.root),[])

    def test_operational_work_is_tracked_but_does_not_raise_delivery_percentage(self):
        self.scope['criteria'][1].update(status='done',kind='operation',evidence=[self.evidence])
        score=evaluate(self.scope,self.root,self.private)
        self.assertEqual((score.get('completed'),score.get('total')),(1,1))
        self.assertEqual((score['operational_completed'],score['operational_total']),(1,1))

    def test_dashboard_key_states_follow_evidence_instead_of_fixed_incomplete_text(self):
        self.scope.update(objective='goal',groups={'W':'web','S':'sim','D':'display'})
        self.scope['criteria']=[dict(id=id,group=id[0],title=id,status='done',evidence=[self.evidence]) for id in ['W6','S6','D3']]
        text=render(self.scope,evaluate(self.scope,self.root,self.private),[])
        self.assertIn('Integrated main (S6): Done',text)
        self.assertNotIn('Full firmware boot and integrated screen output are incomplete',text)

    def test_emulator_scope_uses_its_own_key_states_and_coverage_label(self):
        self.scope.update(objective='emulator',dashboard_states=[['S1','Original execution'],['S2','Integrated display']],
                          metric_label='Emulator acceptance criteria met')
        text=render(self.scope,evaluate(self.scope,self.root,self.private),[])
        self.assertIn('Emulator acceptance criteria met: 50.0%',text)
        self.assertIn('Original execution: Done',text)
        self.assertIn('Integrated display: Partial',text)
        self.assertNotIn('Web device path',text)

    def test_current_outcome_counts_evidence_without_raising_overall_score(self):
        self.scope['current_outcome']={'title':'First screen','gates':[
            dict(id='M1',title='Original send',status='done',evidence=[self.evidence]),
            dict(id='M2',title='Original receive',status='done',evidence=[self.evidence])]}
        score=evaluate(self.scope,self.root,self.private)
        self.assertEqual((score['completed'],score['total']),(1,2))
        self.assertEqual((score['current_outcome']['completed'],score['current_outcome']['total']),(2,2))
        self.scope['objective']='goal'
        self.assertIn('First screen: 2/2',render(self.scope,score,[]))
        self.proof.unlink()
        score=evaluate(self.scope,self.root,self.private)
        self.assertEqual(score['current_outcome']['completed'],0)

    def test_dashboard_separates_active_work_from_historical_deferred_records(self):
        self.scope['objective']='goal'
        rows=[dict(phase='bw-0001',task_key='old',event='finish',result='deferred',why='old overall 44.8%'),
              dict(phase='bw-0002',task_key='current',event='start',result='in-progress',why='current review')]
        text=render(self.scope,evaluate(self.scope,self.root,self.private),rows)
        current=text.split('## Current work and next steps')[1].split('## Deferred and failed work history')[0]
        self.assertIn('current review',current)
        self.assertNotIn('old overall 44.8%',current)
        self.assertIn('old overall 44.8%',text.split('## Deferred and failed work history')[1])
