"""Opaque, clickable desktop guards; no global input hooks or foreign window mutation."""
from .i18n import tr
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QApplication


class GuardWindow(QWidget):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.setWindowTitle(tr("Focus Lock · 此視窗未允許"))
        self.setWindowOpacity(1.0)
        self.setStyleSheet("QWidget {background:#171c29; color:#ecf0ff; font-family:'Segoe UI'; font-size:16px;}"
                           "QPushButton,QComboBox {background:#303b54; padding:12px; border:1px solid #52617f; border-radius:6px;}")
        layout = QVBoxLayout(self)
        layout.addStretch()
        self.title = QLabel(tr("請返回這次專注允許的工具"))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size:30px; color:#91e6c4;")
        layout.addWidget(self.title)
        self.countdown = QLabel()
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown.setStyleSheet("font-size:40px; color:#91e6c4;")
        layout.addWidget(self.countdown)
        self.message = QLabel(); self.message.setWordWrap(True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.message)
        self.choices = QComboBox(); self.choices.setMinimumWidth(500); self.choices.setMaximumWidth(800)
        layout.addWidget(self.choices, alignment=Qt.AlignmentFlag.AlignHCenter)
        row = QHBoxLayout(); row.addStretch()
        self.back_button = QPushButton(tr("切換至選取的工作視窗")); self.back_button.clicked.connect(self.return_to_work); row.addWidget(self.back_button)
        self.refresh_button = QPushButton(tr("重新整理視窗")); self.refresh_button.clicked.connect(self.refresh); row.addWidget(self.refresh_button)
        row.addStretch(); layout.addLayout(row)
        row = QHBoxLayout(); row.addStretch()
        self.pause_button = QPushButton(tr("暫停專注")); self.pause_button.clicked.connect(owner.pause); row.addWidget(self.pause_button)
        self.end_button = QPushButton(tr("提前結束")); self.end_button.clicked.connect(owner.stop); row.addWidget(self.end_button)
        unlock = QPushButton(tr("緊急解鎖")); unlock.clicked.connect(owner.guard_unlock); row.addWidget(unlock)
        row.addStretch(); layout.addLayout(row)
        self.hint = QLabel()
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.hint)
        layout.addStretch()

    def refresh(self):
        if self.owner.active and self.owner.active.policy == "away":
            self.choices.clear()
            return
        selected = self.choices.currentData()
        self.choices.clear()
        for hwnd, executable, _, title in self.owner.windows.visible_windows():
            if not self.owner.blocked(executable):
                self.choices.addItem(f"{Path(executable).name} — {title[:100]}", hwnd)
        if not self.choices.count():
            self.choices.addItem(tr("尚未找到允許的視窗；請先暫停或解鎖後開啟工具"), None)
        index = self.choices.findData(selected)
        if index >= 0:
            self.choices.setCurrentIndex(index)

    def return_to_work(self):
        hwnd = self.choices.currentData()
        # Recheck the handle and executable immediately before switching.
        allowed = {item[0] for item in self.owner.windows.visible_windows() if not self.owner.blocked(item[1])}
        if hwnd in allowed and self.owner.windows.activate(hwnd):
            self.owner.last_allowed = hwnd
            self.owner.hide_guards()
        else:
            self.message.setText(tr("無法切換：請重新整理，或使用 Alt+Tab 返回允許的工具。"))
            self.refresh()

    def closeEvent(self, event):
        if self.owner.exiting:
            event.accept()
        else:
            event.ignore()


class DesktopGuard:
    def __init__(self, owner):
        self.owner = owner
        self.windows = []
        self.executable = ""

    @property
    def visible(self):
        return any(window.isVisible() for window in self.windows)

    def show(self, executable, activate=True, away=False):
        self.executable = executable
        screens = QApplication.screens()
        while len(self.windows) < len(screens):
            self.windows.append(GuardWindow(self.owner))
        for index, window in enumerate(self.windows):
            if index >= len(screens):
                window.hide()
                continue
            window.setGeometry(screens[index].geometry())
            window.title.setText(tr("休息一下，暫時離開筆電") if away else tr("請返回這次專注允許的工具"))
            window.message.setText(f"{self.owner.active.name}{tr('\n時間到會自動解除遮罩。')}" if away else f"{tr('已阻擋操作：')}{Path(executable).name}{tr('\n專注方案：')}{self.owner.active.name}")
            window.hint.setText(tr("請起身走動、看看遠方或做不需螢幕的事情。\n背景工作仍繼續；需要處理重要事情時可緊急解鎖。") if away else
                                tr("未允許的程式仍在背景執行。可用 Alt+Tab 切回允許的工具。\n若尚未開啟工作工具，請先暫停或緊急解鎖，再開啟它。"))
            for control in (window.choices, window.back_button, window.refresh_button): control.setVisible(not away)
            window.countdown.setText(self.owner.time_label.text())
            window.pause_button.setVisible(not self.owner.active.strict)
            window.end_button.setVisible(away and not self.owner.active.strict)
            window.refresh()
            window.show(); window.raise_()
        if self.windows and activate:
            self.windows[0].activateWindow()

    def update_time(self, text):
        for window in self.windows:
            window.countdown.setText(text)

    def hide(self):
        for window in self.windows:
            window.hide()
