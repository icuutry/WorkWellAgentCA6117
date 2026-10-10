import types
import unittest
from unittest.mock import patch

import app
from contracts import check_result, make_result
import workflow
import safety
import retrieval
import llm
import storage
import feedback


class InterfaceTests(unittest.TestCase):
    def test_remaining_placeholder_modules_are_explicit_errors(self):
        results = [retrieval.retrieve_guidance({}), llm.generate_plan({}, {}, []),
                   storage.load_history('demo-user'), storage.load_logs('demo-user'),
                   storage.save_record({}), storage.append_log({}),
                   storage.save_feedback('demo-user', 'plan-1', {}), feedback.build_feedback_context({}, [])]
        for result in results:
            check_result(result)
            self.assertEqual(result['status'], 'error')
            self.assertEqual(result['error_code'], 'NOT_IMPLEMENTED')

    def test_input_validation_reports_invalid_input(self):
        result = check_result(safety.validate_input({}))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'INVALID_INPUT')
        self.assertEqual(result['data'], {})

    def test_safety_check_reports_invalid_input(self):
        result = check_result(safety.check_safety({}, []))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'INVALID_INPUT')
        self.assertEqual(result['data'], {})

    def test_plan_validation_reports_invalid_output(self):
        result = check_result(safety.validate_plan({}, []))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'INVALID_MODEL_OUTPUT')
        self.assertEqual(result['data'], {})

    def test_workflow_input_validation_is_real(self):
        result = check_result(workflow.start_workflow({}))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'INVALID_INPUT')
        self.assertEqual(result['data'], {})

    def test_decision_validation_is_real(self):
        result = check_result(workflow.submit_decision({}))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'INVALID_INPUT')
        self.assertEqual(result['data'], {})

    def test_errors_need_codes(self):
        with self.assertRaises(ValueError): make_result('error')
        with self.assertRaises(ValueError): check_result({'status': 'ok', 'data': {}})

    def test_adapter_maps_formal_workflow_result(self):
        fake_workflow = types.ModuleType('workflow')
        fake_storage = types.ModuleType('storage')
        fake_workflow.start_workflow = lambda x: make_result('stopped', message='Stop', error_code='SAFETY_STOP')
        fake_workflow.submit_decision = lambda x: make_result('saved')
        fake_storage.load_history = lambda u: make_result('ok', data={'records': [{'user_id': u}]})
        fake_storage.load_logs = lambda u: make_result('ok', data={'events': []})
        with patch.dict('sys.modules', {'workflow': fake_workflow, 'storage': fake_storage}):
            backend = app.TeamBackend()
            self.assertEqual(backend.start_workflow({})['status'], 'stopped')
            self.assertEqual(backend.load_history('demo-user')[0]['user_id'], 'demo-user')
            self.assertEqual(backend.load_logs('demo-user'), [])
            self.assertEqual(backend.submit_decision({})['status'], 'saved')

    def test_invalid_real_workflow_input_is_not_a_mock_plan(self):
        backend = app.TeamBackend()
        result = backend.start_workflow({})
        app.validate_result(result)
        self.assertEqual(result['status'], 'error')
        self.assertIsNone(result['plan'])
        with self.assertRaises(ValueError): backend.load_history('demo-user')
