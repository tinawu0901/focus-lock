"""Resolve and launch explicit tools without shell commands."""
from .i18n import tr
import shutil
import subprocess
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from .core import matches


def discover_browser(name, windows=None):
    executable = {"chrome": "chrome.exe", "edge": "msedge.exe"}.get(name)
    if not executable:
        return None
    if windows is not None:
        found = resolve_executable(executable, windows.visible_windows())
        if found: return found
    if os.name == "nt":
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(root, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}", 0, winreg.KEY_READ | view) as key:
                        candidate = os.path.expandvars(winreg.QueryValueEx(key, "")[0]).strip('"')
                        if Path(candidate).is_file(): return candidate
                except OSError:
                    pass
    relative = r"Google\Chrome\Application\chrome.exe" if name == "chrome" else r"Microsoft\Edge\Application\msedge.exe"
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(variable):
            candidate = Path(os.environ[variable]) / relative
            if candidate.is_file(): return str(candidate)
    return resolve_executable(executable)


def validate_url(value):
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError(tr("網址只接受 http／https，不接受帳號密碼或程式指令"))
    if any(c.isspace() for c in value):
        raise ValueError(tr("網址不可包含空白"))
    try:
        parts.port
    except ValueError as exc:
        raise ValueError(tr("網址連接埠無效")) from exc
    host = parts.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))


def resolve_executable(entry, visible=()):
    if not entry or '"' in entry or not entry.casefold().endswith(".exe"):
        return None
    path = Path(entry)
    if path.is_file():
        return str(path.resolve())
    if "\\" in entry or "/" in entry:
        return None
    for _, executable, *_ in visible:
        if matches(executable, [entry]) and Path(executable).is_file():
            return executable
    found = shutil.which(entry)
    return found if found and Path(found).is_file() else None


def inspect_tools(profile, windows):
    visible = windows.visible_windows()
    result = []
    for tool in profile.launch_tools:
        entry = tool["executable"]
        titles = [title for _, executable, _, title in visible if matches(executable, [entry])]
        resolved = resolve_executable(entry, visible)
        result.append({"executable": entry, "resolved": resolved, "arguments": list(tool["arguments"]),
                       "titles": titles, "status": tr("已開啟工作視窗") if titles else tr("可開啟") if resolved else tr("找不到 EXE")})
    return result


def launch_missing(profile, windows, popen=subprocess.Popen):
    report = inspect_tools(profile, windows)
    errors = []
    for tool in report:
        if tool["titles"]:
            continue
        if not tool["resolved"]:
            errors.append(f"{tr('找不到：')}{tool['executable']}")
            continue
        try:
            popen([tool["resolved"], *tool["arguments"]], cwd=str(Path(tool["resolved"]).parent), shell=False)
        except OSError as exc:
            errors.append(f"{tool['executable']}：{exc}")
    if profile.urls:
        browser = resolve_executable(profile.browser_executable, windows.visible_windows())
        if not browser:
            errors.append(tr("請選取有效的 Chrome 或 Edge EXE，以開啟方案網址"))
        else:
            try:
                popen([browser, *[validate_url(url) for url in profile.urls]], shell=False)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    return errors
