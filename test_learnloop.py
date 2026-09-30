"""Business-rule tests; model-quality evidence is recorded separately."""
import copy,io,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from quiz_core import *
from database import Store
from colab_worker import generate_pack

ROOT=Path(__file__).parent

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT)
        self.store=Store(Path(self.tmp.name)/'test.sqlite3')
        self.sources=parse_notes(ROOT.joinpath('sample_notes.md').read_text(encoding='utf-8'),'Test notes')
        self.job=make_job(self.sources,'Test pack',3)
        # Explicit synthetic fixtures, never presented as AI-generated demo evidence.
        facts=[('What Python collection is mutable and ordered?','Lists','Lists are mutable ordered collections.'),
               ('What uniquely identifies each database row?','primary key','A primary key uniquely identifies each row in a table.'),
               ('Which data is used to fit model parameters?','training set','A training set is used to fit model parameters.')]
        self.result={'job_id':self.job['job_id'],'sha256':self.job['sha256'],'model':'SYNTHETIC TEST FIXTURE','records':[]}
        for i,(stem,answer,quote) in enumerate(facts):
            self.result['records'].append({'id':f'Q{i+1}','raw':json.dumps(dict(stem=stem,options=[answer,'other option','third option','fourth option'],correct=0,explanation='The source directly states this fact.',quote=quote))})
    def tearDown(self):self.tmp.cleanup()
    def pack(self,approve=True):
        self.store.save_job(self.job);p=self.store.import_pack(self.job['job_id'],self.result)
        if approve:
            for q in p['questions']:self.store.review(p['id'],q['id'],q)
        return self.store.get('pack',p['id'])
    def test_topics_extracted(self):self.assertEqual(len(self.sources),3)
    def test_empty_notes_rejected(self):
        with self.assertRaises(ValueError):parse_notes('tiny')
    def test_source_quote_rejected(self):
        q=json.loads(self.result['records'][0]['raw']);q['quote']='This sentence is invented and absent.'
        with self.assertRaises(ValueError):validate_question(q,self.sources[0])
    def test_boolean_answer_rejected(self):
        q=json.loads(self.result['records'][0]['raw']);q['correct']=True
        with self.assertRaises(ValueError):validate_question(q,self.sources[0])
    def test_placeholder_explanation_rejected(self):
        q=json.loads(self.result['records'][0]['raw']);q['explanation']='Why the answer is correct.'
        with self.assertRaises(ValueError):validate_question(q,self.sources[0])
    def test_duplicate_options_rejected(self):
        q=json.loads(self.result['records'][0]['raw']);q['options'][1]=q['options'][0].upper()
        with self.assertRaises(ValueError):validate_question(q,self.sources[0])
    def test_job_mismatch_rejected(self):
        self.result['sha256']='wrong'
        with self.assertRaises(ValueError):import_generated(self.job,self.result)
    def test_unknown_question_rejected(self):
        self.result['records'][0]['id']='Q99'
        with self.assertRaises(ValueError):import_generated(self.job,self.result)
    def test_partial_output_records_missing(self):
        self.result['records']=self.result['records'][:1]
        p=import_generated(self.job,self.result)
        self.assertEqual(len(p['questions']),1);self.assertEqual(len(p['rejected']),2)
    def test_malformed_json_excluded(self):
        self.result['records'][0]['raw']='not JSON'
        p=import_generated(self.job,self.result);self.assertEqual(len(p['questions']),2)
    def test_unreviewed_blocked(self):
        p=self.pack(False)
        with self.assertRaises(ValueError):self.store.start_attempt(p['id'])
    def test_duplicate_import_blocked(self):
        self.pack()
        with self.assertRaises(ValueError):self.store.import_pack(self.job['job_id'],self.result)
    def test_unanswered_quiz_not_saved_as_finished(self):
        a=self.store.start_attempt(self.pack()['id'])
        with self.assertRaises(ValueError):self.store.finish(a['id'],{'Q1':0})
        self.assertFalse(self.store.get('attempt',a['id'])['finished'])
    def test_scoring_weakness_and_revision(self):
        p=self.pack();a=self.store.start_attempt(p['id']);a=self.store.finish(a['id'],{'Q1':0,'Q2':1,'Q3':0})
        self.assertEqual(a['result']['percent'],66.7)
        self.assertEqual(weak_topics(a['result']),[self.sources[1]['topic']])
        revision=self.store.start_attempt(p['id'],'Weak topics')
        self.assertEqual([q['id'] for q in revision['questions']],['Q2'])
    def test_restart_persistence_and_idempotence(self):
        a=self.store.start_attempt(self.pack()['id']);first=self.store.finish(a['id'],{'Q1':0,'Q2':0,'Q3':0})
        reopened=Store(self.store.path);second=reopened.finish(a['id'],{'Q1':1,'Q2':1,'Q3':1})
        self.assertEqual(first,second);self.assertEqual(len(reopened.list('attempt')),1)
    def test_review_does_not_rewrite_active_attempt(self):
        p=self.pack();a=self.store.start_attempt(p['id']);q=copy.deepcopy(p['questions'][0]);q['stem']='Which collection is ordered and mutable according to the notes?'
        self.store.review(p['id'],q['id'],q)
        self.assertNotEqual(self.store.get('pack',p['id'])['questions'][0]['stem'],self.store.get('attempt',a['id'])['questions'][0]['stem'])
    def test_worker_checksum_blocks_inference(self):
        self.job['title']='tampered'
        with self.assertRaises(ValueError):generate_pack(self.job,lambda _:self.fail('Model must not run'),'test')
    def test_live_generation_calls_configured_groq_qwen_model(self):
        client=Mock()
        client.chat.completions.create.return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"stem":"mock question"}'))]
        )
        with patch('groq.Groq',return_value=client):
            result=generate_live(self.job,'test-only-key')
        self.assertEqual(result['model'],'qwen/qwen3.8-27b (Groq API)')
        self.assertEqual(len(result['records']),len(self.job['items']))
        self.assertEqual(client.chat.completions.create.call_count,len(self.job['items']))
        self.assertTrue(all(c.kwargs['model']=='qwen/qwen3.8-27b' for c in client.chat.completions.create.call_args_list))
    def test_pdf_page_evidence(self):
        from reportlab.pdfgen.canvas import Canvas
        buff=io.BytesIO();c=Canvas(buff);c.drawString(40,760,self.sources[0]['text'][:180]);c.showPage();c.drawString(40,760,self.sources[1]['text'][:180]);c.save()
        sources=parse_pdf(buff.getvalue(),'test.pdf');self.assertEqual([s['page'] for s in sources],[1,2])
    def test_invalid_pdf_rejected(self):
        with self.assertRaises(ValueError):parse_pdf(b'not a pdf','broken.pdf')

if __name__=='__main__':unittest.main(verbosity=2)
