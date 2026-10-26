"""User-authored learning intentions and required retrieval checkpoints."""
from .i18n import tr
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton


def pending_recall(records):
    return next((r for r in records if r.get("recall_required") and not r.get("reflection_done") and not r.get("away")), None)


def validate_reflection(summary, example, stuck, no_stuck):
    if not summary.strip(): raise ValueError(tr("請用自己的話寫下：這一節在回答什麼？"))
    if not example.strip(): raise ValueError(tr("請寫下一個你能解釋的例子、步驟或實作結果。"))
    if not no_stuck and not stuck.strip(): raise ValueError(tr("請寫下卡點，或勾選「目前沒有卡點」。"))
    return {"summary": summary.strip(), "example": example.strip(), "stuck": "目前沒有" if no_stuck else stuck.strip()}


class IntentionDialog(QDialog):
    def __init__(self, owner, question="", criterion=""):
        super().__init__(owner)
        self.setWindowTitle(tr("開始前 · 這段要學會什麼？")); self.resize(520, 280)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("用一句話設定方向。結束後合上教材，用自己的話回想。")); hint.setWordWrap(True); layout.addWidget(hint)
        layout.addWidget(QLabel(tr("這段要弄懂什麼？"))); self.question = QLineEdit(question); layout.addWidget(self.question)
        layout.addWidget(QLabel(tr("做到什麼算完成？"))); self.criterion = QLineEdit(criterion); layout.addWidget(self.criterion)
        self.error = QLabel(); self.error.setStyleSheet("color:#f28b82;"); layout.addWidget(self.error)
        start = QPushButton(tr("確認目標，開始專注")); start.clicked.connect(self.validate); layout.addWidget(start)
        cancel = QPushButton(tr("取消")); cancel.clicked.connect(self.reject); layout.addWidget(cancel)

    def validate(self):
        if not self.question.text().strip() or not self.criterion.text().strip():
            self.error.setText(tr("請填寫本段問題與完成標準。")); return
        self.accept()
