import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from focus_lock.core import Profile, Timer, is_blocked
from focus_lock.storage import Storage


class TimerTests(unittest.TestCase):
    def test_delayed_tick_does_not_drift(self):
        now = [100.0]
        timer = Timer(lambda: now[0]); timer.start(1500)
        now[0] += 123.4
        self.assertAlmostEqual(timer.remaining, 1376.6)
        now[0] += 2000
        self.assertEqual(timer.remaining, 0)

    def test_pause_resume(self):
        now = [0.0]; timer = Timer(lambda: now[0]); timer.start(60)
        now[0] = 10; timer.pause(); now[0] = 200
        self.assertEqual(timer.remaining, 50)
        timer.resume(); now[0] = 205
        self.assertEqual(timer.remaining, 45)
        timer.stop(); self.assertEqual(timer.remaining, 0)


class PolicyTests(unittest.TestCase):
    def test_away_does_not_allow_even_whitelisted_tools(self):
        profile = Profile(policy="away", allowed=["Code.exe", "chrome.exe"])
        self.assertTrue(is_blocked("Code.exe", profile))
        self.assertTrue(is_blocked("chrome.exe", profile))

    def test_allowed_browser_overrides_browser_block(self):
        profile = Profile(allowed=[r"C:\Browser\chrome.exe"])
        self.assertFalse(is_blocked(r"c:\browser\CHROME.EXE", profile))
        self.assertTrue(is_blocked(r"D:\Browser\chrome.exe", profile))

    def test_allowlist_and_denylist(self):
        profile = Profile(allowed=["Code.exe"])
        self.assertFalse(is_blocked(r"C:\Code.exe", profile))
        self.assertTrue(is_blocked(r"C:\LINE.exe", profile))
        profile.policy = "denylist"
        self.assertFalse(is_blocked(r"C:\WINWORD.EXE", profile))
        self.assertTrue(is_blocked(r"C:\Discord.exe", profile))
        profile.block_browsers = False
        self.assertFalse(is_blocked(r"C:\msedge.exe", profile))

    def test_allowlist_wins_conflict(self):
        self.assertFalse(is_blocked("LINE.exe", Profile(allowed=["LINE.exe"])))


class StorageTests(unittest.TestCase):
    def test_existing_settings_get_away_once_without_readding_deleted_presets(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root)
            custom = Profile(name="我的方案", allowed=["Study.exe"]).to_dict()
            store.save({"profiles": [custom], "starter_profiles_version": 1})
            upgraded = store.load()
            self.assertEqual([p["name"] for p in upgraded["profiles"]], ["我的方案", "離開筆電 25 分鐘"])
            self.assertEqual(upgraded["profiles"][0], custom)
            upgraded["profiles"].pop()
            store.save(upgraded)
            self.assertEqual([p["name"] for p in store.load()["profiles"]], ["我的方案"])
    def test_three_starter_profiles(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            with patch("focus_lock.presets.executable", side_effect=lambda name, relatives: name):
                profiles = Storage(root).load()["profiles"]
            self.assertEqual([p["name"] for p in profiles], ["雅思聽力", "Robotics", "雅思口說", "離開筆電 25 分鐘"])
            self.assertFalse(profiles[0]["allowed"])
            for profile in profiles:
                self.assertEqual(profile["focus_minutes"], 25)
                self.assertIn(profile["policy"], ("allowlist", "away"))
            speaking = Profile(**profiles[2])
            self.assertFalse(is_blocked("WINWORD.EXE", Profile(allowed=["WINWORD.EXE"])))
            self.assertEqual(len(speaking.allowed), 2)

    def test_detect_listening_executable_without_arguments(self):
        from focus_lock.presets import starter_profiles
        expected = r"C:\Study\九分学长考雅机考平台.exe"
        with patch("focus_lock.presets.executable", side_effect=lambda name, relatives: expected if name == "" else name):
            profile = starter_profiles()[0]
        self.assertEqual(profile.allowed, [expected])
        self.assertFalse(is_blocked(expected, profile))
        self.assertNotIn("--disable-gpu", profile.allowed[0])

    def test_fill_empty_listening_but_preserve_custom_path(self):
        from focus_lock.presets import add_starter_profiles
        empty = Profile(name="雅思聽力").to_dict()
        settings = {"profiles": [empty], "starter_profiles_version": 1}
        with patch("focus_lock.presets.executable", return_value=r"C:\Study\IELTS.exe"):
            result = add_starter_profiles(settings)
            self.assertEqual(result["profiles"][0]["allowed"], [r"C:\Study\IELTS.exe"])
            result["profiles"][0]["allowed"] = [r"D:\Custom.exe"]
            self.assertEqual(add_starter_profiles(result)["profiles"][0]["allowed"], [r"D:\Custom.exe"])

    def test_upgrade_preserves_custom_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root)
            custom = Profile(name="Robotics", focus_minutes=45, allowed=["MyTool.exe"]).to_dict()
            store.save({"profiles": [custom], "opacity": 80, "position": [10, 20]})
            upgraded = store.load()
            self.assertEqual(upgraded["profiles"][0], custom)
            self.assertEqual(len(upgraded["profiles"]), 4)
            self.assertEqual(upgraded["opacity"], 80)
            store.save(upgraded)
            self.assertEqual(store.load(), upgraded)
            upgraded["profiles"][1]["name"] = "我的聽力"
            store.save(upgraded)
            self.assertEqual(len(store.load()["profiles"]), 4)

    def test_roundtrip_and_unlock_log(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root); data = store.load(); store.save(data)
            self.assertEqual(store.load(), data)
            store.log_unlock("口說")
            self.assertIn("口說", (Path(root) / "events.jsonl").read_text(encoding="utf-8"))

    def test_corrupt_settings_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root); store.path.write_text("broken", encoding="utf-8")
            self.assertTrue(store.load()["profiles"])
            self.assertTrue(store.warning)
            self.assertEqual(store.path.read_text(), "broken")

    def test_invalid_profile_falls_back(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as root:
            store = Storage(root)
            store.path.write_text('{"profiles": [{"focus_minutes": -1}]}')
            self.assertEqual(store.load()["profiles"][0]["focus_minutes"], 25)
            self.assertTrue(store.warning)


if __name__ == "__main__":
    unittest.main()
