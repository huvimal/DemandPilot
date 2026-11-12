import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'DEMANDPILOT_DATA_DIR': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def start(self):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=40).run()
        self.assertFalse(app.exception)
        return app

    def click(self, app, label):
        next(b for b in app.button if b.label == label).click().run()
        self.assertFalse(app.exception)

    def test_run_review_export_and_rerun_invalidates(self):
        app = self.start()
        self.click(app, 'Chạy backtest và lập dự báo')
        self.assertTrue(app.session_state['report']['recommendations'])
        next(t for t in app.text_input if t.label == 'Tên / bí danh người duyệt').set_value('Huni')
        next(t for t in app.text_input if t.label.startswith('Ghi chú')).set_value('Checked inventory assumptions')
        next(c for c in app.checkbox if c.label.startswith('Tôi đã đối chiếu')).check()
        self.click(app, 'Xác nhận rà soát báo cáo hiện tại')
        exported_id = app.session_state['reviewed_zip']['report_id']
        self.assertTrue(app.session_state['reviewed_zip']['data'])
        self.click(app, 'Chạy backtest và lập dự báo')
        from dataio import digest
        self.assertNotEqual(digest(app.session_state['report']), exported_id)
        with self.assertRaises(KeyError):
            _ = app.session_state['reviewed_zip']

    def test_review_requires_acknowledgement(self):
        app = self.start()
        self.click(app, 'Chạy backtest và lập dự báo')
        self.click(app, 'Xác nhận rà soát báo cáo hiện tại')
        self.assertTrue(app.error)
        with self.assertRaises(KeyError):
            _ = app.session_state['reviewed_zip']

    def test_switching_to_missing_upload_clears_export(self):
        app = self.start()
        self.click(app, 'Chạy backtest và lập dự báo')
        app.radio[0].set_value('CSV của tôi').run()
        self.assertFalse(app.exception)
        with self.assertRaises(KeyError):
            _ = app.session_state['report']
