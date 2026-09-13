# -*- coding: utf-8 -*-
"""各类弹窗：设置/校验密码、番茄参数、家长面板、题库导入。"""

import os
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import theme as T
from . import courses


def _center(dlg, parent, w, h):
    parent.update_idletasks()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    except Exception:
        px = py = 0
        pw, ph = 800, 600
    x = px + max(0, (pw - w) // 2)
    y = py + max(0, (ph - h) // 2)
    dlg.geometry("%dx%d+%d+%d" % (w, h, x, y))


def _modal(parent, title, w, h):
    w, h = T.px(w), T.px(h)
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=T.CARD)
    dlg.resizable(False, False)
    dlg.transient(parent)
    _center(dlg, parent, w, h)
    dlg.protocol("WM_DELETE_WINDOW", lambda: None)   # 不许直接叉掉
    dlg.grab_set()
    dlg.focus_force()
    return dlg


def _btn(parent, text, cmd, primary=False, width=10):
    b = tk.Button(parent, text=text, command=cmd, width=width,
                  font=T.FONT_UI_B, relief="flat", cursor="hand2",
                  bg=T.ACCENT if primary else "#e8edf5",
                  fg=T.WHITE if primary else T.INK,
                  activebackground=T.ACCENT_D if primary else "#dbe4f0",
                  activeforeground=T.WHITE if primary else T.INK,
                  padx=T.px(10), pady=T.px(7), bd=0)
    b.bind("<Enter>", lambda e: b.configure(bg=(T.ACCENT_D if primary else "#dbe4f0")))
    b.bind("<Leave>", lambda e: b.configure(bg=(T.ACCENT if primary else "#e8edf5")))
    return b


# ------------------------------------------------------------ 密码

def ask_password(parent, store, title="需要密码", prompt="请输入管理密码：",
                 allow_cancel=True):
    """弹出密码框，通过返回 True。"""
    result = {"ok": False}
    dlg = _modal(parent, title, 400, 230)

    tk.Label(dlg, text=prompt, font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
             wraplength=T.px(350), justify="left").pack(pady=(T.px(24), T.px(10)), padx=T.px(24), anchor="w")

    var = tk.StringVar()
    ent = tk.Entry(dlg, textvariable=var, show="●", font=("Consolas", 18),
                   width=16, justify="center", relief="flat",
                   highlightthickness=2, highlightbackground=T.LINE,
                   highlightcolor=T.ACCENT)
    ent.pack(pady=T.px(6))
    ent.focus_set()

    msg = tk.Label(dlg, text="", font=T.FONT_SM, bg=T.CARD, fg=T.BAD)
    msg.pack()

    def submit(_e=None):
        if store.check_password(var.get()):
            result["ok"] = True
            dlg.grab_release()
            dlg.destroy()
        else:
            msg.configure(text="密码不对，再试一次")
            var.set("")
            ent.focus_set()

    row = tk.Frame(dlg, bg=T.CARD)
    row.pack(pady=T.px(12))
    _btn(row, "确定", submit, primary=True).pack(side="left", padx=T.px(6))
    if allow_cancel:
        def cancel():
            dlg.grab_release()
            dlg.destroy()
        _btn(row, "取消", cancel).pack(side="left", padx=T.px(6))

    ent.bind("<Return>", submit)
    try:
        parent.wait_window(dlg)
    except Exception:
        pass
    return result["ok"]


def set_password_dialog(parent, store, first_time=False):
    """设置/修改密码。返回是否成功。"""
    result = {"ok": False}
    dlg = _modal(parent, "设置管理密码", 430, 330)

    title = "第一次使用，先设一个管理密码" if first_time else "修改管理密码"
    tk.Label(dlg, text=title, font=T.FONT_H2, bg=T.CARD, fg=T.INK).pack(pady=(T.px(20), T.px(4)))
    tip = ("这个密码是给家长用的：关程序、停番茄、改设置都要它。\n"
           "小朋友不知道密码就退出不了。请自己记牢 —— 程序不存明文。")
    tk.Label(dlg, text=tip, font=T.FONT_SM, bg=T.CARD, fg=T.MUTED,
             justify="left").pack(padx=T.px(24), pady=(T.px(0), T.px(12)), anchor="w")

    if not first_time:
        tk.Label(dlg, text="原密码", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(24))
        old = tk.Entry(dlg, show="●", font=("Consolas", 14), width=22, relief="flat",
                       highlightthickness=1, highlightbackground=T.LINE, highlightcolor=T.ACCENT)
        old.pack(pady=(T.px(2), T.px(8)))
    else:
        old = None

    tk.Label(dlg, text="新密码", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(24))
    n1 = tk.Entry(dlg, show="●", font=("Consolas", 14), width=22, relief="flat",
                  highlightthickness=1, highlightbackground=T.LINE, highlightcolor=T.ACCENT)
    n1.pack(pady=(T.px(2), T.px(8)))

    tk.Label(dlg, text="再输一遍", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(24))
    n2 = tk.Entry(dlg, show="●", font=("Consolas", 14), width=22, relief="flat",
                  highlightthickness=1, highlightbackground=T.LINE, highlightcolor=T.ACCENT)
    n2.pack(pady=(T.px(2), T.px(4)))

    msg = tk.Label(dlg, text="", font=T.FONT_SM, bg=T.CARD, fg=T.BAD)
    msg.pack(pady=T.px(4))
    (n1 if first_time else old).focus_set()

    def submit(_e=None):
        if old is not None and not store.check_password(old.get()):
            msg.configure(text="原密码不对")
            return
        p1, p2 = n1.get(), n2.get()
        if len(p1) < 4:
            msg.configure(text="密码至少 4 位")
            return
        if p1 != p2:
            msg.configure(text="两次输入不一样")
            n2.delete(0, "end")
            return
        store.set_password(p1)
        result["ok"] = True
        dlg.grab_release()
        dlg.destroy()

    row = tk.Frame(dlg, bg=T.CARD)
    row.pack(pady=T.px(8))
    _btn(row, "保存", submit, primary=True).pack(side="left", padx=T.px(6))
    if not first_time:
        def cancel():
            dlg.grab_release()
            dlg.destroy()
        _btn(row, "取消", cancel).pack(side="left", padx=T.px(6))

    for e in (n1, n2) + ((old,) if old else ()):
        e.bind("<Return>", submit)

    parent.wait_window(dlg)
    return result["ok"]


# ------------------------------------------------------------ 番茄参数

def pomodoro_dialog(parent, store):
    """设置工作时间 / 休息时间。返回是否保存。"""
    cfg = store.pomodoro
    result = {"ok": False}
    dlg = _modal(parent, "番茄参数", 400, 300)

    tk.Label(dlg, text="番茄工作法 · 时间设置", font=T.FONT_H2,
             bg=T.CARD, fg=T.INK).pack(pady=(T.px(22), T.px(2)))
    tk.Label(dlg, text="到点会自动锁住屏幕让他休息", font=T.FONT_SM,
             bg=T.CARD, fg=T.MUTED).pack(pady=(T.px(0), T.px(14)))

    body = tk.Frame(dlg, bg=T.CARD)
    body.pack(padx=T.px(30), fill="x")

    def row(label, value, lo, hi, unit="分钟"):
        f = tk.Frame(body, bg=T.CARD)
        f.pack(fill="x", pady=T.px(7))
        tk.Label(f, text=label, font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
                 width=10, anchor="w").pack(side="left")
        var = tk.IntVar(value=value)
        sp = tk.Spinbox(f, from_=lo, to=hi, textvariable=var, width=6,
                        font=("Consolas", 15), justify="center", relief="flat",
                        highlightthickness=1, highlightbackground=T.LINE,
                        highlightcolor=T.ACCENT, buttonbackground="#e8edf5")
        sp.pack(side="left", padx=T.px(6))
        tk.Label(f, text=unit, font=T.FONT_UI, bg=T.CARD, fg=T.MUTED).pack(side="left")
        return var

    work = row("工作时间", cfg.get("work", 20), 1, 120)
    brk = row("休息时间", cfg.get("break", 5), 1, 60)

    hint = tk.Label(dlg, text="（剩 60 秒会提醒他准备休息）", font=T.FONT_SM,
                    bg=T.CARD, fg=T.MUTED)
    hint.pack(pady=(T.px(6), T.px(0)))

    def save():
        try:
            w, b = int(work.get()), int(brk.get())
        except Exception:
            messagebox.showwarning("提示", "请填整数分钟", parent=dlg)
            return
        if w < 1 or b < 1:
            messagebox.showwarning("提示", "时间要大于 0 分钟", parent=dlg)
            return
        store.set_pomodoro(w, b)
        result["ok"] = True
        dlg.grab_release()
        dlg.destroy()

    rowb = tk.Frame(dlg, bg=T.CARD)
    rowb.pack(pady=T.px(16))
    _btn(rowb, "保存", save, primary=True).pack(side="left", padx=T.px(6))
    _btn(rowb, "取消", lambda: (dlg.grab_release(), dlg.destroy())).pack(side="left", padx=T.px(6))

    parent.wait_window(dlg)
    return result["ok"]


# ------------------------------------------------------------ 每日额度

def fmt_dur(sec):
    """把秒数说成人话：2 小时 00 分 / 37 分钟 / 45 秒。"""
    sec = max(0, int(sec))
    h, m = sec // 3600, (sec % 3600) // 60
    if h and m:
        return "%d 小时 %02d 分" % (h, m)
    if h:
        return "%d 小时" % h
    if m:
        return "%d 分钟" % m
    return "%d 秒" % sec


GRANT_PRESETS = [(30 * 60, "30 分钟"), (3600, "1 小时"),
                 (2 * 3600, "2 小时"), (5 * 3600, "5 小时")]


def limit_grant_dialog(parent, store, used_sec):
    """额度用完后的家长解锁：设定今天还能再用多久。

    返回 {"done": bool, "seconds": int|None}
      done=False  -> 取消
      seconds=None -> 今天不限制（只对今天有效）
    """
    result = {"done": False, "seconds": None}
    dlg = _modal(parent, "解锁练习时间", 470, 440)

    tk.Label(dlg, text="今天的练习时间用完啦", font=T.FONT_H2, bg=T.CARD,
             fg=T.BAD).pack(pady=(T.px(20), T.px(2)))
    tk.Label(dlg, text="今天已经练了 %s" % fmt_dur(used_sec), font=T.FONT_UI,
             bg=T.CARD, fg=T.MUTED).pack(pady=(0, T.px(16)))

    body = tk.Frame(dlg, bg=T.CARD)
    body.pack(padx=T.px(32), fill="x")
    tk.Label(body, text="家长解锁 —— 今天还能再用：", font=T.FONT_UI_B,
             bg=T.CARD, fg=T.INK).pack(anchor="w")

    v = tk.StringVar(value=str(3600))
    opts = tk.Frame(body, bg=T.CARD)
    opts.pack(fill="x", pady=(T.px(8), T.px(4)))
    for i, (sec, txt) in enumerate(GRANT_PRESETS):
        tk.Radiobutton(opts, text=txt, variable=v, value=str(sec),
                       font=T.FONT_UI, bg=T.CARD, fg=T.INK,
                       activebackground=T.CARD, selectcolor=T.CARD,
                       anchor="w").grid(row=i // 2, column=i % 2,
                                        sticky="w", padx=T.px(4), pady=T.px(2))
    tk.Radiobutton(opts, text="今天不限制", variable=v, value="none",
                   font=T.FONT_UI, bg=T.CARD, fg=T.INK,
                   activebackground=T.CARD, selectcolor=T.CARD,
                   anchor="w").grid(row=2, column=0, columnspan=2,
                                    sticky="w", padx=T.px(4), pady=T.px(2))

    cf = tk.Frame(body, bg=T.CARD)
    cf.pack(fill="x", pady=(T.px(6), 0))
    tk.Radiobutton(cf, text="自定义", variable=v, value="custom",
                   font=T.FONT_UI, bg=T.CARD, fg=T.INK,
                   activebackground=T.CARD, selectcolor=T.CARD).pack(side="left")
    v_min = tk.IntVar(value=30)
    sp = tk.Spinbox(cf, from_=1, to=720, textvariable=v_min, width=5,
                    font=("Consolas", 13), justify="center", relief="flat",
                    highlightthickness=1, highlightbackground=T.LINE,
                    highlightcolor=T.ACCENT, buttonbackground="#e8edf5",
                    command=lambda: v.set("custom"))
    sp.pack(side="left", padx=T.px(6))
    tk.Label(cf, text="分钟", font=T.FONT_UI, bg=T.CARD, fg=T.MUTED).pack(side="left")

    tk.Label(dlg, text="「今天不限制」只对今天有效，明天照常恢复每天的额度。",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(pady=(T.px(16), 0))

    def ok():
        sel = v.get()
        if sel == "none":
            result["seconds"] = None
        elif sel == "custom":
            try:
                result["seconds"] = max(1, int(v_min.get())) * 60
            except Exception:
                messagebox.showwarning("提示", "请填整数分钟", parent=dlg)
                return
        else:
            result["seconds"] = int(sel)
        result["done"] = True
        dlg.grab_release()
        dlg.destroy()

    rowb = tk.Frame(dlg, bg=T.CARD)
    rowb.pack(pady=T.px(18))
    _btn(rowb, "解锁", ok, primary=True, width=8).pack(side="left", padx=T.px(6))
    _btn(rowb, "取消", lambda: (dlg.grab_release(), dlg.destroy()),
         width=8).pack(side="left", padx=T.px(6))

    parent.wait_window(dlg)
    return result


# ------------------------------------------------------------ 题库（单词 / 句子）

def content_set_dialog(parent, store, init=None, source=""):
    """新建 / 编辑一个题库。返回保存后的 set 字典，取消返回 None。"""
    init = init or {}
    result = {"set": None}
    dlg = _modal(parent, "单词 / 句子题库", 720, 660)

    tk.Label(dlg, text="单词 / 句子题库", font=T.FONT_H2, bg=T.CARD,
             fg=T.INK).pack(pady=(T.px(16), T.px(2)))
    tk.Label(dlg, text="一行一条：一行一个单词，或者一行一整句话",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(pady=(0, T.px(12)))

    # ---- 名称 ----
    nf = tk.Frame(dlg, bg=T.CARD)
    nf.pack(fill="x", padx=T.px(24))
    tk.Label(nf, text="名称", font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
             width=6, anchor="w").pack(side="left")
    v_name = tk.StringVar(value=init.get("name") or "")
    tk.Entry(nf, textvariable=v_name, font=T.FONT_UI, relief="flat",
             highlightthickness=1, highlightbackground=T.LINE,
             highlightcolor=T.ACCENT).pack(side="left", fill="x", expand=True,
                                          padx=T.px(8), ipady=T.px(4))

    # ---- 内容 ----
    tk.Label(dlg, text="内容（一行一条）", font=T.FONT_UI_B, bg=T.CARD,
             fg=T.INK).pack(anchor="w", padx=T.px(24), pady=(T.px(12), T.px(3)))
    wrap = tk.Frame(dlg, bg=T.CARD, highlightthickness=1, highlightbackground=T.LINE)
    wrap.pack(fill="both", expand=True, padx=T.px(24))
    box = tk.Text(wrap, font=("Consolas", 12), bg=T.CARD, fg=T.INK, relief="flat",
                  wrap="none", height=12, highlightthickness=0,
                  spacing1=T.px(2), spacing3=T.px(2))
    sb = ttk.Scrollbar(wrap, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    box.pack(side="left", fill="both", expand=True, padx=T.px(4), pady=T.px(4))

    seed = init.get("text_raw")
    if seed is None:
        seed = "\n".join(init.get("items") or [])
    box.insert("1.0", seed or "")
    box.focus_set()

    # ---- 选项 ----
    of = tk.Frame(dlg, bg=T.CARD)
    of.pack(fill="x", padx=T.px(24), pady=(T.px(12), 0))

    v_mode = tk.StringVar(value="line")
    tk.Label(of, text="怎么拆", font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
             width=6, anchor="w").pack(side="left")
    for val, txt in (("line", "一行一条（句子用这个）"), ("split", "自动拆词")):
        tk.Radiobutton(of, text=txt, variable=v_mode, value=val, font=T.FONT_SM,
                       bg=T.CARD, fg=T.INK, activebackground=T.CARD,
                       selectcolor=T.CARD).pack(side="left")

    of2 = tk.Frame(dlg, bg=T.CARD)
    of2.pack(fill="x", padx=T.px(24), pady=(T.px(8), 0))
    tk.Label(of2, text="每条打", font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
             width=6, anchor="w").pack(side="left")
    v_rep = tk.IntVar(value=int(init.get("repeats", 3) or 3))
    tk.Spinbox(of2, from_=1, to=20, textvariable=v_rep, width=4,
               font=("Consolas", 13), justify="center", relief="flat",
               highlightthickness=1, highlightbackground=T.LINE,
               highlightcolor=T.ACCENT, buttonbackground="#e8edf5",
               command=lambda: refresh_preview()).pack(side="left", padx=T.px(4))
    tk.Label(of2, text="遍", font=T.FONT_UI, bg=T.CARD, fg=T.MUTED).pack(side="left")
    v_shuffle = tk.BooleanVar(value=bool(init.get("shuffle")))
    tk.Checkbutton(of2, text="打乱顺序", variable=v_shuffle, font=T.FONT_SM,
                   bg=T.CARD, fg=T.INK, activebackground=T.CARD,
                   selectcolor=T.CARD,
                   command=lambda: refresh_preview()).pack(side="left", padx=T.px(18))
    v_drop = tk.BooleanVar(value=True)
    tk.Checkbutton(of2, text="自动去掉打不出的字符（? ! 中文等）",
                   variable=v_drop, font=T.FONT_SM, bg=T.CARD, fg=T.INK,
                   activebackground=T.CARD, selectcolor=T.CARD,
                   command=lambda: refresh_preview()).pack(side="left")

    lbl_prev = tk.Label(dlg, text="", font=T.FONT_SM, bg=T.CARD, fg=T.ACCENT,
                        justify="left", anchor="w")
    lbl_prev.pack(fill="x", padx=T.px(24), pady=(T.px(8), 0))
    tk.Label(dlg, text="只支持英文、数字、空格和  ,  .  /  ;  '  -  =  [  ]  \\",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(24))

    # ---- 预览 ----
    def collect():
        try:
            rep = max(1, min(20, int(v_rep.get())))
        except Exception:
            rep = 3
        items, skipped, fixed = courses.clean_items(box.get("1.0", "end"),
                                                    v_mode.get(), v_drop.get())
        return items, skipped, fixed, rep

    def refresh_preview(*_a):
        try:
            items, skipped, fixed, rep = collect()
        except Exception:
            return
        rows = sum(len(courses.wrap_item(i, 60)) * rep for i in items)
        txt = "共 %d 条 · 每条 %d 遍 · 约 %d 行练习" % (len(items), rep, rows)
        if fixed:
            txt += "     已去掉 %d 条里的特殊字符" % len(fixed)
        if skipped:
            txt += "     跳过 %d 条（含打不出的字符）" % len(skipped)
        lbl_prev.configure(text=txt)

    box.bind("<KeyRelease>", refresh_preview)
    v_mode.trace_add("write", lambda *a: refresh_preview())
    refresh_preview()

    def save():
        items, skipped, fixed, rep = collect()
        name = (v_name.get() or "").strip()
        if not items:
            messagebox.showwarning("提示", "没有可用的内容。\n换一种拆分方式，"
                                           "或者勾上「自动去掉打不出的字符」。",
                                   parent=dlg)
            return
        if not name:
            name = "我的题库"
        if init.get("id"):
            st = store.update_content_set(init["id"], name=name, items=items,
                                          repeats=rep, shuffle=bool(v_shuffle.get()))
        else:
            st = store.add_content_set(name, items, repeats=rep,
                                       shuffle=bool(v_shuffle.get()), source=source)
        result["set"] = st
        notes = []
        if fixed:
            notes.append("有 %d 条里的特殊字符（如 ? ! 中文）被自动去掉了" % len(fixed))
        if skipped:
            head = "\n".join(skipped[:8])
            if len(skipped) > 8:
                head += "\n…… 还有 %d 条" % (len(skipped) - 8)
            notes.append("跳过 %d 条（含打不出的字符）：\n%s" % (len(skipped), head))
        if notes:
            messagebox.showinfo("已保存",
                                "这个题库一共 %d 条。\n\n%s"
                                % (len(items), "\n\n".join(notes)), parent=dlg)
        dlg.grab_release()
        dlg.destroy()

    rb = tk.Frame(dlg, bg=T.CARD)
    rb.pack(pady=T.px(14))
    _btn(rb, "保存", save, primary=True, width=10).pack(side="left", padx=T.px(6))
    _btn(rb, "取消", lambda: (dlg.grab_release(), dlg.destroy()),
         width=10).pack(side="left", padx=T.px(6))

    parent.wait_window(dlg)
    return result["set"]


# ------------------------------------------------------------ 家长面板

def parent_panel(parent, store, on_reset=None, on_changed=None, on_content=None):
    dlg = _modal(parent, "家长面板", 720, 700)

    tk.Label(dlg, text="家长面板", font=T.FONT_H1, bg=T.CARD, fg=T.INK).pack(pady=(T.px(18), T.px(0)))
    tk.Label(dlg, text="只有输过密码才能进这里", font=T.FONT_SM,
             bg=T.CARD, fg=T.MUTED).pack(pady=(T.px(0), T.px(10)))

    nb = ttk.Notebook(dlg)
    nb.pack(fill="both", expand=True, padx=T.px(18), pady=(T.px(0), T.px(8)))

    # ---- 记录页 ----
    tab1 = tk.Frame(nb, bg=T.CARD)
    nb.add(tab1, text="  练习记录  ")

    total_min = store.progress.get("total_seconds", 0) / 60.0
    days = store.progress.get("days", {})
    today = days.get(time.strftime("%Y-%m-%d"), {})
    head = "累计练习 %.1f 分钟     今天 %.1f 分钟" % (
        total_min, today.get("seconds", 0) / 60.0)
    tk.Label(tab1, text=head, font=T.FONT_UI_B, bg=T.CARD, fg=T.ACCENT).pack(pady=T.px(10))

    cols = ("lesson", "stars", "acc", "cpm", "plays")
    tv = ttk.Treeview(tab1, columns=cols, show="headings", height=13)
    for c, w, t in (("lesson", 230, "课程"), ("stars", 80, "最好成绩"),
                    ("acc", 80, "正确率"), ("cpm", 80, "字/分"), ("plays", 60, "次数")):
        tv.heading(c, text=t)
        tv.column(c, width=w, anchor="center")
    tv.pack(fill="both", expand=True, padx=T.px(12), pady=T.px(6))

    prog = store.progress.get("lessons", {})
    for les in courses.LESSONS:
        p = prog.get(les["id"])
        if not p:
            continue
        tv.insert("", "end", values=(
            les["title"], courses.star_text(p.get("stars", 0)),
            "%.0f%%" % (p.get("best_acc", 0) * 100), p.get("best_cpm", 0), p.get("plays", 0)))

    if not prog:
        tk.Label(tab1, text="还没有练习记录", font=T.FONT_UI, bg=T.CARD,
                 fg=T.MUTED).pack(pady=T.px(4))

    # ---- 我的内容（单词 / 句子题库） ----
    tab0 = tk.Frame(nb, bg=T.CARD)
    nb.add(tab0, text="  我的内容  ")

    tk.Label(tab0, text="导入单词 / 句子，让小朋友照着打",
             font=T.FONT_UI_B, bg=T.CARD, fg=T.INK).pack(anchor="w",
                                                        padx=T.px(16), pady=(T.px(10), T.px(2)))
    tk.Label(tab0,
             text="三种办法，随便挑一种：\n"
                  "① 把 .txt 丢进「我的题库」文件夹（一行一条），点下面「扫描文件夹」就进来了\n"
                  "② 点「粘贴导入」，把单词或句子直接贴进去\n"
                  "③ 点「从文件导入」，挑一个 txt",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED, justify="left").pack(
        anchor="w", padx=T.px(16))

    cols = ("name", "count", "rep", "src")
    tv2 = ttk.Treeview(tab0, columns=cols, show="headings", height=8)
    for c, w, t in (("name", 210, "名称"), ("count", 70, "条数"),
                    ("rep", 70, "每遍"), ("src", 130, "来源")):
        tv2.heading(c, text=t)
        tv2.column(c, width=w, anchor="center" if c != "name" else "w")
    tv2.pack(fill="both", expand=True, padx=T.px(16), pady=T.px(6))

    lbl_msg = tk.Label(tab0, text="", font=T.FONT_SM, bg=T.CARD, fg=T.MUTED)
    lbl_msg.pack(anchor="w", padx=T.px(16))

    def refresh_sets():
        for iid in tv2.get_children(""):
            tv2.delete(iid)
        for s in store.content_sets:
            tv2.insert("", "end", iid=s["id"], values=(
                s.get("name", ""), len(s.get("items") or []),
                s.get("repeats", 3), s.get("source") or "手动"))
        n = len(store.content_sets)
        lbl_msg.configure(text="共 %d 个题库" % n if n else "还没有题库，用上面三种办法导入一个试试")

    def after_change():
        refresh_sets()
        if on_content:
            on_content()

    def selected_set():
        sel = tv2.selection()
        if not sel:
            messagebox.showinfo("提示", "先在上面选中一个题库。", parent=dlg)
            return None
        return store.set_by_id(sel[0])

    def do_paste():
        if content_set_dialog(dlg, store):
            after_change()

    def do_file():
        path = filedialog.askopenfilename(
            parent=dlg, title="选择单词 / 句子文件",
            filetypes=[("文本文件", "*.txt *.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except Exception as e:
            messagebox.showerror("读不了这个文件", str(e), parent=dlg)
            return
        stem = os.path.splitext(os.path.basename(path))[0]
        if content_set_dialog(dlg, store,
                              init={"name": stem, "text_raw": raw,
                                    "repeats": 3},
                              source=os.path.basename(path)):
            after_change()

    def do_edit():
        s = selected_set()
        if not s:
            return
        if content_set_dialog(dlg, store, init=s):
            after_change()

    def do_delete():
        s = selected_set()
        if not s:
            return
        if not messagebox.askyesno(
                "确认", "删除题库「%s」？\n这一课的星星也会一起清掉。"
                        % s.get("name"), parent=dlg):
            return
        store.remove_content_set(s["id"])
        after_change()

    def do_open_folder():
        from .store import content_dir
        d = content_dir()
        try:
            os.startfile(d)                      # 只在 Windows 上有
        except Exception:
            messagebox.showinfo("题库文件夹", "题库文件夹在：\n" + d, parent=dlg)

    def do_scan():
        added, updated, _all = store.scan_content_folder()
        after_change()
        messagebox.showinfo(
            "扫描完成",
            "新增 %d 个题库，更新 %d 个。\n\n"
            "（文件夹里的 .txt 一行一条，改完文件再点一次就能同步过来）"
            % (len(added), len(updated)), parent=dlg)

    b1 = tk.Frame(tab0, bg=T.CARD)
    b1.pack(pady=(T.px(4), 0))
    _btn(b1, "粘贴导入", do_paste, primary=True).pack(side="left", padx=T.px(4))
    _btn(b1, "从文件导入", do_file).pack(side="left", padx=T.px(4))
    _btn(b1, "编辑", do_edit, width=7).pack(side="left", padx=T.px(4))
    _btn(b1, "删除", do_delete, width=7).pack(side="left", padx=T.px(4))

    b2 = tk.Frame(tab0, bg=T.CARD)
    b2.pack(pady=(T.px(6), T.px(10)))
    _btn(b2, "打开题库文件夹", do_open_folder, width=14).pack(side="left", padx=T.px(4))
    _btn(b2, "扫描文件夹", do_scan, width=12).pack(side="left", padx=T.px(4))

    refresh_sets()

    # ---- 时间管理页 ----
    tabt = tk.Frame(nb, bg=T.CARD)
    nb.add(tabt, text="  时间管理  ")

    tk.Label(tabt, text="两件事分开管：番茄管「节奏」，每日额度管「总量」",
             font=T.FONT_UI_B, bg=T.CARD, fg=T.INK).pack(
        anchor="w", padx=T.px(18), pady=(T.px(12), T.px(2)))
    tk.Label(tabt, text="两个开关互相独立，都可以单独开关；改动只有输过密码才进得来。",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(18))

    # ① 番茄节奏
    box1 = tk.Frame(tabt, bg="#f4f8ff", highlightthickness=1,
                    highlightbackground="#dce6f6")
    box1.pack(fill="x", padx=T.px(18), pady=(T.px(12), 0))
    pcfg = store.pomodoro
    v_pomo_on = tk.BooleanVar(value=bool(pcfg["enabled"]))
    cb1 = tk.Checkbutton(box1, text="", variable=v_pomo_on, font=T.FONT_UI_B,
                         bg="#f4f8ff", fg=T.INK, activebackground="#f4f8ff",
                         activeforeground=T.INK, selectcolor="#f4f8ff",
                         anchor="w", bd=0, highlightthickness=0)

    def _sync_cb1(*_a):
        on = bool(v_pomo_on.get())
        cb1.configure(text="① 番茄节奏　——　%s" % ("已开启" if on else "已关闭"),
                      fg=T.INK if on else T.MUTED)

    cb1.configure(command=_sync_cb1)
    _sync_cb1()
    cb1.pack(anchor="w", padx=T.px(12), pady=(T.px(8), 0))

    prow = tk.Frame(box1, bg="#f4f8ff")
    prow.pack(anchor="w", padx=T.px(34), pady=(T.px(4), 0))
    v_work = tk.IntVar(value=pcfg["work"])
    v_brk = tk.IntVar(value=pcfg["break"])
    for label, var in (("工作时长", v_work), ("休息时长", v_brk)):
        tk.Label(prow, text=label, font=T.FONT_UI, bg="#f4f8ff",
                 fg=T.INK).pack(side="left")
        tk.Spinbox(prow, from_=1, to=120, textvariable=var, width=5,
                   font=("Consolas", 13), justify="center", relief="flat",
                   highlightthickness=1, highlightbackground=T.LINE,
                   highlightcolor=T.ACCENT,
                   buttonbackground="#e8edf5").pack(side="left", padx=T.px(5))
        tk.Label(prow, text="分钟", font=T.FONT_UI, bg="#f4f8ff",
                 fg=T.MUTED).pack(side="left", padx=(0, T.px(20)))

    tk.Label(box1, text="到点锁屏让他休息，倒计时结束自动继续；剩 60 秒会提醒。",
             font=T.FONT_SM, bg="#f4f8ff", fg=T.MUTED, justify="left").pack(
        anchor="w", padx=T.px(34), pady=(T.px(2), T.px(9)))

    # ② 每日额度
    box2 = tk.Frame(tabt, bg="#fff8ec", highlightthickness=1,
                    highlightbackground="#f2e2c6")
    box2.pack(fill="x", padx=T.px(18), pady=(T.px(10), 0))
    v_lim_on = tk.BooleanVar(value=bool(store.daily_limit["enabled"]))
    cb2 = tk.Checkbutton(box2, text="", variable=v_lim_on, font=T.FONT_UI_B,
                         bg="#fff8ec", fg=T.INK, activebackground="#fff8ec",
                         activeforeground=T.INK, selectcolor="#fff8ec",
                         anchor="w", bd=0, highlightthickness=0)

    def _sync_cb2(*_a):
        on = bool(v_lim_on.get())
        cb2.configure(text="② 每日时长限制　——　%s" % ("已开启" if on else "已关闭"),
                      fg=T.INK if on else T.MUTED)

    cb2.configure(command=_sync_cb2)
    _sync_cb2()
    cb2.pack(anchor="w", padx=T.px(12), pady=(T.px(8), 0))

    lrow = tk.Frame(box2, bg="#fff8ec")
    lrow.pack(anchor="w", padx=T.px(34), pady=(T.px(4), 0))
    tk.Label(lrow, text="每天上限", font=T.FONT_UI, bg="#fff8ec",
             fg=T.INK).pack(side="left")
    v_mins = tk.IntVar(value=int(store.daily_limit["minutes"]))
    tk.Spinbox(lrow, from_=1, to=1440, textvariable=v_mins, width=6,
               font=("Consolas", 13), justify="center", relief="flat",
               highlightthickness=1, highlightbackground=T.LINE,
               highlightcolor=T.ACCENT,
               buttonbackground="#e8edf5").pack(side="left", padx=T.px(5))
    tk.Label(lrow, text="分钟", font=T.FONT_UI, bg="#fff8ec",
             fg=T.MUTED).pack(side="left")
    lbl_eq = tk.Label(lrow, text="", font=T.FONT_SM, bg="#fff8ec", fg=T.ACCENT)
    lbl_eq.pack(side="left", padx=T.px(10))

    lbl_used = tk.Label(box2, text="", font=T.FONT_SM, bg="#fff8ec", fg=T.MUTED)
    lbl_used.pack(anchor="w", padx=T.px(34), pady=(T.px(4), T.px(4)))

    def refresh_used():
        i = store.usage_info()
        extra = ""
        if i["enabled"] and i["unlimited"]:
            extra = "　（今天不限制）"
        elif i["grants"]:
            extra = "　（已加时 %d 次）" % i["grants"]
        lbl_used.configure(text="今天已用 %s%s" % (fmt_dur(i["used"]), extra))
        try:
            m = max(1, int(v_mins.get()))
        except Exception:
            m = store.daily_limit["minutes"]
        lbl_eq.configure(text="= %s" % fmt_dur(m * 60))

    def do_reset_usage():
        store.reset_usage_today()
        refresh_used()
        if on_changed:
            on_changed()

    tk.Button(box2, text="重置今日用量", font=T.FONT_SM, relief="flat", bd=0,
              bg="#f6ecd9", fg="#8a6417", cursor="hand2",
              activebackground="#efe0c4", activeforeground="#8a6417",
              padx=T.px(10), pady=T.px(4),
              command=do_reset_usage).pack(anchor="w", padx=T.px(34))

    tk.Label(box2, text="只算「真的在打字」的时间：停下来发呆、休息、挂机都不算。\n"
                        "用完了会锁屏，需要密码解锁；第二天 0 点自动回满。",
             font=T.FONT_SM, bg="#fff8ec", fg=T.MUTED, justify="left").pack(
        anchor="w", padx=T.px(34), pady=(T.px(4), T.px(9)))

    v_mins.trace_add("write", lambda *a: refresh_used())
    refresh_used()

    def save_time():
        try:
            w = max(1, min(120, int(v_work.get())))
            b = max(1, min(120, int(v_brk.get())))
            m = max(1, min(1440, int(v_mins.get())))
        except Exception:
            messagebox.showwarning("提示", "时间请填整数分钟", parent=dlg)
            return
        store.set_pomodoro(w, b, enabled=bool(v_pomo_on.get()))
        store.set_daily_limit(bool(v_lim_on.get()), m)
        refresh_used()
        if on_changed:
            on_changed()
        messagebox.showinfo("已保存", "时间管理设置已保存，立刻生效。", parent=dlg)

    tr = tk.Frame(tabt, bg=T.CARD)
    tr.pack(pady=T.px(16))
    _btn(tr, "保存时间设置", save_time, primary=True, width=14).pack(side="left")

    # ---- 设置页 ----
    tab2 = tk.Frame(nb, bg=T.CARD)
    nb.add(tab2, text="  设置  ")

    v_full = tk.BooleanVar(value=bool(store.get("fullscreen", True)))
    v_sound = tk.BooleanVar(value=bool(store.get("sound", True)))
    v_strict = tk.BooleanVar(value=bool(store.get("strict", True)))

    def chk(text, var, hint):
        f = tk.Frame(tab2, bg=T.CARD)
        f.pack(fill="x", padx=T.px(18), pady=T.px(6))
        c = tk.Checkbutton(f, text=text, variable=var, font=T.FONT_UI_B,
                           bg=T.CARD, fg=T.INK, activebackground=T.CARD,
                           selectcolor=T.CARD, anchor="w")
        c.pack(anchor="w")
        tk.Label(f, text=hint, font=T.FONT_SM, bg=T.CARD, fg=T.MUTED).pack(anchor="w", padx=T.px(24))

    chk("全屏运行（推荐）", v_full, "全屏下没有关闭按钮，小朋友更难误退；按 Ctrl+Alt+Q 或点「退出」才需密码")
    chk("音效提示", v_sound, "打错 / 完成一串 / 快到时间 时响一下")
    chk("严格模式", v_strict, "打错了必须打对才能继续（推荐初学）；关闭则允许打错直接过")

    # 空格怎么显示 —— 不给空格配字符，免得孩子把某个符号错记成空格
    v_space = tk.StringVar(value=store.get("space_mode", T.SPACE_MODE_DEFAULT))
    sf = tk.Frame(tab2, bg=T.CARD)
    sf.pack(fill="x", padx=T.px(18), pady=T.px(6))
    tk.Label(sf, text="空格怎么显示", font=T.FONT_UI_B, bg=T.CARD, fg=T.INK,
             anchor="w").pack(anchor="w")
    rf = tk.Frame(sf, bg=T.CARD)
    rf.pack(anchor="w", padx=T.px(24))
    for val, txt in (("slot", "浅灰空槽（推荐）"), ("blank", "纯空白")):
        tk.Radiobutton(rf, text=txt, variable=v_space, value=val, font=T.FONT_SM,
                       bg=T.CARD, fg=T.INK, activebackground=T.CARD,
                       selectcolor=T.CARD).pack(side="left", padx=(0, T.px(14)))
    tk.Label(sf, text="不给空格配任何字符：免得孩子把 - 或 _ 这类键错记成空格。\n"
                      "空槽 = 浅灰格子，打过的变浅绿（空格没字可染绿，就染格子）",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED, justify="left").pack(
        anchor="w", padx=T.px(24))

    def save_settings():
        store.set("fullscreen", bool(v_full.get()))
        store.set("sound", bool(v_sound.get()))
        store.set("strict", bool(v_strict.get()))
        store.set("space_mode", v_space.get())
        if on_changed:
            on_changed()
        messagebox.showinfo("已保存",
                            "设置已保存。\n\n空格显示方式已经生效；\n"
                            "全屏设置的改变下次启动生效。", parent=dlg)

    tk.Frame(tab2, bg=T.CARD, height=8).pack()
    _btn(tab2, "保存设置", save_settings, primary=True, width=12).pack(pady=T.px(6))

    # ---- 安全页 ----
    tab3 = tk.Frame(nb, bg=T.CARD)
    nb.add(tab3, text="  安全  ")

    tk.Label(tab3, text="改管理密码", font=T.FONT_H2, bg=T.CARD, fg=T.INK).pack(pady=(T.px(20), T.px(4)))
    _btn(tab3, "修改密码", lambda: set_password_dialog(dlg, store, first_time=False),
         width=14).pack(pady=T.px(6))

    tk.Label(tab3, text="重置练习进度（课程星星会清空）", font=T.FONT_H2,
             bg=T.CARD, fg=T.INK).pack(pady=(T.px(26), T.px(4)))

    def do_reset():
        if messagebox.askyesno("确认", "确定清空所有练习记录和星星？\n此操作不可撤销。", parent=dlg):
            store.reset_progress()
            if on_reset:
                on_reset()
            messagebox.showinfo("完成", "记录已清空。", parent=dlg)
            dlg.grab_release()
            dlg.destroy()

    _btn(tab3, "清空记录", do_reset, width=14).pack(pady=T.px(6))

    tk.Label(tab3, text="忘了密码怎么办：关闭程序，删除 data/config.json，\n"
                        "重新打开会让您重设密码（练习记录不受影响）。",
             font=T.FONT_SM, bg=T.CARD, fg=T.MUTED, justify="left").pack(pady=(T.px(30), T.px(0)))

    _btn(dlg, "关闭", lambda: (dlg.grab_release(), dlg.destroy())).pack(pady=(T.px(0), T.px(14)))
    parent.wait_window(dlg)
    return dlg
