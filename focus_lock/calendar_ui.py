"""A month planner with multiple local events in each date cell."""
from .i18n import tr
import calendar
import hashlib
from datetime import date, datetime
from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy


COLORS = ("#8ab4f8", "#81c995", "#c4a7e7", "#f6bd60", "#78d9dc", "#f28b82")


def color_for(name):
    return COLORS[int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16) % len(COLORS)]


def month_events(store, year, month):
    """Return actual records/reminders plus future recurring occurrences, without saving."""
    events = {}
    def add(day, item): events.setdefault(day, []).append(item)
    for record in store.data["records"]:
        at = datetime.fromisoformat(record["started"]).astimezone()
        if (at.year, at.month) == (year, month):
            add(at.date(), {"kind": "record", "id": record["id"], "time": at.strftime("%H:%M"),
                "name": record["task"], "detail": record["step"],
                "label": f"{at:%H:%M}  {record['task']} · {record['seconds'] / 60:g}{tr('分')}",
                "tooltip": f"{record['task']}／{record['step']}{tr('\n專注 ')}{record['seconds'] / 60:.1f}{tr(' 分鐘\n')}{record.get('note', '')}",
                "done": True})
    occurrences = set()
    for reminder in store.data["reminders"]:
        at = datetime.fromisoformat(reminder["at"]).astimezone()
        occurrences.add((reminder["plan_id"], at.date(), at.strftime("%H:%M")))
        if reminder["status"] != "pending" or (at.year, at.month) != (year, month): continue
        plan = store.plan(reminder["plan_id"])
        name = plan["name"] if plan else reminder.get("profile", tr("專注"))
        task = reminder.get("task") or (plan["steps"][reminder["step"]]["name"] if plan and reminder["step"] < len(plan["steps"]) else "")
        add(at.date(), {"kind": "reminder", "id": reminder["id"], "time": at.strftime("%H:%M"), "name": name,
            "detail": task, "label": f"{at:%H:%M}  {name}", "tooltip": f"{tr('待辦 · ')}{name}\n{task}\n{at:%m/%d %H:%M}", "done": False})
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        day_date = date(year, month, day)
        if day_date < date.today(): continue
        for plan in store.data["plans"]:
            daily = plan.get("daily_time")
            if not daily or plan.get("last_daily") == day_date.isoformat() or (plan["id"], day_date, daily) in occurrences: continue
            add(day_date, {"kind": "daily", "id": plan["id"], "time": daily, "name": plan["name"], "detail": plan["steps"][0]["name"],
                "label": f"{daily}  {plan['name']}", "tooltip": f"{tr('每日 ')}{daily} · {plan['name']}{tr('\n點選查看任務')}", "done": False})
    for items in events.values(): items.sort(key=lambda item: (item["time"], item["name"]))
    return events


class EventChip(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.full_text = text

    def resizeEvent(self, event):
        self.setText(self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, max(10, self.width()-15)))
        super().resizeEvent(event)


