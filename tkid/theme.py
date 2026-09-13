# -*- coding: utf-8 -*-
"""配色、字体、指法映射、全局缩放系数。

缩放策略：
  - 字号一律用 pt，靠 tkinter 的 tk scaling 跟着屏幕走（App 启动时设好）
  - 像素尺寸（宽高、padding、canvas）一律过 px() 换算
这样 1080p / 2K / 4K 屏上长得一样，不会"字小得像蚂蚁"或"挤成一团"。
"""

SCALE = 1.0          # 由 app.App 在建立界面之前设好


def set_scale(s):
    global SCALE
    SCALE = max(0.7, float(s))


def px(v):
    """设计像素 -> 实际像素。"""
    return max(1, int(round(v * SCALE)))


# ---------- 浅色主题配色 ----------
BG        = "#eef2f8"   # 页面底色
CARD      = "#ffffff"   # 卡片
SIDEBAR   = "#f7f9fd"   # 侧栏
INK       = "#1e2a3a"   # 主文字
MUTED     = "#7b8a9e"   # 次要文字
LINE      = "#dde5ef"   # 分隔线

ACCENT    = "#2f6fed"   # 主题蓝
ACCENT_D  = "#1f56c4"
OK        = "#17a673"   # 打对
BAD       = "#e5484d"   # 打错
WARN      = "#f59f00"   # 提醒
STAR      = "#f7b500"   # 星星

CURSOR_BG = "#ffd76a"   # 当前字符底色
PENDING   = "#9aa8ba"   # 还没打到的字
OK_DIM    = "#a9dcc4"   # 已经打完的上一行（淡一点，不抢当前行）
WHITE     = "#ffffff"

# ---------- 空格怎么显示 ----------
# 原则上不给空格配任何"字符"。原因：任何代替空格的符号，都可能和键盘上真实存在的键
# 撞脸（- 撞减号、_ 撞下划线、. 撞句点），孩子会把那个符号错记成"空格"。
# 所以这里用图形化的"空槽"，而不是一个字的代替品；空格就应该是空的。
SPACE_MODES = ("slot", "blank")          # slot=浅灰空槽（默认）/ blank=纯空白
SPACE_MODE_DEFAULT = "slot"

SLOT_BG       = "#e6edf7"   # 空槽底色（这里是个空格，还没打）
SLOT_LINE     = "#c8d6e8"   # 空槽描边
SLOT_DONE_BG  = "#cdeedb"   # 打完的空格：空槽变浅绿（没字符可染绿，就染格子）
BLANK_DONE_BG = "#e2f5ea"   # 纯空白模式下，打完的空格留个很淡的绿印子

# ---------- 每日额度 ----------
LIMIT_NORMAL = "#2f6fed"   # 剩余充裕（跟主题蓝一致）
LIMIT_LOW    = "#e8590c"   # 剩余不多了（橙）
LIMIT_OUT    = "#e5484d"   # 快没了 / 已用完

# 额度用完的锁屏：用暖色，跟番茄休息的冷色明显区分开
LOCK_LIMIT_BG   = "#2c1a10"
LOCK_LIMIT_HEAD = "#ffb454"
LOCK_LIMIT_TEXT = "#ffffff"
LOCK_LIMIT_SUB  = "#d9b79a"
LOCK_LIMIT_BTN  = "#42281a"
LOCK_LIMIT_BTNF = "#c9a184"

# ---------- 字体 ----------
FONT_UI   = ("Microsoft YaHei UI", 11)
FONT_UI_B = ("Microsoft YaHei UI", 11, "bold")
FONT_SM   = ("Microsoft YaHei UI", 9)
FONT_H1   = ("Microsoft YaHei UI", 22, "bold")
FONT_H2   = ("Microsoft YaHei UI", 14, "bold")
FONT_HUGE = ("Microsoft YaHei UI", 44, "bold")
FONT_MONO = ("Consolas", 38, "bold")     # 打字段
FONT_KEY  = ("Consolas", 13, "bold")     # 虚拟键盘按键

# ---------- 指法映射：哪个键归哪根手指 ----------
# 左：小指 无名指 中指 食指 | 右：食指 中指 无名指 小指 | 空格 -> 大拇指
_FINGER_KEYS = [
    ("左手小指",   "1qaz"),
    ("左手无名指", "2wsx"),
    ("左手中指",   "3edc"),
    ("左手食指",   "45rtfgvb"),
    ("右手食指",   "67yuhjnm"),
    ("右手中指",   "8ik,"),
    ("右手无名指", "9ol."),
    ("右手小指",   "0p;/'-=[]\\"),
    ("大拇指",     " "),
]

FINGER_MAP = {}
for _f, _ks in _FINGER_KEYS:
    for _k in _ks:
        FINGER_MAP[_k] = _f

# 每根手指一种颜色（柔和色，配深色字/描边都清楚）
FINGER_COLORS = {
    "左手小指":   "#ffc2cb",
    "左手无名指": "#ffdfa8",
    "左手中指":   "#cdeeb0",
    "左手食指":   "#b6dcff",
    "右手食指":   "#cfc6ff",
    "右手中指":   "#b2ebe2",
    "右手无名指": "#ffcdb0",
    "右手小指":   "#dfd8cc",
    "大拇指":     "#e8e8ee",
}

def finger_of(ch):
    """返回按键对应的手指名，未知返回 None。"""
    if not ch:
        return None
    return FINGER_MAP.get(ch.lower())

def finger_color(ch):
    f = finger_of(ch)
    return FINGER_COLORS.get(f, "#e8e8ee")
