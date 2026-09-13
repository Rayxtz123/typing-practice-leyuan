# -*- coding: utf-8 -*-
"""虚拟键盘 + 手部示意图。

两层：
  1. 键盘本体 —— 每个键按"归哪根手指"上色
  2. 手 —— 十根手指从手掌位置伸到基准键上；当前该敲的那个键，
     对应的手指会变蓝加粗，一路指到键的根部

坐标系全部按 scale 缩放，改大小只传 scale。
"""

import tkinter as tk
from . import theme as T

KW, KH, GAP = 45, 44, 5          # 基准键宽 / 键高 / 键间距
ROWS = [                          # (键序列, 左边距)
    ("1234567890", 0),
    ("qwertyuiop", 21),
    ("asdfghjkl;", 33),
    ("zxcvbnm,./", 54),
]
TOP = 10
SPACE_H = 44
HAND_H = 112                      # 键盘下方留给手的区域
BASE_W = 10 * KW + 9 * GAP + 54   # 549

# 八根手指的基准键（顺序 = 从左到右）
FINGERS = [
    ("左手小指", "a"), ("左手无名指", "s"), ("左手中指", "d"), ("左手食指", "f"),
    ("右手食指", "j"), ("右手中指", "k"), ("右手无名指", "l"), ("右手小指", ";"),
]
HOME_KEY = dict(FINGERS)          # 手指 -> 它的基准键（兜底指向用）
# 手指根部相对掌心的横向偏移 —— 让手指从手掌"有宽度地"长出来，而不是一个点发散
ROOT_DX = {
    "左手小指": -46, "左手无名指": -17, "左手中指": 3, "左手食指": 21,
    "右手食指": -21, "右手中指": -3, "右手无名指": 17, "右手小指": 46,
}

HAND_IDLE = "#ccd8e8"             # 静止的手
HAND_TIP = "#b8c8dc"
HAND_PALM = "#dde6f1"


