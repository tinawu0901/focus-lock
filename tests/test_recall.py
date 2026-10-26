import unittest
from focus_lock.recall import pending_recall, validate_reflection


class RecallTests(unittest.TestCase):
    def test_all_answers_required_and_no_stuck_is_explicit(self):
        for args in (("", "例子", "疑問", False), ("重點", "", "疑問", False), ("重點", "例子", "", False)):
            with self.assertRaises(ValueError): validate_reflection(*args)
        self.assertEqual(validate_reflection(" 重點 ", "例子", "", True)["stuck"], "目前沒有")

    def test_pending_survives_mode_toggle_and_excludes_away(self):
        records = [{"recall_required": True, "away": True}, {"id": "pending", "recall_required": True}, {"recall_required": True, "reflection_done": True}]
        self.assertEqual(pending_recall(records)["id"], "pending")

    def test_crash_checkpoint_retains_recall_requirement(self):
        import tempfile
        from pathlib import Path
        from focus_lock.learning import LearningStore
        from focus_lock.core import Profile
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = LearningStore(Path(root)); record = store.begin(Profile(), 1500)
            record.update(recall_required=True, intention={"question": "目標", "criterion": "完成標準"})
            store.checkpoint(100)
            restored = LearningStore(Path(root))
            self.assertEqual(pending_recall(restored.data["records"])["intention"]["question"], "目標")
