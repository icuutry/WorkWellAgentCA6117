"""Test actual component interactions with Streamlit AppTest; no model calls or repository data writes."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HAS_STREAMLIT = importlib.util.find_spec('streamlit') is not None


@unittest.skipUnless(HAS_STREAMLIT, 'Install requirements-dev.txt to run UI tests')
class UITests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {'WORKWELL_DEMO_FILE': str(Path(self.tmp.name) / 'ui.json')})
        self.patch.start()
        self.ui = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        self.ui.radio[0].set_value('Offline UI preview').run()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_generate_then_accept_buttons_update(self):
        self.assertFalse(self.ui.exception)
        self.assertTrue(self.ui.button[1].disabled)
        self.ui.button[0].click().run()
        self.assertFalse(self.ui.exception)
        self.assertFalse(self.ui.button[1].disabled)
        self.ui.button[1].click().run()
        self.assertFalse(self.ui.exception)
        self.assertEqual(self.ui.session_state['current']['decision'], 'accepted')
        self.assertTrue(self.ui.button[1].disabled)
        self.ui.run()
        import app
        backend = app.DemoBackend(Path(self.tmp.name) / 'ui.json')
        self.assertEqual(len(backend.load_history('demo-user')), 1)
        self.assertEqual(len(backend.load_logs('demo-user')), 2)

    def test_changed_form_cannot_confirm(self):
        self.ui.button[0].click().run()
        self.ui.slider[1].set_value(8)
        self.ui.button[1].click().run()
        self.assertFalse(self.ui.exception)
        self.assertNotIn('current', self.ui.session_state)
        self.assertTrue(self.ui.button[1].disabled)

    def test_warning_disables_confirmation(self):
        self.ui.multiselect[0].set_value(['Numbness'])
        self.ui.button[0].click().run()
        self.assertFalse(self.ui.exception)
        self.assertEqual(self.ui.session_state['current']['result']['status'], 'stopped')
        self.assertTrue(self.ui.button[1].disabled)

    def test_final_decisions_replace_draft_message(self):
        for decision, button in [('accepted', 1), ('rejected', 2)]:
            self.ui.button[0].click().run()
            self.ui.button[button].click().run()
            self.assertFalse(self.ui.exception)
            self.assertTrue(any(f'Plan {decision}.' in x.value for x in self.ui.success))
            self.assertFalse(any('Offline UI fixture' in x.value for x in self.ui.info))
            self.assertEqual(len(self.ui.dataframe), 2)
            self.assertTrue(all(not x.proto.expanded for x in self.ui.expander
                                if 'details (JSON)' in x.label))
            self.ui.button[3].click().run()

    def test_user_change_refreshes_history_without_generation(self):
        self.ui.button[0].click().run()
        self.ui.button[1].click().run()
        self.ui.text_input[0].set_value('other-user').run()
        self.assertFalse(self.ui.exception)
        self.assertNotIn('current', self.ui.session_state)
        self.assertTrue(self.ui.button[1].disabled)
        self.assertEqual(len(self.ui.dataframe), 0)
        self.ui.text_input[0].set_value('demo-user').run()
        self.assertEqual(len(self.ui.dataframe), 2)
        import app
        backend = app.DemoBackend(Path(self.tmp.name) / 'ui.json')
        self.assertEqual(len(backend.load_logs('demo-user')), 2)
        self.assertEqual(backend.load_logs('other-user'), [])

    def test_user_change_clears_unconfirmed_draft(self):
        self.ui.button[0].click().run()
        self.ui.text_input[0].set_value('other-user').run()
        self.assertNotIn('current', self.ui.session_state)
        self.assertTrue(self.ui.button[1].disabled)

    def test_user_change_disabled_during_uncertain_save(self):
        self.ui.button[0].click().run()
        current = self.ui.session_state['current']
        current['pending_record'] = {'decision': 'accepted'}
        self.ui.run()
        self.assertFalse(self.ui.exception)
        self.assertTrue(self.ui.text_input[0].disabled)
        self.assertTrue(self.ui.button[0].disabled)
        self.assertFalse(self.ui.button[1].disabled)
        current['decision'] = 'accepted'
        self.ui.run()
        self.assertFalse(self.ui.text_input[0].disabled)
