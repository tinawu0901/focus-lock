from .i18n import tr
from .i18n import set_language
import math
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QPlainTextEdit, QFormLayout, QFileDialog,
    QDialogButtonBox, QMessageBox, QSystemTrayIcon, QMenu, QInputDialog, QLineEdit, QSlider,
    QTabWidget, QTableWidget, QTableWidgetItem, QAbstractItemView)
from .core import Profile, Timer, is_blocked
from .storage import Storage
from .windows import Windows
from .guard import DesktopGuard
from .compact import CompactTimer
from .tools import validate_url, inspect_tools, launch_missing, resolve_executable, discover_browser
from .browser import BrowserBridge
from .selectors import CheckListDialog
from .learning_flow import LearningFlow


STYLE = """
QWidget { background: #171c29; color: #ecf0ff; font-family: 'Segoe UI'; font-size: 13px; }
QPushButton { background: #303b54; border: 1px solid #52617f; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #465678; }
QComboBox, QSpinBox, QPlainTextEdit, QLineEdit { background: #232c40; padding: 5px; }
QLabel#time { color: #91e6c4; font-size: 36px; font-weight: bold; }
"""


class ProfileDialog(QDialog):
    def __init__(self, profile, windows, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("專注方案設定"))
        self.resize(610, 650)
        self.windows = windows
        self.bridge = parent.bridge if hasattr(parent, "bridge") else BrowserBridge(parent.storage.root)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs)
        general = QWidget(); tabs.addTab(general, tr("方案與允許程式"))
        layout = QVBoxLayout(general)
        form = QFormLayout()
        self.name = QLineEdit(profile.name)
        self.description = QLineEdit(profile.description)
        self.focus = QSpinBox(); self.focus.setRange(1, 240); self.focus.setValue(profile.focus_minutes)
        self.rest = QSpinBox(); self.rest.setRange(1, 240); self.rest.setValue(profile.break_minutes)
        self.policy = QComboBox(); self.policy.addItems([tr("僅允許指定應用程式"), tr("只封鎖黑名單"), tr("離開筆電（全螢幕倒數遮罩）")])
        self.policy.setCurrentIndex({"allowlist": 0, "denylist": 1, "away": 2}[profile.policy])
        self.strict = QCheckBox(tr("嚴格模式（開始前再次確認）")); self.strict.setChecked(profile.strict)
        self.browser = QCheckBox(tr("封鎖瀏覽器（明確加入允許清單者除外）")); self.browser.setChecked(profile.block_browsers)
        for label, control in [(tr("方案名稱"), self.name), (tr("方案說明"), self.description), (tr("專注分鐘"), self.focus), (tr("休息分鐘"), self.rest),
                               (tr("限制方式"), self.policy), ("", self.strict), ("", self.browser)]:
            form.addRow(label, control)
        layout.addLayout(form)
        self.mode_hint = QLabel(); self.mode_hint.setWordWrap(True); layout.addWidget(self.mode_hint)
        self.allowed = QPlainTextEdit("\n".join(profile.allowed))
        self.blocked = QPlainTextEdit("\n".join(profile.blocked))
        self.allowed.setMaximumHeight(110); self.blocked.setMaximumHeight(80)
        layout.addWidget(QLabel(tr("允許的應用程式（每行一個 EXE 完整路徑或名稱）"))); layout.addWidget(self.allowed)
        row = QHBoxLayout()
        for title, callback in [(tr("選擇 EXE"), self.pick_file), (tr("勾選目前開啟的應用程式"), self.pick_running)]:
            button = QPushButton(title); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel(tr("程式黑名單（每行一個 EXE 路徑或名稱）"))); layout.addWidget(self.blocked)
        tools_page = QWidget(); tabs.addTab(tools_page, tr("啟動工具與參數"))
        tool_layout = QVBoxLayout(tools_page)
        tool_layout.addWidget(QLabel(tr("設定要一鍵開啟的工具。每個工具的 EXE 路徑與啟動參數分開儲存。")))
        self.launch_tools = copy.deepcopy(profile.launch_tools)
        self.tool_table = QTableWidget(0, 2); self.tool_table.setHorizontalHeaderLabels(["EXE", tr("啟動參數")])
        self.tool_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tool_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tool_table.horizontalHeader().setStretchLastSection(True)
        self.tool_table.cellDoubleClicked.connect(lambda row, col: self.edit_tool(row))
        tool_layout.addWidget(self.tool_table)
        actions = QHBoxLayout()
        for text, callback in [(tr("加入工具"), lambda: self.edit_tool()), (tr("編輯工具"), lambda: self.edit_tool(self.tool_table.currentRow())),
                               (tr("移除工具"), self.remove_tool)]:
            button = QPushButton(text); button.clicked.connect(callback); actions.addWidget(button)
        tool_layout.addLayout(actions); self.refresh_tools()
        running_tools = QPushButton(tr("勾選目前開啟的工具加入"))
        running_tools.clicked.connect(lambda: self.pick_running(True)); tool_layout.addWidget(running_tools)
        sites_page = QWidget(); tabs.addTab(sites_page, tr("允許網址"))
        sites = QVBoxLayout(sites_page)
        self.website_lock = QCheckBox(tr("僅允許以下網址（需要 Focus Lock 瀏覽器擴充功能）"))
        self.website_lock.setChecked(profile.website_lock or bool(profile.urls)); sites.addWidget(self.website_lock)
        sites.addWidget(QLabel(tr("選擇使用的瀏覽器；程式會自動偵測，不需要知道 EXE 在哪裡。")))
        row = QHBoxLayout()
        self.browser_choice = QComboBox(); self.browser_choice.addItem("Google Chrome", "chrome"); self.browser_choice.addItem("Microsoft Edge", "edge")
        row.addWidget(self.browser_choice)
        detect = QPushButton(tr("重新偵測")); detect.clicked.connect(lambda: self.detect_browser())
        row.addWidget(detect); sites.addLayout(row)
        self.browser_status = QLabel(); self.browser_status.setWordWrap(True); sites.addWidget(self.browser_status)
        self.browser_executable = QLineEdit(profile.browser_executable)
        self.manual_browser = QWidget(); manual_layout = QVBoxLayout(self.manual_browser); manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(self.browser_executable)
        pick_browser = QPushButton(tr("手動選擇瀏覽器 EXE")); pick_browser.clicked.connect(self.pick_browser); manual_layout.addWidget(pick_browser)
        manual = QPushButton(tr("進階：手動指定安裝位置"))
        manual.clicked.connect(lambda: self.manual_browser.setVisible(self.manual_browser.isHidden()))
        sites.addWidget(manual); sites.addWidget(self.manual_browser); self.manual_browser.hide()
        self.browser_choice.setCurrentIndex(1 if BrowserBridge.browser_name(profile.browser_executable) == "edge" else 0)
        self.browser_choice.currentIndexChanged.connect(lambda: self.detect_browser())
        self.browser_executable.textChanged.connect(self.refresh_browser_status)
        if not profile.browser_executable: self.detect_browser()
        else: self.refresh_browser_status()
        opened = QPushButton(tr("勾選瀏覽器目前開啟的網址")); opened.clicked.connect(self.pick_open_tabs); sites.addWidget(opened)
        sites.addWidget(QLabel(tr("每行一個網址。只有網域表示整站；含路徑表示該路徑與子路徑。\n子網域、登入跳轉網站需另外加入。此清單也是一鍵開啟的網址。")))
        self.urls = QPlainTextEdit("\n".join(profile.urls)); self.urls.setPlaceholderText("https://chatgpt.com/\nhttps://docs.ros.org/"); sites.addWidget(self.urls)
        self.urls.textChanged.connect(self.enable_url_restriction)
        sites.addWidget(QLabel(tr("請先開啟瀏覽器，再勾選需要的分頁。\n若未連線，請在瀏覽器擴充功能頁啟用或重新載入 Focus Lock。")))
        self.domain_blacklist = profile.domain_blacklist
        self.domain_whitelist = profile.domain_whitelist
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("儲存"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("取消"))
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.connection_timer = QTimer(self); self.connection_timer.timeout.connect(self.refresh_browser_status); self.connection_timer.start(1000)
        self.tabs = tabs
        self.policy.currentIndexChanged.connect(lambda: self.update_mode(True))
        self.update_mode()

    def enable_url_restriction(self):
        if self.urls.toPlainText().strip() and self.policy.currentIndex() != 2:
            self.website_lock.setChecked(True)

    def update_mode(self, recommend=False):
        away = self.policy.currentIndex() == 2
        self.mode_hint.setText(tr("離開模式：不允許工作視窗，倒數結束立即解除，不另計休息時間。") if away else "")
        for widget in (self.allowed, self.blocked, self.browser, self.rest): widget.setEnabled(not away)
        self.tabs.setTabEnabled(1, not away); self.tabs.setTabEnabled(2, not away)
        if away and recommend: self.strict.setChecked(True)

    def done(self, result):
        self.connection_timer.stop()
        super().done(result)

    def detect_browser(self):
        name = self.browser_choice.currentData()
        detected = discover_browser(name, self.windows)
        self.browser_executable.setText(detected or "")
        self.refresh_browser_status()

    def refresh_browser_status(self):
        path = self.browser_executable.text().strip()
        installed = bool(resolve_executable(path, self.windows.visible_windows())) if path else False
        connected = self.bridge.ready(path) if path else False
        if not installed:
            self.browser_status.setText(tr("未找到瀏覽器。請先安裝或開啟它，再按「重新偵測」；也可手動選擇。"))
        elif connected:
            self.browser_status.setText(tr("瀏覽器：已找到　｜　Focus Lock 擴充功能：已連線"))
        else:
            self.browser_status.setText(tr("瀏覽器：已找到　｜　擴充功能：未連線（請開啟瀏覽器並啟用擴充功能）"))
        self.browser_status.setStyleSheet("color:#91e6c4" if connected else "color:#f2c879")

    def pick_open_tabs(self):
        path = self.browser_executable.text().strip()
        if not path:
            self.detect_browser(); path = self.browser_executable.text().strip()
        if not path:
            QMessageBox.information(self, tr("瀏覽器"), tr("請先開啟所選瀏覽器，再按重新偵測。"))
            return
        def loader():
            self.bridge.request_tabs(path)
            tabs, status = self.bridge.open_tabs(path)
            return [([tab.get("title") or tr("未命名分頁"), tab["url"]], tab["url"]) for tab in tabs], status
        dialog = CheckListDialog(tr("勾選目前開啟的網址"), [tr("分頁標題"), tr("網址")], loader, self)
        scope = QComboBox(); scope.addItem(tr("僅允許勾選的頁面／路徑（建議）"), "path"); scope.addItem(tr("允許整個網站（含其他頁面）"), "site")
        dialog.options.insertWidget(0, scope)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                entries = [line.strip() for line in self.urls.toPlainText().splitlines() if line.strip()]
                for value in dialog.selected():
                    url = validate_url(value)
                    if scope.currentData() == "site":
                        parsed = urlsplit(url); url = urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
                    if url not in entries: entries.append(url)
                self.urls.setPlainText("\n".join(entries))
                if dialog.selected(): self.website_lock.setChecked(True)
                self.append_allowed(path)
        finally:
            self.bridge.request_tabs(path, enabled=False)
            dialog.deleteLater()

    def refresh_tools(self):
        self.tool_table.setRowCount(len(self.launch_tools))
        for row, tool in enumerate(self.launch_tools):
            self.tool_table.setItem(row, 0, QTableWidgetItem(tool["executable"]))
            self.tool_table.setItem(row, 1, QTableWidgetItem(" · ".join(tool["arguments"])))
        self.tool_table.resizeColumnToContents(0)

    def edit_tool(self, row=None):
        if row is not None and row < 0: return
        old = self.launch_tools[row] if row is not None else {"executable": "", "arguments": []}
        dialog = QDialog(self); dialog.setWindowTitle(tr("啟動工具"))
        layout = QVBoxLayout(dialog)
        executable = QLineEdit(old["executable"]); layout.addWidget(QLabel(tr("EXE 路徑（不含參數）"))); layout.addWidget(executable)
        pick = QPushButton(tr("選擇 EXE"))
        def choose():
            path, _ = QFileDialog.getOpenFileName(dialog, tr("選擇 EXE"), "", tr("Windows 程式 (*.exe)"))
            if path: executable.setText(path)
        pick.clicked.connect(choose); layout.addWidget(pick)
        layout.addWidget(QLabel(tr("每行一個啟動參數，不需要加引號；例如：\n--disable-gpu\nC:\\Study Files\\robotics.code-workspace")))
        arguments = QPlainTextEdit("\n".join(old["arguments"])); layout.addWidget(arguments)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = executable.text().strip()
            if not path.casefold().endswith(".exe") or '"' in path:
                QMessageBox.warning(self, tr("工具"), tr("請填寫 EXE 路徑，啟動參數填在下方。"))
                return
            tool = {"executable": path, "arguments": [a for a in arguments.toPlainText().splitlines() if a]}
            if row is None: self.launch_tools.append(tool)
            else: self.launch_tools[row] = tool
            self.append_allowed(path); self.refresh_tools()

    def remove_tool(self):
        row = self.tool_table.currentRow()
        if row >= 0:
            self.launch_tools.pop(row); self.refresh_tools()

    def pick_browser(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("選擇 Chrome 或 Edge"), "", tr("Windows 程式 (*.exe)"))
        if path:
            self.browser_choice.blockSignals(True)
            self.browser_choice.setCurrentIndex(1 if BrowserBridge.browser_name(path) == "edge" else 0)
            self.browser_choice.blockSignals(False)
            self.browser_executable.setText(path); self.append_allowed(path)

    def append_allowed(self, path):
        entries = self.allowed.toPlainText().splitlines()
        if path not in entries:
            self.allowed.appendPlainText(path)

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("選擇應用程式"), "", tr("Windows 應用程式 (*.exe)"))
        if path:
            self.append_allowed(path)

    def pick_running(self, add_tools=False):
        def loader():
            apps = {}
            for _, executable, _, title in self.windows.visible_windows():
                key = executable.casefold()
                apps.setdefault(key, [executable, []])[1].append(title)
            rows = [([Path(exe).stem, "、".join(dict.fromkeys(titles))], exe) for exe, titles in apps.values()]
            rows.sort(key=lambda row: row[0][0].casefold())
            return rows, f"{tr('找到 ')}{len(rows)}{tr(' 個有工作視窗的應用程式；同程式的多個視窗會合併，不列純背景程序。')}"
        dialog = CheckListDialog(tr("勾選允許的應用程式"), [tr("應用程式"), tr("目前工作視窗")], loader, self)
        launch = QCheckBox(tr("同時加入一鍵開啟")); launch.setChecked(add_tools); dialog.options.insertWidget(0, launch)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            existing = {tool["executable"].casefold() for tool in self.launch_tools}
            for path in dialog.selected():
                self.append_allowed(path)
                if launch.isChecked() and path.casefold() not in existing:
                    self.launch_tools.append({"executable": path, "arguments": []}); existing.add(path.casefold())
            self.refresh_tools()
        dialog.deleteLater()

    def validate(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, tr("方案"), tr("請輸入方案名稱。"))
            return
        try:
            urls = [validate_url(url) for url in self.urls.toPlainText().splitlines() if url.strip()] if self.policy.currentIndex() != 2 else []
            if self.policy.currentIndex() != 2 and self.website_lock.isChecked() and not urls:
                raise ValueError(tr("請至少加入一個允許網址"))
            if urls and not BrowserBridge.browser_name(self.browser_executable.text().strip()):
                raise ValueError(tr("請選取 Chrome 或 Edge 的 EXE"))
        except ValueError as exc:
            QMessageBox.warning(self, tr("網址"), str(exc)); return
        if self.policy.currentIndex() == 0 and not self.allowed.toPlainText().strip():
            QMessageBox.warning(self, tr("方案"), tr("請至少加入一個允許的應用程式。"))
            return
        self.accept()

    def profile(self):
        allowed = [x.strip() for x in self.allowed.toPlainText().splitlines() if x.strip()]
        for entry in [tool["executable"] for tool in self.launch_tools] + ([self.browser_executable.text().strip()] if self.urls.toPlainText().strip() else []):
            if entry and entry not in allowed: allowed.append(entry)
        return Profile(name=self.name.text().strip(), description=self.description.text().strip(), focus_minutes=self.focus.value(), break_minutes=self.rest.value(),
                       policy=("allowlist", "denylist", "away")[self.policy.currentIndex()],
                       strict=self.strict.isChecked(), block_browsers=self.browser.isChecked(),
                       allowed=allowed,
                       blocked=[x.strip() for x in self.blocked.toPlainText().splitlines() if x.strip()],
                       domain_blacklist=self.domain_blacklist, domain_whitelist=self.domain_whitelist,
                       launch_tools=copy.deepcopy(self.launch_tools),
                       urls=[validate_url(url) for url in self.urls.toPlainText().splitlines() if url.strip()] if self.policy.currentIndex() != 2 else [],
                       website_lock=self.website_lock.isChecked() and self.policy.currentIndex() != 2, browser_executable=self.browser_executable.text().strip())


