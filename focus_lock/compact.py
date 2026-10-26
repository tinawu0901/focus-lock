"""Small session timer with controls revealed only on hover."""
from .i18n import tr
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QProgressBar


class HoverControls(QWidget):
    def __init__(self, timer):
        super().__init__(timer, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.timer_widget = timer
        self.setStyleSheet("QWidget {background:#171c29; color:#ecf0ff; font-family:'Segoe UI'; font-size:13px;}"
                           "QPushButton {background:#303b54; padding:8px; border:1px solid #52617f; border-radius:5px;}")
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        owner = timer.owner
        self.pause_button = QPushButton(tr("暫停")); self.pause_button.clicked.connect(owner.pause)
        self.stop_button = QPushButton(tr("結束")); self.stop_button.clicked.connect(owner.stop)
        self.unlock_button = QPushButton(tr("緊急解鎖")); self.unlock_button.clicked.connect(owner.unlock)
        for button in (self.pause_button, self.stop_button, self.unlock_button):
            row.addWidget(button)
        layout.addLayout(row)
        close = QPushButton(tr("退出 Focus Lock")); close.clicked.connect(owner.quit); layout.addWidget(close)

    def enterEvent(self, event):
        self.timer_widget.collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.timer_widget.schedule_collapse()
        super().leaveEvent(event)

    def closeEvent(self, event):
        event.accept()
        self.hide()


class CompactTimer(QWidget):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.setWindowTitle(tr("Focus Lock · 精簡計時器"))
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("QWidget {background:#171c29;} QLabel {color:#91e6c4; font-family:'Segoe UI'; font-size:30px; font-weight:bold;}")
        self.setFixedSize(140, 48)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 2, 8, 2); layout.setSpacing(0)
        self.step_label = QLabel(); self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setStyleSheet("font-size:10px; color:#c2cbe0;")
        self.step_label.hide(); layout.addWidget(self.step_label)
        self.time_label = QLabel("25:00"); self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.time_label)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000); self.progress.setTextVisible(False); self.progress.setFixedHeight(3)
        self.progress.setStyleSheet("QProgressBar {border:0; background:#303b54;} QProgressBar::chunk {background:#91e6c4;}")
        layout.addWidget(self.progress)
        self.controls = HoverControls(self)
        self.controls.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.collapse_timer = QTimer(self); self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_if_outside)
        self.drag_offset = None

    def show_timer(self):
        screen = self.owner.screen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 8)
        self.setWindowOpacity(self.owner.settings["opacity"] / 100)
        self.sync()
        self.show(); self.raise_()

    def sync(self):
        self.time_label.setText(self.owner.time_label.text())
        context = self.owner.learning_context
        has_steps = bool(context and context["plan"])
        self.step_label.setVisible(has_steps)
        self.time_label.setStyleSheet("font-size:24px;" if has_steps else "font-size:30px;")
        if has_steps:
            plan = context["plan"]; step = context["step"]
            self.step_label.setText(f"{plan['steps'][step]['name'][:10]} {step+1}/{len(plan['steps'])}")
        total = self.owner.focus_seconds if self.owner.timer.phase == "focus" else ((self.owner.active.break_minutes * 60) if self.owner.active else 1)
        self.progress.setValue(max(0, min(1000, round(1000 * (1 - self.owner.timer.remaining / max(1, total))))))
        self.setToolTip(self.owner.status.text())
        self.controls.status.setText(self.owner.status.text())
        active = self.owner.active
        strict = active is not None and active.strict and self.owner.timer.phase == "focus"
        self.controls.pause_button.setVisible(not strict)
        self.controls.stop_button.setVisible(not strict)
        self.controls.pause_button.setText(tr("繼續") if self.owner.timer.paused else tr("暫停"))
        if self.controls.isVisible():
            self.position_controls()

    def position_controls(self):
        self.controls.adjustSize()
        screen = self.screen().availableGeometry()
        x = self.x() + (self.width() - self.controls.width()) // 2
        x = max(screen.left(), min(x, screen.right() - self.controls.width() + 1))
        y = self.y() + self.height() + 4
        if y + self.controls.height() > screen.bottom() + 1:
            y = max(screen.top(), self.y() - self.controls.height() - 4)
        self.controls.move(x, y)

    def expand(self):
        if self.owner.timer.phase == "idle":
            return
        self.collapse_timer.stop()
        self.sync(); self.position_controls()
        self.controls.show(); self.controls.raise_()

    def hide_all(self):
        self.collapse_timer.stop()
        self.controls.hide(); self.hide()

    def schedule_collapse(self):
        self.collapse_timer.start(350)

    def collapse_if_outside(self):
        point = QCursor.pos()
        if not self.frameGeometry().contains(point) and not self.controls.frameGeometry().contains(point):
            self.controls.hide()

    def enterEvent(self, event):
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.schedule_collapse()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            self.position_controls()

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

    def closeEvent(self, event):
        if self.owner.exiting:
            event.accept()
        else:
            event.ignore()
            self.owner.quit()