class VirtualKeyboard(tk.Canvas):
    def __init__(self, master, scale=1.0, **kw):
        s = scale
        self.s = s
        self.kw = KW * s
        self.kh = KH * s
        self.gap = GAP * s
        self.top = TOP * s
        self.row_h = (KH + GAP) * s
        self.space_h = SPACE_H * s
        self.hand_h = HAND_H * s

        w = (BASE_W + 20) * s
        h = self.top + 4 * self.row_h + self.space_h + self.hand_h
        super().__init__(master, width=w, height=h, bg=T.CARD,
                         highlightthickness=0, **kw)

        self._key = {}            # ch -> (rect_id, text_id)
        self._center = {}         # ch -> (cx, cy)
        self._active = None
        self._build()

    # ------------------------------------------------------------ 按键
    def _build(self):
        s = self.s
        for row_idx, (keys, offset) in enumerate(ROWS):
            ox = (10 + offset) * s
            oy = self.top + row_idx * self.row_h
            for i, ch in enumerate(keys):
                x = ox + i * (self.kw + self.gap)
                self._draw_key(ch, x, oy)

        # 空格键
        oy = self.top + 4 * self.row_h
        sp_w = 6.2 * self.kw
        ox = (10 + (BASE_W - 54 - sp_w) / 2) * s
        rid = self.create_rectangle(ox, oy, ox + sp_w, oy + self.space_h,
                                    fill=T.finger_color(" "), outline=T.LINE, width=1)
        tid = self.create_text(ox + sp_w / 2, oy + self.space_h / 2,
                               text="空格", font=("Microsoft YaHei UI", 11), fill=T.INK)
        self._key[" "] = (rid, tid)
        self._center[" "] = (ox + sp_w / 2, oy + self.space_h / 2)

        self._draw_hands(None)

    def _draw_key(self, ch, x, y):
        rid = self.create_rectangle(x, y, x + self.kw, y + self.kh,
                                    fill=T.finger_color(ch), outline=T.LINE, width=1)
        tid = self.create_text(x + self.kw / 2, y + self.kh / 2,
                               text=ch.upper(), font=self._font(13), fill=T.INK)
        self._key[ch.lower()] = (rid, tid)
        self._center[ch.lower()] = (x + self.kw / 2, y + self.kh / 2)

    def _font(self, size):
        # 字号给 pt，交给 tkinter 的 tk scaling 换算成像素；
        # 不要再乘 self.s，否则和 tk scaling 叠加会变成两倍大。
        return ("Consolas", size, "bold")

    # ------------------------------------------------------------ 手
    def _palm(self, side):
        """掌心位置：左手在 d 下面，右手在 k 下面。"""
        anchor = "d" if side == "L" else "k"
        cx, _ = self._center[anchor]
        return cx, self.winfo_reqheight() - 24 * self.s

    def _finger_root(self, finger):
        px, py = self._palm("L" if finger.startswith("左") else "R")
        if finger == "大拇指":
            return px, py
        return px + ROOT_DX.get(finger, 0) * self.s, py

    def _finger_points(self, finger, tip_ch):
        """[根x, 根y, 控制x, 控制y, 指尖x, 指尖y] —— 先斜出去再弯向按键。"""
        rx, ry = self._finger_root(finger)
        s = self.s

        if tip_ch == " ":
            cx, cy = self._center[" "]
            k = 1.35 if finger.startswith("右") else -1.35
            tx = cx + self.kw * k
            ty = cy - self.space_h / 2 + 3 * s
        else:
            # 有些键（' - = [ ] \）键盘上没画出来，就让手指落到它的基准键
            if tip_ch not in self._center:
                tip_ch = HOME_KEY.get(finger, "f")
            tx, ty = self._center[tip_ch]
            ty += self.kh / 2 - 2 * s          # 指到键根部，别压住字母

        cx = tx + (rx - tx) * 0.22
        cy = ry - (ry - ty) * 0.50
        return [rx, ry, cx, cy, tx, ty]

    def _stroke(self, pts, width, color, tag):
        self.create_line(*pts, smooth=True, splinesteps=24,
                         width=width, fill=color,
                         capstyle="round", joinstyle="round", tags=tag)

    def _tip_dot(self, pts, r, color, tag):
        self.create_oval(pts[4] - r, pts[5] - r, pts[4] + r, pts[5] + r,
                         fill=color, outline="", tags=tag)

    def _draw_hands(self, active_ch):
        """重画整只手：静止的压在键盘底下，当前用的那根手指亮蓝压在最上面。"""
        self.delete("hand_idle")
        self.delete("hand_active")
        s = self.s
        w_idle = max(2.0, 4.2 * s)
        active_finger = T.finger_of(active_ch) if active_ch else None

        # 掌根
        for side in ("L", "R"):
            px, py = self._palm(side)
            w, h = 160 * s, 40 * s
            self.create_oval(px - w / 2, py - h / 2, px + w / 2, py + h / 2,
                             fill=HAND_PALM, outline="", tags="hand_idle")

        # 八根手指 + 两根大拇指
        for finger, home in FINGERS:
            if finger == active_finger:
                continue
            pts = self._finger_points(finger, home)
            self._stroke(pts, w_idle, HAND_IDLE, "hand_idle")
            self._tip_dot(pts, 3.6 * s, HAND_TIP, "hand_idle")
        if active_finger != "大拇指":
            for side in ("L", "R"):
                pts = self._finger_points("大拇指", " ")
                if side == "L":
                    cx, cy = self._center[" "]
                    pts[4] = cx - self.kw * 1.35
                    pts[5] = cy - self.space_h / 2 + 3 * s
                    pts[0], pts[1] = self._palm("L")
                    pts[2] = pts[4] + (pts[0] - pts[4]) * 0.22
                    pts[3] = pts[1] - (pts[1] - pts[5]) * 0.50
                self._stroke(pts, w_idle, HAND_IDLE, "hand_idle")
                self._tip_dot(pts, 3.6 * s, HAND_TIP, "hand_idle")

        # 当前该用的手指
        if active_finger:
            if active_finger == "大拇指":
                cx, cy = self._center[" "]
                pts = self._finger_points("大拇指", " ")
                pts[4] = cx + self.kw * 1.35
                pts[5] = cy - self.space_h / 2 + 3 * s
                pts[2] = pts[4] + (pts[0] - pts[4]) * 0.22
                pts[3] = pts[1] - (pts[1] - pts[5]) * 0.50
            else:
                pts = self._finger_points(active_finger, active_ch)
            self._stroke(pts, max(3.0, 9 * s), T.ACCENT, "hand_active")
            self._tip_dot(pts, 6 * s, T.ACCENT, "hand_active")

        self.tag_lower("hand_idle")        # 静止的手藏在键盘下面
        self.tag_raise("hand_active")      # 当前的手指压在键盘上面

    # ------------------------------------------------------------ 高亮
    def clear_highlight(self):
        for ch, (rid, tid) in self._key.items():
            self.itemconfig(rid, fill=T.finger_color(ch), outline=T.LINE, width=1)
            self.itemconfig(tid, fill=T.INK)
        self._active = None
        self._draw_hands(None)

    def highlight(self, ch):
        """把 ch 标蓝，并让对应的手指指过来。ch=None 则清除。"""
        if not ch:
            self.clear_highlight()
            return
        key = ch.lower()
        for c, (rid, tid) in self._key.items():
            if c == key:
                self.itemconfig(rid, fill=T.ACCENT, outline=T.ACCENT_D, width=3)
                self.itemconfig(tid, fill=T.WHITE)
                self.tag_raise(rid)
                self.tag_raise(tid)
            else:
                self.itemconfig(rid, fill=T.finger_color(c), outline=T.LINE, width=1)
                self.itemconfig(tid, fill=T.INK)
        self._active = ch
        self._draw_hands(ch)
