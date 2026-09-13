# -*- coding: utf-8 -*-
"""课程内容 —— 照搬 hellotyping 的「配对键位递进」结构。

结构：
  认识键盘（图文说明）
  一、基准键   f j  ->  d k  ->  s l  ->  a ;  ->  g h     每对键：练习 + 游戏
  二、上排字母 r u  ->  e i  ->  w o  ->  q t  ->  p y
  三、下排字母 v m  ->  c ,  ->  x .  ->  z /  ->  b n
  四、数字键   4 7  ->  3 8  ->  2 9  ->  1 0  ->  5 6
  五、拼音与单词（结合拼音，顺便练拼音）

每课是「一行一行」打的，一行打完自动进下一行。
kind: info(说明页) / drill(练习) / game(限时游戏)
pool: 本课允许出现的字符集合（累进）
focus: 本课重点键（前两个字符），会优先出对打

要加课 / 改内容，只改这个文件的 LESSONS 就行。
"""

import re
import zlib
import string
import random

HOME = "asdfghjkl;"
TOP = "qwertyuiop"
BOTTOM = "zxcvbnm,./"
NUM = "1234567890"

# ---------------------------------------------------------------- 题库（家长导入）

# 支持的字符：虚拟键盘上画得出来的那些。
# 不在这个集合里的（? ! : " 中文 ……）打不了，导入时要么跳过、要么让家长勾选自动去掉。
SUPPORTED_CHARS = set(string.ascii_letters + string.digits + " ,./;'-=[]\\")

USER_GROUP = "六、我导入的题库"
USER_TARGET_ROWS = 24        # 一课最多铺多少行，超了就自动切成好几课

_NUM_PREFIX = re.compile(r"^\s*\d+\s*[.、):：]\s*")
_SPLIT_RE = re.compile(r"[\s,，、;；/]+")


def clean_item(s):
    """一条内容的规范化：去序号前缀、压缩连续空格。"""
    s = _NUM_PREFIX.sub("", (s or "").strip())
    return " ".join(s.split())


def clean_items(text, mode="line", drop_unsupported=False):
    """原始文本 -> 条目列表。

    mode: "line" 一行一条（句子用这个）；"split" 再按空格/逗号/顿号拆成词
    drop_unsupported: True=自动删掉不支持的字符；False=含不支持字符的整条跳过
    返回 (items, skipped, fixed)：跳过的条 / 被自动改过的条
    """
    if mode == "split":
        raw = _SPLIT_RE.split(text or "")
    else:
        raw = (text or "").splitlines()

    items, skipped, fixed = [], [], []
    for line in raw:
        if (line or "").strip().startswith("#"):
            continue                       # # 开头当注释
        s = clean_item(line)
        if not s:
            continue
        if any(c not in SUPPORTED_CHARS for c in s):
            if not drop_unsupported:
                skipped.append(s)
                continue
            s2 = clean_item("".join(c for c in s if c in SUPPORTED_CHARS))
            if not s2:
                skipped.append("（去掉之后空了）")
                continue
            fixed.append(s)
            s = s2
        items.append(s)
    return items, skipped, fixed


