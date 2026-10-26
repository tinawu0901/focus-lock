import json
import os
from pathlib import Path
from datetime import datetime, timezone
from .core import Profile
from .presets import starter_profiles, add_starter_profiles
from .tools import validate_url


class Storage:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FocusLock"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "settings.json"
        self.warning = ""

    def load(self):
        defaults = {"opacity": 95, "position": None, "profiles": [p.to_dict() for p in starter_profiles()],
                    "starter_profiles_version": 2}
        if not self.path.exists():
            return defaults
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("設定必須是物件")
            profiles = data.get("profiles", defaults["profiles"])
            if not isinstance(profiles, list) or not profiles:
                raise ValueError("缺少方案")
            for item in profiles:
                profile = Profile(**item)
                if not isinstance(item.get("name"), str):
                    raise ValueError("缺少方案名稱")
                if not isinstance(profile.name, str) or not profile.name.strip():
                    raise ValueError("方案名稱無效")
                if not isinstance(profile.description, str):
                    raise ValueError("方案說明無效")
                if not all(type(v) is int and 1 <= v <= 240 for v in (profile.focus_minutes, profile.break_minutes)):
                    raise ValueError("時間無效")
                if profile.policy not in ("allowlist", "denylist", "away"):
                    raise ValueError("規則無效")
                for entries in (profile.allowed, profile.blocked, profile.domain_blacklist, profile.domain_whitelist):
                    if not isinstance(entries, list) or not all(isinstance(x, str) for x in entries):
                        raise ValueError("清單無效")
                if type(profile.website_lock) is not bool or not isinstance(profile.browser_executable, str):
                    raise ValueError("瀏覽器設定無效")
                if not isinstance(profile.urls, list) or not all(isinstance(url, str) for url in profile.urls):
                    raise ValueError("網址清單無效")
                for url in profile.urls:
                    validate_url(url)
                if not isinstance(profile.launch_tools, list):
                    raise ValueError("啟動工具無效")
                for tool in profile.launch_tools:
                    if not isinstance(tool, dict) or set(tool) != {"executable", "arguments"}:
                        raise ValueError("啟動工具格式無效")
                    if not isinstance(tool["executable"], str) or not isinstance(tool["arguments"], list) or not all(isinstance(a, str) for a in tool["arguments"]):
                        raise ValueError("啟動參數無效")
            if type(data.get("opacity", 95)) is not int or not 35 <= data.get("opacity", 95) <= 100:
                raise ValueError("透明度無效")
            position = data.get("position")
            if position is not None and (not isinstance(position, list) or len(position) != 2 or not all(type(x) is int for x in position)):
                raise ValueError("位置無效")
            if type(data.get("starter_profiles_version", 0)) is not int:
                raise ValueError("預設方案版本無效")
            result = defaults | data
            result["starter_profiles_version"] = data.get("starter_profiles_version", 0)
            return add_starter_profiles(result)
        except (OSError, ValueError, TypeError) as exc:
            self.warning = f"設定無法讀取，已使用預設值：{exc}。原檔已保留；儲存設定前請先備份。"
            return defaults

    def save(self, settings):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def log_unlock(self, profile):
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": "emergency_unlock", "profile": profile,
                                     "time": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False) + "\n")
