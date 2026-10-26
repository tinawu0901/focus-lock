import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from focus_lock.core import Profile, is_blocked
from focus_lock.tools import launch_missing, inspect_tools, validate_url
from focus_lock.browser import BrowserBridge
from focus_lock.native_host import read_message, write_message, respond


class ToolTests(unittest.TestCase):
    def test_argument_boundaries_no_shell(self):
        profile = Profile(launch_tools=[{"executable": "Study.exe", "arguments": ["--disable-gpu", "file with spaces", "$(no-shell)"]}])
        windows = Mock(); windows.visible_windows.return_value = []
        launch = Mock()
        with patch("focus_lock.tools.resolve_executable", return_value=r"C:\Study Files\Study.exe"):
            self.assertEqual(launch_missing(profile, windows, launch), [])
        args, options = launch.call_args
        self.assertEqual(args[0], [r"C:\Study Files\Study.exe", "--disable-gpu", "file with spaces", "$(no-shell)"])
        self.assertFalse(options["shell"])

    def test_running_window_not_launched_twice(self):
        profile = Profile(launch_tools=[{"executable": "Study.exe", "arguments": []}])
        windows = Mock(); windows.visible_windows.return_value = [(1, r"C:\Study.exe", 123, "My work")]
        launch = Mock()
        with patch("focus_lock.tools.resolve_executable", return_value=r"C:\Study.exe"):
            self.assertEqual(inspect_tools(profile, windows)[0]["titles"], ["My work"])
            self.assertEqual(launch_missing(profile, windows, launch), [])
        launch.assert_not_called()

    def test_missing_tool_reported(self):
        windows = Mock(); windows.visible_windows.return_value = []
        profile = Profile(launch_tools=[{"executable": "missing.exe", "arguments": []}])
        with patch("focus_lock.tools.resolve_executable", return_value=None):
            self.assertTrue(launch_missing(profile, windows, Mock()))

    def test_urls_not_commands(self):
        self.assertEqual(validate_url("ChatGPT.com"), "https://chatgpt.com/")
        for value in ("javascript:alert(1)", "file:///C:/secret", "https://user:pass@example.com", "https://bad host"):
            with self.assertRaises(ValueError, msg=value): validate_url(value)

    def test_website_mode_does_not_allow_other_browser(self):
        profile = Profile(website_lock=True, browser_executable="msedge.exe", allowed=["chrome.exe", "msedge.exe"])
        self.assertTrue(is_blocked("chrome.exe", profile))
        self.assertFalse(is_blocked("msedge.exe", profile))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.directory.name)
        self.now = [1000.0]
        self.bridge = BrowserBridge(self.root, lambda: self.now[0])
        self.profile = Profile(website_lock=True, browser_executable="msedge.exe", urls=["https://chatgpt.com/"])

    def tearDown(self): self.directory.cleanup()

    def test_ack_lease_and_pause(self):
        self.bridge.publish(self.profile, active=True)
        self.assertFalse(self.bridge.ready("msedge.exe", True))
        respond(self.root, {"browser": "edge", "revision": self.bridge.revision, "applied": True}, lambda: self.now[0])
        self.assertTrue(self.bridge.ready("msedge.exe", True))
        self.assertFalse(self.bridge.ready("chrome.exe", True))
        self.bridge.publish(force=True)
        self.assertFalse(json.loads(self.bridge.path.read_text())["active"])
        self.assertFalse(self.bridge.ready("msedge.exe", True))
        self.now[0] += 6
        self.assertFalse(self.bridge.ready("msedge.exe"))

    def test_expired_policy_is_released(self):
        self.bridge.publish(self.profile, True)
        response = respond(self.root, {"browser": "edge"}, lambda: self.now[0] + 9)
        self.assertFalse(response["active"])

    def test_native_message_frames_and_limits(self):
        stream = io.BytesIO(); write_message(stream, {"name": "口說"}); stream.seek(0)
        self.assertEqual(read_message(stream), {"name": "口說"})
        self.assertIsNone(read_message(stream))
        with self.assertRaises(ValueError): read_message(io.BytesIO(struct.pack("<I", 300000)))
        with self.assertRaises(ValueError): read_message(io.BytesIO(struct.pack("<I", 20) + b'{}'))

    def test_tabs_are_requested_on_demand_and_cleared_after_close(self):
        self.bridge.request_tabs("chrome.exe")
        request = {"browser": "chrome", "protocol": 3, "tabs": [{"title": "Work", "url": "https://example.com/work"},
                   {"title": "Settings", "url": "chrome://settings/"}]}
        response = respond(self.root, request, lambda: self.now[0])
        self.assertTrue(response["request_tabs"])
        tabs, status = self.bridge.open_tabs("chrome.exe")
        self.assertEqual(tabs, [{"title": "Work", "url": "https://example.com/work"}])
        self.bridge.request_tabs("chrome.exe", False)
        response = respond(self.root, request, lambda: self.now[0])
        self.assertFalse(response["request_tabs"])
        self.assertIsNone(json.loads((self.root / "browser-chrome.json").read_text())["tabs"])

    def test_old_extension_has_actionable_reload_message(self):
        respond(self.root, {"browser": "chrome"}, lambda: self.now[0])
        tabs, status = self.bridge.open_tabs("chrome.exe")
        self.assertEqual(tabs, [])
        self.assertIn("重新載入", status)
