"""Learning workflow widgets; no cloud connection or executable AI output."""
from .i18n import tr
import json
from datetime import datetime
from PySide6.QtCore import Qt, QDateTime, QTime
from PySide6.QtGui import QTextCharFormat, QColor
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QPlainTextEdit, QComboBox, QCheckBox, QTimeEdit, QDateTimeEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QCalendarWidget, QTabWidget, QWidget,
    QDialogButtonBox, QSpinBox, QSplitter, QHeaderView, QScrollArea)
from .learning import validate_plan, parse_plan
from .calendar_ui import MonthCalendar


def button(text, callback, layout):
    item = QPushButton(text); item.clicked.connect(callback); layout.addWidget(item)
    return item


class PlanDialog(QDialog):
    def __init__(self, owner, plan=None):
        super().__init__(owner)
        self.setWindowTitle(tr("學習任務 · 步驟與提醒")); self.resize(740, 560)
        self.owner = owner
        layout = QVBoxLayout(self)
        self.name = QLineEdit((plan or {}).get("name", "")); self.name.setPlaceholderText(tr("例如：Writing Task 1"))
        layout.addWidget(QLabel(tr("任務名稱"))); layout.addWidget(self.name)
        self.profile = QComboBox(); self.profile.addItems([p["name"] for p in owner.settings["profiles"] if p.get("policy") != "away"])
        self.profile.setCurrentText((plan or {}).get("profile", owner.selected().name))
        layout.addWidget(QLabel(tr("沿用允許程式與網址的方案"))); layout.addWidget(self.profile)
        self.steps = QTableWidget(0, 3); self.steps.setHorizontalHeaderLabels([tr("步驟"), tr("分鐘"), tr("預計成果（選填）")])
        self.steps.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.steps)
        row = QHBoxLayout(); layout.addLayout(row)
        button(tr("新增步驟"), lambda: self.add_step(), row)
        button(tr("刪除步驟"), self.remove_step, row)
        button(tr("上移"), lambda: self.move_step(-1), row); button(tr("下移"), lambda: self.move_step(1), row)
        for step in (plan or {}).get("steps", [{"name": tr("複習"), "minutes": 30}, {"name": tr("寫作"), "minutes": 30}, {"name": tr("檢討"), "minutes": 30}]):
            self.add_step(step)
        row = QHBoxLayout(); layout.addLayout(row)
        self.daily = QCheckBox(tr("每天固定時間提醒")); self.daily.setChecked(bool((plan or {}).get("daily_time")))
        self.time = QTimeEdit(QTime.fromString((plan or {}).get("daily_time") or "08:00", "HH:mm")); self.time.setDisplayFormat("HH:mm")
        row.addWidget(self.daily); row.addWidget(self.time)
        button(tr("套用聽力範本"), self.listening, row)
        row = QHBoxLayout(); layout.addLayout(row)
        button(tr("複製 AI 拆解提示詞"), self.copy_prompt, row)
        button(tr("貼上 AI 方案並預覽"), self.import_plan, row)
        layout.addWidget(QLabel(tr("步驟完成後由你確認再開始下一步；提醒不會自動啟動封鎖。")))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("儲存任務"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("取消"))
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def add_step(self, step=None):
        step = step or {"name": tr("新步驟"), "minutes": 25}
        row = self.steps.rowCount(); self.steps.insertRow(row)
        for col, value in enumerate((step["name"], str(step["minutes"]), step.get("goal", ""))):
            self.steps.setItem(row, col, QTableWidgetItem(value))
        self.steps.setCurrentCell(row, 0)

    def remove_step(self):
        if self.steps.currentRow() >= 0: self.steps.removeRow(self.steps.currentRow())

    def move_step(self, direction):
        row = self.steps.currentRow(); other = row + direction
        if row < 0 or not 0 <= other < self.steps.rowCount(): return
        for col in range(3):
            first = self.steps.takeItem(row, col); second = self.steps.takeItem(other, col)
            self.steps.setItem(row, col, second); self.steps.setItem(other, col, first)
        self.steps.setCurrentCell(other, 0)

    def listening(self):
        self.name.setText(tr("每日聽力"))
        self.steps.setRowCount(0)
        self.add_step({"name": tr("做題"), "minutes": 10, "goal": tr("完成一篇聽力題目")})
        self.add_step({"name": tr("檢討"), "minutes": 15, "goal": tr("整理錯題與沒聽懂的句子")})
        self.daily.setChecked(True); self.time.setTime(QTime(8, 0))

    def draft(self):
        steps = []
        for row in range(self.steps.rowCount()):
            values = [(self.steps.item(row, col).text() if self.steps.item(row, col) else "") for col in range(3)]
            try: minutes = int(values[1])
            except ValueError: raise ValueError(tr("分鐘請填整數")) from None
            steps.append({"name": values[0], "minutes": minutes, "goal": values[2]})
        return validate_plan({"name": self.name.text(), "profile": self.profile.currentText(), "steps": steps,
                              "daily_time": self.time.time().toString("HH:mm") if self.daily.isChecked() else ""},
                             [self.profile.itemText(i) for i in range(self.profile.count())])

    def validate(self):
        try: self.result_plan = self.draft()
        except ValueError as exc:
            QMessageBox.warning(self, tr("請檢查任務"), str(exc)); return
        self.accept()

    def copy_prompt(self):
        template = {"name": self.name.text() or tr("學習任務"), "profile": self.profile.currentText(),
                    "steps": [{"name": tr("複習"), "minutes": 30, "goal": tr("整理重點")}], "daily_time": ""}
        text = (tr("請先詢問我的學習目標、可用總分鐘及是否每天提醒，再拆成可執行的小任務。每步 1–240 分鐘，最多 30 步。"
                "只輸出以下格式的 JSON，profile 必須原樣保留，不加入應用程式、網址或指令。daily_time 為空字串或 HH:MM。\n")
                + json.dumps(template, ensure_ascii=False, indent=2))
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, tr("已複製"), tr("貼到你使用的 AI，取得 JSON 後按「貼上 AI 方案並預覽」。Focus Lock 不會自行傳送資料。"))

    def import_plan(self):
        dialog = QDialog(self); dialog.setWindowTitle(tr("貼上 AI 方案 · 先預覽再確認")); dialog.resize(650, 480)
        layout = QVBoxLayout(dialog); editor = QPlainTextEdit(); layout.addWidget(editor)
        preview = QPlainTextEdit(); preview.setReadOnly(True); layout.addWidget(preview)
        parsed = [None]
        accept = QPushButton(tr("套用到編輯畫面")); accept.setEnabled(False)
        def inspect():
            try:
                parsed[0] = parse_plan(editor.toPlainText(), [self.profile.itemText(i) for i in range(self.profile.count())])
                data = parsed[0]
                preview.setPlainText(f"{data['name']}{tr(' · 共 ')}{sum((s['minutes'] for s in data['steps']))}{tr(' 分鐘\n方案：')}{data['profile']}\n" +
                    "\n".join(f"{i + 1}. {s['name']} · {s['minutes']}{tr(' 分鐘 · ')}{s['goal']}" for i, s in enumerate(data["steps"])))
                accept.setEnabled(True)
            except ValueError as exc:
                parsed[0] = None; preview.setPlainText(str(exc)); accept.setEnabled(False)
        editor.textChanged.connect(lambda: (accept.setEnabled(False), parsed.__setitem__(0, None)))
        button(tr("驗證與預覽"), inspect, layout)
        accept.clicked.connect(dialog.accept); layout.addWidget(accept)
        button(tr("取消"), dialog.reject, layout)
        if dialog.exec() == QDialog.DialogCode.Accepted and parsed[0]:
            data = parsed[0]; self.name.setText(data["name"]); self.profile.setCurrentText(data["profile"])
            self.steps.setRowCount(0)
            for step in data["steps"]: self.add_step(step)
            self.daily.setChecked(bool(data["daily_time"]))
            if data["daily_time"]: self.time.setTime(QTime.fromString(data["daily_time"], "HH:mm"))
        dialog.deleteLater()


