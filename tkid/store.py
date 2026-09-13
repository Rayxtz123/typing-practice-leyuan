# -*- coding: utf-8 -*-
"""配置与进度落盘：
    data/config.json    密码哈希 + 番茄参数 + 每日额度 + 设置
    data/progress.json  练习记录 + 今日额度用量
    data/content.json   家长导入的题库（单词 / 句子）
    <程序目录>/我的题库/  放 .txt 进去就自动变成课程（一行一条）

密码用 PBKDF2-HMAC-SHA256 + 随机盐，不存明文。
忘记密码的唯一解法：删掉 data/config.json 重启（程序会要求重新设密码）。

两层时长管控（互相独立）：
  ① 番茄节奏 —— 管节奏，墙钟倒计时，到点锁屏休息，会自动恢复
  ② 每日额度 —— 管总量，活跃计时（按键驱动），到点锁屏**必须密码**，次日 0 点才回满
"""

import os
import sys
import json
import time
import base64
import hashlib
import secrets

from . import courses

PBKDF2_ROUNDS = 200_000

DEFAULT_CONFIG = {
    "pwd_salt": "",
    "pwd_hash": "",
    "pomodoro": {"work": 20, "break": 5, "enabled": True},
    # 每日额度：默认关闭 —— 家长自己去「家长面板 → 时间管理」打开，
    # 免得装上就被限时，孩子还以为软件坏了
    "daily_limit": {"enabled": False, "minutes": 120, "idle_grace_sec": 15},
    "fullscreen": True,
    "sound": True,
    "strict": True,          # True=打错必须打对才前进
    "created": "",
}

DEFAULT_CONTENT = {"sets": [], "files": {}}


def _blank_usage(quota_seconds=0):
    """今天的额度记录。left = quota_seconds - used_seconds。"""
    return {
        "date": time.strftime("%Y-%m-%d"),
        "used_seconds": 0,          # 只算"真的在打字"的时长
        "quota_seconds": int(quota_seconds),
        "unlimited": False,         # 家长选了"今天不限制"
        "grants": 0,                # 今天加时了几次
    }


