"""Checkbox selectors for live application windows and browser tabs."""
from .i18n import tr
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QDialogButtonBox, QAbstractItemView


class CheckListDialog(QDialog):
    def __init__(self, title, headers, loader, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(800, 500)
        self.loader = loader; self.rows = None
        self.layout_box = QVBoxLayout(self)
        self.search = QLineEdit(); self.search.setPlaceholderText(tr("搜尋名稱、視窗標題或網址"))
        self.layout_box.addWidget(self.search)
        self.status = QLabel(); self.status.setWordWrap(True); self.layout_box.addWidget(self.status)
        self.table = QTableWidget(0, len(headers)); self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260); self.layout_box.addWidget(self.table)
        self.options = QHBoxLayout(); self.layout_box.addLayout(self.options)
        select = QPushButton(tr("勾選顯示項目")); select.clicked.connect(self.select_visible)
        refresh = QPushButton(tr("重新整理")); refresh.clicked.connect(self.refresh)
        self.options.addWidget(select); self.options.addWidget(refresh)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("加入勾選項目"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("取消"))
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        self.layout_box.addWidget(self.buttons)
        self.search.textChanged.connect(self.filter_rows)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000)
        self.refresh()

    def selected(self):
        return [self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(self.table.rowCount())
                if self.table.item(row, 0).checkState() == Qt.CheckState.Checked]

    def refresh(self):
        rows, status = self.loader()
        self.status.setText(status)
        if rows == self.rows: return
        selected = set(self.selected())
        self.rows = rows; self.table.setRowCount(len(rows))
        for row, (columns, value) in enumerate(rows):
            for column, text in enumerate(columns):
                item = QTableWidgetItem(text); item.setToolTip(value)
                if column == 0:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setData(Qt.ItemDataRole.UserRole, value)
                    item.setCheckState(Qt.CheckState.Checked if value in selected else Qt.CheckState.Unchecked)
                self.table.setItem(row, column, item)
        self.filter_rows()

    def filter_rows(self):
        term = self.search.text().casefold()
        for row in range(self.table.rowCount()):
            text = " ".join(self.table.item(row, col).text() for col in range(self.table.columnCount()))
            self.table.setRowHidden(row, term not in text.casefold())

    def select_visible(self):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row): self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

    def done(self, result):
        self.timer.stop()
        super().done(result)
