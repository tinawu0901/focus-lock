from dataclasses import dataclass, field, asdict
import time


@dataclass
class Profile:
    name: str = "新專注方案"
    focus_minutes: int = 25
    break_minutes: int = 5
    policy: str = "allowlist"
    strict: bool = False
    block_browsers: bool = True
    allowed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=lambda: ["LINE.exe", "Discord.exe"])
    domain_blacklist: list[str] = field(default_factory=lambda: ["youtube.com", "facebook.com", "instagram.com", "threads.net", "threads.com"])
    domain_whitelist: list[str] = field(default_factory=lambda: ["chatgpt.com"])
    description: str = ""
    launch_tools: list[dict] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    website_lock: bool = False
    browser_executable: str = ""

    def to_dict(self):
        return asdict(self)


class Timer:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.phase = "idle"
        self.deadline = 0.0
        self.paused = False
        self.saved_remaining = 0.0

    def start(self, seconds, phase="focus"):
        self.phase = phase
        self.deadline = self.clock() + seconds
        self.paused = False

    @property
    def remaining(self):
        if self.phase == "idle":
            return 0.0
        return self.saved_remaining if self.paused else max(0.0, self.deadline - self.clock())

    def pause(self):
        self.saved_remaining = self.remaining
        self.paused = True

    def resume(self):
        self.deadline = self.clock() + self.saved_remaining
        self.paused = False

    def stop(self):
        self.phase = "idle"
        self.paused = False


BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe"}


def normalize(path):
    return path.replace("/", "\\").casefold()


def matches(executable, entries):
    path = normalize(executable)
    name = path.rsplit("\\", 1)[-1]
    return any(path == normalize(entry) if "\\" in normalize(entry) else name == normalize(entry)
               for entry in entries if entry.strip())


def is_blocked(executable, profile):
    if profile.policy == "away":
        return True
    if profile.website_lock and normalize(executable).rsplit("\\", 1)[-1] in BROWSERS:
        return not matches(executable, [profile.browser_executable])
    # Explicit allowed applications always win, including browser exceptions.
    if matches(executable, profile.allowed):
        return False
    if profile.block_browsers and normalize(executable).rsplit("\\", 1)[-1] in BROWSERS:
        return True
    if profile.policy == "allowlist":
        return True
    return matches(executable, profile.blocked)