def base_dir():
    """程序所在目录（打包成 exe 后是 exe 所在目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_DATA_DIR_OVERRIDE = None


def set_data_dir(path):
    """自检时把数据写到临时目录，别碰用户真实配置。"""
    global _DATA_DIR_OVERRIDE
    _DATA_DIR_OVERRIDE = path


def data_dir():
    d = _DATA_DIR_OVERRIDE or os.path.join(base_dir(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def content_dir():
    """「我的题库」文件夹 —— 放 .txt 进去就自动变成课程。"""
    d = os.path.join(_DATA_DIR_OVERRIDE or base_dir(), "我的题库")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(fallback))


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Store:
    """配置 + 进度。"""

    def __init__(self):
        self.config_path = os.path.join(data_dir(), "config.json")
        self.progress_path = os.path.join(data_dir(), "progress.json")
        self.content_path = os.path.join(data_dir(), "content.json")
        self.config = _read_json(self.config_path, DEFAULT_CONFIG)
        for k, v in DEFAULT_CONFIG.items():
            if isinstance(v, dict):                     # 嵌套项要逐个子键补默认值
                cur = self.config.get(k)
                if not isinstance(cur, dict):
                    cur = {}
                    self.config[k] = cur
                for kk, vv in v.items():
                    cur.setdefault(kk, json.loads(json.dumps(vv)))
            else:
                self.config.setdefault(k, v)
        self.progress = _read_json(
            self.progress_path,
            {"lessons": {}, "total_seconds": 0, "days": {}, "updated": ""},
        )
        self.progress.setdefault("lessons", {})
        self.progress.setdefault("days", {})
        self.progress.setdefault("usage", _blank_usage())
        u = self.progress["usage"]
        for k, v in _blank_usage().items():
            u.setdefault(k, v)
        self.content = _read_json(self.content_path, DEFAULT_CONTENT)
        self.content.setdefault("sets", [])
        self.content.setdefault("files", {})

    # ---------------- 题库（家长导入的单词 / 句子） ----------------
    @property
    def content_sets(self):
        return self.content.get("sets") or []

    def set_by_id(self, set_id):
        for s in self.content_sets:
            if s.get("id") == set_id:
                return s
        return None

    def save_content(self):
        _write_json(self.content_path, self.content)

    def add_content_set(self, name, items, repeats=3, shuffle=False, source=""):
        s = {
            "id": secrets.token_hex(4),
            "name": (name or "").strip() or "我的题库",
            "items": list(items),
            "repeats": max(1, min(20, int(repeats or 3))),
            "shuffle": bool(shuffle),
            "source": source or "",
        }
        self.content["sets"].append(s)
        self.save_content()
        return s

    def update_content_set(self, set_id, name=None, items=None,
                           repeats=None, shuffle=None):
        s = self.set_by_id(set_id)
        if not s:
            return None
        if name is not None and str(name).strip():
            s["name"] = str(name).strip()
        if items is not None:
            s["items"] = list(items)
        if repeats is not None:
            s["repeats"] = max(1, min(20, int(repeats)))
        if shuffle is not None:
            s["shuffle"] = bool(shuffle)
        self.save_content()
        return s

    def remove_content_set(self, set_id):
        s = self.set_by_id(set_id)
        if not s:
            return False
        self.content["sets"] = [x for x in self.content_sets if x.get("id") != set_id]
        # 顺带把文件登记清掉，文件还在的话下次扫描会重新导进来
        for fn, rec in list(self.content.get("files", {}).items()):
            if rec.get("set_id") == set_id:
                del self.content["files"][fn]
        self.save_content()
        return True

    def scan_content_folder(self, default_repeats=3):
        """把「我的题库」文件夹里的 txt/csv 同步成题库。

        新文件 -> 新建一个题库；改过的文件 -> 更新内容；文件删了不动已有题库。
        返回 (added, updated, files) 三个名字列表。
        """
        d = content_dir()
        try:
            names = sorted(os.listdir(d))
        except Exception:
            return [], [], []
        known = self.content.setdefault("files", {})
        added, updated = [], []

        for fn in names:
            if not fn.lower().endswith((".txt", ".csv")):
                continue
            path = os.path.join(d, fn)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            rec = known.get(fn) or {}
            if rec and abs(float(rec.get("mtime", 0)) - mtime) < 1.0:
                continue                                   # 没动过
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception:
                continue
            items, _skipped, _fixed = courses.clean_items(raw, mode="line")
            if not items:
                continue

            sid = rec.get("set_id")
            if sid and self.set_by_id(sid):
                self.update_content_set(sid, items=items)
                updated.append(fn)
            else:
                st = self.add_content_set(os.path.splitext(fn)[0], items,
                                          repeats=default_repeats, source=fn)
                sid = st["id"]
                added.append(fn)
            known[fn] = {"mtime": mtime, "set_id": sid}

        self.save_content()
        return added, updated, names

    # ---------------- 密码 ----------------
    @staticmethod
    def _hash(pwd, salt_b64):
        salt = base64.b64decode(salt_b64)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, PBKDF2_ROUNDS)
        return base64.b64encode(dk).decode("ascii")

    @property
    def has_password(self):
        return bool(self.config.get("pwd_hash"))

    def set_password(self, pwd):
        salt = secrets.token_bytes(16)
        self.config["pwd_salt"] = base64.b64encode(salt).decode("ascii")
        self.config["pwd_hash"] = self._hash(pwd, self.config["pwd_salt"])
        if not self.config.get("created"):
            self.config["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_config()

    def check_password(self, pwd):
        if not self.has_password:
            return False
        return secrets.compare_digest(self._hash(pwd, self.config["pwd_salt"]),
                                      self.config["pwd_hash"])

    # ---------------- 番茄参数 ----------------
    @property
    def pomodoro(self):
        d = self.config.get("pomodoro") or {}
        return {
            "work": max(1, int(d.get("work", 20))),
            "break": max(1, int(d.get("break", 5))),
            "enabled": bool(d.get("enabled", True)),
        }

    def set_pomodoro(self, work, brk, enabled=None):
        d = dict(self.config.get("pomodoro") or {})
        d["work"] = max(1, int(work))
        d["break"] = max(1, int(brk))
        if enabled is not None:
            d["enabled"] = bool(enabled)
        d.setdefault("enabled", True)
        self.config["pomodoro"] = d
        self.save_config()

    # ---------------- 每日额度 ----------------
    @property
    def daily_limit(self):
        d = self.config.get("daily_limit") or {}
        return {
            "enabled": bool(d.get("enabled", False)),
            "minutes": max(1, int(d.get("minutes", 120))),
            "idle_grace_sec": max(3, int(d.get("idle_grace_sec", 15))),
        }

    def set_daily_limit(self, enabled, minutes):
        self.config["daily_limit"] = {
            "enabled": bool(enabled),
            "minutes": max(1, int(minutes)),
            "idle_grace_sec": self.daily_limit["idle_grace_sec"],
        }
        self.save_config()
        self.progress.setdefault("usage", _blank_usage())
        self.progress["usage"].setdefault("quota_seconds", 0)

    def roll_day(self):
        """跨天 -> 今日用量归零、额度按配置重算。返回是否真的跨了天。"""
        u = self.progress.setdefault("usage", _blank_usage())
        today = time.strftime("%Y-%m-%d")
        if u.get("date") == today:
            return False
        u.clear()
        u.update(_blank_usage(self.daily_limit["minutes"] * 60))
        self.save_progress()
        return True

    def usage_info(self):
        """今日额度状态。

        left=None 表示"不限制"（开关没开，或家长选了今天不限制）；
        否则 left 就是今天还能用多少秒（不会小于 0）。
        """
        self.roll_day()
        u = self.progress.setdefault("usage", _blank_usage())
        dl = self.daily_limit
        used = max(0, int(u.get("used_seconds", 0)))
        grants = int(u.get("grants", 0))
        if not dl["enabled"]:
            return {"enabled": False, "used": used, "quota": 0,
                    "unlimited": True, "left": None, "grants": grants}
        if u.get("unlimited"):
            return {"enabled": True, "used": used,
                    "quota": int(u.get("quota_seconds", 0)),
                    "unlimited": True, "left": None, "grants": grants}
        quota = int(u.get("quota_seconds", 0)) or dl["minutes"] * 60
        return {"enabled": True, "used": used, "quota": quota,
                "unlimited": False, "left": max(0, quota - used),
                "grants": grants}

    def add_usage(self, seconds):
        """累计"真的在打字"的时长。"""
        n = int(seconds)
        if n <= 0:
            return
        self.roll_day()
        u = self.progress.setdefault("usage", _blank_usage())
        u["used_seconds"] = max(0, int(u.get("used_seconds", 0))) + n
        self.save_progress()

    def grant_usage(self, seconds):
        """家长加时。seconds=None 表示「今天不限制」；否则=今天还能再用这么多秒。"""
        self.roll_day()
        u = self.progress.setdefault("usage", _blank_usage())
        u["grants"] = int(u.get("grants", 0)) + 1
        if seconds is None:
            u["unlimited"] = True
        else:
            u["unlimited"] = False
            u["quota_seconds"] = int(u.get("used_seconds", 0)) + max(1, int(seconds))
        self.save_progress()

    def reset_usage_today(self):
        """家长手动把今天的用量清零。"""
        u = self.progress.setdefault("usage", _blank_usage())
        u.clear()
        u.update(_blank_usage(self.daily_limit["minutes"] * 60))
        self.save_progress()

    # ---------------- 设置项 ----------------
    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def save_config(self):
        _write_json(self.config_path, self.config)

    # ---------------- 练习进度 ----------------
    def record(self, lesson_id, stars, accuracy, cpm, seconds, last_row_counts=None):
        item = self.progress["lessons"].setdefault(
            lesson_id, {"stars": 0, "best_acc": 0.0, "best_cpm": 0.0, "plays": 0}
        )
        item["stars"] = max(item.get("stars", 0), int(stars))
        item["best_acc"] = max(item.get("best_acc", 0.0), round(float(accuracy), 4))
        item["best_cpm"] = max(item.get("best_cpm", 0.0), round(float(cpm), 1))
        item["plays"] = int(item.get("plays", 0)) + 1
        item["last"] = time.strftime("%Y-%m-%d %H:%M")

        today = time.strftime("%Y-%m-%d")
        day = self.progress.setdefault("days", {}).setdefault(today, {"seconds": 0, "chars": 0})
        day["seconds"] += int(seconds)
        day["chars"] += int(last_row_counts or 0)
        self.progress["total_seconds"] = self.progress.get("total_seconds", 0) + int(seconds)
        self.progress["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_progress()

    def stars_of(self, lesson_id):
        return int((self.progress.get("lessons", {}).get(lesson_id) or {}).get("stars", 0))

    def add_seconds(self, seconds):
        self.progress["total_seconds"] = self.progress.get("total_seconds", 0) + int(seconds)
        today = time.strftime("%Y-%m-%d")
        day = self.progress.setdefault("days", {}).setdefault(today, {"seconds": 0, "chars": 0})
        day["seconds"] += int(seconds)
        self.save_progress()

    def save_progress(self):
        _write_json(self.progress_path, self.progress)

    def reset_progress(self):
        self.progress = {"lessons": {}, "total_seconds": 0, "days": {}, "updated": "",
                         "usage": _blank_usage(self.daily_limit["minutes"] * 60)}
        self.save_progress()
