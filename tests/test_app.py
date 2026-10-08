import tempfile
import unittest
from pathlib import Path

import app

class PageLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.backend=app.DemoBackend(Path(self.tmp.name)/'data.json')
        self.state={}
        self.input={'user_id':'demo-user','date':'2026-10-08','sitting_hours':6.0,
                    'pain_location':'Neck','pain_score':3,'fatigue_score':4,
                    'warning_signs':[],'previous_completion':'Not applicable'}
    def tearDown(self): self.tmp.cleanup()
    def generate(self): app.handle_action(self.state,self.backend,self.input,'generate')
    def test_generation_and_accept_do_not_generate_twice(self):
        self.generate()
        app.handle_action(self.state,self.backend,self.input,'generate')
        self.assertEqual(len(self.backend.load_logs('demo-user')),1)
        app.handle_action(self.state,self.backend,self.input,'accepted')
        app.handle_action(self.state,self.backend,self.input,'accepted')
        self.assertEqual(len(self.backend.load_history('demo-user')),1)
        self.assertEqual(len(self.backend.load_logs('demo-user')),2)
    def test_changed_input_cannot_accept_old_plan(self):
        self.generate()
        self.input['fatigue_score']=9
        level,_=app.handle_action(self.state,self.backend,self.input,'accepted')
        self.assertEqual(level,'warning')
        self.assertNotIn('current',self.state)
        self.assertEqual(self.backend.load_history('demo-user'),[])
    def test_warning_stops_and_cannot_be_accepted(self):
        self.input['warning_signs']=['Numbness']
        self.generate()
        self.assertEqual(self.state['current']['result']['status'],'stopped')
        app.handle_action(self.state,self.backend,self.input,'accepted')
        self.assertEqual(self.backend.load_history('demo-user'),[])
    def test_persistence_user_isolation_and_feedback(self):
        self.generate()
        app.handle_action(self.state,self.backend,self.input,'accepted')
        reopened=app.DemoBackend(self.backend.path)
        self.assertEqual(len(reopened.load_history('demo-user')),1)
        self.assertEqual(reopened.load_history('other-user'),[])
        self.input['date']='2026-10-09'
        self.input['previous_completion']='Partly completed'
        self.generate()
        reason=self.state['current']['result']['plan']['actions'][0]['reason']
        self.assertIn('Partly completed',reason)
    def test_rejected_plan_does_not_count_as_accepted(self):
        self.generate()
        app.handle_action(self.state,self.backend,self.input,'rejected')
        self.input['date']='2026-10-09'
        self.generate()
        self.assertIn('No previously accepted',self.state['current']['result']['plan']['actions'][0]['reason'])
    def test_invalid_source_and_invalid_return_are_rejected(self):
        result=self.backend.start_workflow(self.input)
        result['plan']['actions'][0]['source_ids']=['MISSING']
        with self.assertRaises(ValueError):app.validate_result(result)
        with self.assertRaises(ValueError):app.validate_result(None)
    def test_corrupt_file_is_preserved(self):
        self.backend.path.write_text('broken',encoding='utf-8')
        with self.assertRaises(Exception):self.backend.load_history('demo-user')
        self.assertEqual(self.backend.path.read_text(encoding='utf-8'),'broken')
    def test_failure_leaves_retryable_same_record(self):
        self.generate()
        actual=self.backend.submit_decision
        attempts=[]
        def uncertain_save(record):
            attempts.append(record)
            actual(record)
            raise OSError('Simulate lost success response')
        self.backend.submit_decision=uncertain_save
        with self.assertRaises(OSError):app.handle_action(self.state,self.backend,self.input,'accepted')
        self.assertIsNone(self.state['current']['decision'])
        level,_=app.handle_action(self.state,self.backend,self.input,'rejected')
        self.assertEqual(level,'warning')
        self.backend.submit_decision=actual
        app.handle_action(self.state,self.backend,self.input,'accepted')
        self.assertEqual(len(self.backend.load_history('demo-user')),1)
        self.assertEqual(self.state['current']['decision'],'accepted')

if __name__=='__main__':unittest.main(verbosity=2)