class PreflightDialog(QDialog):
    def __init__(self, profile, owner):
        super().__init__(owner)
        self.setWindowTitle(tr("開始前檢查與一鍵開啟")); self.resize(680, 420)
        self.profile_data = profile; self.owner = owner
        layout = QVBoxLayout(self)
        self.report = QPlainTextEdit(); self.report.setReadOnly(True); layout.addWidget(self.report)
        self.launch_button = QPushButton(tr("一鍵開啟工具與網址"))
        self.launch_button.clicked.connect(self.launch); layout.addWidget(self.launch_button)
        refresh = QPushButton(tr("重新檢查")); refresh.clicked.connect(self.refresh); layout.addWidget(refresh)
        self.begin = QPushButton(tr("開始專注")); self.begin.clicked.connect(self.accept); layout.addWidget(self.begin)
        cancel = QPushButton(tr("取消")); cancel.clicked.connect(self.reject); layout.addWidget(cancel)
        self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.refresh); self.refresh_timer.start(1000)
        self.refresh()

    def refresh(self):
        profile = self.profile_data
        lines = [f"{tr('方案：')}{profile.name}", ""]
        report = inspect_tools(profile, self.owner.windows)
        ready = True
        for tool in report:
            lines.append(f"{tool['status']}：{tool['executable']}")
            lines.extend(f"{tr('  視窗：')}{title}" for title in tool["titles"])
            if not tool["resolved"] and not tool["titles"]: ready = False
            if not tool["titles"]: ready = False
        if not report:
            allowed = [(exe, title) for _, exe, _, title in self.owner.windows.visible_windows() if not is_blocked(exe, profile)]
            tools = [title for exe, title in allowed if not BrowserBridge.browser_name(exe)]
            browser_count = sum(bool(BrowserBridge.browser_name(exe)) for exe, _ in allowed)
            lines.append(tr("其他允許應用程式：") + ("、".join(tools) if tools else tr("無")))
            if browser_count:
                lines.append(f"{tr('瀏覽器已開啟（')}{browser_count}{tr(' 個視窗）；這不表示所有分頁都被允許。')}")
            if not allowed: lines.append(tr("尚未找到工作視窗，請先開啟工具或瀏覽器。"))
            ready = bool(allowed)
        if profile.urls:
            path = resolve_executable(profile.browser_executable, self.owner.windows.visible_windows())
            lines.append(tr("網址瀏覽器：") + ("Google Chrome" if BrowserBridge.browser_name(profile.browser_executable) == "chrome" else "Microsoft Edge") if path else tr("找不到網址瀏覽器"))
            ready = ready and bool(path)
            lines.append(f"{tr('\n實際允許網址（')}{len(profile.urls)}{tr(' 個）：')}")
            lines.extend(profile.urls)
            if not profile.website_lock:
                lines.append(tr("\n網址限制尚未啟用：請返回編輯方案，勾選「僅允許以下網址」後再開始。"))
                ready = False
        if profile.website_lock:
            linked = self.owner.bridge.ready(profile.browser_executable)
            lines.append(tr("\n網站擴充功能：") + (tr("已連線，開始後只放行上列網址") if linked else tr("未連線，請確認擴充功能已啟用")))
            ready = ready and linked
        if any(not tool["titles"] for tool in report):
            lines.append(tr("\n工具已啟動但尚無視窗，請等待或移除不必要的啟動項目。"))
        self.report.setPlainText("\n".join(lines)); self.begin.setEnabled(ready)

    def launch(self):
        errors = launch_missing(self.profile_data, self.owner.windows)
        if errors: QMessageBox.warning(self, tr("無法開啟部分工具"), "\n".join(errors))
        self.refresh()


class EmergencyDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("緊急解鎖"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("需要處理重要工作時，請輸入「緊急解鎖」。\n等待 10 秒後可結束此次專注。")))
        self.text = QLineEdit(); layout.addWidget(self.text)
        self.confirm = QPushButton(); self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.accept); layout.addWidget(self.confirm)
        cancel = QPushButton(tr("繼續專注")); cancel.clicked.connect(self.reject); layout.addWidget(cancel)
        self.timer = Timer(); self.timer.start(10)
        self.ticker = QTimer(self); self.ticker.timeout.connect(self.tick); self.ticker.start(100)
        self.text.textChanged.connect(self.tick); self.tick()

    def tick(self):
        remaining = math.ceil(self.timer.remaining)
        self.confirm.setText(f"{tr('等待 ')}{remaining}{tr(' 秒')}" if remaining else tr("確認緊急解鎖"))
        self.confirm.setEnabled(remaining == 0 and self.text.text().strip() == tr("緊急解鎖"))


class FocusWindow(LearningFlow, QWidget):
    def __init__(self, storage=None):
        super().__init__()
        self.storage = storage if storage is not None else Storage(); self.settings = self.storage.load()
        set_language(self.settings.get("language", "zh_TW"))
        self.bridge = BrowserBridge(self.storage.root)
        self.bridge.publish(force=True)
        self.windows = Windows(); self.timer = Timer()
        self.init_learning()
        self.active = None; self.last_allowed = None; self.drag_offset = None; self.exiting = False
        self.guard = DesktopGuard(self)
        self.unlock_open = False
        self.emergency_dialog = None
        self.session_ui = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Focus Lock")
        self.setWindowOpacity(self.settings["opacity"] / 100)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel(tr("FOCUS LOCK  0.7 DEV · 雙語版")); header.addWidget(title)
        header.addStretch()
        self.language_choice = QComboBox(); self.language_choice.addItem("繁體中文", "zh_TW"); self.language_choice.addItem("English", "en")
        self.language_choice.setCurrentIndex(1 if self.settings.get("language") == "en" else 0)
        self.language_choice.currentIndexChanged.connect(self.choose_language); header.addWidget(self.language_choice)
        self.close_button = QPushButton("×"); self.close_button.setFixedWidth(36)
        self.close_button.setToolTip(tr("關閉 Focus Lock"))
        self.close_button.setAccessibleName(tr("關閉 Focus Lock"))
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button); layout.addLayout(header)
        self.time_label = QLabel("25:00"); self.time_label.setObjectName("time"); layout.addWidget(self.time_label)
        self.status = QLabel(tr("待機 · 封鎖未啟用")); layout.addWidget(self.status)
        self.profiles = QComboBox(); layout.addWidget(self.profiles); self.refresh_profiles()
        self.profile_hint = QLabel(); self.profile_hint.setWordWrap(True); self.profile_hint.setMaximumWidth(550)
        layout.addWidget(self.profile_hint)
        self.profiles.currentIndexChanged.connect(self.preview)
        row = QHBoxLayout()
        self.start_button = QPushButton(tr("開始")); self.start_button.clicked.connect(self.start)
        self.pause_button = QPushButton(tr("暫停")); self.pause_button.clicked.connect(self.pause)
        self.stop_button = QPushButton(tr("結束")); self.stop_button.clicked.connect(self.stop)
        self.unlock_button = QPushButton(tr("緊急解鎖")); self.unlock_button.clicked.connect(self.unlock)
        for button in (self.start_button, self.pause_button, self.stop_button, self.unlock_button): row.addWidget(button)
        layout.addLayout(row)
        self.advanced_toggle = QPushButton(tr("方案管理與回想設定 ▾")); self.advanced_toggle.setCheckable(True)
        layout.addWidget(self.advanced_toggle)
        self.advanced_panel = QWidget(); advanced = QVBoxLayout(self.advanced_panel); advanced.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.advanced_panel); self.advanced_panel.hide()
        self.advanced_toggle.toggled.connect(self.advanced_panel.setVisible)
        row = QHBoxLayout()
        self.edit_button = QPushButton(tr("編輯方案")); self.edit_button.clicked.connect(self.edit_profile)
        self.new_button = QPushButton(tr("新增方案")); self.new_button.clicked.connect(lambda: self.edit_profile(True))
        appearance = QPushButton(tr("外觀／設定")); appearance.clicked.connect(self.appearance)
        for button in (self.edit_button, self.new_button, appearance): row.addWidget(button)
        advanced.addLayout(row)
        row = QHBoxLayout()
        self.copy_button = QPushButton(tr("複製方案")); self.copy_button.clicked.connect(self.copy_profile)
        self.delete_button = QPushButton(tr("刪除方案")); self.delete_button.clicked.connect(self.delete_profile)
        self.check_button = QPushButton(tr("工具檢查／一鍵開啟")); self.check_button.clicked.connect(self.check_tools)
        for button in (self.copy_button, self.delete_button, self.check_button): row.addWidget(button)
        advanced.addLayout(row)
        self.learning_button = QPushButton(tr("學習任務／AI 拆解／成果日曆"))
        self.learning_button.clicked.connect(self.show_learning); layout.addWidget(self.learning_button)
        self.recall_checkbox = QCheckBox(tr("回想檢查模式：開始前訂目標，完成回想才能開始下一段"))
        self.recall_checkbox.setChecked(self.settings.get("recall_mode", False))
        self.recall_checkbox.toggled.connect(lambda value: (self.settings.update(recall_mode=value), self.save()))
        advanced.addWidget(self.recall_checkbox)
        tray_button = QPushButton(tr("縮到系統匣（保留提醒）")); tray_button.clicked.connect(self.hide); layout.addWidget(tray_button)
        self.resize(570, 245)
        screen = self.screen().availableGeometry()
        position = self.settings.get("position")
        if position and any(s.availableGeometry().contains(position[0], position[1]) for s in self.screen().virtualSiblings()):
            self.move(*position)
        else:
            self.move(screen.center().x() - self.width() // 2, screen.top())
        pixmap = QPixmap(64, 64); pixmap.fill(QColor("#171c29"))
        painter = QPainter(pixmap); painter.setPen(QColor("#91e6c4")); painter.drawEllipse(8, 8, 48, 48)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "FL"); painter.end()
        self.setWindowIcon(QIcon(pixmap))
        self.tray = QSystemTrayIcon(QIcon(pixmap), self)
        menu = QMenu(self)
        for name, callback in [(tr("顯示 Focus Lock"), self.show_panel), (tr("學習任務與成果日曆"), self.show_learning), (tr("緊急解鎖"), self.unlock), (tr("退出"), self.quit)]:
            action = QAction(name, self); action.triggered.connect(callback); menu.addAction(action)
        self.tray.setContextMenu(menu); self.tray.setToolTip("Focus Lock")
        self.tray.activated.connect(lambda reason: self.show_panel() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()
        self.compact = CompactTimer(self)
        self.ticker = QTimer(self); self.ticker.timeout.connect(self.tick); self.ticker.start(100)
        self.preview(); self.update_controls()

    def save(self):
        try:
            self.storage.save(self.settings)
        except OSError as exc:
            QMessageBox.warning(self, tr("無法儲存"), str(exc))

    def choose_language(self):
        self.settings["language"] = self.language_choice.currentData(); self.save()
        QMessageBox.information(self, "Language / 語言", "Language saved. Restart Focus Lock to apply.\n語言已儲存，重新啟動 Focus Lock 後套用。")

    def refresh_profiles(self):
        self.profiles.clear()
        self.profiles.addItems([p["name"] for p in self.settings["profiles"]])

    def selected(self):
        return Profile(**self.settings["profiles"][self.profiles.currentIndex()])

    def preview(self):
        if self.timer.phase == "idle" and self.profiles.currentIndex() >= 0:
            self.time_label.setText(f"{self.selected().focus_minutes:02d}:00")
            self.profile_hint.setText(self.selected().description)

    def edit_profile(self, new=False):
        if self.timer.phase != "idle": return
        index = self.profiles.currentIndex()
        dialog = ProfileDialog(Profile() if new else self.selected(), self.windows, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if new:
                self.settings["profiles"].append(dialog.profile().to_dict()); index = len(self.settings["profiles"]) - 1
            else:
                self.settings["profiles"][index] = dialog.profile().to_dict()
            self.save(); self.refresh_profiles(); self.profiles.setCurrentIndex(index); self.preview()

    def copy_profile(self):
        if self.timer.phase != "idle": return
        profile = copy.deepcopy(self.settings["profiles"][self.profiles.currentIndex()])
        names = {item["name"] for item in self.settings["profiles"]}
        base = profile["name"] + tr("（副本）")
        name = base; number = 2
        while name in names:
            name = f"{base} {number}"; number += 1
        profile["name"] = name
        self.settings["profiles"].append(profile)
        self.save(); self.refresh_profiles(); self.profiles.setCurrentIndex(len(self.settings["profiles"]) - 1)

    def delete_profile(self):
        if self.timer.phase != "idle": return
        if len(self.settings["profiles"]) == 1:
            QMessageBox.information(self, tr("方案"), tr("請至少保留一個方案；可先新增其他方案。"))
            return
        index = self.profiles.currentIndex()
        if QMessageBox.question(self, tr("刪除方案"), f"{tr('刪除「')}{self.selected().name}」？") != QMessageBox.StandardButton.Yes: return
        self.settings["profiles"].pop(index)
        self.save(); self.refresh_profiles(); self.profiles.setCurrentIndex(min(index, len(self.settings["profiles"]) - 1)); self.preview()

    def check_tools(self):
        if self.timer.phase == "idle":
            if self.selected().policy == "away":
                QMessageBox.information(self, tr("離開筆電模式"), tr("此模式不需要啟動工具或瀏覽器，按開始並確認即可。"))
                return
            dialog = PreflightDialog(self.selected(), self)
            dialog.begin.setText(tr("檢查完成"))
            dialog.exec()
            dialog.refresh_timer.stop(); dialog.deleteLater()

    def start(self):
        if self.timer.phase == "focus": return
        if not self.recall_gate(): return
        if self.outcome_dialog and self.outcome_dialog.isVisible():
            self.outcome_dialog.raise_(); self.outcome_dialog.activateWindow()
            return
        profile = self.selected()
        if self.pending_learning:
            profile.focus_minutes = self.pending_learning["minutes"]
        if profile.policy == "away":
            text = f"{tr('接下來 ')}{profile.focus_minutes}{tr(' 分鐘，各螢幕會顯示倒數遮罩，不能使用一般工作視窗。\n')}"
            text += tr("嚴格模式只有緊急解鎖可提前離開。") if profile.strict else tr("一般模式可以暫停或提前結束。")
            text += tr("\n不會關閉背景程式或未儲存文件。確定開始？")
            if QMessageBox.question(self, tr("開始離開筆電模式"), text) != QMessageBox.StandardButton.Yes: return
            self.active = profile; self.last_allowed = None
            self.bridge.publish(force=True)
            self.timer.start(profile.focus_minutes * 60); self.begin_learning_record(); self.update_controls(); self.tick()
            return
        if profile.policy == "allowlist" and not profile.allowed:
            QMessageBox.information(self, tr("先設定方案"), tr("請編輯方案，加入這次學習允許的應用程式。"))
            return
        if profile.strict and QMessageBox.question(self, tr("開始嚴格模式"), tr("專注期間隱藏一般暫停與結束按鈕。\n仍可使用緊急解鎖。確定開始？")) != QMessageBox.StandardButton.Yes:
            return
        dialog = PreflightDialog(profile, self)
        result = dialog.exec()
        dialog.refresh_timer.stop(); dialog.refresh()
        ready = dialog.begin.isEnabled(); dialog.deleteLater()
        if result != QDialog.DialogCode.Accepted or not ready: return
        if profile.website_lock and not self.bridge.ready(profile.browser_executable):
            QMessageBox.warning(self, tr("網站限制"), tr("擴充功能已斷線，請重新檢查。"))
            return
        if not self.prepare_intention(): return
        self.active = profile; self.last_allowed = None
        self.bridge.publish(profile, active=True, force=True)
        self.timer.start(profile.focus_minutes * 60); self.begin_learning_record(); self.update_controls(); self.tick()

    def update_controls(self):
        idle = self.timer.phase == "idle"
        strict = not idle and self.timer.phase == "focus" and self.active.strict
        self.start_button.setVisible(idle)
        self.learning_button.setEnabled(self.timer.phase != "focus")
        self.pause_button.setVisible(not idle and not strict)
        self.stop_button.setVisible(not idle and not strict)
        self.unlock_button.setVisible(not idle)
        self.pause_button.setText(tr("繼續") if self.timer.paused else tr("暫停"))
        for control in (self.profiles, self.edit_button, self.new_button, self.copy_button, self.delete_button, self.check_button): control.setEnabled(idle)
        if idle:
            self.compact.hide_all()
            if self.session_ui:
                self.session_ui = False
                self.show(); self.raise_()
        else:
            if not self.session_ui:
                self.session_ui = True
                self.hide()
                self.compact.show_timer()
            self.compact.sync()

    def pause(self):
        if self.timer.phase == "idle" or (self.timer.phase == "focus" and self.active.strict): return
        self.timer.resume() if self.timer.paused else self.timer.pause()
        if self.timer.paused: self.hide_guards()
        self.bridge.publish(self.active, active=self.timer.phase == "focus" and not self.timer.paused, force=True)
        self.update_controls(); self.tick()

    def stop(self):
        if self.timer.phase == "focus" and self.active and self.active.strict: return
        self.finish()

    def finish(self):
        record = self.end_learning_record("early") if self.timer.phase == "focus" else None
        self.bridge.publish(force=True)
        self.hide_guards()
        self.timer.stop(); self.active = None; self.last_allowed = None
        self.status.setText(tr("待機 · 封鎖未啟用")); self.update_controls(); self.preview()
        if record: self.show_outcome(record)

    def unlock(self):
        if self.timer.phase == "idle": return
        if self.unlock_open: return
        self.unlock_open = True
        dialog = EmergencyDialog(self)
        self.emergency_dialog = dialog
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self.unlock_open = False
            self.emergency_dialog = None
        if accepted:
            try:
                if self.active is not None:
                    self.storage.log_unlock(self.active.name)
            except OSError:
                pass  # Disk failure must never prevent emergency access.
            self.finish()

    def guard_unlock(self):
        # Keep the guard beneath a modal emergency dialog, without any focus stealing.
        self.unlock()

    def blocked(self, executable):
        if self.active is not None and self.active.website_lock and BrowserBridge.browser_name(executable):
            if not self.bridge.ready(executable, require_applied=True):
                return True
        return self.active is not None and is_blocked(executable, self.active)

    def hide_guards(self):
        self.guard.hide()

    def tick(self):
        self.tick_learning()
        if self.timer.phase == "idle": return
        remaining = math.ceil(self.timer.remaining)
        self.time_label.setText(f"{remaining // 60:02d}:{remaining % 60:02d}")
        self.compact.sync()
        self.guard.update_time(self.time_label.text())
        if remaining == 0:
            self.bridge.publish(force=True)
            self.hide_guards()
            if self.active.policy == "away":
                self.end_learning_record("completed")
                self.tray.showMessage("Focus Lock", tr("離開筆電倒數完成，已解除遮罩。"))
                self.finish()
            elif self.timer.phase == "focus":
                record = self.end_learning_record("completed")
                self.timer.start(self.active.break_minutes * 60, "break")
                self.tray.showMessage("Focus Lock", tr("專注完成！開始休息。"))
                self.compact.show(); self.update_controls()
                self.show_outcome(record)
            else:
                self.tray.showMessage("Focus Lock", tr("休息結束，可以開始下一次專注。"))
                self.finish()
            return
        enforcing = self.timer.phase == "focus" and not self.timer.paused
        self.bridge.publish(self.active, active=enforcing)
        if enforcing and self.guard.visible and not self.blocked(self.guard.executable):
            self.hide_guards()
        if not enforcing:
            self.hide_guards()
        mode = tr("嚴格") if self.active.strict else tr("一般")
        state = tr("已暫停 · 封鎖未啟用") if self.timer.paused else ((tr("離開筆電 · 全螢幕遮罩") if self.active.policy == "away" else tr("專注 · 封鎖啟用")) if enforcing else tr("休息 · 封鎖未啟用"))
        context = self.learning_context
        step_text = ""
        if context and context["plan"]:
            plan = context["plan"]; step = context["step"]
            step_text = f" · {plan['steps'][step]['name']} {step+1}/{len(plan['steps'])}"
        self.status.setText(f"{self.active.name}{step_text} · {mode} · {state}")
        self.compact.sync()
        self.tray.setToolTip(f"Focus Lock {self.time_label.text()} · {state}")
        if enforcing:
            if self.active.policy == "away":
                self.guard.show("", activate=not self.unlock_open, away=True)
                if self.unlock_open and self.emergency_dialog is not None:
                    self.emergency_dialog.raise_(); self.emergency_dialog.activateWindow()
                return
            foreground = self.windows.foreground()
            if foreground:
                hwnd, executable, _ = foreground
                if self.blocked(executable):
                    self.status.setText(f"{tr('已遮罩封鎖：')}{Path(executable).name}")
                    self.guard.show(executable, activate=not self.unlock_open)
                    if self.unlock_open and self.emergency_dialog is not None:
                        self.emergency_dialog.raise_()
                        self.emergency_dialog.activateWindow()
                else:
                    self.hide_guards()
                    self.last_allowed = hwnd

    def appearance(self):
        dialog = QDialog(self); dialog.setWindowTitle(tr("外觀與設定"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr("深色模式 · 透明度（35%–100%）")))
        slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(35, 100); slider.setValue(self.settings["opacity"])
        slider.valueChanged.connect(lambda value: self.setWindowOpacity(value / 100)); layout.addWidget(slider)
        layout.addWidget(QLabel(f"{tr('資料位置：')}{self.storage.root}{tr('\n學習紀錄每 5 秒保存；重啟後保留中斷紀錄，不自動恢復封鎖。\n提醒需要程式在執行；電腦喚醒後提示到期任務。')}"))
        button = QPushButton(tr("儲存並關閉"))
        button.clicked.connect(dialog.accept); layout.addWidget(button)
        dialog.exec()
        self.settings["opacity"] = slider.value(); self.save()

    def show_panel(self):
        if self.timer.phase != "idle":
            self.compact.show(); self.compact.raise_(); self.compact.expand()
        else:
            self.show(); self.raise_()

    def quit(self):
        self.close()

    def prepare_exit(self):
        if self.exiting:
            return True
        if self.timer.phase == "focus" and self.active.strict:
            self.unlock()
            if self.timer.phase != "idle": return False
        elif self.timer.phase != "idle":
            if QMessageBox.question(self, tr("退出"), tr("結束目前計時並退出？")) != QMessageBox.StandardButton.Yes: return False
        self.save()
        if self.timer.phase == "focus": self.end_learning_record("interrupted")
        self.exiting = True
        self.bridge.publish(force=True)
        self.compact.hide_all()
        self.hide_guards()
        self.timer.stop()
        self.ticker.stop()
        self.tray.hide()
        return True

    def exit_application(self):
        from PySide6.QtWidgets import QApplication
        # Finish this close event before asking QApplication to close all windows.
        QTimer.singleShot(0, QApplication.instance().quit)

    def closeEvent(self, event):
        if self.prepare_exit():
            event.accept()
            self.exit_application()
            return
        event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        if self.drag_offset is not None:
            self.drag_offset = None
            self.settings["position"] = [self.x(), self.y()]; self.save()
