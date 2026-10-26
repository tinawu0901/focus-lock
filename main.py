import sys
import os
import json
import tempfile
from pathlib import Path
if "--smoke-test" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QTimer, QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox
from focus_lock.ui import FocusWindow
from focus_lock.storage import Storage


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Focus Lock")
    app.setQuitOnLastWindowClosed(False)
    if "--smoke-test" in sys.argv:
        # Explicit diagnostics mode: isolated storage, no focus session, automatic exit.
        index = sys.argv.index("--smoke-test")
        destination = Path(sys.argv[index + 1]).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination) as root:
            window = FocusWindow(storage=Storage(root))
            window.show()
            def complete():
                (destination / "smoke-result.json").write_text(json.dumps({
                    "ok": True, "python": sys.version, "phase": window.timer.phase,
                    "profiles": window.profiles.count(), "timer": window.time_label.text()
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                window.close()
            QTimer.singleShot(500, complete)
            return app.exec()
    storage = Storage()
    instance_lock = QLockFile(str(storage.root / "application.lock"))
    if not instance_lock.tryLock(100):
        QMessageBox.information(None, "Focus Lock 已在執行", "請從系統匣開啟現有 Focus Lock，或先退出舊版再啟動。")
        return 0
    window = FocusWindow(storage=storage)
    window.show()
    if window.storage.warning:
        QMessageBox.warning(window, "設定讀取", window.storage.warning)
    if window.learning.warning:
        QMessageBox.warning(window, "學習紀錄讀取", window.learning.warning)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