def wrap_item(item, max_cols):
    """一条内容切成不超过 max_cols 的显示行，尽量在空格处断开。"""
    if max_cols <= 0 or len(item) <= max_cols:
        return [item]
    out, cur = [], ""
    for w in item.split(" "):
        while len(w) > max_cols:           # 超长单词硬切
            if cur:
                out.append(cur)
                cur = ""
            out.append(w[:max_cols])
            w = w[max_cols:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_cols:
            cur = cur + " " + w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return [x for x in out if x]


def build_user_lessons(sets, max_cols):
    """把家长导入的题库变成课程表。条数多就自动切成好几课。"""
    out = []
    for st in (sets or []):
        items = [i for i in (st.get("items") or []) if i]
        if not items:
            continue
        try:
            repeats = int(st.get("repeats", 3) or 3)
        except Exception:
            repeats = 3
        repeats = max(1, min(20, repeats))

        # 按目标行数切课
        chunks, cur, cur_rows = [], [], 0
        for it in items:
            cnt = len(wrap_item(it, max_cols)) * repeats
            if cur and cur_rows + cnt > USER_TARGET_ROWS:
                chunks.append(cur)
                cur, cur_rows = [], 0
            cur.append(it)
            cur_rows += cnt
        if cur:
            chunks.append(cur)

        for k, ch in enumerate(chunks, 1):
            rows = []
            for it in ch:
                frags = wrap_item(it, max_cols)
                for _ in range(repeats):
                    rows.extend(frags)
            title = (st.get("name") or "我的题库").strip() or "我的题库"
            if len(chunks) > 1:
                title += "（%d/%d）" % (k, len(chunks))
            out.append({
                "id": "user_%s_%d" % (st.get("id"), k),
                "group": USER_GROUP, "kind": "drill",
                "title": title, "rows": rows, "nrows": 0,
                "dedup": False,                       # 每遍都要保留，不能去重
                "shuffle": bool(st.get("shuffle")),
                "source_set": st.get("id"),
                "note": "共 %d 条 · 每条打 %d 遍" % (len(ch), repeats),
            })
    return out


def rebuild(user_sets=None, max_cols=24):
    """重建课程表（家长改了题库就调一次）。"""
    global LESSONS, LESSON_BY_ID
    LESSONS = build_lessons() + build_user_lessons(user_sets, max_cols)
    LESSON_BY_ID = {l["id"]: l for l in LESSONS}
    return LESSONS


# ---------------------------------------------------------------- 生成器

def _seed_of(lesson_id, extra=0):
    """稳定的种子（不用内置 hash，它每个进程都不一样）。"""
    return zlib.crc32(lesson_id.encode("utf-8")) ^ (extra * 2654435761)


def _chunk(s, size):
    return " ".join(s[i:i + size] for i in range(0, len(s), size))


def make_rows(lesson, variant=0):
    """生成一课的所有练习行。固定 rows 的直接返回，否则按 pool 随机生成。"""
    if lesson.get("rows"):
        rows = list(lesson["rows"])
        if lesson.get("shuffle"):
            random.Random(_seed_of(lesson["id"], variant)).shuffle(rows)
        return rows

    rng = random.Random(_seed_of(lesson["id"], variant))
    pool = lesson.get("pool") or HOME
    focus = lesson.get("focus") or ""
    nrows = lesson.get("nrows", 6)
    rows = []

    for i in range(nrows):
        mode = i % 4
        if mode == 0 and len(focus) >= 2:
            a, b = focus[0], focus[1]
            rows.append(" ".join([a * 2, b * 2, a + b, b + a]))
        elif mode == 1:
            rows.append(_chunk("".join(rng.choice(pool) for _ in range(8)), 2))
        elif mode == 2:
            rows.append(_chunk("".join(rng.choice(pool) for _ in range(9)), 3))
        else:
            rows.append(_chunk("".join(rng.choice(pool) for _ in range(10)), 2))
    return rows


def make_game_rows(lesson, rng):
    """游戏模式：无限出题，调用方按时间截断。"""
    pool = lesson.get("pool") or HOME
    size = lesson.get("gsize", 2)
    return _chunk("".join(rng.choice(pool) for _ in range(size * 4)), size)


# ---------------------------------------------------------------- 课程表

def _pair_group(group_name, gid, pairs, base_pool, base_title):
    """一对键 -> 两课（练习 + 游戏）。"""
    out = []
    pool = base_pool
    for a, b in pairs:
        pool = pool + a + b
        out.append({
            "id": "%s_%s%s" % (gid, ord(a), ord(b)),
            "group": group_name, "kind": "drill",
            "title": "练习：%s 和 %s" % (a, b),
            "pool": pool, "focus": a + b, "nrows": 6,
        })
        out.append({
            "id": "%s_%s%s_g" % (gid, ord(a), ord(b)),
            "group": group_name, "kind": "game",
            "title": "游戏：%s %s" % (a, b),
            "pool": pool, "focus": a + b, "seconds": 45, "gsize": 2,
        })
    # 本组通关游戏
    out.append({
        "id": "%s_final_g" % gid,
        "group": group_name, "kind": "game",
        "title": "通关游戏：%s" % base_title,
        "pool": pool, "focus": pairs[-1][0] + pairs[-1][1],
        "seconds": 60, "gsize": 3,
    })
    return out


def build_lessons():
    L = []

    # -------- 0. 认识键盘 --------
    L.append({
        "id": "intro", "group": "开始之前", "kind": "info",
        "title": "认识键盘和坐姿",
        "text": (
            "【坐姿口诀】\n"
            "  背挺直，脚踩地，眼睛离屏一尺远\n"
            "  两肘贴住身两边，手腕轻轻放桌上\n\n"
            "【手指分工】\n"
            "  下面键盘的每个按键都涂上了颜色，\n"
            "  颜色相同的键，用同一根手指去敲。\n\n"
            "【基准键——手指的家】\n"
            "  左手食指放 F，右手食指放 J\n"
            "  （这两个键上有小凸点，闭眼也能摸到）\n"
            "  其余手指依次搭在 A S D 和 K L ；\n\n"
            "【大拇指 —— 只管空格】\n"
            "  空格 = 什么都不打，敲一下最长的那根键。\n"
            "  屏幕上词和词中间的空位，就是要按空格。\n"
            "  两根大拇指都能按，敲完立刻回位。\n\n"
            "【打一会儿要休息】\n"
            "  时间到了屏幕会自己锁住，那是提醒你歇一歇。\n"
            "  站起来走两步，看看远处，休息好了再继续。\n\n"
            "准备好了就点下面的按钮开始吧！"
        ),
    })

    # -------- 一、基准键 --------
    L += _pair_group("一、基准键", "home",
                     [("f", "j"), ("d", "k"), ("s", "l"), ("a", ";"), ("g", "h")],
                     "", "8个基准键")

    # -------- 二、上排字母 --------
    L += _pair_group("二、上排字母", "top",
                     [("r", "u"), ("e", "i"), ("w", "o"), ("q", "t"), ("p", "y")],
                     HOME, "上排字母")

    # -------- 三、下排字母 --------
    L += _pair_group("三、下排字母", "bottom",
                     [("v", "m"), ("c", ","), ("x", "."), ("z", "/"), ("b", "n")],
                     HOME + TOP, "下排字母")

    # -------- 四、数字键 --------
    L += _pair_group("四、数字键", "num",
                     [("4", "7"), ("3", "8"), ("2", "9"), ("1", "0"), ("5", "6")],
                     HOME + TOP + BOTTOM, "0~9")

    # -------- 五、拼音与单词 --------
    L.append({
        "id": "py_bpmf", "group": "五、拼音与单词", "kind": "drill",
        "title": "拼音：b p m f", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "ba ba  pa pa  ma ma",
            "fa fa  bo bo  po po",
            "ma mi mu  fa fu",
            "bi pi mi  bo po mo fo",
        ],
    })
    L.append({
        "id": "py_dtnl", "group": "五、拼音与单词", "kind": "drill",
        "title": "拼音：d t n l", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "da ta na la  de te",
            "ni li  na ne  di ti",
            "da di du  ta ti tu",
            "ni hao ma  wo hen hao",
        ],
    })
    L.append({
        "id": "py_gkh_jqx", "group": "五、拼音与单词", "kind": "drill",
        "title": "拼音：g k h / j q x", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "ga ka ha  ge ke he",
            "ji qi xi  ju qu xu",
            "gu ku hu  jia qia xia",
            "ge ge  he he  xi xi",
        ],
    })
    L.append({
        "id": "py_zcs_zhchshr", "group": "五、拼音与单词", "kind": "drill",
        "title": "拼音：z c s / zh ch sh r", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "za ca sa  ze ce se",
            "zha cha sha  re ri",
            "zhong guo  shang hai",
            "lao shi  xue sheng",
        ],
    })
    L.append({
        "id": "word3", "group": "五、拼音与单词", "kind": "drill",
        "title": "单词：三个字母", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "cat dog  sun hat  bed cup",
            "red pen  map toy  key bus",
            "box fox  jam leg  net zip",
        ],
        "note": "不用管意思，看准字母敲就行。",
    })
    L.append({
        "id": "word4", "group": "五、拼音与单词", "kind": "drill",
        "title": "单词：四个字母", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "book fish  tree bird",
            "milk door  cake rain",
            "hand jump  star moon",
        ],
    })
    L.append({
        "id": "sentence", "group": "五、拼音与单词", "kind": "drill",
        "title": "短句挑战", "pool": HOME + TOP + BOTTOM, "nrows": 0,
        "rows": [
            "i am a boy",
            "she is my mom",
            "a cat and a dog",
            "i like my book",
        ],
    })
    L.append({
        "id": "final_game", "group": "五、拼音与单词", "kind": "game",
        "title": "终极挑战：全键盘", "pool": HOME + TOP + BOTTOM,
        "focus": "fj", "seconds": 90, "gsize": 3,
    })

    return L


LESSONS = build_lessons()
LESSON_BY_ID = {l["id"]: l for l in LESSONS}


def groups():
    """按 group 聚合，保持顺序。"""
    out = []
    for l in LESSONS:
        if not out or out[-1][0] != l["group"]:
            out.append((l["group"], []))
        out[-1][1].append(l)
    return out


def stars_for(accuracy, cpm, finished, kind):
    """星级：3星要又准又快。"""
    if not finished:
        return 0
    if accuracy >= 0.98:
        return 3
    if accuracy >= 0.92:
        return 2
    return 1


def star_text(n):
    return "★" * n + "☆" * (3 - n)
