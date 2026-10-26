"""Generate UI previews without interacting with other applications."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QTabWidget
from PySide6.QtGui import QFontDatabase
from focus_lock.storage import Storage
from focus_lock.ui import FocusWindow, ProfileDialog
from focus_lock.core import Profile
from focus_lock.selectors import CheckListDialog


def main():
    app = QApplication([])
    for filename in ("segoeui.ttf", "msjh.ttc"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    english = "--english" in sys.argv
    def demo(zh, en): return en if english else zh
    output = Path(__file__).parent / "previews" / ("en" if english else "zh_TW")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
        storage = Storage(root)
        settings = storage.load(); settings["language"] = "en" if english else "zh_TW"
        if english:
            for profile, name in zip(settings["profiles"], ["IELTS Listening", "Robotics", "IELTS Speaking", "Away 25 minutes"]):
                profile["name"] = name; profile["description"] = "Choose the apps you need, then start a focus session."
        storage.save(settings)
        with patch("focus_lock.ui.Storage", return_value=storage):
            window = FocusWindow()
        window.ticker.stop()
        window.show(); app.processEvents()
        window.grab().save(str(output / "timer.png"))
        dialog = ProfileDialog(Profile(name="雅思聽力", allowed=[r"C:\Study\Listening.exe"],
            launch_tools=[{"executable": r"C:\Study\Listening.exe", "arguments": ["--disable-gpu"]}],
            urls=["https://chatgpt.com/", "https://docs.ros.org/en/"], website_lock=True,
            browser_executable=r"C:\Program Files\Google\Chrome\Application\chrome.exe"), window.windows, window)
        dialog.show(); app.processEvents()
        dialog.grab().save(str(output / "profile.png"))
        tabs = dialog.findChild(QTabWidget)
        tabs.setCurrentIndex(1); app.processEvents()
        dialog.grab().save(str(output / "launch-tools.png"))
        tabs.setCurrentIndex(2); app.processEvents()
        dialog.grab().save(str(output / "websites.png"))
        apps = CheckListDialog("勾選允許的應用程式", ["應用程式", "目前工作視窗"], lambda: (
            [(["Code", "Robotics 專案 — Visual Studio Code"], r"C:\Apps\Code.exe"),
             (["VirtualBoxVM", "Ubuntu ROS 2 — Oracle VirtualBox"], r"C:\Apps\VirtualBoxVM.exe"),
             (["WINWORD", "雅思口說筆記 — Word"], r"C:\Apps\WINWORD.EXE")], "找到 3 個有工作視窗的應用程式；勾選後加入方案。"), window)
        from PySide6.QtCore import Qt
        apps.table.item(0, 0).setCheckState(Qt.CheckState.Checked); apps.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        apps.show(); app.processEvents(); apps.grab().save(str(output / "app-picker.png")); apps.reject()
        sites = CheckListDialog("勾選目前開啟的網址", ["分頁標題", "網址"], lambda: (
            [(["ChatGPT", "https://chatgpt.com/"], "https://chatgpt.com/"),
             (["ROS 2 Documentation", "https://docs.ros.org/en/humble/"], "https://docs.ros.org/en/humble/")],
            "找到 2 個分頁；選擇允許整站或指定路徑。"), window)
        sites.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        sites.show(); app.processEvents(); sites.grab().save(str(output / "tab-picker.png")); sites.reject()
        dialog.hide()
        window.active = Profile(name="Robotics", allowed=["Code.exe"])
        window.timer.start(1500)
        window.status.setText("Robotics · 一般 · 專注 · 封鎖啟用")
        window.update_controls()
        app.processEvents()
        window.compact.controls.hide()
        window.compact.grab().save(str(output / "compact.png"))
        window.compact.expand()
        app.processEvents()
        window.compact.controls.grab().save(str(output / "hover-controls.png"))
        window.compact.hide_all()
        window.guard.show("chrome.exe")
        app.processEvents()
        guard = window.guard.windows[0]
        guard.resize(1100, 680)
        app.processEvents()
        guard.grab().save(str(output / "guard.png"))
        window.hide_guards()
        from focus_lock.presets import away_profile
        window.active = away_profile(); window.guard.show("", away=True)
        app.processEvents()
        away = window.guard.windows[0]; away.resize(1100, 680); app.processEvents()
        away.grab().save(str(output / "away.png"))
        window.hide_guards(); window.tray.hide(); window.hide()
        from focus_lock.learning_ui import PlanDialog, LearningDialog, OutcomeDialog
        from focus_lock.learning import validate_plan
        window.timer.stop(); window.active = None
        window.settings["profiles"].append(Profile(name=demo("雅思作文 Task1", "IELTS Writing Task 1")).to_dict()); window.refresh_profiles()
        window.profiles.setCurrentIndex(window.profiles.count()-1)
        plan = window.learning.put_plan(validate_plan({"name": "Writing Task 1", "profile": window.selected().name,
            "steps": [{"name": demo("複習", "Review"), "minutes": 30, "goal": demo("整理架構與常用句", "Review structure and useful phrases")},
                      {"name": demo("寫作", "Write"), "minutes": 30, "goal": demo("完成一篇初稿", "Complete a first draft")},
                      {"name": demo("檢討", "Reflect"), "minutes": 30, "goal": demo("檢查 overview 與時態", "Check the overview and verb tenses")}], "daily_time": "08:00"}, [window.selected().name]))
        editor = PlanDialog(window, plan); editor.show(); app.processEvents()
        editor.grab().save(str(output / "learning-plan.png")); editor.hide()
        window.learning.begin(window.selected(), 1800, plan, 0)
        record = window.learning.end(1800, "completed"); record["note"] = demo("整理了折線圖架構與比較句", "Reviewed line-chart structure and comparisons."); window.learning.save()
        result = OutcomeDialog(window, record, plan); result.action.setCurrentIndex(result.action.findData("next"))
        result.show(); app.processEvents(); result.grab().save(str(output / "learning-outcome.png")); result.hide()
        from focus_lock.recall import IntentionDialog
        intention = IntentionDialog(window, demo("ROS 2 的 topic 如何讓節點交換資料？", "How do ROS 2 topics let nodes exchange data?"), demo("能自己解釋，並跑出 publisher／subscriber", "Explain it and run a publisher / subscriber example."))
        intention.show(); app.processEvents(); intention.grab().save(str(output / "recall-intention.png")); intention.hide()
        recall_record = {**record, "recall_required": True, "reflection_done": False,
            "intention": {"question": demo("這一節如何安排 overview？", "How should I structure an overview?"), "criterion": demo("能不看範文寫出兩句主要趨勢", "Write two key trends without looking at a model answer.")}}
        recall = OutcomeDialog(window, recall_record, plan)
        recall.recall_summary.setPlainText(demo("Overview 回答整張圖最重要的趨勢，不逐項抄寫數字。", "An overview explains the main trends, rather than listing every number."))
        recall.recall_example.setPlainText(demo("先描述整體上升，再指出增幅最大的類別。", "Describe the overall rise, then identify the category with the largest increase."))
        recall.recall_stuck.setText(demo("遇到趨勢交叉時，應該優先比較什麼？", "Which comparison matters most when two trends cross?"))
        recall.action.setCurrentIndex(recall.action.findData("review"))
        recall.show(); app.processEvents(); recall.grab().save(str(output / "recall-outcome.png")); recall.hide()
        from datetime import datetime
        today = datetime.now().astimezone()
        listening = window.learning.put_plan(validate_plan({"name": demo("雅思聽力", "IELTS Listening"), "profile": window.selected().name,
            "steps": [{"name": demo("做題", "Practice"), "minutes": 10, "goal": demo("完成一篇聽力", "Complete a listening exercise")}, {"name": demo("檢討", "Review"), "minutes": 15}], "daily_time": "08:00"}, [window.selected().name]))
        for hour, title, task, note in ((9, "雅思聽力", "錯題檢討", "整理 5 個沒聽懂的句子"), (11, "Robotics", "ROS 2 練習", "完成 publisher 與 subscriber"), (14, "Writing Task 1", "限時寫作", "完成折線圖初稿")):
            window.learning.begin(window.selected(), 1800)
            sample = window.learning.end(1800, "completed")
            if english:
                title, task, note = {9: ("IELTS Listening", "Review", "Reviewed five unclear sentences."), 11: ("Robotics", "ROS 2 practice", "Built a publisher and subscriber."), 14: ("Writing Task 1", "Timed writing", "Completed a first draft.")}[hour]
            sample.update(started=today.replace(hour=hour, minute=0).isoformat(), task=title, step=task, note=note)
        for hour, task in ((18, "修改作文第二稿"), (20, "整理 overview 筆記")):
            if english: task = "Revise the second draft" if hour == 18 else "Review overview notes"
            window.learning.data["reminders"].append({"id": f"preview-{hour}", "plan_id": plan["id"], "step": 2, "at": today.replace(hour=hour, minute=30).isoformat(), "task": task, "status": "pending", "minutes": 30})
        window.learning.save()
        calendar = LearningDialog(window); calendar.findChild(QTabWidget).setCurrentIndex(1)
        calendar.show(); app.processEvents(); calendar.grab().save(str(output / "learning-calendar.png")); calendar.hide()
        window.active = window.selected(); window.learning_context = {"plan": plan, "step": 1}
        window.focus_seconds = 1800; window.timer.start(1440)
        window.time_label.setText("24:00"); window.compact.sync(); window.compact.show(); app.processEvents()
        window.compact.grab().save(str(output / "learning-compact.png")); window.compact.hide_all()


if __name__ == "__main__":
    main()
