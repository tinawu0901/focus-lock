"""Local learning plans, validated AI drafts, session records and reminders."""
from .i18n import tr
import copy
import json
import uuid
from datetime import datetime, timedelta


def now_iso():
    return datetime.now().astimezone().isoformat()


def validate_plan(data, profiles):
    if not isinstance(data, dict):
        raise ValueError(tr("方案必須是 JSON 物件"))
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError(tr("請輸入 1–100 字的任務名稱"))
    if data.get("profile") not in profiles:
        raise ValueError(tr("請選擇已存在的 Focus Lock 方案；匯入不會修改程式或網址權限"))
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 30:
        raise ValueError(tr("請設定 1–30 個步驟"))
    cleaned = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"].strip() or len(step["name"]) > 100:
            raise ValueError(tr("每個步驟需要 1–100 字的名稱"))
        if type(step.get("minutes")) is not int or not 1 <= step["minutes"] <= 240:
            raise ValueError(tr("步驟時長必須是 1–240 的整數分鐘"))
        goal = step.get("goal", "")
        if not isinstance(goal, str) or len(goal) > 2000:
            raise ValueError(tr("成果目標最多 2000 字"))
        cleaned.append({"name": step["name"].strip(), "minutes": step["minutes"], "goal": goal})
    daily = data.get("daily_time", "")
    if not isinstance(daily, str):
        raise ValueError(tr("每日提醒時間請使用 HH:MM"))
    if daily:
        try:
            parsed = datetime.strptime(daily, "%H:%M")
            if parsed.strftime("%H:%M") != daily: raise ValueError()
        except ValueError:
            raise ValueError(tr("每日提醒時間請使用 HH:MM，例如 08:00")) from None
    return {"name": name.strip(), "profile": data["profile"], "steps": cleaned, "daily_time": daily}


def parse_plan(text, profiles):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if len(text) > 100000: raise ValueError(tr("匯入內容過長"))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(tr("請貼上完整 JSON 方案，不含其他說明")) from None
    return validate_plan(data, profiles)


