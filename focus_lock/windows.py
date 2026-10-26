"""Read foreground processes; never terminate or suspend a process."""
import ctypes
from ctypes import wintypes
import os
import psutil


class Windows:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = [self.enum_callback, wintypes.LPARAM]

    def foreground(self):
        hwnd = self.user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return None
        try:
            process = psutil.Process(pid.value)
            return hwnd, process.exe(), pid.value
        except (psutil.Error, OSError):
            return None

    def activate(self, hwnd):
        if hwnd and self.user32.IsWindow(hwnd):
            self.user32.ShowWindow(hwnd, 9)
            return bool(self.user32.SetForegroundWindow(hwnd))
        return False

    def applications(self):
        result = set()
        for process in psutil.process_iter(["exe"]):
            try:
                if process.info["exe"]:
                    result.add(process.info["exe"])
            except psutil.Error:
                pass
        return sorted(result, key=str.casefold)

    def visible_windows(self):
        result = []

        @self.enum_callback
        def collect(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            length = self.user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            pid = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == os.getpid():
                return True
            try:
                executable = psutil.Process(pid.value).exe()
                title = ctypes.create_unicode_buffer(length + 1)
                self.user32.GetWindowTextW(hwnd, title, length + 1)
                result.append((hwnd, executable, pid.value, title.value))
            except (psutil.Error, OSError):
                pass
            return True

        self.user32.EnumWindows(collect, 0)
        return result
