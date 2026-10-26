"""Local starter profiles. Never overwrite a user's saved profile."""
import os
from pathlib import Path
from .core import Profile


def executable(name, relatives):
    for variable, relative in relatives:
        base = os.environ.get(variable)
        if base:
            candidate = Path(base) / relative
            if candidate.is_file():
                return str(candidate)
    return name


def away_profile():
    return Profile(name="離開筆電 25 分鐘", policy="away", strict=True, focus_minutes=25,
                   description="25 分鐘離開螢幕：各螢幕顯示倒數遮罩，時間到解除；保留緊急解鎖。")


def starter_profiles():
    listening = executable("", [("LOCALAPPDATA", r"Programs\xxgg-ielts\九分学长考雅机考平台.exe")])
    code = executable("Code.exe", [("LOCALAPPDATA", r"Programs\Microsoft VS Code\Code.exe"),
                                    ("ProgramFiles", r"Microsoft VS Code\Code.exe")])
    word = executable("WINWORD.EXE", [(variable, path) for variable in ("ProgramFiles", "ProgramFiles(x86)")
                                      for path in (r"Microsoft Office\root\Office16\WINWORD.EXE",
                                                   r"Microsoft Office\Office16\WINWORD.EXE")])
    edge = executable("msedge.exe", [(variable, r"Microsoft\Edge\Application\msedge.exe")
                                     for variable in ("ProgramFiles(x86)", "ProgramFiles")])
    virtualbox = executable("VirtualBoxVM.exe", [("ProgramFiles", r"Oracle\VirtualBox\VirtualBoxVM.exe")])
    return [
        Profile(name="雅思聽力", allowed=[listening] if listening else [],
                launch_tools=[{"executable": listening, "arguments": ["--disable-gpu"]}] if listening else [],
                description="九分學長：僅允許考雅機考平台，專注 25 分鐘。" if listening else
                            "九分學長：請先編輯方案，選取你安裝的九分學長 EXE，再開始 25 分鐘練習。"),
        Profile(name="Robotics", allowed=[code, "Codex.exe", "WindowsTerminal.exe", "OpenConsole.exe", "conhost.exe",
                                            "VirtualBox.exe", virtualbox, "vmware.exe", "vmware-vmx.exe"],
                description="允許 Codex、VS Code、Terminal、VirtualBox 與 VMware；可編輯刪除不需要的工具。"),
        Profile(name="雅思口說", allowed=[word, edge],
                launch_tools=[{"executable": word, "arguments": []}], urls=["https://chatgpt.com/"],
                website_lock=True, browser_executable=edge,
                description="Word＋ChatGPT；開始前檢查工具與網站擴充功能。"),
        away_profile(),
    ]


def add_starter_profiles(settings):
    # Upgrade an unconfigured listening starter without changing an edited allowlist.
    for profile in settings["profiles"]:
        if profile.get("name") == "雅思聽力" and "launch_tools" not in profile:
            allowed = profile.get("allowed", [])
            if len(allowed) == 1 and allowed[0].replace("\\", "/").endswith("/九分学长考雅机考平台.exe"):
                profile["launch_tools"] = [{"executable": allowed[0], "arguments": ["--disable-gpu"]}]
        if profile.get("name") == "雅思聽力" and not profile.get("allowed"):
            detected = executable("", [("LOCALAPPDATA", r"Programs\xxgg-ielts\九分学长考雅机考平台.exe")])
            if detected:
                profile["allowed"] = [detected]
                profile["description"] = "九分學長：僅允許考雅機考平台，專注 25 分鐘。"
    version = settings.get("starter_profiles_version", 0)
    if version >= 2:
        return settings
    existing_names = {item["name"] for item in settings["profiles"]}
    settings["profiles"] = list(settings["profiles"]) + [
        profile.to_dict() for profile in (starter_profiles() if version == 0 else [away_profile()]) if profile.name not in existing_names
    ]
    settings["starter_profiles_version"] = 2
    return settings
