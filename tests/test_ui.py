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
