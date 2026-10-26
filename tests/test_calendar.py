import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QPushButton
from focus_lock.core import Profile
from focus_lock.learning import LearningStore
from focus_lock.calendar_ui import MonthCalendar, month_events


class CalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.store = LearningStore(Path(self.directory.name))
        self.plan = self.store.put_plan({"name": "聽力", "profile": "Study", "steps": [{"name": "做題", "minutes": 10}], "daily_time": "08:00"})

    def tearDown(self): self.directory.cleanup()

    def test_month_preview_does_not_create_notifications_or_write(self):
        before = self.store.path.read_bytes()
        future = date.today() + timedelta(days=35)
        events = month_events(self.store, future.year, future.month)
        self.assertTrue(events)
        self.assertTrue(all(item["kind"] == "daily" for items in events.values() for item in items))
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertFalse(self.store.data["reminders"])

    def test_multiple_events_overflow_and_date_selection(self):
        for i in range(5):
            self.store.begin(Profile(name="Writing"), 1800)
            self.store.end(1800, "completed")
        widget = MonthCalendar(self.store)
        today_cell = next(cell for cell in widget.cells if cell.day == date.today())
        more = [button for button in today_cell.findChildren(QPushButton) if button.text().startswith("還有")]
        self.assertEqual(len(more), 1)
        self.assertEqual(len(widget.events[date.today()]), 6)  # 5 actual records plus daily plan
        more[0].click()
        self.assertEqual(widget.selectedDate(), QDate.currentDate())
        widget.deleteLater()

    def test_skipped_reminder_not_reintroduced_as_daily_event(self):
        now = datetime.now().astimezone()
        self.store.data["reminders"].append({"id": "test", "plan_id": self.plan["id"], "step": 0,
            "at": now.replace(hour=8, minute=0).isoformat(), "status": "skipped", "task": "做題"})
        events = month_events(self.store, now.year, now.month)
        self.assertNotIn(now.date(), events)

    def test_month_navigation_clamps_dates_and_click_keeps_event_id(self):
        widget = MonthCalendar(self.store)
        widget.setSelectedDate(QDate(2028, 1, 31)); widget.shift(1)
        self.assertEqual(widget.selectedDate(), QDate(2028, 2, 29))
        activated = []; widget.eventActivated.connect(activated.append)
        widget.activate(date(2028, 2, 29), {"kind": "record", "id": "same-record"})
        self.assertEqual(activated[0]["id"], "same-record")
        widget.deleteLater()