class DayCell(QFrame):
    def __init__(self, owner, day, items, current_month):
        super().__init__(owner)
        self.owner = owner; self.day = day
        self.setObjectName("dayCell")
        selected = day == owner.selected
        self.setStyleSheet(f"QFrame#dayCell {{background:{'#25354c' if selected else '#1b2230' if current_month else '#171d28'}; border:1px solid {'#8ab4f8' if selected else '#30394a'}; border-radius:5px;}}")
        layout = QVBoxLayout(self); layout.setContentsMargins(5, 4, 5, 4); layout.setSpacing(3)
        head = QHBoxLayout(); layout.addLayout(head)
        label = QLabel(str(day.day)); label.setFixedSize(25, 23); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background:#8ab4f8; color:#142238; border-radius:11px; font-weight:bold;" if day == date.today() else f"color:{'#e6edf7' if current_month else '#626e82'}; background:transparent;")
        head.addWidget(label); head.addStretch()
        if items:
            total = sum(1 for item in items if item["done"])
            if total:
                badge = QLabel(f"{total}{tr(' 筆')}"); badge.setStyleSheet("color:#81c995; font-size:10px; background:transparent;"); head.addWidget(badge)
        for item in items[:3]:
            event = EventChip(item["label"]); event.setFixedHeight(23); event.setToolTip(item["tooltip"])
            event.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            color = color_for(item["name"])
            event.setStyleSheet(f"QPushButton {{background:{'#263846' if item['done'] else '#30364a'}; color:{color}; border:0; border-left:3px solid {color}; border-radius:4px; padding:2px 3px; text-align:left; font-size:11px;}} QPushButton:hover {{background:#43516b;}}")
            event.clicked.connect(lambda checked=False, value=item: owner.activate(day, value)); layout.addWidget(event)
        if len(items) > 3:
            more = QPushButton(f"{tr('還有 ')}{len(items) - 3}{tr(' 個')}")
            more.setFixedHeight(20); more.setStyleSheet("text-align:left; color:#b9c7df; background:transparent; border:0; padding:0; font-size:11px;")
            more.clicked.connect(lambda: owner.select(day)); layout.addWidget(more)
        layout.addStretch()
        self.setMinimumHeight(110 if len(items) > 3 else 95)
        self.setMinimumWidth(95)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.owner.select(self.day)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.select(self.day); self.owner.addRequested.emit()
        super().mouseDoubleClickEvent(event)


class MonthCalendar(QWidget):
    selectionChanged = Signal()
    eventActivated = Signal(object)
    addRequested = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store; self.selected = date.today(); self.year = self.selected.year; self.month = self.selected.month
        self.cells = []
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout(); layout.addLayout(row)
        self.title = QLabel(); self.title.setStyleSheet("font-size:23px; font-weight:600; color:#e8eef8;"); row.addWidget(self.title)
        row.addStretch()
        for text, callback in ((tr("今天"), self.today), ("‹", lambda: self.shift(-1)), ("›", lambda: self.shift(1))):
            button = QPushButton(text); button.clicked.connect(callback); row.addWidget(button)
        self.caption = QLabel(tr("色彩區分任務 · 每格顯示多筆行程 · 雙擊日期新增安排"))
        self.caption.setStyleSheet("color:#9eacc2; font-size:11px;"); layout.addWidget(self.caption)
        self.grid = QGridLayout(); self.grid.setSpacing(3); layout.addLayout(self.grid, 1)
        for col, name in enumerate((tr("週日"), tr("週一"), tr("週二"), tr("週三"), tr("週四"), tr("週五"), tr("週六"))):
            label = QLabel(name); label.setAlignment(Qt.AlignmentFlag.AlignCenter); label.setFixedHeight(24)
            label.setStyleSheet(f"color:{'#e6a5a5' if col in (0,6) else '#9eacc2'}; font-size:11px;")
            self.grid.addWidget(label, 0, col); self.grid.setColumnStretch(col, 1)
        self.refresh()

    def selectedDate(self): return QDate(self.selected.year, self.selected.month, self.selected.day)

    def setSelectedDate(self, day): self.select(date(day.year(), day.month(), day.day()))

    def select(self, day):
        self.selected = day; self.year = day.year; self.month = day.month
        self.refresh(); self.selectionChanged.emit()

    def activate(self, day, item):
        self.select(day); self.eventActivated.emit(item)

    def today(self): self.select(date.today())

    def shift(self, delta):
        month = self.year * 12 + self.month - 1 + delta
        year, month = divmod(month, 12); month += 1
        self.select(date(year, month, min(self.selected.day, calendar.monthrange(year, month)[1])))

    def refresh(self):
        for cell in self.cells: self.grid.removeWidget(cell); cell.hide(); cell.deleteLater()
        self.cells = []
        self.title.setText(f"{self.year}{tr(' 年 ')}{self.month}{tr(' 月')}")
        self.events = month_events(self.store, self.year, self.month)
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.year, self.month)
        for row in range(1, 7): self.grid.setRowStretch(row, 0)
        for row, week in enumerate(weeks, 1):
            self.grid.setRowStretch(row, 1)
            for col, day in enumerate(week):
                cell = DayCell(self, day, self.events.get(day, []), day.month == self.month)
                self.grid.addWidget(cell, row, col); self.cells.append(cell)
