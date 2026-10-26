import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from focus_lock.i18n import tr, set_language
from focus_lock.storage import Storage
from focus_lock.ui import FocusWindow, ProfileDialog, EmergencyDialog
from focus_lock.core import Profile
from focus_lock.learning_ui import OutcomeDialog


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def tearDown(self): set_language('zh_TW')

    def test_catalog_and_unknown_user_text(self):
        set_language('en')
        self.assertEqual(tr('開始'), 'Start')
        self.assertEqual(tr('我自己的私人筆記'), '我自己的私人筆記')
        set_language('unsupported')
        self.assertEqual(tr('開始'), '開始')

    def test_all_explicit_ui_translations_are_in_catalog(self):
        import ast
        from focus_lock.translations import EN
        missing = set()
        for path in (Path(__file__).resolve().parents[1] / 'focus_lock').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr' and node.args and isinstance(node.args[0], ast.Constant):
                    value = node.args[0].value
                    if isinstance(value, str) and any('\u4e00' <= c <= '\u9fff' for c in value) and value not in EN: missing.add(value)
        self.assertEqual(missing, set())

    def test_english_widgets_preserve_user_content_and_unlock(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root); settings = store.load(); settings['language'] = 'en'
            settings['profiles'][0]['name'] = '我的學習方案'; store.save(settings)
            window = FocusWindow(storage=store); window.ticker.stop()
            self.assertEqual(window.start_button.text(), 'Start')
            self.assertEqual(window.profiles.itemText(0), '我的學習方案')
            self.assertTrue(window.advanced_panel.isHidden())
            profile = ProfileDialog(Profile(name='我的任務'), window.windows, window)
            self.assertEqual(profile.name.text(), '我的任務')
            self.assertEqual(profile.website_lock.text(), 'Allow only these URLs (requires the Focus Lock browser extension)')
            profile.connection_timer.stop(); profile.deleteLater()
            record = window.learning.begin(Profile(name='我的任務'), 60)
            record = window.learning.end(60, 'completed'); record['note'] = '保留我的原文'
            card = OutcomeDialog(window, record)
            self.assertEqual(card.note.toPlainText(), '保留我的原文')
            self.assertEqual(card.when.itemText(1), 'Start now'); card.deleteLater()
            unlock = EmergencyDialog(window); unlock.timer.deadline = unlock.timer.clock() - 1
            unlock.text.setText('Emergency unlock'); unlock.tick()
            self.assertTrue(unlock.confirm.isEnabled()); unlock.ticker.stop(); unlock.deleteLater()
            with patch('focus_lock.ui.QMessageBox.information'):
                window.language_choice.setCurrentIndex(0)
            self.assertEqual(store.load()['language'], 'zh_TW')
            window.tray.hide(); window.compact.hide_all(); window.hide_guards(); window.deleteLater()
