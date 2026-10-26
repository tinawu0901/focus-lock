"""Short-lived local browser policy and acknowledged extension health."""
from .i18n import tr
import json
import time
import uuid
from pathlib import Path


class BrowserBridge:
    def __init__(self, root, clock=time.time):
        self.root = Path(root)
        self.clock = clock
        self.path = self.root / "browser-policy.json"
        self.signature = None
        self.revision = ""
        self.last_write = 0
        self.error = ""

    def publish(self, profile=None, active=False, force=False):
        enabled = bool(active and profile and profile.website_lock and profile.policy != "away")
        urls = list(profile.urls) if enabled else []
        browser = self.browser_name(profile.browser_executable) if enabled else ""
        signature = (enabled, tuple(urls), browser)
        if signature != self.signature:
            self.signature = signature
            self.revision = str(uuid.uuid4())
            force = True
        if not force and self.clock() - self.last_write < 1:
            return
        data = {"active": enabled, "urls": urls, "browser": browser, "revision": self.revision,
                "expires_at": self.clock() + 8}
        try:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data), encoding="utf-8")
            temporary.replace(self.path)
            self.last_write = self.clock()
            self.error = ""
        except OSError as exc:
            self.error = str(exc)

    @staticmethod
    def browser_name(executable):
        name = executable.replace("\\", "/").rsplit("/", 1)[-1].casefold()
        return {"chrome.exe": "chrome", "msedge.exe": "edge"}.get(name, "")

    def ready(self, executable, require_applied=False):
        browser = self.browser_name(executable)
        if not browser or self.error:
            return False
        try:
            status = json.loads((self.root / f"browser-{browser}.json").read_text(encoding="utf-8"))
            if not 0 <= self.clock() - status["updated_at"] < 5:
                return False
            if status.get("error"):
                return False
            return not require_applied or (status.get("revision") == self.revision and status.get("applied") is True)
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def request_tabs(self, executable, enabled=True):
        request = {"browser": self.browser_name(executable), "expires_at": self.clock() + 30 if enabled else 0}
        target = self.root / "browser-tabs-request.json"
        try:
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(request), encoding="utf-8")
            temporary.replace(target)
        except OSError:
            return False
        return True

    def open_tabs(self, executable):
        browser = self.browser_name(executable)
        if not browser: return [], tr("請先選擇 Chrome 或 Edge")
        if not self.ready(executable): return [], tr("擴充功能未連線；請開啟瀏覽器並確認 Focus Lock 擴充功能已啟用")
        try:
            status = json.loads((self.root / f"browser-{browser}.json").read_text(encoding="utf-8"))
            if status.get("protocol", 0) < 3:
                return [], tr("擴充功能需要更新：請在瀏覽器擴充功能頁按一次「重新載入」")
            if status.get("tabs") is None:
                return [], tr("正在讀取目前分頁…")
            tabs = status["tabs"]
            return tabs, f"{tr('找到 ')}{len(tabs)}{tr(' 個分頁（最多 100 個，不含無痕與瀏覽器設定頁）')}"
        except (OSError, ValueError, TypeError):
            return [], tr("正在等候分頁資料…")