class OutcomeDialog(QDialog):
    def __init__(self, owner, record, plan=None):
        super().__init__(owner)
        self.setWindowTitle(tr("專注成果與下一次安排")); self.resize(540, 530)
        self.record = record; self.plan = plan; self.owner = owner
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content); root.addWidget(scroll)
        labels = {"completed": tr("完成"), "interrupted": tr("中斷"), "early": tr("提前結束")}
        layout.addWidget(QLabel(f"{record['task']} · {record['step']}\n{labels.get(record['status'], record['status'])}{tr(' · 專注 ')}{record['seconds'] / 60:.1f}{tr(' 分鐘')}"))
        if record.get("recall_required"):
            self.resize(600, 800)
            intention = record.get("intention", {})
            goal = QLabel(f"{tr('本段問題：')}{intention.get('question', '')}{tr('\n完成標準：')}{intention.get('criterion', '')}")
            goal.setWordWrap(True); goal.setStyleSheet("color:#8ab4f8;"); layout.addWidget(goal)
            hint = QLabel(tr("請先合上教材，用自己的話回想。休息照常進行；填寫完成後才能開始下一段。")); hint.setWordWrap(True); layout.addWidget(hint)
            reflection = record.get("reflection", {})
            layout.addWidget(QLabel(tr("1. 這一節在回答什麼？")))
            self.recall_summary = QPlainTextEdit(reflection.get("summary", "")); self.recall_summary.setMaximumHeight(65); layout.addWidget(self.recall_summary)
            layout.addWidget(QLabel(tr("2. 一個你能解釋的例子、步驟或實作結果？")))
            self.recall_example = QPlainTextEdit(reflection.get("example", "")); self.recall_example.setMaximumHeight(65); layout.addWidget(self.recall_example)
            layout.addWidget(QLabel(tr("3. 還卡在哪裡？")))
            self.recall_stuck = QLineEdit(reflection.get("stuck", "")); layout.addWidget(self.recall_stuck)
            self.no_stuck = QCheckBox(tr("目前沒有卡點")); self.no_stuck.setChecked(reflection.get("stuck") == "目前沒有")
            self.recall_stuck.setEnabled(not self.no_stuck.isChecked())
            self.no_stuck.toggled.connect(lambda value: self.recall_stuck.setEnabled(not value)); layout.addWidget(self.no_stuck)
        layout.addWidget(QLabel(tr("這次完成了什麼？（可稍後補）")))
        self.note = QPlainTextEdit(record.get("note", "")); self.note.setMaximumHeight(140); layout.addWidget(self.note)
        if record.get("recall_required"): self.note.setMaximumHeight(50)
        self.done_task = QCheckBox(tr("這個任務已完成")); self.done_task.setChecked(record.get("task_done", False)); layout.addWidget(self.done_task)
        self.action = QComboBox()
        self.action.addItem(tr("今天先到這裡／稍後決定"), "end")
        self.action.addItem(tr("繼續目前任務：") + record["step"], "continue")
        if record.get("recall_required"):
            self.action.addItem(tr("回頭補強：把卡點變成下一段目標"), "review")
            self.action.addItem(tr("實作驗證：選擇練習任務"), "switch")
        if plan and record["step_index"] + 1 < len(plan["steps"]): self.action.addItem(tr("進入下一步：") + plan["steps"][record["step_index"] + 1]["name"], "next")
        if not record.get("recall_required"): self.action.addItem(tr("切換到新的學習任務"), "switch")
        layout.addWidget(self.action)
        self.target = QComboBox()
        for p in owner.learning.data["plans"]: self.target.addItem(p["name"], p["id"])
        layout.addWidget(self.target)
        self.next_task = QLineEdit(record.get("next_task", "")); self.next_task.setPlaceholderText(tr("下次具體要做什麼？（選填）")); layout.addWidget(self.next_task)
        self.duration_label = QLabel(tr("下次專注時長（開始前選好）")); layout.addWidget(self.duration_label)
        self.minutes = QSpinBox(); self.minutes.setRange(1, 240); self.minutes.setSuffix(tr(" 分鐘"))
        self.minutes.setValue(max(1, round(record["planned_seconds"]/60))); layout.addWidget(self.minutes)
        self.when = QComboBox(); self.when.addItem(tr("休息結束後提醒"), "break"); self.when.addItem(tr("現在開始"), "now"); self.when.addItem(tr("指定日期與時間"), "scheduled"); layout.addWidget(self.when)
        self.at = QDateTimeEdit(QDateTime.currentDateTime().addSecs(1800)); self.at.setCalendarPopup(True); self.at.setDisplayFormat("yyyy-MM-dd HH:mm"); layout.addWidget(self.at)
        self.action.currentIndexChanged.connect(self.sync); self.when.currentIndexChanged.connect(self.sync)
        self.action.currentIndexChanged.connect(self.suggest_minutes)
        self.action.currentIndexChanged.connect(self.fill_review_target)
        self.target.currentIndexChanged.connect(self.suggest_minutes)
        row = QHBoxLayout(); root.addLayout(row)
        button(tr("儲存成果與安排"), self.commit, row); button(tr("稍後回想") if record.get("recall_required") else tr("稍後補"), self.reject, row)
        self.sync()

    def fill_review_target(self):
        if self.action.currentData() == "review" and self.recall_stuck.text().strip():
            self.next_task.setText(self.recall_stuck.text().strip())

    def suggest_minutes(self):
        action = self.action.currentData()
        plan = self.owner.learning.plan(self.target.currentData()) if action == "switch" else self.plan
        step = 0 if action == "switch" else self.record["step_index"] + (1 if action == "next" else 0)
        if plan and 0 <= step < len(plan["steps"]): self.minutes.setValue(plan["steps"][step]["minutes"])
        else: self.minutes.setValue(max(1, round(self.record["planned_seconds"]/60)))

    def sync(self):
        enabled = self.action.currentData() != "end"
        self.target.setVisible(self.action.currentData() == "switch")
        for widget in (self.next_task, self.duration_label, self.minutes, self.when): widget.setVisible(enabled)
        self.at.setVisible(enabled and self.when.currentData() == "scheduled")

    def commit(self):
        try:
            self.owner.save_outcome(self)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("無法儲存"), str(exc)); return
        self.accept()


class LearningDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner; self.setWindowTitle(tr("學習任務、成果與日曆")); self.resize(1250, 850)
        root = QVBoxLayout(self); tabs = QTabWidget(); root.addWidget(tabs)
        page = QWidget(); layout = QVBoxLayout(page); tabs.addTab(page, tr("學習任務"))
        self.plans = QComboBox(); layout.addWidget(self.plans)
        self.detail = QPlainTextEdit(); self.detail.setReadOnly(True); layout.addWidget(self.detail)
        self.plans.currentIndexChanged.connect(self.show_plan)
        row = QHBoxLayout(); layout.addLayout(row)
        button(tr("新增／AI 拆解"), lambda: self.edit_plan(True), row); button(tr("編輯"), self.edit_plan, row)
        button(tr("複製"), self.copy_plan, row); button(tr("刪除"), self.delete_plan, row)
        row = QHBoxLayout(); layout.addLayout(row)
        button(tr("繼續上次步驟"), self.start_plan, row); button(tr("從第一步開始"), lambda: self.start_plan(True), row)
        page = QWidget(); layout = QVBoxLayout(page); tabs.addTab(page, tr("紀錄與日曆"))
        split = QSplitter(); layout.addWidget(split)
        self.calendar = MonthCalendar(owner.learning); split.addWidget(self.calendar)
        sidebar = QWidget(); sidebar.setMinimumWidth(300); split.addWidget(sidebar)
        split.setSizes([880, 320]); split.setStretchFactor(0, 1)
        layout = QVBoxLayout(sidebar); layout.setContentsMargins(14, 0, 0, 0)
        self.day_title = QLabel(); self.day_title.setStyleSheet("font-size:20px; font-weight:600;"); layout.addWidget(self.day_title)
        self.calendar.selectionChanged.connect(self.show_day)
        self.calendar.eventActivated.connect(self.open_event)
        self.calendar.addRequested.connect(self.schedule_task)
        self.summary = QLabel(); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        button(tr("＋ 新增這天的學習安排"), self.schedule_task, layout)
        layout.addWidget(QLabel(tr("已記錄的專注 · 雙擊補寫成果")))
        self.records = QTableWidget(0, 3); self.records.setHorizontalHeaderLabels([tr("任務／步驟"), tr("分鐘／狀態"), tr("成果")])
        self.records.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.records.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.records.cellDoubleClicked.connect(self.edit_record); layout.addWidget(self.records)
        button(tr("編輯選取紀錄的成果"), self.edit_record, layout)
        self.upcoming = QPlainTextEdit(); self.upcoming.setReadOnly(True); self.upcoming.setMaximumHeight(180); layout.addWidget(self.upcoming)
        root.addWidget(QLabel(tr("資料儲存在本機。提醒需要 Focus Lock 執行；睡眠／關閉期間的當日提醒會在回來後提示。")))
        self.refresh()

    def refresh(self):
        current = self.plans.currentData(); self.plans.blockSignals(True); self.plans.clear()
        for plan in self.owner.learning.data["plans"]: self.plans.addItem(plan["name"], plan["id"])
        index = self.plans.findData(current)
        if index >= 0: self.plans.setCurrentIndex(index)
        self.plans.blockSignals(False); self.show_plan(); self.show_day()
        self.calendar.refresh()

    def show_plan(self):
        plan = self.owner.learning.plan(self.plans.currentData())
        if not plan:
            self.detail.setPlainText(tr("新增一次任務，以後一鍵開始。可套用 Writing 或每天 08:00 聽力範本，也可匯入 AI 拆解草稿。"))
            return
        self.detail.setPlainText(f"{tr('沿用方案：')}{plan['profile']}{tr('\n每日提醒：')}{plan.get('daily_time') or '未設定'}{tr('\n下次接續：第 ')}{plan.get('next_step', 0) + 1}{tr(' 步\n\n')}" +
            "\n".join(f"{i + 1}. {s['name']} · {s['minutes']}{tr(' 分鐘\n   ')}{s.get('goal', '')}" for i, s in enumerate(plan["steps"])))

    def edit_plan(self, new=False):
        plan = None if new else self.owner.learning.plan(self.plans.currentData())
        if not new and not plan: return
        dialog = PlanDialog(self.owner, plan)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try: self.owner.learning.put_plan(dialog.result_plan, plan["id"] if plan else None)
            except OSError as exc: QMessageBox.warning(self, tr("無法儲存"), str(exc))
            self.refresh()
        dialog.deleteLater()

    def copy_plan(self):
        plan = self.owner.learning.plan(self.plans.currentData())
        if not plan: return
        data = {**plan, "name": plan["name"] + tr("（副本）")}
        self.owner.learning.put_plan(data); self.refresh()

    def delete_plan(self):
        plan_id = self.plans.currentData()
        if not plan_id: return
        if QMessageBox.question(self, tr("刪除任務"), tr("刪除此任務及待辦提醒？既有成果紀錄會保留。")) != QMessageBox.StandardButton.Yes: return
        self.owner.learning.data["plans"] = [p for p in self.owner.learning.data["plans"] if p["id"] != plan_id]
        self.owner.learning.data["reminders"] = [r for r in self.owner.learning.data["reminders"] if r["plan_id"] != plan_id]
        self.owner.learning.save(); self.refresh()

    def start_plan(self, reset=False):
        plan = self.owner.learning.plan(self.plans.currentData())
        if not plan: return
        step = 0 if reset else plan.get("next_step", 0)
        if self.owner.start_learning(plan, step): self.accept()

    def show_day(self):
        day = self.calendar.selectedDate().toString("yyyy-MM-dd")
        self.day_title.setText(self.calendar.selectedDate().toString(tr("M 月 d 日")))
        store = self.owner.learning; self.day_items = store.day_records(day)
        self.summary.setText(f"{day}{tr(' · 專注 ')}{store.day_seconds(day) / 60:.1f}{tr(' 分鐘 · ')}{sum((r['status'] == 'completed' and (not r.get('away')) for r in self.day_items))}{tr(' 次完成（離開筆電另計）')}")
        self.records.setRowCount(len(self.day_items))
        labels = {"completed": tr("完成"), "early": tr("提前結束"), "interrupted": tr("中斷")}
        for row, record in enumerate(self.day_items):
            reflection = record.get("reflection", {})
            note = record.get("note", "")
            if reflection: note += f"{tr('\n回想：')}{reflection['summary']}{tr('\n例子／實作：')}{reflection['example']}{tr('\n卡點：')}{reflection['stuck']}"
            elif record.get("recall_required"): note += tr("\n待完成回想")
            values = [record["task"] + "／" + record["step"], f"{record['seconds']/60:.1f} · {labels.get(record['status'], record['status'])}" + (tr(" · 離開筆電") if record.get("away") else "") + (tr(" · 任務完成") if record.get("task_done") else ""), note.strip(), record.get("next_task", "")]
            for col, text in enumerate(values[:3]):
                item = QTableWidgetItem(text)
                item.setToolTip(text + (tr("\n下次任務：") + record.get("next_task", "") if col == 2 else "")); self.records.setItem(row, col, item)
        reminders = [r for r in store.data["reminders"] if r["status"] == "pending" and datetime.fromisoformat(r["at"]).astimezone().date().isoformat() == day]
        lines = [f"{datetime.fromisoformat(r['at']).astimezone():%H:%M} · {(store.plan(r['plan_id']) or {}).get('name', r.get('profile', '專注'))} · {r.get('task', '')}" for r in reminders]
        lines += [f"{tr('每天 ')}{p['daily_time']} · {p['name']}" for p in store.data["plans"] if p.get("daily_time")]
        self.upcoming.setPlainText(tr("當日待辦／固定提醒：\n") + ("\n".join(lines) or tr("無")))

    def schedule_task(self):
        if not self.owner.learning.data["plans"]:
            QMessageBox.information(self, tr("先建立學習任務"), tr("請在學習任務頁新增任務，再安排到日曆。"))
            return
        dialog = QDialog(self); dialog.setWindowTitle(tr("新增學習安排")); dialog.resize(460, 360)
        layout = QVBoxLayout(dialog)
        plan_choice = QComboBox()
        for plan in self.owner.learning.data["plans"]: plan_choice.addItem(plan["name"], plan["id"])
        layout.addWidget(QLabel(tr("學習任務"))); layout.addWidget(plan_choice)
        steps = QComboBox(); layout.addWidget(QLabel(tr("開始步驟"))); layout.addWidget(steps)
        minutes = QSpinBox(); minutes.setRange(1, 240); minutes.setSuffix(tr(" 分鐘"))
        layout.addWidget(QLabel(tr("本次時長"))); layout.addWidget(minutes)
        def select_step():
            plan = self.owner.learning.plan(plan_choice.currentData())
            if plan and steps.currentIndex() >= 0: minutes.setValue(plan["steps"][steps.currentIndex()]["minutes"])
        def select_plan():
            plan = self.owner.learning.plan(plan_choice.currentData()); steps.clear()
            for step in plan["steps"]: steps.addItem(step["name"])
            select_step()
        plan_choice.currentIndexChanged.connect(select_plan); steps.currentIndexChanged.connect(select_step); select_plan()
        at = QDateTimeEdit(QDateTime(self.calendar.selectedDate(), QTime(8, 0)))
        if at.dateTime() <= QDateTime.currentDateTime() and at.date() == QDateTime.currentDateTime().date(): at.setDateTime(QDateTime.currentDateTime().addSecs(1800))
        at.setCalendarPopup(True); at.setDisplayFormat("yyyy-MM-dd HH:mm"); layout.addWidget(QLabel(tr("提醒時間"))); layout.addWidget(at)
        task = QLineEdit(); task.setPlaceholderText(tr("本次目標（選填）")); layout.addWidget(task)
        def save():
            plan = self.owner.learning.plan(plan_choice.currentData())
            try:
                self.owner.learning.schedule(plan["id"], steps.currentIndex(), at.dateTime().toPython().astimezone(),
                    task.text() or steps.currentText(), minutes=minutes.value(), profile=plan["profile"])
            except (OSError, ValueError) as exc:
                QMessageBox.warning(dialog, tr("無法安排"), str(exc)); return
            dialog.accept()
        button(tr("加入日曆"), save, layout); button(tr("取消"), dialog.reject, layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.calendar.setSelectedDate(at.date()); self.refresh()
        dialog.deleteLater()

    def open_event(self, event):
        if event["kind"] == "record":
            for row, record in enumerate(self.day_items):
                if record["id"] == event["id"]:
                    self.records.setCurrentCell(row, 0); self.edit_record(); return
        elif event["kind"] == "daily":
            plan = self.owner.learning.plan(event["id"])
            if plan:
                self.plans.setCurrentIndex(self.plans.findData(plan["id"]))
                QMessageBox.information(self, plan["name"], f"{tr('每天 ')}{plan['daily_time']}{tr(' 提醒\n')}" + "\n".join(f"{s['name']} · {s['minutes']}{tr(' 分鐘')}" for s in plan["steps"]))
        else:
            reminder = next((r for r in self.owner.learning.data["reminders"] if r["id"] == event["id"]), None)
            if reminder:
                message = QMessageBox(self); message.setWindowTitle(tr("學習安排"))
                message.setText(event["tooltip"] + f"{tr('\n時長：')}{reminder.get('minutes', '依任務設定')}{tr(' 分鐘')}")
                cancel = message.addButton(tr("取消這次安排"), QMessageBox.ButtonRole.DestructiveRole)
                message.addButton(tr("關閉"), QMessageBox.ButtonRole.RejectRole); message.exec()
                if message.clickedButton() == cancel:
                    try: self.owner.learning.resolve(reminder, "skipped")
                    except OSError as exc: QMessageBox.warning(self, tr("無法儲存"), str(exc))
                    self.refresh()

    def edit_record(self, *_):
        row = self.records.currentRow()
        if not 0 <= row < len(self.day_items): return
        record = self.day_items[row]
        if record.get("recall_required") and not record.get("reflection_done"):
            self.owner.show_outcome(record); return
        dialog = QDialog(self); dialog.setWindowTitle(tr("補寫成果")); layout = QVBoxLayout(dialog)
        note = QPlainTextEdit(record.get("note", "")); layout.addWidget(QLabel(tr("成果"))); layout.addWidget(note)
        next_task = QLineEdit(record.get("next_task", "")); layout.addWidget(QLabel(tr("下次任務"))); layout.addWidget(next_task)
        button(tr("儲存"), dialog.accept, layout); button(tr("取消"), dialog.reject, layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            record.update(note=note.toPlainText(), next_task=next_task.text()); self.owner.learning.save(); self.refresh()
        dialog.deleteLater()