class LearningStore:
    def __init__(self, root):
        self.path = root / "learning.json"
        self.warning = ""
        self.read_only = False
        self.data = {"version": 1, "plans": [], "records": [], "reminders": [], "active": None}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict) or loaded.get("version") != 1:
                    raise ValueError(tr("不支援的學習紀錄版本"))
                for key in ("plans", "records", "reminders"):
                    if not isinstance(loaded.get(key), list) or not all(isinstance(x, dict) for x in loaded[key]):
                        raise ValueError(tr("學習紀錄格式錯誤"))
                for plan in loaded["plans"]:
                    validate_plan(plan, [plan.get("profile")])
                    if not isinstance(plan.get("id"), str) or type(plan.get("next_step")) is not int or not 0 <= plan["next_step"] < len(plan["steps"]):
                        raise ValueError(tr("任務識別或步驟無效"))
                records = loaded["records"] + ([loaded["active"]] if loaded.get("active") else [])
                for record in records:
                    if not isinstance(record, dict): raise ValueError(tr("紀錄無效"))
                    for key in ("id", "profile", "task", "step", "started"):
                        if not isinstance(record.get(key), str): raise ValueError(tr("紀錄欄位無效"))
                    if datetime.fromisoformat(record["started"]).tzinfo is None: raise ValueError(tr("紀錄缺少時區"))
                    for key in ("seconds", "planned_seconds"):
                        if type(record.get(key)) not in (int, float) or not 0 <= record[key] <= 14400:
                            raise ValueError(tr("紀錄時長無效"))
                    if type(record.get("step_index")) is not int: raise ValueError(tr("步驟編號無效"))
                for reminder in loaded["reminders"]:
                    if not isinstance(reminder.get("at"), str) or datetime.fromisoformat(reminder["at"]).tzinfo is None:
                        raise ValueError(tr("提醒時間無效"))
                    if reminder.get("status") not in ("pending", "started", "skipped", "deleted") or type(reminder.get("step")) is not int:
                        raise ValueError(tr("提醒狀態無效"))
                self.data.update(loaded)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self.warning = f"{tr('學習紀錄讀取失敗，原檔保留：')}{exc}"
                self.read_only = True
        # A previous process can leave a checkpoint; never count offline time.
        if self.data["active"]:
            record = self.data["active"]
            record.update(status="interrupted", ended=record.get("checkpoint", now_iso()))
            self.data["records"].append(record)
            self.data["active"] = None
            try: self.save()
            except OSError as exc:
                self.warning = f"{tr('中斷紀錄無法儲存，原檔保留：')}{exc}"
                self.read_only = True

    def save(self):
        if self.read_only: raise OSError(self.warning)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def put_plan(self, plan, plan_id=None):
        plan = copy.deepcopy(plan)
        plan["id"] = plan_id or uuid.uuid4().hex
        old = next((p for p in self.data["plans"] if p["id"] == plan["id"]), None)
        plan["next_step"] = min(old.get("next_step", 0), len(plan["steps"]) - 1) if old else 0
        plan["last_daily"] = old.get("last_daily", "") if old else ""
        self.data["plans"] = [p for p in self.data["plans"] if p["id"] != plan["id"]] + [plan]
        self.save()
        return plan

    def plan(self, plan_id):
        return next((p for p in self.data["plans"] if p["id"] == plan_id), None)

    def begin(self, profile, seconds, plan=None, step=0):
        record = {"id": uuid.uuid4().hex, "profile": profile.name, "away": profile.policy == "away",
                  "started": now_iso(), "seconds": 0.0, "planned_seconds": seconds,
                  "plan_id": plan["id"] if plan else None, "task": plan["name"] if plan else profile.name,
                  "step": plan["steps"][step]["name"] if plan else tr("專注"), "step_index": step,
                  "note": "", "next_task": "", "task_done": False}
        self.data["active"] = record
        self.save()
        return record

    def checkpoint(self, seconds):
        if self.data["active"]:
            self.data["active"].update(seconds=max(0, seconds), checkpoint=now_iso())
            self.save()

    def end(self, seconds, status):
        record = self.data["active"]
        if not record: return None
        record.update(seconds=max(0, min(seconds, record["planned_seconds"])), status=status, ended=now_iso())
        self.data["records"].append(record)
        self.data["active"] = None
        self.save()
        return record

    def schedule(self, plan_id, step, at, task="", **extra):
        if at <= datetime.now().astimezone(): raise ValueError(tr("提醒時間已經過了，請選擇未來時間"))
        self.data["reminders"].append({"id": uuid.uuid4().hex, "plan_id": plan_id, "step": step,
                                       "at": at.isoformat(), "task": task, "status": "pending", **extra})
        self.save()

    def due(self, now=None):
        now = now or datetime.now().astimezone()
        changed = False
        for plan in self.data["plans"]:
            time = plan.get("daily_time", "")
            if time and plan.get("last_daily") != now.date().isoformat() and now.strftime("%H:%M") >= time:
                plan["last_daily"] = now.date().isoformat()
                self.data["reminders"].append({"id": uuid.uuid4().hex, "plan_id": plan["id"], "step": 0,
                    "at": now.replace(hour=int(time[:2]), minute=int(time[3:]), second=0, microsecond=0).isoformat(),
                    "task": plan["steps"][0]["name"], "status": "pending"})
                changed = True
        due = [r for r in self.data["reminders"] if r["status"] == "pending" and datetime.fromisoformat(r["at"]) <= now]
        if changed: self.save()
        return due

    def resolve(self, reminder, action):
        if action == "snooze":
            reminder["at"] = (datetime.now().astimezone() + timedelta(minutes=10)).isoformat()
        else:
            reminder["status"] = action
        self.save()

    def day_records(self, day):
        return [r for r in self.data["records"] if datetime.fromisoformat(r["started"]).astimezone().date().isoformat() == day]

    def day_seconds(self, day):
        return sum(r["seconds"] for r in self.day_records(day) if not r.get("away"))
