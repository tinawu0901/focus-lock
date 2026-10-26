"""Headless widget integration tests; never enforce rules against real windows."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
    from focus_lock.ui import FocusWindow, EmergencyDialog, ProfileDialog
    from focus_lock.storage import Storage
    from focus_lock.core import Profile
    HAS_QT = True
except ImportError:
    HAS_QT = False


class FakeWindows:
    def foreground(self): return None
    def applications(self): return [r"C:\Tools\Study.exe"]
    def activate(self, hwnd): return False
    def visible_windows(self): return [(123, r"C:\Study.exe", 100, "Study")]


@unittest.skipUnless(HAS_QT, "需要安裝 PySide6")
class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.preflight = patch("focus_lock.ui.PreflightDialog.exec", return_value=1)
        self.preflight_mock = self.preflight.start()
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.store = Storage(self.directory.name)
        with patch("focus_lock.ui.Storage", return_value=self.store), patch("focus_lock.ui.Windows", FakeWindows):
            self.window = FocusWindow()

    def tearDown(self):
        self.preflight.stop()
        self.window.compact.hide_all()
        self.window.hide_guards()
        self.window.ticker.stop(); self.window.tray.hide()
        self.window.hide(); self.window.deleteLater(); self.app.processEvents()
        self.directory.cleanup()

    def test_focus_pause_break_idle(self):
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.start()
        self.assertEqual(self.window.timer.phase, "focus")
        self.window.pause(); self.assertTrue(self.window.timer.paused)
        self.window.pause(); self.assertFalse(self.window.timer.paused)
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick(); self.assertEqual(self.window.timer.phase, "break")
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick(); self.assertEqual(self.window.timer.phase, "idle")

    def test_strict_controls_and_stop_guard(self):
        self.window.active = Profile(strict=True, allowed=["Study.exe"])
        self.window.timer.start(60); self.window.update_controls()
        self.assertTrue(self.window.pause_button.isHidden())
        self.assertTrue(self.window.stop_button.isHidden())
        self.window.stop(); self.window.pause()
        self.assertEqual(self.window.timer.phase, "focus")
        self.assertFalse(self.window.timer.paused)

    def test_emergency_requires_time_and_text(self):
        dialog = EmergencyDialog(self.window)
        dialog.text.setText("緊急解鎖")
        self.assertFalse(dialog.confirm.isEnabled())
        dialog.timer.deadline = dialog.timer.clock() - 1; dialog.tick()
        self.assertTrue(dialog.confirm.isEnabled())
        dialog.text.setText("wrong"); self.assertFalse(dialog.confirm.isEnabled())
        dialog.ticker.stop(); dialog.deleteLater()

    def test_profile_roundtrip(self):
        dialog = ProfileDialog(Profile(name="聽力", allowed=["Study.exe"], description="方案說明"), FakeWindows(), self.window)
        self.assertEqual(dialog.profile().name, "聽力")
        self.assertEqual(dialog.profile().allowed, ["Study.exe"])
        self.assertEqual(dialog.profile().description, "方案說明")
        dialog.deleteLater()

    def test_foreground_policy_and_pause(self):
        self.window.active = Profile(allowed=["Study.exe"])
        self.window.timer.start(60)
        self.window.windows.foreground = lambda: (123, r"C:\Study.exe", 100)
        self.window.tick()
        self.assertEqual(self.window.last_allowed, 123)
        activations = []
        self.window.windows.activate = lambda hwnd: activations.append(hwnd) or True
        self.window.windows.foreground = lambda: (456, r"C:\LINE.exe", 200)
        self.window.tick()
        self.assertTrue(self.window.guard.visible)
        self.assertEqual(self.window.guard.windows[0].choices.currentData(), 123)
        self.window.guard.windows[0].return_to_work()
        self.assertEqual(activations, [123])
        self.assertFalse(self.window.guard.visible)
        self.window.tick()
        self.assertTrue(self.window.guard.visible)
        self.window.timer.pause(); self.window.tick()
        self.assertEqual(activations, [123])
        self.assertFalse(self.window.guard.visible)

    def test_guard_hides_on_allowed_foreground_and_finish(self):
        self.window.active = Profile(allowed=["Study.exe"])
        self.window.timer.start(60)
        self.window.windows.foreground = lambda: (456, r"C:\LINE.exe", 200)
        self.window.tick(); self.assertTrue(self.window.guard.visible)
        self.window.windows.foreground = lambda: None
        self.window.tick(); self.assertTrue(self.window.guard.visible)
        self.window.windows.foreground = lambda: (123, r"C:\Study.exe", 100)
        self.window.tick(); self.assertFalse(self.window.guard.visible)
        self.window.guard.show("LINE.exe")
        self.window.finish(); self.assertFalse(self.window.guard.visible)

    def test_guard_strict_and_window_revalidation(self):
        self.window.active = Profile(strict=True, allowed=["Study.exe"])
        self.window.timer.start(60)
        self.window.guard.show("LINE.exe")
        guard = self.window.guard.windows[0]
        self.assertTrue(guard.pause_button.isHidden())
        self.window.windows.visible_windows = lambda: [(123, "LINE.exe", 200, "Changed handle")]
        with patch.object(self.window.windows, "activate") as activate:
            guard.return_to_work()
            activate.assert_not_called()
        self.assertTrue(self.window.guard.visible)
        self.assertIsNone(guard.choices.currentData())

    def test_break_releases_guard(self):
        self.window.active = Profile(allowed=["Study.exe"])
        self.window.timer.start(60)
        self.window.guard.show("LINE.exe")
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick()
        self.assertEqual(self.window.timer.phase, "break")
        self.assertFalse(self.window.guard.visible)

    def test_unlock_dialog_does_not_suspend_enforcement(self):
        self.window.active = Profile(allowed=["Study.exe"])
        self.window.timer.start(60)
        self.window.unlock_open = True
        self.window.windows.foreground = lambda: (456, "LINE.exe", 200)
        with patch.object(self.window.guard, "show") as show:
            self.window.tick()
            show.assert_called_once_with("LINE.exe", activate=False)

    def test_explicit_exit_accepts_close(self):
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        self.window.exiting = True
        with patch.object(self.window, "exit_application"):
            self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())

    def test_idle_close_exits(self):
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch.object(self.window, "exit_application") as exit_app:
            self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertTrue(self.window.exiting)
        self.assertFalse(self.window.ticker.isActive())
        exit_app.assert_called_once()

    def test_normal_close_confirm_or_cancel(self):
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QMessageBox
        self.window.active = Profile(allowed=["Study.exe"])
        self.window.timer.start(60)
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No), patch.object(self.window, "exit_application") as exit_app:
            event = QCloseEvent(); self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertFalse(self.window.exiting)
            self.assertEqual(self.window.timer.phase, "focus")
            exit_app.assert_not_called()
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch.object(self.window, "exit_application"):
            event = QCloseEvent(); self.window.closeEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(self.window.timer.phase, "idle")

    def test_strict_close_requires_unlock(self):
        from PySide6.QtGui import QCloseEvent
        self.window.active = Profile(strict=True, allowed=["Study.exe"])
        self.window.timer.start(60)
        with patch.object(self.window, "unlock") as unlock, patch.object(self.window, "exit_application") as exit_app:
            event = QCloseEvent(); self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            unlock.assert_called_once(); exit_app.assert_not_called()
        with patch.object(self.window, "unlock", side_effect=self.window.finish), patch.object(self.window, "exit_application"):
            event = QCloseEvent(); self.window.closeEvent(event)
            self.assertTrue(event.isAccepted())

    def test_tray_and_close_button_share_close_action(self):
        with patch.object(self.window, "close") as close:
            self.window.quit()
            close.assert_called_once()
        with patch.object(self.window, "exit_application"):
            self.window.close_button.click()
        self.assertTrue(self.window.exiting)

    def test_session_shows_only_small_timer_at_top(self):
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.show(); self.window.start()
        self.assertTrue(self.window.isHidden())
        self.assertTrue(self.window.compact.isVisible())
        self.assertEqual((self.window.compact.width(), self.window.compact.height()), (140, 48))
        self.assertEqual(self.window.compact.y(), self.window.screen().availableGeometry().top() + 8)
        self.assertFalse(self.window.compact.controls.isVisible())
        self.window.finish()
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.compact.isVisible())

    def test_hover_controls_expand_and_collapse(self):
        from PySide6.QtCore import QPoint, QPointF
        from PySide6.QtGui import QEnterEvent
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.start()
        compact = self.window.compact
        compact.enterEvent(QEnterEvent(QPointF(10, 10), QPointF(10, 10), QPointF(compact.pos())))
        self.assertTrue(compact.controls.isVisible())
        with patch("focus_lock.compact.QCursor.pos", return_value=compact.controls.frameGeometry().center()):
            compact.collapse_if_outside()
            self.assertTrue(compact.controls.isVisible())
        with patch("focus_lock.compact.QCursor.pos", return_value=QPoint(-100000, -100000)):
            compact.collapse_if_outside()
            self.assertFalse(compact.controls.isVisible())
        self.assertTrue(compact.isVisible())

    def test_strict_compact_keeps_only_unlock_and_exit(self):
        self.window.active = Profile(strict=True, allowed=["Study.exe"])
        self.window.timer.start(60); self.window.update_controls()
        self.window.compact.expand()
        controls = self.window.compact.controls
        self.assertTrue(controls.pause_button.isHidden())
        self.assertTrue(controls.stop_button.isHidden())
        self.assertTrue(controls.unlock_button.isVisible())

    def test_compact_pause_resume_and_break_remain_small(self):
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.start(); self.window.compact.expand()
        self.window.compact.controls.pause_button.click()
        self.assertTrue(self.window.timer.paused)
        self.assertEqual(self.window.compact.controls.pause_button.text(), "繼續")
        self.window.compact.controls.pause_button.click()
        self.assertFalse(self.window.timer.paused)
        self.window.compact.controls.hide()
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick()
        self.assertEqual(self.window.timer.phase, "break")
        self.assertTrue(self.window.isHidden())
        self.assertTrue(self.window.compact.isVisible())
        self.assertFalse(self.window.compact.controls.isVisible())

    def test_tray_reveals_compact_controls(self):
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.start(); self.window.show_panel()
        self.assertTrue(self.window.isHidden())
        self.assertTrue(self.window.compact.controls.isVisible())

    def test_compact_close_can_cancel_or_exit_with_hidden_main(self):
        from PySide6.QtWidgets import QMessageBox
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        self.window.start()
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No), patch.object(self.window, "exit_application"):
            self.window.compact.close()
            self.assertTrue(self.window.compact.isVisible())
            self.assertFalse(self.window.exiting)
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch.object(self.window, "exit_application") as exit_app:
            self.window.compact.close()
            self.assertTrue(self.window.exiting)
            self.assertFalse(self.window.compact.isVisible())
            exit_app.assert_called_once()

    def test_copy_and_delete_profile_persist_without_aliasing(self):
        from PySide6.QtWidgets import QMessageBox
        self.window.settings["profiles"][0]["launch_tools"] = [{"executable": "Study.exe", "arguments": ["--mode"]}]
        self.window.copy_profile()
        self.assertIn("副本", self.window.selected().name)
        self.window.settings["profiles"][-1]["launch_tools"][0]["arguments"].append("new")
        self.assertEqual(self.window.settings["profiles"][0]["launch_tools"][0]["arguments"], ["--mode"])
        count = len(self.window.settings["profiles"])
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.delete_profile()
        self.assertEqual(len(self.window.settings["profiles"]), count)
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_profile()
        self.assertEqual(len(self.store.load()["profiles"]), count - 1)

    def test_website_ack_loss_blocks_browser_pause_and_finish_release(self):
        from focus_lock.native_host import respond
        import time
        profile = Profile(allowed=["msedge.exe"], browser_executable="msedge.exe", website_lock=True, urls=["https://chatgpt.com/"])
        self.window.active = profile; self.window.timer.start(60)
        self.window.bridge.publish(profile, active=True, force=True)
        self.assertTrue(self.window.blocked("msedge.exe"))
        respond(self.store.root, {"browser": "edge", "revision": self.window.bridge.revision, "applied": True})
        self.assertFalse(self.window.blocked("msedge.exe"))
        self.window.guard.show("msedge.exe")
        self.window.pause()
        self.assertFalse(self.window.guard.visible)
        import json
        self.assertFalse(json.loads(self.window.bridge.path.read_text())["active"])
        self.window.finish()
        self.assertFalse(json.loads(self.window.bridge.path.read_text())["active"])

    def test_preflight_waits_for_actual_work_window(self):
        from focus_lock.ui import PreflightDialog
        profile = Profile(allowed=["Study.exe"], launch_tools=[{"executable": "Study.exe", "arguments": []}])
        self.window.windows.visible_windows = lambda: []
        with patch("focus_lock.tools.resolve_executable", return_value=r"C:\Study.exe"):
            dialog = PreflightDialog(profile, self.window)
            self.assertFalse(dialog.begin.isEnabled())
            self.window.windows.visible_windows = lambda: [(1, r"C:\Study.exe", 1, "Work")]
            dialog.refresh(); self.assertTrue(dialog.begin.isEnabled())
            dialog.refresh_timer.stop(); dialog.deleteLater()

    def test_profile_tool_arguments_and_urls_roundtrip(self):
        profile = Profile(name="口說", allowed=["WINWORD.EXE"], launch_tools=[{"executable": "WINWORD.EXE", "arguments": ["document with spaces.docx"]}],
                          website_lock=True, urls=["https://chatgpt.com/"], browser_executable="msedge.exe")
        dialog = ProfileDialog(profile, FakeWindows(), self.window)
        saved = dialog.profile()
        self.assertEqual(saved.launch_tools, profile.launch_tools)
        self.assertEqual(saved.urls, profile.urls)
        self.assertIn("msedge.exe", saved.allowed)
        self.assertTrue(saved.website_lock)
        dialog.deleteLater()

    def test_checkbox_selector_refresh_search_and_selection(self):
        from focus_lock.selectors import CheckListDialog
        from PySide6.QtCore import Qt
        rows = [(["Code", "Project"], "Code.exe"), (["Word", "Notes"], "WINWORD.EXE")]
        dialog = CheckListDialog("Apps", ["App", "Window"], lambda: (list(rows), "ready"), self.window)
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        rows.append((["Terminal", "Shell"], "WindowsTerminal.exe"))
        dialog.refresh(); self.assertEqual(dialog.selected(), ["Code.exe"])
        dialog.search.setText("Notes")
        self.assertTrue(dialog.table.isRowHidden(0))
        self.assertFalse(dialog.table.isRowHidden(1))
        dialog.select_visible(); self.assertEqual(dialog.selected(), ["Code.exe", "WINWORD.EXE"])
        dialog.reject(); self.assertFalse(dialog.timer.isActive()); dialog.deleteLater()

    def test_multiselect_apps_preserves_existing_launch_arguments(self):
        from focus_lock.selectors import CheckListDialog
        from PySide6.QtCore import Qt
        dialog = ProfileDialog(Profile(launch_tools=[{"executable": r"C:\Study.exe", "arguments": ["--keep"]}]), FakeWindows(), self.window)
        def choose(picker):
            picker.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
            return 1
        with patch.object(CheckListDialog, "exec", choose): dialog.pick_running(True)
        self.assertIn(r"C:\Study.exe", dialog.allowed.toPlainText())
        self.assertEqual(dialog.launch_tools, [{"executable": r"C:\Study.exe", "arguments": ["--keep"]}])
        dialog.connection_timer.stop(); dialog.deleteLater()

    def test_multiselect_tabs_deduplicates_sites_and_stops_request(self):
        from focus_lock.selectors import CheckListDialog
        from PySide6.QtCore import Qt
        import json
        dialog = ProfileDialog(Profile(browser_executable="chrome.exe"), FakeWindows(), self.window)
        tabs = [{"title": "One", "url": "https://example.com/a"}, {"title": "Two", "url": "https://example.com/b"}]
        def choose(picker):
            from PySide6.QtWidgets import QComboBox
            scope = picker.findChild(QComboBox)
            scope.setCurrentIndex(scope.findData("site"))
            for row in range(picker.table.rowCount()): picker.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
            return 1
        with patch.object(self.window.bridge, "open_tabs", return_value=(tabs, "ready")), patch.object(CheckListDialog, "exec", choose):
            dialog.pick_open_tabs()
        self.assertEqual(dialog.urls.toPlainText(), "https://example.com/")
        self.assertEqual(json.loads((self.store.root / "browser-tabs-request.json").read_text())["expires_at"], 0)
        dialog.connection_timer.stop(); dialog.deleteLater()

    def test_urls_enable_restriction_for_old_profiles_and_edits(self):
        dialog = ProfileDialog(Profile(urls=["https://example.com/a"], website_lock=False), FakeWindows(), self.window)
        self.assertTrue(dialog.website_lock.isChecked())
        dialog.website_lock.setChecked(False)
        dialog.urls.setPlainText("https://example.com/b")
        self.assertTrue(dialog.website_lock.isChecked())
        dialog.connection_timer.stop(); dialog.deleteLater()

    def test_preflight_refuses_urls_without_restriction(self):
        from focus_lock.ui import PreflightDialog
        profile = Profile(name="URL only", allowed=["chrome.exe"], urls=["https://example.com/a"], browser_executable="chrome.exe", website_lock=False)
        with patch.object(self.window.windows, "visible_windows", return_value=[(1, "chrome.exe", 12, "YouTube unrelated")]), patch("focus_lock.ui.resolve_executable", return_value="chrome.exe"), patch.object(self.window.bridge, "ready", return_value=True):
            dialog = PreflightDialog(profile, self.window)
            self.assertFalse(dialog.begin.isEnabled())
            self.assertIn("網址限制尚未啟用", dialog.report.toPlainText())
            self.assertNotIn("YouTube unrelated", dialog.report.toPlainText())
            profile.website_lock = True
            dialog.refresh()
            self.assertTrue(dialog.begin.isEnabled())
            self.assertIn("實際允許網址（1 個）", dialog.report.toPlainText())
            dialog.refresh_timer.stop(); dialog.deleteLater()

    def test_browser_autodetect_does_not_require_path_typing(self):
        with patch("focus_lock.ui.discover_browser", return_value=r"C:\Browser\chrome.exe"), patch("focus_lock.ui.resolve_executable", return_value=r"C:\Browser\chrome.exe"):
            dialog = ProfileDialog(Profile(), FakeWindows(), self.window)
            self.assertEqual(dialog.browser_executable.text(), r"C:\Browser\chrome.exe")
            self.assertTrue(dialog.manual_browser.isHidden())
            self.assertIn("已找到", dialog.browser_status.text())
            dialog.connection_timer.stop(); dialog.deleteLater()

    def start_away(self, strict=True):
        from PySide6.QtWidgets import QMessageBox
        index = self.window.profiles.findText("離開筆電 25 分鐘")
        self.window.profiles.setCurrentIndex(index)
        self.window.settings["profiles"][index]["strict"] = strict
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.start()

    def make_learning_plan(self):
        self.window.settings["profiles"][0]["allowed"] = ["Study.exe"]
        return self.window.learning.put_plan({"name": "Writing", "profile": self.window.settings["profiles"][0]["name"],
            "steps": [{"name": "複習", "minutes": 30, "goal": "整理"}, {"name": "寫作", "minutes": 15, "goal": "初稿"}], "daily_time": ""})

    def start_recall_session(self):
        from focus_lock.recall import IntentionDialog
        plan = self.make_learning_plan()
        self.window.settings["recall_mode"] = True
        def choose(dialog):
            dialog.question.setText("topic 如何交換資料？")
            dialog.criterion.setText("能解釋並跑出範例")
            return 1
        with patch.object(IntentionDialog, "exec", choose): self.window.start_learning(plan)
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick()
        return plan, self.window.learning.data["records"][-1]

    def test_recall_required_blocks_next_after_card_dismissal_and_restart(self):
        from focus_lock.learning import LearningStore
        plan, record = self.start_recall_session()
        self.assertEqual(self.window.timer.phase, "break")
        self.assertEqual(record["intention"]["question"], "topic 如何交換資料？")
        self.window.outcome_dialog.reject()
        self.window.settings["recall_mode"] = False
        self.assertFalse(self.window.start_learning(plan, 1))
        self.assertEqual(self.window.outcome_dialog.record["id"], record["id"])
        self.assertEqual(LearningStore(self.store.root).data["records"][-1]["recall_required"], True)
        self.window.outcome_dialog.reject()

    def test_recall_validation_persists_answers_and_next_question(self):
        plan, record = self.start_recall_session()
        card = self.window.outcome_dialog
        with self.assertRaises(ValueError): self.window.save_outcome(card)
        self.assertFalse(record.get("reflection_done"))
        card.recall_summary.setPlainText("節點透過 topic 傳送訊息")
        card.recall_example.setPlainText("publisher 發布，subscriber 接收")
        card.recall_stuck.setText("QoS 如何影響傳輸？")
        card.action.setCurrentIndex(card.action.findData("review"))
        self.assertEqual(card.next_task.text(), "QoS 如何影響傳輸？")
        self.window.save_outcome(card)
        self.assertTrue(record["reflection_done"])
        self.assertEqual(self.window.learning.data["reminders"][-1]["question"], "QoS 如何影響傳輸？")
        card.reject()
        self.assertTrue(self.window.recall_gate())

    def test_intention_cancel_does_not_start_or_enforce(self):
        from focus_lock.recall import IntentionDialog
        plan = self.make_learning_plan(); self.window.settings["recall_mode"] = True
        with patch.object(IntentionDialog, "exec", return_value=0): self.window.start_learning(plan)
        self.assertEqual(self.window.timer.phase, "idle")
        self.assertIsNone(self.window.learning.data["active"])
        self.assertFalse(self.window.guard.visible)

    def test_calendar_adds_multiple_schedules_on_same_date(self):
        from focus_lock.learning_ui import LearningDialog
        from PySide6.QtWidgets import QDialog, QDateTimeEdit, QPushButton
        from PySide6.QtCore import QDateTime
        self.make_learning_plan()
        dialog = LearningDialog(self.window)
        next_day = QDateTime.currentDateTime().addDays(1)
        def choose(picker):
            picker.findChild(QDateTimeEdit).setDateTime(next_day)
            save = next(b for b in picker.findChildren(QPushButton) if b.text() == "加入日曆")
            save.click()
            return QDialog.DialogCode.Accepted
        with patch.object(QDialog, "exec", choose):
            dialog.schedule_task(); dialog.schedule_task()
        self.assertEqual(len(self.window.learning.data["reminders"]), 2)
        self.assertEqual(len(dialog.calendar.events[next_day.toPython().date()]), 2)
        self.assertEqual(self.window.learning.data["reminders"][0]["minutes"], 30)
        dialog.deleteLater()

    def test_learning_step_duration_and_outcome_immediate(self):
        plan = self.make_learning_plan()
        self.assertTrue(self.window.start_learning(plan, 1))
        self.assertEqual(self.window.active.focus_minutes, 15)
        self.assertEqual(self.window.selected().focus_minutes, 25)
        self.assertEqual(self.window.learning.data["active"]["step"], "寫作")
        self.assertIn("2/2", self.window.compact.step_label.text())
        self.window.timer.deadline = self.window.timer.clock() - 1; self.window.tick()
        self.assertEqual(self.window.timer.phase, "break")
        self.assertIsNotNone(self.window.outcome_dialog)
        self.assertTrue(self.window.outcome_dialog.isVisible())
        record = self.window.learning.data["records"][-1]
        self.assertEqual(record["seconds"], 900)
        self.assertEqual(record["status"], "completed")
        self.window.outcome_dialog.reject()

    def test_paused_time_not_counted_and_early_stop_recorded(self):
        plan = self.make_learning_plan(); self.window.start_learning(plan, 0)
        self.window.timer.deadline = self.window.timer.clock() + 1740
        self.window.pause()
        self.window.timer.deadline -= 600
        self.window.stop()
        record = self.window.learning.data["records"][-1]
        self.assertAlmostEqual(record["seconds"], 60, delta=1)
        self.assertEqual(record["status"], "early")
        self.window.outcome_dialog.reject()

    def test_next_step_uses_its_own_duration_and_saves_schedule(self):
        plan = self.make_learning_plan(); self.window.start_learning(plan, 0)
        self.window.timer.deadline = self.window.timer.clock() - 1; self.window.tick()
        card = self.window.outcome_dialog
        card.action.setCurrentIndex(card.action.findData("next"))
        self.assertEqual(card.minutes.value(), 15)
        card.note.setPlainText("複習完成")
        self.window.save_outcome(card)
        reminder = self.window.learning.data["reminders"][-1]
        self.assertEqual(reminder["step"], 1)
        self.assertEqual(reminder["minutes"], 15)
        self.assertEqual(plan["next_step"], 1)
        self.assertEqual(self.window.learning.data["records"][-1]["note"], "複習完成")
        card.reject()

    def test_reminder_never_starts_timer_and_defers_during_focus(self):
        from datetime import datetime, timedelta
        plan = self.make_learning_plan()
        self.window.learning.schedule(plan["id"], 0, datetime.now().astimezone() + timedelta(seconds=1))
        reminder = self.window.learning.data["reminders"][-1]
        reminder["at"] = (datetime.now().astimezone() - timedelta(seconds=1)).isoformat()
        with patch.object(self.window.tray, "showMessage"):
            self.window.tick_learning()
        self.assertIsNotNone(self.window.reminder_dialog)
        self.assertEqual(self.window.timer.phase, "idle")
        self.window.reminder_dialog.reject()
        self.assertEqual(reminder["status"], "pending")
        self.assertGreater(datetime.fromisoformat(reminder["at"]), datetime.now().astimezone())
        self.window.start_learning(plan)
        self.window.last_reminder_check = 0
        reminder["at"] = (datetime.now().astimezone() - timedelta(seconds=1)).isoformat()
        self.window.tick_learning()
        self.assertIsNone(self.window.reminder_dialog)

    def test_listening_template_and_calendar_show_saved_results(self):
        from focus_lock.learning_ui import PlanDialog, LearningDialog
        editor = PlanDialog(self.window); editor.listening()
        self.assertEqual(editor.draft()["daily_time"], "08:00")
        self.assertEqual([s["minutes"] for s in editor.draft()["steps"]], [10, 15])
        editor.deleteLater()
        self.window.learning.begin(Profile(name="Test"), 1500)
        record = self.window.learning.end(1500, "completed")
        record["note"] = "完成初稿"; self.window.learning.save()
        dialog = LearningDialog(self.window)
        self.assertIn("25.0", dialog.summary.text())
        self.assertEqual(dialog.records.item(0, 2).text(), "完成初稿")
        dialog.deleteLater()

    def test_away_starts_without_tools_and_blocks_every_window(self):
        self.start_away()
        self.preflight_mock.assert_not_called()
        self.assertEqual(self.window.timer.phase, "focus")
        self.assertTrue(self.window.guard.visible)
        guard = self.window.guard.windows[0]
        self.assertTrue(guard.choices.isHidden())
        self.assertTrue(guard.back_button.isHidden())
        self.assertTrue(guard.pause_button.isHidden())
        self.assertTrue(guard.end_button.isHidden())
        self.assertTrue(self.window.blocked("Code.exe"))
        self.assertTrue(self.window.blocked("chrome.exe"))
        self.window.windows.foreground = lambda: None
        self.window.tick(); self.assertTrue(self.window.guard.visible)

    def test_away_cancel_does_not_start(self):
        from PySide6.QtWidgets import QMessageBox
        self.window.profiles.setCurrentIndex(self.window.profiles.findText("離開筆電 25 分鐘"))
        with patch("focus_lock.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.start()
        self.assertEqual(self.window.timer.phase, "idle")
        self.assertFalse(self.window.guard.visible)

    def test_away_finishes_directly_without_break(self):
        self.start_away()
        self.window.timer.deadline = self.window.timer.clock() - 1
        self.window.tick()
        self.assertEqual(self.window.timer.phase, "idle")
        self.assertFalse(self.window.guard.visible)
        self.assertIsNone(self.window.active)

    def test_away_general_pause_resume_end(self):
        self.start_away(strict=False)
        guard = self.window.guard.windows[0]
        self.assertTrue(guard.pause_button.isVisible())
        self.assertTrue(guard.end_button.isVisible())
        self.window.pause(); self.assertFalse(self.window.guard.visible)
        self.window.pause(); self.assertTrue(self.window.guard.visible)
        self.window.stop(); self.assertFalse(self.window.guard.visible)

    def test_away_strict_emergency_unlock_releases(self):
        self.start_away()
        self.window.stop(); self.window.pause()
        self.assertEqual(self.window.timer.phase, "focus")
        with patch("focus_lock.ui.EmergencyDialog.exec", return_value=1):
            self.window.unlock()
        self.assertEqual(self.window.timer.phase, "idle")
        self.assertFalse(self.window.guard.visible)

    def test_away_dialog_mode_disables_work_configuration(self):
        from focus_lock.presets import away_profile
        dialog = ProfileDialog(away_profile(), FakeWindows(), self.window)
        self.assertEqual(dialog.policy.currentIndex(), 2)
        self.assertFalse(dialog.tabs.isTabEnabled(1))
        self.assertFalse(dialog.tabs.isTabEnabled(2))
        self.assertEqual(dialog.profile().policy, "away")
        dialog.connection_timer.stop(); dialog.deleteLater()

    def test_away_covers_all_reported_screens(self):
        from PySide6.QtCore import QRect
        from unittest.mock import Mock
        self.start_away()
        screens = [Mock(), Mock()]
        screens[0].geometry.return_value = QRect(0, 0, 800, 600)
        screens[1].geometry.return_value = QRect(800, 0, 800, 600)
        with patch("focus_lock.guard.QApplication.screens", return_value=screens):
            self.window.tick()
        self.assertEqual(len(self.window.guard.windows), 2)
        self.assertTrue(all(window.isVisible() for window in self.window.guard.windows))
