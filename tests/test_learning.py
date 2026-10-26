import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from focus_lock.core import Profile
from focus_lock.learning import LearningStore, validate_plan, parse_plan


def draft():
    return {"name": "Writing Task 1", "profile": "Writing", "steps": [
        {"name": "複習", "minutes": 30}, {"name": "寫作", "minutes": 30},
        {"name": "檢討", "minutes": 30}], "daily_time": ""}


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.directory.name)
        self.store = LearningStore(self.root)

    def tearDown(self): self.directory.cleanup()

    def test_import_does_not_accept_commands_or_change_permissions(self):
        data = draft(); data["allowed"] = ["evil.exe"]; data["command"] = "shell"
        parsed = parse_plan("```json\n" + json.dumps(data) + "\n```", ["Writing"])
        self.assertNotIn("allowed", parsed); self.assertNotIn("command", parsed)
        data["profile"] = "Unknown"
        with self.assertRaises(ValueError): validate_plan(data, ["Writing"])

    def test_invalid_minutes_and_dates_are_rejected(self):
        for value in (True, 0, 241, 2.5, "30"):
            data = draft(); data["steps"][0]["minutes"] = value
            with self.assertRaises(ValueError): validate_plan(data, ["Writing"])
        for value in ("8:00", "24:00", "12:70", False):
            data = draft(); data["daily_time"] = value
            with self.assertRaises(ValueError): validate_plan(data, ["Writing"])

    def test_recovery_counts_checkpoint_not_offline_time(self):
        plan = self.store.put_plan(validate_plan(draft(), ["Writing"]))
        self.store.begin(Profile(name="Writing"), 1800, plan, 1)
        self.store.checkpoint(120)
        restored = LearningStore(self.root)
        self.assertIsNone(restored.data["active"])
        record = restored.data["records"][0]
        self.assertEqual(record["seconds"], 120)
        self.assertEqual(record["status"], "interrupted")
        self.assertEqual(record["step"], "寫作")
        self.assertEqual(len(LearningStore(self.root).data["records"]), 1)

    def test_end_is_idempotent_and_away_excluded(self):
        self.store.begin(Profile(name="Writing"), 60)
        self.store.end(90, "completed")
        self.assertIsNone(self.store.end(60, "completed"))
        self.store.begin(Profile(name="Away", policy="away"), 60)
        self.store.end(60, "completed")
        today = datetime.now().astimezone().date().isoformat()
        self.assertEqual(self.store.day_seconds(today), 60)
        self.assertEqual(len(self.store.day_records(today)), 2)

    def test_daily_once_per_day_and_snooze_persists(self):
        data = draft(); data["daily_time"] = "08:00"
        self.store.put_plan(validate_plan(data, ["Writing"]))
        at = datetime.now().astimezone().replace(hour=8, minute=0)
        self.assertEqual(len(self.store.due(at - timedelta(minutes=1))), 0)
        due = self.store.due(at)
        self.assertEqual(len(due), 1)
        self.assertEqual(len(self.store.due(at)), 1)
        self.store.resolve(due[0], "skipped")
        self.assertEqual(len(self.store.due(at + timedelta(minutes=1))), 0)
        tomorrow = self.store.due(at + timedelta(days=1))
        self.assertEqual(len(tomorrow), 1)
        self.store.resolve(tomorrow[0], "snooze")
        restored = LearningStore(self.root)
        self.assertEqual(restored.data["reminders"][-1]["status"], "pending")

    def test_schedule_retains_duration_and_rejects_past(self):
        with self.assertRaises(ValueError): self.store.schedule(None, 0, datetime.now().astimezone() - timedelta(seconds=1))
        self.store.schedule(None, 0, datetime.now().astimezone() + timedelta(hours=1), "修改", minutes=15, profile="Writing")
        restored = LearningStore(self.root)
        self.assertEqual(restored.data["reminders"][0]["minutes"], 15)
        self.assertEqual(restored.data["reminders"][0]["profile"], "Writing")

    def test_corrupt_data_never_overwritten(self):
        self.store.path.write_text('{"version":1,"plans":42}', encoding="utf-8")
        restored = LearningStore(self.root)
        self.assertTrue(restored.read_only)
        with self.assertRaises(OSError): restored.save()
        self.assertEqual(self.store.path.read_text(), '{"version":1,"plans":42}')


if __name__ == "__main__": unittest.main()
