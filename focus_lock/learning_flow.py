"""Connect the learning workflow to the existing safe timer and preflight."""
from .i18n import tr
import time
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QMessageBox, QPushButton
from .learning import LearningStore
from .learning_ui import LearningDialog, OutcomeDialog
from .recall import IntentionDialog, pending_recall, validate_reflection


class LearningFlow:
    def init_learning(self):
        self.learning = LearningStore(self.storage.root)
        self.learning_dialog = None
        self.outcome_dialog = None
        self.reminder_dialog = None
        self.pending_learning = None
        self.learning_context = None
        self.focus_seconds = 0
        self.last_checkpoint = time.monotonic()
        self.last_reminder_check = 0
        self.session_intention = None

    def recall_gate(self):
        record = pending_recall(self.learning.data["records"])
        if record:
            if not self.outcome_dialog or self.outcome_dialog.record["id"] != record["id"]: self.show_outcome(record)
            else: self.outcome_dialog.show(); self.outcome_dialog.raise_()
            return False
        return True

    def prepare_intention(self):
        self.session_intention = None
        if not self.settings.get("recall_mode", False): return True
        context = self.pending_learning
        step = context["plan"]["steps"][context["step"]] if context and context["plan"] else {}
        question = context.get("question", "") if context else ""
        dialog = IntentionDialog(self, question or step.get("name", ""), step.get("goal", ""))
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            self.session_intention = {"question": dialog.question.text().strip(), "criterion": dialog.criterion.text().strip()}
        dialog.deleteLater()
        return accepted

    def learning_error(self, exc):
        self.tray.showMessage(tr("Focus Lock · 紀錄儲存失敗"), str(exc))

    def show_learning(self):
        if self.timer.phase == "focus":
            self.tray.showMessage("Focus Lock", tr("請先完成專注，再查看學習紀錄。"))
            return
        if self.learning_dialog:
            self.learning_dialog.refresh(); self.learning_dialog.show(); self.learning_dialog.raise_(); return
        self.learning_dialog = LearningDialog(self)
        self.learning_dialog.finished.connect(lambda _: setattr(self, "learning_dialog", None))
        self.learning_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.learning_dialog.show()

    def start_learning(self, plan, step=0, minutes=None, profile_name=None, question=""):
        if not self.recall_gate(): return False
        if self.outcome_dialog and self.outcome_dialog.isVisible():
            self.outcome_dialog.raise_(); return False
        if self.timer.phase == "focus":
            QMessageBox.information(self, tr("已有專注進行中"), tr("請先完成目前的專注。")); return False
        profile_name = plan["profile"] if plan else profile_name
        index = self.profiles.findText(profile_name or "")
        if index < 0:
            QMessageBox.warning(self, tr("找不到方案"), tr("原方案已刪除或更名，請編輯任務並重新選擇方案。")); return False
        if plan and not 0 <= step < len(plan["steps"]): return False
        if self.timer.phase != "idle": self.finish()
        self.profiles.setCurrentIndex(index)
        self.pending_learning = {"plan": plan, "step": step, "minutes": minutes or (plan["steps"][step]["minutes"] if plan else self.selected().focus_minutes), "question": question}
        try: self.start()
        finally: self.pending_learning = None
        return self.timer.phase == "focus"

    def begin_learning_record(self):
        if self.learning_dialog: self.learning_dialog.hide()
        self.learning_context = self.pending_learning
        if self.learning_context and self.learning_context["plan"]:
            plan = self.learning_context["plan"]
            plan["next_step"] = self.learning_context["step"]
        self.focus_seconds = self.active.focus_minutes * 60
        try:
            self.learning.begin(self.active, self.focus_seconds,
                self.learning_context["plan"] if self.learning_context else None,
                self.learning_context["step"] if self.learning_context else 0)
            if self.session_intention and self.active.policy != "away":
                self.learning.data["active"].update(recall_required=True, intention=self.session_intention, reflection_done=False)
                self.learning.save()
        except OSError as exc: self.learning_error(exc)
        self.last_checkpoint = time.monotonic()

    def record_elapsed(self):
        return max(0, self.focus_seconds - self.timer.remaining)

    def end_learning_record(self, status):
        if not self.learning.data["active"]: return None
        try: return self.learning.end(self.focus_seconds if status == "completed" else self.record_elapsed(), status)
        except OSError as exc:
            self.learning_error(exc); return None

    def show_outcome(self, record):
        if not record or record.get("away"): return
        if self.outcome_dialog:
            self.outcome_dialog.close()
        plan = self.learning.plan(record.get("plan_id"))
        self.outcome_dialog = OutcomeDialog(self, record, plan)
        self.outcome_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.outcome_dialog.finished.connect(lambda _: setattr(self, "outcome_dialog", None))
        self.outcome_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.outcome_dialog.show(); self.outcome_dialog.raise_(); self.outcome_dialog.activateWindow()

    def save_outcome(self, dialog):
        record = dialog.record
        reflection = None
        if record.get("recall_required"):
            reflection = validate_reflection(dialog.recall_summary.toPlainText(), dialog.recall_example.toPlainText(), dialog.recall_stuck.text(), dialog.no_stuck.isChecked())
        action = dialog.action.currentData()
        plan = dialog.plan
        step = record["step_index"]
        if action == "next": step += 1
        if action == "switch":
            plan = self.learning.plan(dialog.target.currentData()); step = 0
            if not plan: raise ValueError(tr("請先建立或選擇新的學習任務"))
        if action != "end" and plan and not 0 <= step < len(plan["steps"]): raise ValueError(tr("任務已變更，請重新選擇步驟"))
        when = dialog.when.currentData()
        at = None
        if action != "end" and when != "now":
            if when == "scheduled":
                at = dialog.at.dateTime().toPython().astimezone()
            else:
                remaining = self.timer.remaining if self.timer.phase == "break" else 0
                at = datetime.now().astimezone() + timedelta(seconds=max(1, remaining))
            if at <= datetime.now().astimezone(): raise ValueError(tr("指定時間已過，請選擇未來的日期與時間"))
        record.update(note=dialog.note.toPlainText(), next_task=dialog.next_task.text(), task_done=dialog.done_task.isChecked())
        if reflection:
            record.update(reflection=reflection, reflection_done=True)
        if plan and action != "end": plan["next_step"] = step
        try: self.learning.save()
        except OSError:
            if reflection: record["reflection_done"] = False
            raise
        if action == "end": return
        if at:
            self.learning.schedule(plan["id"] if plan else None, step, at, dialog.next_task.text(),
                                   minutes=dialog.minutes.value(), profile=record["profile"], question=dialog.next_task.text())
        else:
            # Close the outcome first, then preflight/strict confirmation as usual.
            minutes = dialog.minutes.value()
            question = dialog.next_task.text()
            QTimer.singleShot(0, lambda: self.start_learning(plan, step, minutes, record["profile"], question))

    def tick_learning(self):
        if self.learning.read_only: return
        now = time.monotonic()
        if self.timer.phase == "focus" and now - self.last_checkpoint >= 5:
            try: self.learning.checkpoint(self.record_elapsed())
            except OSError as exc: self.learning_error(exc)
            self.last_checkpoint = now
        if now - self.last_reminder_check < 1: return
        self.last_reminder_check = now
        # Pending reminders stay on disk until acknowledged; defer UI during focus.
        try: due = self.learning.due()
        except (OSError, ValueError) as exc:
            self.learning_error(exc); return
        if not due or self.reminder_dialog or self.outcome_dialog or self.timer.phase == "focus" or QApplication.activeModalWidget(): return
        self.show_reminder(due[0])

    def show_reminder(self, reminder):
        plan = self.learning.plan(reminder["plan_id"])
        if reminder["plan_id"] and not plan:
            self.learning.resolve(reminder, "deleted"); return
        if plan and not 0 <= reminder["step"] < len(plan["steps"]):
            self.learning.resolve(reminder, "deleted")
            self.tray.showMessage("Focus Lock", tr("任務步驟已變更，請在學習任務中重新安排提醒。"))
            return
        name = plan["name"] if plan else reminder.get("profile", tr("專注"))
        task = reminder.get("task") or (plan["steps"][reminder["step"]]["name"] if plan else "")
        self.tray.showMessage(tr("Focus Lock · 學習時間到了"), f"{name}\n{task}")
        dialog = QDialog(self); self.reminder_dialog = dialog
        dialog.setWindowTitle(tr("學習提醒")); dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{name}\n{task}{tr('\n原訂時間：')}{datetime.fromisoformat(reminder['at']).astimezone():%m/%d %H:%M}"))
        def act(action):
            if action == "started" and not self.start_learning(plan, reminder["step"], reminder.get("minutes"), reminder.get("profile"), reminder.get("question", "")): return
            try: self.learning.resolve(reminder, action)
            except OSError as exc: self.learning_error(exc); return
            dialog.accept()
        for text, action in ((tr("開始任務"), "started"), (tr("延後 10 分鐘"), "snooze"), (tr("略過這次"), "skipped")):
            item = QPushButton(text); item.clicked.connect(lambda checked=False, value=action: act(value)); layout.addWidget(item)
        def closed(_):
            # Closing the card behaves as snooze, so it doesn't reappear each second.
            if dialog.result() != QDialog.DialogCode.Accepted:
                try: self.learning.resolve(reminder, "snooze")
                except OSError as exc: self.learning_error(exc)
            self.reminder_dialog = None
        dialog.finished.connect(closed); dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose); dialog.show()
