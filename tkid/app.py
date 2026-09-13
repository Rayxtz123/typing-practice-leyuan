# -*- coding: utf-8 -*-
"""主程序：练习界面 + 番茄钟 + 锁屏 + 密码拦截。"""

import os
import sys
import time
import threading

import tkinter as tk
from tkinter import ttk

try:
    import winsound
except Exception:                                   # 非 Windows
    winsound = None

from . import theme as T
from . import courses, dialogs
from .keyboard import VirtualKeyboard
from .store import Store

APP_TITLE = "打字练习乐园"
SND_WRONG = [(196, 90)]
SND_ROW = [(880, 45), (1175, 60)]
SND_DONE = [(784, 85), (988, 85), (1319, 140)]
SND_WARN = [(1046, 130), (1046, 130)]


class App:
    # ------------------------------------------------------------------ 初始化
    def __init__(self, selftest=False):
        self.selftest = selftest
        self.store = Store()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg=T.BG)

        self._ui = self._compute_ui()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        s = self._ui["s"]
        win_w = min(int(1240 * s), sw - 40)
        win_h = min(int(880 * s), sh - 70)
        self.root.geometry("%dx%d+%d+%d" % (win_w, win_h,
                                            max(0, (sw - win_w) // 2),
                                            max(0, (sh - win_h) // 3)))
        self.root.minsize(int(960 * s), min(int(680 * s), sh - 70))

        self._setup_style()

        # 练习状态
        self.lesson = None
        self.rows = []
        self.row_idx = 0
        self.char_idx = 0
        self.correct = 0
        self.wrong = 0
        self.variant = 0
        self.finished = False
        self.game_end = 0.0
        self._row_start = time.monotonic()
        self._char_labels = []      # list[list[Label]]
        self._row_frames = []
        self._view_start = 0        # 当前显示的第几行开头
        self._busy = False

        # 番茄状态
        self.pomo = {"state": "off", "end": 0.0, "warned": False, "cycles": 0}
        self._last_tick = time.monotonic()
        self._pending_seconds = 0.0
        self._last_sec = None

        # 每日额度状态
        self._last_activity = 0.0     # 最后一次真实按键的时刻（活跃窗口用）
        self._quota_pending = 0.0
        self._limit_locked = False
        self._lock_mode = None        # "break" / "limit"
        self._limit_marks = {}        # 提醒过没有：m5 / m1
        self._limit_info = None

        self._build_topbar()
        self._build_body()
        self._build_lock()
        self._bind_keys()

        # 每行最多排几个字符（按键盘宽度算），长句子会在这上面折行
        self._max_cols = self._compute_max_cols()
        # 同步「我的题库」文件夹，再按题库重建课程表
        try:
            self.store.scan_content_folder()
        except Exception:
            pass
        courses.rebuild(self.store.content_sets, self._max_cols)
        self.refresh_tree()

        self._open_lesson(courses.LESSONS[0]["id"])
        self._sync_pomo_button()
        self._update_limit_ui()

        if not self.selftest:
            if not self.store.has_password:
                dialogs.set_password_dialog(self.root, self.store, first_time=True)
            self.root.after(120, self._apply_fullscreen)
            # 重启也绕不过去：一进来就先查今天的额度
            self._check_limit_on_start()

        self.root.after(250, self._tick)

    # ------------------------------------------------------------------ 尺寸档位
    def _compute_max_cols(self):
        """打字段一行最多排几个字符 —— 以虚拟键盘的宽度为准，长句子在这里折行。"""
        from tkinter import font as tkfont
        try:
            f = tkfont.Font(family="Consolas", size=self._ui["mono"][1], weight="bold")
            cw = max(1, f.measure("M"))
        except Exception:
            cw = T.px(20)
        try:
            avail = self.kb.winfo_reqwidth() - T.px(40)
        except Exception:
            avail = T.px(500)
        return max(12, int(max(T.px(240), avail) // cw))

    def _compute_ui(self):
        """按屏幕定一个统一缩放系数，像素尺寸走 T.px()、字号走 tk scaling。"""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        s = min(sw / 1280.0, sh / 900.0)
        s = max(0.85, min(3.2, s))
        T.set_scale(s)
        try:
            self.root.tk.call("tk", "scaling", s)
        except Exception:
            pass
        return {
            "s": s,
            "rows": 6 if sh >= 1000 else 5,
            "kb": 0.92 * s,          # 键盘是纯像素 canvas，自己乘
            "gap": T.px(4),
            "mono": ("Consolas", 28, "bold"),
        }

    # ------------------------------------------------------------------ 样式
    def _setup_style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Treeview", background=T.CARD, fieldbackground=T.CARD,
                     foreground=T.INK, rowheight=T.px(30), borderwidth=0,
                     indent=T.px(16), font=T.FONT_UI)
        st.configure("Treeview.Heading", background="#e8edf5", foreground=T.MUTED,
                     relief="flat", font=T.FONT_SM)
        st.map("Treeview", background=[("selected", "#d9e6ff")],
               foreground=[("selected", T.ACCENT_D)])
        st.configure("TNotebook", background=T.CARD, borderwidth=0)
        st.configure("TNotebook.Tab", font=T.FONT_UI_B, padding=(T.px(14), T.px(7)),
                     background="#e8edf5", foreground=T.MUTED)
        st.map("TNotebook.Tab", background=[("selected", T.CARD)],
               foreground=[("selected", T.ACCENT)])

    # ------------------------------------------------------------------ 顶栏
    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=T.CARD, height=T.px(60))
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        tk.Frame(self.root, bg=T.LINE, height=T.px(1)).pack(fill="x", side="top")

        tk.Label(bar, text="打字练习乐园", font=("Microsoft YaHei UI", 15, "bold"),
                 bg=T.CARD, fg=T.ACCENT).pack(side="left", padx=T.px(20))

        self.lbl_pomo = tk.Label(bar, text="番茄钟：未开启", font=T.FONT_UI_B,
                                 bg=T.CARD, fg=T.MUTED)
        self.lbl_pomo.pack(side="left", padx=T.px(12))

        # 今日剩余（只在「每日额度」开启时有意义）
        self.lbl_limit = tk.Label(bar, text="", font=T.FONT_UI_B,
                                  bg=T.CARD, fg=T.LIMIT_NORMAL)
        self.lbl_limit.pack(side="left", padx=T.px(6))

        self.btn_exit = self._flat_btn(bar, "退出", self.on_exit, width=6)
        self.btn_exit.pack(side="right", padx=(T.px(6), T.px(18)))

        self.btn_parent = self._flat_btn(bar, "家长", self.open_parent, width=6)
        self.btn_parent.pack(side="right", padx=T.px(6))

        self.btn_pomo = self._flat_btn(bar, "开始番茄学习", self.toggle_pomodoro,
                                       width=13, primary=True)
        self.btn_pomo.pack(side="right", padx=T.px(6))

    def _flat_btn(self, parent, text, cmd, width=10, primary=False):
        b = tk.Button(parent, text=text, command=cmd, width=width, font=T.FONT_UI_B,
                      relief="flat", bd=0, cursor="hand2",
                      padx=T.px(8), pady=T.px(7),
                      bg=T.ACCENT if primary else "#e8edf5",
                      fg=T.WHITE if primary else T.INK,
                      activebackground=T.ACCENT_D if primary else "#dbe4f0",
                      activeforeground=T.WHITE if primary else T.INK)
        b._primary = primary

        def hover(on):
            if str(b.cget("state")) == "disabled":
                return                       # 停用的按钮不跟着变色
            if primary:
                b.configure(bg=T.ACCENT_D if on else T.ACCENT)
            else:
                b.configure(bg="#dbe4f0" if on else "#e8edf5")

        b.bind("<Enter>", lambda e: hover(True))
        b.bind("<Leave>", lambda e: hover(False))
        return b

    def _paint_btn(self, b, primary):
        b._primary = primary
        b.configure(bg=T.ACCENT if primary else "#e8edf5",
                    fg=T.WHITE if primary else T.INK)

    # ------------------------------------------------------------------ 主体
    def _build_body(self):
        body = tk.Frame(self.root, bg=T.BG)
        body.pack(fill="both", expand=True)

        # ---- 左侧课程树 ----
        side = tk.Frame(body, bg=T.SIDEBAR, width=T.px(258))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        sh = tk.Frame(side, bg=T.SIDEBAR)
        sh.pack(fill="x", padx=T.px(18), pady=(T.px(18), T.px(8)))
        tk.Label(sh, text="课程列表", font=T.FONT_H2, bg=T.SIDEBAR,
                 fg=T.INK).pack(anchor="w")
        tk.Label(sh, text="★ = 已经拿到的成绩", font=T.FONT_SM, bg=T.SIDEBAR,
                 fg=T.MUTED).pack(anchor="w", pady=(T.px(3), 0))

        wrap = tk.Frame(side, bg=T.SIDEBAR)
        wrap.pack(fill="both", expand=True, padx=(T.px(14), 0), pady=(0, T.px(14)))
        self.tree = ttk.Treeview(wrap, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("group", font=T.FONT_UI_B, foreground=T.MUTED)
        self.tree.tag_configure("done", foreground=T.OK)
        self.tree.tag_configure("cur", background="#d9e6ff", foreground=T.ACCENT_D)
        self._loading = False
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        tk.Frame(body, bg=T.LINE, width=T.px(1)).pack(side="left", fill="y")

        # ---- 右侧练习区 ----
        main = tk.Frame(body, bg=T.BG)
        main.pack(side="left", fill="both", expand=True)

        # 上下两条弹性垫片，让内容在窗口里垂直居中；
        # content 不 fill，宽度取最宽的子块（通常就是键盘），整块再水平居中
        tk.Frame(main, bg=T.BG).pack(expand=True)
        content = tk.Frame(main, bg=T.BG)
        content.pack()
        tk.Frame(main, bg=T.BG).pack(expand=True)

        # 标题行
        self.head = tk.Frame(content, bg=T.BG)
        self.head.pack(fill="x", padx=T.px(28), pady=(0, T.px(10)))
        self.lbl_title = tk.Label(self.head, text="", font=T.FONT_H1, bg=T.BG, fg=T.INK)
        self.lbl_title.pack(side="left")
        self.lbl_stars = tk.Label(self.head, text="",
                                  font=("Microsoft YaHei UI", 18, "bold"),
                                  bg=T.BG, fg=T.STAR)
        self.lbl_stars.pack(side="right")

        # 提醒横幅（平时不显示）
        self.banner = tk.Label(content, text="", font=T.FONT_UI_B, bg="#fff3d6",
                               fg="#8a5a00", pady=T.px(7))

        # 打字段卡片
        card = tk.Frame(content, bg=T.CARD, highlightthickness=1,
                        highlightbackground=T.LINE)
        card.pack(fill="x", padx=T.px(28))

        top = tk.Frame(card, bg=T.CARD)
        top.pack(fill="x", padx=T.px(20), pady=(T.px(13), 0))
        self.lbl_progress = tk.Label(top, text="", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED)
        self.lbl_progress.pack(side="left")
        self.lbl_stat = tk.Label(top, text="", font=T.FONT_SM, bg=T.CARD, fg=T.ACCENT)
        self.lbl_stat.pack(side="right")

        self.text_frame = tk.Frame(card, bg=T.CARD)
        self.text_frame.pack(fill="x", padx=T.px(20), pady=(T.px(10), T.px(16)))

        self.lbl_info = tk.Label(card, text="", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED)
        self.lbl_info.pack(pady=(0, T.px(12)))

        # 虚拟键盘 + 手
        kbcard = tk.Frame(content, bg=T.CARD, highlightthickness=1,
                          highlightbackground=T.LINE)
        kbcard.pack(pady=(T.px(13), 0), padx=T.px(28))
        self.kb = VirtualKeyboard(kbcard, scale=self._ui["kb"])
        self.kb.pack(padx=T.px(16), pady=(T.px(12), T.px(14)))

        # 操作按钮
        ops = tk.Frame(content, bg=T.BG)
        ops.pack(pady=(T.px(15), 0))
        self._flat_btn(ops, "重打本组", self.restart_row, width=10).pack(side="left", padx=T.px(5))
        self._flat_btn(ops, "换一组题", self.reshuffle, width=10).pack(side="left", padx=T.px(5))
        self._flat_btn(ops, "下一课 →", self.skip_lesson, width=10).pack(side="left", padx=T.px(5))

    # ------------------------------------------------------------------ 锁屏
    def _build_lock(self):
        self.lock = tk.Frame(self.root, bg="#12203a")

        # ---- ① 番茄休息 ----
        self.lock_break = tk.Frame(self.lock, bg="#12203a")
        inner = tk.Frame(self.lock_break, bg="#12203a")
        inner.pack()

        tk.Label(inner, text="该休息啦！", font=("Microsoft YaHei UI", 46, "bold"),
                 bg="#12203a", fg="#ffd76a").pack(pady=(0, T.px(6)))
        self.lbl_lock_time = tk.Label(inner, text="05:00", font=("Consolas", 76, "bold"),
                                      bg="#12203a", fg="#ffffff")
        self.lbl_lock_time.pack()
        self.lbl_lock_hint = tk.Label(inner, text="再等 5 分钟", font=T.FONT_UI,
                                      bg="#12203a", fg="#8fa8cc")
        self.lbl_lock_hint.pack(pady=(T.px(4), T.px(24)))

        tips = ("离开椅子，站起来走两步\n"
                "看看窗外远处的东西，让眼睛歇一会儿\n"
                "喝口水，伸伸胳膊")
        tk.Label(inner, text=tips, font=("Microsoft YaHei UI", 15), bg="#12203a",
                 fg="#cfe0ff", justify="center").pack(pady=(0, T.px(30)))

        tk.Button(inner, text="家长：提前结束休息", font=T.FONT_SM, relief="flat",
                  bd=0, bg="#1d3055", fg="#7f97bd", activebackground="#26406e",
                  activeforeground="#cfe0ff", cursor="hand2",
                  padx=T.px(12), pady=T.px(6),
                  command=self._skip_break).pack()

        # ---- ② 今日额度用完（暖色，跟休息的冷色明显区分）----
        self.lock_limit = tk.Frame(self.lock, bg=T.LOCK_LIMIT_BG)
        inner2 = tk.Frame(self.lock_limit, bg=T.LOCK_LIMIT_BG)
        inner2.pack()

        tk.Label(inner2, text="今天的练习时间用完啦",
                 font=("Microsoft YaHei UI", 44, "bold"),
                 bg=T.LOCK_LIMIT_BG, fg=T.LOCK_LIMIT_HEAD).pack(pady=(0, T.px(12)))
        self.lbl_limit_used = tk.Label(inner2, text="", font=("Microsoft YaHei UI", 24),
                                       bg=T.LOCK_LIMIT_BG, fg=T.LOCK_LIMIT_TEXT)
        self.lbl_limit_used.pack(pady=(0, T.px(22)))

        tk.Label(inner2, text="练了这么久，该让眼睛歇歇了。\n"
                              "明天 0 点时间会重新回来，明天接着练。",
                 font=("Microsoft YaHei UI", 17), bg=T.LOCK_LIMIT_BG,
                 fg=T.LOCK_LIMIT_SUB, justify="center").pack(pady=(0, T.px(34)))

        tk.Button(inner2, text="家长解锁", font=T.FONT_UI_B, relief="flat",
                  bd=0, bg=T.LOCK_LIMIT_BTN, fg=T.LOCK_LIMIT_BTNF,
                  activebackground="#5a3826", activeforeground="#f0c9a8",
                  cursor="hand2", padx=T.px(14), pady=T.px(7),
                  command=self._limit_unlock).pack()

    def _show_lock(self, seconds=0, mode="break"):
        self._lock_mode = mode
        if mode == "break":
            self.lock.configure(bg="#12203a")          # 冷色 = 只是休息一下
            self.lock_limit.pack_forget()
            self.lock_break.pack(expand=True)
        else:
            self.lock.configure(bg=T.LOCK_LIMIT_BG)    # 暖色 = 今天到此为止
            self.lock_break.pack_forget()
            self.lock_limit.pack(expand=True)
        self.lock.place(x=0, y=0, relwidth=1, relheight=1)
        self.lock.lift()
        self.root.focus_force()

    def _hide_lock(self):
        self.lock.place_forget()
        self._lock_mode = None

    # ------------------------------------------------------------------ 事件绑定
    def _bind_keys(self):
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Escape>", lambda e: "break")
        self.root.bind("<Tab>", lambda e: "break")
        self.root.bind("<Control-w>", lambda e: "break")
        self.root.bind("<F11>", lambda e: "break")
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.root.bind("<Alt-F4>", self.on_exit)
        self.root.bind("<Control-Alt-q>", self.on_exit)

    def _on_key(self, event):
        if self._limit_locked or self.pomo["state"] == "break":
            return "break"                       # 锁屏中，输入全部吃掉
        if self._busy:
            return "break"
        ch = event.char
        if not ch or ord(ch) > 126:
            return "break"                       # 方向键/回车/退格/中文输入法
        if event.keysym in ("BackSpace", "Delete", "Return", "Tab", "Escape"):
            return "break"
        if self.lesson is None:
            return "break"
        self._type_char(ch)
        return "break"

    # ------------------------------------------------------------------ 课程树
    def refresh_tree(self):
        self._loading = True
        sel = self.lesson["id"] if self.lesson else None
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        for gname, lessons in courses.groups():
            self.tree.insert("", "end", text=gname, open=True, tags=("group",))
            g = self.tree.get_children("")[-1]
            for les in lessons:
                stars = self.store.stars_of(les["id"])
                tags = []
                if stars >= 3:
                    tags.append("done")
                if les["id"] == sel:
                    tags.append("cur")
                label = les["title"]
                if stars:
                    label += "   " + courses.star_text(stars)
                self.tree.insert(g, "end", iid=les["id"], text=label, tags=tuple(tags))
        if sel and self.tree.exists(sel):
            self.tree.selection_set(sel)
        self._loading = False

    def _on_tree_select(self, _e=None):
        if self._loading:
            return
        s = self.tree.selection()
        if not s:
            return
        iid = s[0]
        if iid not in courses.LESSON_BY_ID:
            return
        # 已经在上的课就别重开（Treeview 的选中事件是异步的，不判断会自我循环）
        if self.lesson is not None and iid == self.lesson["id"]:
            return
        self._open_lesson(iid)

    # ------------------------------------------------------------------ 开课
    def _sync_tree_selection(self, lesson_id):
        if not self.tree.exists(lesson_id):
            return
        self._loading = True
        self.tree.selection_set(lesson_id)
        self.tree.see(lesson_id)
        self._loading = False

    def _open_lesson(self, lesson_id):
        self.lesson = courses.LESSON_BY_ID[lesson_id]
        self.variant = 0
        self.lbl_title.configure(text=self.lesson["title"])
        self.lbl_info.configure(text=self.lesson.get("note", ""))
        self._paint_stars()

        if self.lesson["kind"] == "info":
            self.lbl_progress.configure(text="先看一遍，然后开始")
            self.lbl_stat.configure(text="")
            self.lbl_stars.configure(text="")
            self.kb.clear_highlight()
            self._render_info(self.lesson["text"])
            self._sync_tree_selection(lesson_id)
            return

        self._reset_stats()
        self.rows = courses.make_rows(self.lesson, self.variant)

        if self.lesson["kind"] == "game":
            self.game_end = time.monotonic() + self.lesson.get("seconds", 45)
            self._game_rng = _Rng(courses._seed_of(lesson_id, 99))
            self._game_rows = [courses.make_game_rows(self.lesson, self._game_rng)
                               for _ in range(200)]
            self.rows = self._game_rows
        elif self.lesson.get("dedup", True):
            # 内置练习课：去掉重复行；家长导入的题库不能去重（每一遍都要留）
            seen, uniq = set(), []
            for r in self.rows:
                if r in seen:
                    continue
                seen.add(r)
                uniq.append(r)
            self.rows = uniq or self.rows

        self.row_idx = 0
        self.char_idx = 0
        self.finished = False
        self._view_start = 0
        self._render_rows()
        self._sync_tree_selection(lesson_id)

    def _paint_stars(self):
        if self.lesson and self.lesson["kind"] != "info":
            n = self.store.stars_of(self.lesson["id"])
            self.lbl_stars.configure(text=courses.star_text(n) if n else "")
        else:
            self.lbl_stars.configure(text="")

    def _render_info(self, text):
        for w in self.text_frame.winfo_children():
            w.destroy()
        self._char_labels = []
        self._row_frames = []
        tk.Label(self.text_frame, text=text, font=("Microsoft YaHei UI", 12),
                 bg=T.CARD, fg=T.INK, justify="left", anchor="w").pack(anchor="w")

    def _reset_stats(self):
        self.correct = 0
        self.wrong = 0
        self._reset_row_timer()

    def _reset_row_timer(self):
        self._row_start = time.monotonic()

    # ------------------------------------------------------------------ 渲染
    def _cur_row(self):
        if not self.rows:
            return None
        return self.rows[self.row_idx % len(self.rows)]

    def _label(self, r, c):
        """屏幕上第 r 行、第 c 个字符的 Label。"""
        i = r - self._view_start
        if 0 <= i < len(self._char_labels):
            labels = self._char_labels[i]
            if 0 <= c < len(labels):
                return labels[c]
        return None

    def _slot_metrics(self):
        """空槽的高度：按字体算，取到大约等于一个字母（大写）那么高。"""
        if not hasattr(self, "_slot_h"):
            from tkinter import font as tkfont
            try:
                f = tkfont.Font(family="Consolas", size=self._ui["mono"][1],
                                weight="bold")
                h = int(f.metrics("ascent") * 0.77)
            except Exception:
                h = T.px(20)
            self._slot_h = max(T.px(8), h)
        return self._slot_h

    def _make_space_cell(self, parent, mode):
        """造一个空格格子。

        关键：里面不写任何字符 —— 只用图形表示"这里有个空位"。
        宽度靠一个和字母格子配置完全相同的空 Label 撑住，所以等宽不会被撑歪。
        """
        cell = tk.Frame(parent, bg=T.CARD, bd=0, highlightthickness=0)
        ruler = tk.Label(cell, text="", font=self._ui["mono"], width=1,
                         bg=T.CARD, padx=0, pady=T.px(2), bd=0,
                         highlightthickness=T.px(1),
                         highlightbackground=T.CARD, highlightcolor=T.CARD)
        ruler.pack()
        slot = tk.Frame(cell, bg=T.SLOT_BG, bd=0, highlightthickness=0)
        if mode == "slot":
            slot.configure(highlightthickness=T.px(1),
                           highlightbackground=T.SLOT_LINE)
        slot.place(x=0, rely=0.5, anchor="w", relwidth=1.0,
                   height=self._slot_metrics())
        cell.pack(side="left")
        return slot

    def _render_rows(self):
        """把这一课的行铺开显示（一屏最多 max_rows 行，跟着当前行滚动）。"""
        for w in self.text_frame.winfo_children():
            w.destroy()
        self._char_labels = []
        self._row_frames = []
        if not self.rows:
            return

        n = len(self.rows)
        maxr = self._ui["rows"]
        if n > maxr:
            self._view_start = max(0, min(self.row_idx - maxr // 2, n - maxr))
        else:
            self._view_start = 0

        mode = self._space_mode()
        for row in self.rows[self._view_start:self._view_start + maxr]:
            fr = tk.Frame(self.text_frame, bg=T.CARD)
            fr.pack(anchor="w", pady=self._ui["gap"])
            cells = []
            for ch in row:
                if ch == " ":
                    cells.append(self._make_space_cell(fr, mode))
                    continue
                lb = tk.Label(fr, text=ch, font=self._ui["mono"], width=1,
                              bg=T.CARD, fg=T.PENDING, padx=0, pady=T.px(2),
                              bd=0, highlightthickness=T.px(1),
                              highlightbackground=T.CARD, highlightcolor=T.CARD)
                lb.pack(side="left")
                cells.append(lb)
            self._row_frames.append(fr)
            self._char_labels.append(cells)

        self._paint()
        self._update_progress_label()
        self._update_stat_label()

    def _display_row(self, i):
        """屏幕上第 i 行对应的内容（i 是在可视区里的下标）。"""
        k = self._view_start + i
        return self.rows[k] if 0 <= k < len(self.rows) else ""

    def _space_mode(self):
        m = self.store.get("space_mode", T.SPACE_MODE_DEFAULT)
        return m if m in T.SPACE_MODES else T.SPACE_MODE_DEFAULT

    def _space_bg(self, done):
        """空格格子该用什么底色。done=True 表示这个空已经打过了。"""
        if self._space_mode() == "slot":
            return T.SLOT_DONE_BG if done else T.SLOT_BG
        return T.BLANK_DONE_BG if done else T.CARD

    @staticmethod
    def _tint(w, fg=None, bg=None):
        """给格子染色。空槽是 Frame，没有 fg，跳过就行。"""
        if bg is not None:
            w.configure(bg=bg)
        if fg is not None:
            try:
                w.configure(fg=fg)
            except Exception:
                pass

    @staticmethod
    def _cell_text(w):
        """格子里显示的字符（空槽是 Frame，本来就没有文字）。"""
        try:
            return str(w.cget("text"))
        except Exception:
            return ""

    def _space_labels(self):
        """当前显示出来的所有空格格子（自查用）。"""
        out = []
        for i, labels in enumerate(self._char_labels):
            row = self._display_row(i)
            for j, lb in enumerate(labels):
                if j < len(row) and row[j] == " ":
                    out.append(lb)
        return out

    def _paint(self):
        """按当前进度上色：已打完的淡绿、当前行绿、光标黄底、未打到的灰。

        空格没有字符可以染绿，所以改染"格子底色"：
        空槽（浅灰）-> 打过的空槽（浅绿）。进度一样看得见。
        """
        cur = self.row_idx - self._view_start
        for i, cells in enumerate(self._char_labels):
            row = self._display_row(i)
            dim = i < cur
            for j, w in enumerate(cells):
                if j < len(row) and row[j] == " ":
                    self._tint(w, bg=self._space_bg(dim))
                elif dim:
                    self._tint(w, fg=T.OK_DIM, bg=T.CARD)
                else:
                    self._tint(w, fg=T.PENDING, bg=T.CARD)
        if 0 <= cur < len(self._char_labels):
            row = self._display_row(cur)
            for j, w in enumerate(self._char_labels[cur]):
                is_sp = (j < len(row) and row[j] == " ")
                if j < self.char_idx:
                    if is_sp:
                        self._tint(w, bg=self._space_bg(True))
                    else:
                        self._tint(w, fg=T.OK, bg=T.CARD)
                elif j == self.char_idx:
                    if is_sp:
                        self._tint(w, bg=T.CURSOR_BG)
                    else:
                        self._tint(w, fg=T.INK, bg=T.CURSOR_BG)
        row = self._cur_row()
        nxt = row[self.char_idx] if (row and self.char_idx < len(row)) else None
        self.kb.highlight(nxt)

    def _update_progress_label(self):
        row = self._cur_row()
        if self.lesson["kind"] == "game":
            left = max(0, self.game_end - time.monotonic())
            self.lbl_progress.configure(
                text="限时挑战   还剩 %02d 秒   已经打了 %d 组"
                     % (int(left + 0.99), self.row_idx))
        elif row:
            unit = "行" if self.lesson.get("source_set") else "组"
            self.lbl_progress.configure(
                text="第 %d / %d %s      本%s %d 个字符"
                     % (self.row_idx + 1, len(self.rows), unit, unit, len(row)))

    def _update_stat_label(self):
        # 用 2 秒打底，免得刚敲两个字速度就飙到几百
        mins = max(time.monotonic() - self._row_start, 2.0) / 60.0
        cpm = self.correct / mins if self.correct else 0
        total = self.correct + self.wrong
        acc = (self.correct / total * 100) if total else 100.0
        self.lbl_stat.configure(
            text="正确率 %.0f%%      速度 %.0f 字/分      打错 %d 次"
                 % (acc, cpm, self.wrong))

    # ------------------------------------------------------------------ 打字逻辑
    def _type_char(self, ch):
        self._last_activity = time.monotonic()   # 活跃窗口：真的在打字才计时长
        row = self._cur_row()
        if row is None or self.char_idx >= len(row):
            return
        target = row[self.char_idx]
        ok = ch.lower() == target.lower()
        lb = self._label(self.row_idx, self.char_idx)
        if ok:
            self.correct += 1
            if lb:
                self._tint(lb, fg=T.OK, bg=T.CARD)
            self.char_idx += 1
            self._paint()
            self._update_stat_label()
            if self.char_idx >= len(row):
                self._row_complete()
        else:
            self.wrong += 1
            if lb:
                self._tint(lb, fg=T.WHITE, bg=T.BAD)
                self.root.after(170, lambda: self._tint(lb, fg=T.INK, bg=T.CURSOR_BG))
            self._beep(SND_WRONG)
            self._update_stat_label()
            if not self.store.get("strict", True):
                self.char_idx += 1
                self._paint()

    def _row_complete(self):
        self._busy = True
        self._beep(SND_ROW)
        self.row_idx += 1
        self.char_idx = 0          # 必须归零：否则下一行从旧列号开始，直接打不进去
        self._reset_row_timer()
        self.root.after(150, self._after_row)

    def _after_row(self):
        self._busy = False
        if self.lesson["kind"] == "game" and time.monotonic() >= self.game_end:
            self._finish(True)
            return
        if self.row_idx >= len(self.rows):
            self._finish(True)
            return
        # 当前行滑出可视区就整屏重排，否则只更新颜色
        if self.row_idx - self._view_start >= self._ui["rows"]:
            self._render_rows()
        else:
            self._paint()
            self._update_progress_label()

    # ------------------------------------------------------------------ 结束
    def _finish(self, finished):
        if self.finished:
            return
        self.finished = True
        self.kb.clear_highlight()
        elapsed = max(time.monotonic() - self._row_start, 0.001)
        total = self.correct + self.wrong
        acc = (self.correct / total) if total else 0.0
        cpm = self.correct / max(elapsed / 60.0, 1e-6)
        stars = courses.stars_for(acc, cpm, finished, self.lesson["kind"])

        self.store.record(self.lesson["id"], stars, acc, cpm, int(elapsed),
                          last_row_counts=self.correct)
        self.refresh_tree()
        self._paint_stars()
        self._beep(SND_DONE)
        self.lbl_stat.configure(text="")
        self._show_result(stars, acc, cpm)

    def _show_result(self, stars, acc, cpm):
        dlg = tk.Toplevel(self.root)
        dlg.title("成绩")
        dlg.configure(bg=T.CARD)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        self.root.update_idletasks()
        w, h = T.px(440), T.px(340)
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        dlg.geometry("%dx%d+%d+%d" % (w, h, x, y))
        dlg.grab_set()

        tk.Label(dlg, text="这一课打完啦！", font=T.FONT_H2, bg=T.CARD,
                 fg=T.INK).pack(pady=(T.px(26), T.px(2)))
        tk.Label(dlg, text="★" * stars + "☆" * (3 - stars),
                 font=("Microsoft YaHei UI", 40), bg=T.CARD, fg=T.STAR).pack(pady=T.px(6))
        tk.Label(dlg, text="正确率 %.0f%%        速度 %.0f 字/分" % (acc * 100, cpm),
                 font=T.FONT_UI_B, bg=T.CARD, fg=T.ACCENT).pack(pady=T.px(4))
        if stars < 3:
            tk.Label(dlg, text="再打一遍，瞄准三颗星！", font=T.FONT_SM,
                     bg=T.CARD, fg=T.MUTED).pack(pady=(0, T.px(8)))

        def close(go_next):
            dlg.grab_release()
            dlg.destroy()
            if go_next:
                self.next_lesson()
            else:
                self._open_lesson(self.lesson["id"])

        row = tk.Frame(dlg, bg=T.CARD)
        row.pack(pady=T.px(18))
        b1 = tk.Button(row, text="再打一遍", font=T.FONT_UI_B, width=10, relief="flat",
                       bd=0, bg="#e8edf5", fg=T.INK, cursor="hand2",
                       padx=T.px(8), pady=T.px(7), command=lambda: close(False))
        b1.pack(side="left", padx=T.px(6))
        b2 = tk.Button(row, text="下一课", font=T.FONT_UI_B, width=10, relief="flat",
                       bd=0, bg=T.ACCENT, fg=T.WHITE, cursor="hand2",
                       padx=T.px(8), pady=T.px(7), command=lambda: close(True))
        b2.pack(side="left", padx=T.px(6))
        b2.focus_set()

    # ------------------------------------------------------------------ 按钮动作
    def restart_row(self):
        if self.lesson is None or self.lesson["kind"] == "info" or self.finished:
            return
        if self._busy_locked():
            return
        self.char_idx = 0
        self._render_rows()

    def reshuffle(self):
        if self.lesson is None or self.lesson["kind"] != "drill":
            return
        if self._busy_locked():
            return
        self.variant += 1
        self._open_lesson(self.lesson["id"])

    def skip_lesson(self):
        if self._busy_locked() or self.lesson is None:
            return
        self.next_lesson()

    def next_lesson(self):
        ids = [l["id"] for l in courses.LESSONS]
        try:
            i = ids.index(self.lesson["id"])
        except ValueError:
            i = 0
        if i + 1 < len(ids):
            self._open_lesson(ids[i + 1])
            for g in self.tree.get_children(""):
                if self.tree.parent(ids[i + 1]) == g:
                    self.tree.item(g, open=True)
            self.tree.see(ids[i + 1])
        else:
            self._open_lesson(ids[0])

    # ------------------------------------------------------------------ 番茄钟
    def toggle_pomodoro(self):
        if not self.store.pomodoro["enabled"]:
            self._flash_banner("番茄钟已被家长关闭（家长 → 时间管理 里可以打开）", 4000)
            self.root.focus_force()
            return
        if self._limit_locked:
            return
        if self.pomo["state"] == "off":
            p = self.store.pomodoro
            self.pomo.update(state="work", end=time.monotonic() + p["work"] * 60,
                             warned=False, cycles=self.pomo.get("cycles", 0) + 1)
            self._last_sec = None
            self._paint_btn(self.btn_pomo, False)
            self.btn_pomo.configure(text="停止番茄（需密码）")
            self.lbl_pomo.configure(text="专注中  %02d:00" % p["work"], fg=T.ACCENT)
            self._flash_banner("番茄学习开始，专心打 %d 分钟！" % p["work"], 4000)
            self._beep([(784, 80), (1046, 110)])
        else:
            if dialogs.ask_password(self.root, self.store, "停止番茄模式",
                                    "停止番茄模式需要管理密码："):
                self._stop_pomodoro(toast="番茄模式已停止")
        self.root.focus_force()

    def _stop_pomodoro(self, toast=None):
        self.pomo.update(state="off", end=0.0, warned=False)
        if self._limit_locked:
            self._show_lock(0, "limit")      # 额度锁优先级更高，别顺手解开
        else:
            self._hide_lock()
        self._sync_pomo_button()
        self.lbl_pomo.configure(
            text="番茄钟：未开启" if self.store.pomodoro["enabled"] else "番茄钟：家长已关闭",
            fg=T.MUTED)
        if toast:
            self._flash_banner(toast, 3000)

    def _start_break(self):
        mins = self.store.pomodoro["break"]
        self.pomo.update(state="break", end=time.monotonic() + mins * 60)
        self._last_sec = None
        self._show_lock(mins * 60, "break")
        self._beep([(880, 160), (660, 160), (523, 260)])
        self.banner.pack_forget()

    def _skip_break(self):
        if dialogs.ask_password(self.root, self.store, "提前结束休息",
                                "提前结束休息需要管理密码："):
            self._end_break()
        self.root.focus_force()

    def _end_break(self):
        mins = self.store.pomodoro["work"]
        self.pomo.update(state="work", end=time.monotonic() + mins * 60, warned=False)
        self._last_sec = None
        # 额度用完优先级更高：休息结束也不能顺手把额度锁解开
        if self._limit_locked:
            self._show_lock(0, "limit")
        else:
            self._hide_lock()
            self._flash_banner("休息结束，继续加油！再来 %d 分钟。" % mins, 4000)
        self._beep([(1046, 80), (1319, 90), (1568, 130)])

    # ------------------------------------------------------------------ 每日额度
    def _busy_locked(self):
        """锁屏中（休息 或 今日额度用完）—— 练习相关操作一律不给用。"""
        return self._limit_locked or self.pomo["state"] == "break"

    def _sync_pomo_button(self):
        """番茄开关被家长关掉时，按钮就停用。"""
        if not self.store.pomodoro["enabled"]:
            self.btn_pomo.configure(state="disabled", text="番茄钟已关闭",
                                    bg="#eef1f6", fg=T.MUTED)
            self.lbl_pomo.configure(text="番茄钟：家长已关闭", fg=T.MUTED)
        else:
            self.btn_pomo.configure(state="normal")
            if self.pomo["state"] == "off":
                self._paint_btn(self.btn_pomo, True)
                self.btn_pomo.configure(text="开始番茄学习")
                self.lbl_pomo.configure(text="番茄钟：未开启", fg=T.MUTED)
            else:
                self._paint_btn(self.btn_pomo, False)
                self.btn_pomo.configure(text="停止番茄（需密码）")

    def _update_limit_ui(self):
        """顶栏「今日剩余」+ 三档提醒（10 分钟变橙 / 5 分钟横幅 / 1 分钟响铃）。"""
        info = self.store.usage_info()
        self._limit_info = info
        left = info["left"]

        if left is None:
            if info["enabled"]:
                self.lbl_limit.configure(text="今日不限制", fg=T.LIMIT_NORMAL)
            else:
                self.lbl_limit.configure(text="")      # 没开就别占地方
            self._limit_marks.clear()
            return

        if left >= 3600:
            txt = "今日剩余 %d 小时 %02d 分" % (left // 3600, (left % 3600) // 60)
        elif left >= 60:
            txt = "今日剩余 %d 分钟" % ((left + 59) // 60)
        else:
            txt = "今日剩余 %d 秒" % left
        color = T.LIMIT_NORMAL if left > 600 else (
            T.LIMIT_LOW if left > 60 else T.LIMIT_OUT)
        self.lbl_limit.configure(text=txt, fg=color)

        if left <= 300 and not self._limit_marks.get("m5"):
            self._limit_marks["m5"] = True
            self._flash_banner("今天的练习时间还剩 5 分钟，把这组打完就收工啦～", 8000)
        if left <= 60 and not self._limit_marks.get("m1"):
            self._limit_marks["m1"] = True
            self._beep(SND_WARN)
        if left <= 0 and not self._limit_locked:
            self._lock_for_limit()

    def _check_limit_on_start(self):
        """启动先查：今天要是已经用完，直接锁屏 —— 重启也续不了命。"""
        info = self.store.usage_info()
        if info["left"] is not None and info["left"] <= 0:
            self._lock_for_limit()
            return True
        return False

    def _lock_for_limit(self):
        self._limit_locked = True
        info = self.store.usage_info()
        self.lbl_limit_used.configure(
            text="今天已经练了 %s" % dialogs.fmt_dur(info["used"]))
        self.kb.clear_highlight()
        self._show_lock(0, "limit")
        self._beep([(523, 200), (415, 200), (330, 320)])

    def _limit_unlock(self):
        """家长解锁：先验密码，再定今天还能再用多久。"""
        if not dialogs.ask_password(self.root, self.store, "解锁练习时间",
                                    "解锁需要管理密码："):
            self.root.focus_force()
            return
        used = self.store.usage_info()["used"]
        res = dialogs.limit_grant_dialog(self.root, self.store, used)
        self.root.focus_force()
        if not res.get("done"):
            return
        self.store.grant_usage(res.get("seconds"))
        self._limit_locked = False
        self._quota_pending = 0.0
        self._limit_marks.clear()
        self._hide_lock()
        left = self.store.usage_info()["left"]
        self._flash_banner(
            "已解锁。今天不再限制练习时间。" if left is None
            else "已解锁。今天还能再练 %s。" % dialogs.fmt_dur(left), 6000)
        self._update_limit_ui()
        self._beep([(784, 90), (1046, 120)])

    def _accrue_usage(self, dt, now):
        """每日额度累计 —— 只有「真的在打字」才算。

        活跃窗口：每次按键刷新一次，窗口内持续计时；超过 idle_grace_sec 没按键就暂停。
        发呆、休息、挂机、翻看说明页都不扣时间。
        """
        if self.selftest or self._limit_locked:
            return
        if self.pomo["state"] == "break":
            return
        if not self.store.daily_limit["enabled"]:
            return
        if (now - self._last_activity) > self.store.daily_limit["idle_grace_sec"]:
            return
        self._quota_pending += dt
        if self._quota_pending >= 5.0:
            n = int(self._quota_pending)
            self.store.add_usage(n)
            self._quota_pending -= n

    # ------------------------------------------------------------------ 主循环
    def _tick(self):
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now

        # 跨天（自然日 0 点）：额度回满，额度锁屏自动解除
        if self.store.roll_day():
            self._limit_locked = False
            self._limit_marks.clear()
            if self._lock_mode == "limit":
                self._hide_lock()

        # 练习时长 / 每日额度：都只在「真的在打字」时累计
        active = (not self.selftest and not self._limit_locked
                  and self.pomo["state"] != "break"
                  and (now - self._last_activity)
                  <= self.store.daily_limit["idle_grace_sec"])
        if active:
            self._pending_seconds += dt
            if self._pending_seconds >= 60:
                n = int(self._pending_seconds)
                self.store.add_seconds(n)
                self._pending_seconds -= n
        self._accrue_usage(dt, now)
        self._update_limit_ui()

        state = self.pomo["state"]
        if state == "work":
            left = self.pomo["end"] - now
            sec = int(left + 0.99)
            if left <= 0:
                self._start_break()
            else:
                if left <= 60 and not self.pomo["warned"]:
                    self.pomo["warned"] = True
                    self._beep(SND_WARN)
                    self._flash_banner("还有 1 分钟！把这一组打完就准备休息啦～", 8000)
                if left <= 10 and sec != self._last_sec:
                    self._beep([(1200, 45)])
                self._last_sec = sec
                self.lbl_pomo.configure(
                    text="专注中  %02d:%02d" % (sec // 60, sec % 60),
                    fg=T.BAD if left <= 60 else T.ACCENT)
        elif state == "break":
            left = self.pomo["end"] - now
            sec = int(left + 0.99)
            if left <= 0:
                self._end_break()
            else:
                if sec != self._last_sec:
                    self.lbl_lock_time.configure(text="%02d:%02d" % (sec // 60, sec % 60))
                    self.lbl_lock_hint.configure(text="再等 %d 分 %02d 秒" % (sec // 60, sec % 60))
                    self._last_sec = sec
                self.lbl_pomo.configure(
                    text="休息中  %02d:%02d" % (sec // 60, sec % 60), fg=T.WARN)

        if self.lesson and self.lesson["kind"] == "game" and not self.finished \
                and self.pomo["state"] != "break":
            if now >= self.game_end:
                self._finish(True)
            else:
                self._update_progress_label()

        if self.lesson and self.lesson["kind"] != "info" and not self.finished \
                and self.pomo["state"] != "break":
            self._update_stat_label()

        self.root.after(200, self._tick)

    # ------------------------------------------------------------------ 提示条
    def _flash_banner(self, text, ms=4000):
        self.banner.configure(text=text)
        self.banner.pack(fill="x", padx=T.px(28), pady=(T.px(10), 0), after=self.head)
        job = getattr(self, "_banner_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._banner_job = self.root.after(ms, self.banner.pack_forget)

    # ------------------------------------------------------------------ 音效
    def _beep(self, seq):
        if not self.store.get("sound", True) or winsound is None:
            return

        def run():
            try:
                for f, d in seq:
                    winsound.Beep(int(f), int(d))
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ 全屏 / 家长 / 退出
    def _apply_fullscreen(self):
        try:
            self.root.attributes("-fullscreen", bool(self.store.get("fullscreen", True)))
        except Exception:
            pass

    def open_parent(self):
        if self._busy_locked():
            return
        if not dialogs.ask_password(self.root, self.store, "家长面板", "请输入管理密码："):
            return
        dialogs.parent_panel(self.root, self.store,
                             on_reset=self.refresh_tree,
                             on_changed=self._on_settings_changed,
                             on_content=self._reload_content)
        self.root.focus_force()

    def _reload_content(self):
        """家长改了题库 -> 重建课程表 + 刷新左侧列表。"""
        try:
            self.store.scan_content_folder()
        except Exception:
            pass
        courses.rebuild(self.store.content_sets, self._max_cols)
        self.refresh_tree()
        cur = self.lesson["id"] if self.lesson else None
        if not cur or cur not in courses.LESSON_BY_ID:
            self._open_lesson(courses.LESSONS[0]["id"])

    def _on_settings_changed(self):
        """家长改了设置 -> 立刻重画（空格显示、番茄开关、额度都要马上生效）。"""
        self._sync_pomo_button()
        self._update_limit_ui()
        if self.lesson and self.lesson["kind"] != "info" and self.rows:
            self._render_rows()

    def on_exit(self, _event=None):
        if self._busy:
            return "break"
        if dialogs.ask_password(self.root, self.store, "退出程序",
                                "退出程序需要管理密码，"):
            self._shutdown()
        self.root.focus_force()
        return "break"

    def _shutdown(self):
        try:
            if self._pending_seconds > 0:
                self.store.add_seconds(int(self._pending_seconds))
                self._pending_seconds = 0.0
            if self._quota_pending >= 1:          # 额度也落一下盘，别丢
                self.store.add_usage(int(self._quota_pending))
                self._quota_pending = 0.0
            self.store.save_progress()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------ 启动
    def run(self):
        self.root.mainloop()


class _Rng:
    """极简可复现随机数（避免依赖 random 的内部实现）。"""

    def __init__(self, seed):
        self.s = (seed or 1) & 0xFFFFFFFF

    def choice(self, seq):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return seq[self.s % len(seq)]


def main(argv=None):
    """入口。--selftest 自检；--debug 自检并把日志写到文件（给无控制台的 exe 用）。"""
    argv = argv if argv is not None else sys.argv
    selftest = ("--selftest" in argv) or ("--debug" in argv)
    log_to_file = "--debug" in argv

    try:                                          # 高分屏清晰一点
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    import traceback
    from .store import base_dir

    if not selftest:
        try:
            app = App(selftest=False)
            app.run()
            return 0
        except Exception:
            tb = traceback.format_exc()
            # 无控制台的 exe 出错就什么都没了，留个 crash.log
            try:
                with open(os.path.join(base_dir(), "crash.log"), "a",
                          encoding="utf-8") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + tb + "\n\n")
            except Exception:
                pass
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "出错了", "程序遇到问题，详情见程序目录下的 crash.log：\n\n"
                              + tb[-700:])
            except Exception:
                pass
            return 1

    import tempfile
    from . import store as _store
    _store.set_data_dir(os.path.join(tempfile.gettempdir(), "tkid_selftest_data"))
    lines = []

    def say(msg):
        lines.append(msg)
        try:
            print(msg, flush=True)
        except Exception:
            pass

    say("selftest start")
    say("frozen=%s" % getattr(sys, "frozen", False))
    say("executable=%s" % sys.executable)
    say("base_dir=%s" % base_dir())

    app = None
    rc = 0
    try:
        app = App(selftest=True)
        for _ in range(6):
            app.root.update()
        say("ui built")

        # 遍历所有课程：渲染 + 模拟输入
        bad = []
        for les in courses.LESSONS:
            try:
                app._open_lesson(les["id"])
                app.root.update()
                if les["kind"] != "info":
                    for ch in app.rows[0]:
                        app._type_char(ch)
                    app.root.update()
            except Exception as e:
                bad.append((les["id"], repr(e)))
        say("lessons=%d  errors=%d" % (len(courses.LESSONS), len(bad)))
        for b in bad:
            say("  ERR %s %s" % b)
        if bad:
            raise AssertionError("有课程打不开")

        # 回归测试：第一行打完，第二行必须能接着打（char_idx 要归零）
        app._open_lesson(courses.LESSONS[1]["id"])
        for ch in app.rows[0]:
            app._type_char(ch)
        time.sleep(0.3)
        app.root.update()
        ok = (app.row_idx == 1 and app.char_idx == 0)
        before = app.correct
        app._type_char(app.rows[1][0])
        if app.correct != before + 1:
            ok = False
        say("row advance ok=%s (row=%d col=%d)" % (ok, app.row_idx, app.char_idx))
        if not ok:
            raise AssertionError("打完第一行后第二行打不了")

        # 家长导入的题库：单词 + 长句子（要能自动折行）
        st = app.store.add_content_set(
            "自检题库",
            ["cat dog", "i like my book",
             "the quick brown fox jumps over the lazy dog"],
            repeats=2)
        courses.rebuild(app.store.content_sets, app._max_cols)
        app.refresh_tree()
        ul = [l for l in courses.LESSONS if l.get("source_set") == st["id"]]
        say("user lessons=%d max_cols=%d first_rows=%s"
            % (len(ul), app._max_cols, ul[0]["rows"][:2] if ul else None))
        if not ul:
            raise AssertionError("导入的题库没有变成课程")
        if max(len(r) for r in ul[0]["rows"]) > app._max_cols:
            raise AssertionError("长句子没有折行")
        app._open_lesson(ul[0]["id"])
        app.root.update()
        for ch in app.rows[0]:
            app._type_char(ch)
        time.sleep(0.3)
        app.root.update()
        say("user lesson rows=%d  row0 typed ok col=%d" % (len(app.rows), app.char_idx))
        app.store.remove_content_set(st["id"])
        courses.rebuild(app.store.content_sets, app._max_cols)
        app.refresh_tree()

        # 空格的显示方式：任何模式下都不能再用一个"字符"冒充空格
        drill = courses.LESSONS[1]["id"]
        for m in T.SPACE_MODES:
            app.store.set("space_mode", m)
            app._open_lesson(drill)
            app.root.update()
            sp = app._space_labels()
            texts = [app._cell_text(w) for w in sp]
            kinds = sorted(set(w.winfo_class() for w in sp))
            say("space mode=%s cells=%d kinds=%s texts=%s"
                % (m, len(sp), kinds, texts[:4]))
            if not sp:
                raise AssertionError("没有渲染出空格格子")
            if any(t.strip() for t in texts):
                raise AssertionError("空格格子还在显示字符：%s" % texts[:4])
            if any(w.winfo_class() != "Frame" for w in sp):
                raise AssertionError("空格格子不是空槽（又被塞了字符？）")
            # 打过一个空格后，格子底色必须变（进度要看得见）
            want = T.SLOT_DONE_BG if m == "slot" else T.BLANK_DONE_BG
            app._type_char("f")
            app._type_char("f")
            app._type_char(" ")
            app.root.update()
            if not any(w.cget("bg") == want for w in sp):
                raise AssertionError("打完空格后格子底色没变（mode=%s）" % m)
        app.store.set("space_mode", T.SPACE_MODE_DEFAULT)
        say("space display ok")

        # 番茄钟：开始 -> 到点锁屏 -> 休息结束
        app._open_lesson(courses.LESSONS[1]["id"])
        app.toggle_pomodoro()
        app.pomo["end"] = time.monotonic() - 1
        time.sleep(0.35)                  # 等 _tick 的 200ms 定时器到点
        app.root.update()
        say("pomodoro work->break state=%s lock=%s"
            % (app.pomo["state"], bool(app.lock.winfo_ismapped())))
        if app.pomo["state"] != "break":
            raise AssertionError("番茄钟没有切换到休息")
        app._end_break()
        app.root.update()
        say("break->work state=%s lock=%s"
            % (app.pomo["state"], bool(app.lock.winfo_ismapped())))

        # ---- 每日额度：活跃窗口 / 加时 / 跨天 / 锁屏 / 重启拦截 ----
        st = app.store
        st.set_daily_limit(True, 120)
        st.reset_usage_today()
        i0 = st.usage_info()
        say("limit init left=%s used=%s" % (i0["left"], i0["used"]))
        if i0["left"] != 120 * 60:
            raise AssertionError("初始额度不等于 2 小时")

        # 发呆不该扣时间（活跃窗口早就过期）；一直在打字才累计
        app.selftest = False          # 临时放开（tick 这段时间不跑，手动调）
        app._limit_locked = False
        app.pomo["state"] = "off"
        app._last_activity = time.monotonic() - 999
        app._quota_pending = 0.0
        before = st.usage_info()["used"]
        app._accrue_usage(30.0, time.monotonic())
        idle_ok = (st.usage_info()["used"] == before)
        app._last_activity = time.monotonic()
        app._accrue_usage(5.0, time.monotonic())
        used_after = st.usage_info()["used"]
        app.selftest = True
        say("active timing: idle_no_change=%s typing_added=%d"
            % (idle_ok, used_after - before))
        if not idle_ok:
            raise AssertionError("发呆也扣了额度")
        if used_after != before + 5:
            raise AssertionError("打字没有累计额度（%d -> %d）" % (before, used_after))

        # 关掉开关 -> 不限制
        st.set_daily_limit(False, 120)
        if st.usage_info()["left"] is not None:
            raise AssertionError("关掉开关还限额")
        st.set_daily_limit(True, 120)

        # 用完 -> 锁屏；重启也拦得住
        st.reset_usage_today()
        st.add_usage(120 * 60)
        app._update_limit_ui()
        app.root.update()
        say("limit lock: locked=%s mode=%s mapped=%s label=%r"
            % (app._limit_locked, app._lock_mode, bool(app.lock.winfo_ismapped()),
               app.lbl_limit.cget("text")))
        if not app._limit_locked or app._lock_mode != "limit":
            raise AssertionError("额度用完没有锁屏")
        if not app.lock.winfo_ismapped():
            raise AssertionError("额度锁屏没有盖上来")
        import types
        if app._on_key(types.SimpleNamespace(char="f", keysym="f")) != "break":
            raise AssertionError("额度锁屏时按键没有被拦掉")

        app._limit_locked = False
        app._hide_lock()
        if not app._check_limit_on_start():
            raise AssertionError("重启没有拦住（今日额度已用完）")
        say("restart blocked = True")

        # 家长加时：今天还能再用 30 分钟
        app._limit_locked = False
        app._hide_lock()
        st.grant_usage(30 * 60)
        app._update_limit_ui()
        app.root.update()
        left = st.usage_info()["left"]
        say("after grant 30min: left=%d locked=%s label=%r"
            % (left, app._limit_locked, app.lbl_limit.cget("text")))
        if left != 30 * 60 or app._limit_locked:
            raise AssertionError("加时没生效")
        if app.lock.winfo_ismapped():
            raise AssertionError("加时后锁屏没解除")

        # 今天不限制
        st.grant_usage(None)
        i2 = st.usage_info()
        say("grant unlimited: left=%s grants=%d" % (i2["left"], i2["grants"]))
        if i2["left"] is not None or i2["grants"] != 2:
            raise AssertionError("「今天不限制」没生效 / 加时次数没记")

        # 跨天 -> 自动回满
        u = st.progress["usage"]
        u["date"] = "2000-01-01"
        u["used_seconds"] = 9999
        u["unlimited"] = True
        if not st.roll_day():
            raise AssertionError("跨天没有归位")
        i3 = st.usage_info()
        say("rollover: used=%d left=%s unlimited=%s grants=%d"
            % (i3["used"], i3["left"], i3["unlimited"], i3["grants"]))
        if i3["used"] or i3["left"] != 120 * 60 or i3["unlimited"] or i3["grants"]:
            raise AssertionError("跨天没有回满")

        # 番茄开关关掉 -> 按钮停用
        st.set_pomodoro(20, 5, enabled=False)
        app._sync_pomo_button()
        if str(app.btn_pomo.cget("state")) != "disabled":
            raise AssertionError("番茄关掉后按钮还能点")
        st.set_pomodoro(20, 5, enabled=True)
        app.pomo["state"] = "off"
        app._sync_pomo_button()
        if str(app.btn_pomo.cget("state")) != "normal":
            raise AssertionError("番茄打开后按钮没恢复")
        say("pomodoro enable/disable ok")

        # 加时对话框能构造
        tk.Misc.wait_window = lambda self, *a, **k: None      # 不让它阻塞
        gd = dialogs.limit_grant_dialog(app.root, st, 3600)
        for w in list(app.root.winfo_children()):
            if w.winfo_class() == "Toplevel":
                try:
                    w.grab_release()
                except Exception:
                    pass
                w.destroy()
        app.root.update()
        say("grant dialog ok done=%s" % gd.get("done"))

        # 收尾：恢复默认（额度默认关闭），别影响后面的用例
        st.set_daily_limit(False, 120)
        app._limit_locked = False
        app._hide_lock()
        app._update_limit_ui()

        # 密码读写
        app.store.set_password("8888")
        say("pwd check ok=%s wrong=%s"
            % (app.store.check_password("8888"), app.store.check_password("8887")))

        # 成绩落盘
        app._finish(True)
        app.root.update()
        say("recorded lessons=%d" % len(app.store.progress.get("lessons", {})))

        if bad:
            rc = 1
            say("SELFTEST FAILED")
        else:
            say("SELFTEST OK")
    except Exception:
        rc = 1
        say("SELFTEST CRASHED")
        say(traceback.format_exc())
    finally:
        try:
            app.root.destroy()
        except Exception:
            pass

    if log_to_file:
        try:
            with open(os.path.join(base_dir(), "selftest.log"), "w",
                      encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass
    return rc
