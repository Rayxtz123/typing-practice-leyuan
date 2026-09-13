# -*- coding: utf-8 -*-
"""把界面渲染结果抓成 PNG，方便自查排版（不需要人盯着屏幕）。

原理：PrintWindow 抓窗口自己的内容，不抓整个屏幕 —— 不碰桌面上其他东西。
用法：python tools/screenshot.py
"""

import os
import sys
import ctypes
import tempfile
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "shots")


def grab(hwnd, path):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    rc = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    if w <= 0 or h <= 0:
        raise RuntimeError("窗口尺寸异常: %sx%s" % (w, h))

    hdc = user32.GetWindowDC(wintypes.HWND(hwnd))
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    bmi = BMIH()
    bmi.biSize = ctypes.sizeof(BMIH)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    user32.PrintWindow(wintypes.HWND(hwnd), mdc, 2)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

    from PIL import Image
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(wintypes.HWND(hwnd), hdc)
    return w, h


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    from tkid import store
    store.set_data_dir(os.path.join(tempfile.gettempdir(), "tkid_shot"))
    s = store.Store()
    if not s.has_password:
        s.set_password("8888")

    from tkid import courses
    from tkid.app import App

    app = App()                       # 已有密码 -> 不弹设置框
    app.root.update()
    app.root.attributes("-fullscreen", False)
    times = [0]

    def full():
        app.root.attributes("-fullscreen", True)
        app.root.update()

    app.root.after(200, full)
    import time as _t
    _t.sleep(0.5)
    app.root.update()

    def snap(name, lesson_id=None, before=None):
        if lesson_id:
            app._open_lesson(lesson_id)
        if before:
            before(app)
        app.root.update_idletasks()
        app.root.update()
        import time
        time.sleep(0.35)
        app.root.update()
        hwnd = app.root.winfo_id()
        p = os.path.join(OUT, name + ".png")
        w, h = grab(hwnd, p)
        print("  %-18s %dx%d -> %s" % (name, w, h, p), flush=True)

    print("抓图中 ...", flush=True)
    # 1) 基准键练习：多行 + 手指指向 f
    def type_a_few(a):
        for ch in "ff jj fj":
            a._type_char(ch)
    snap("01_drill_home", "home_102106", type_a_few)

    # 2) 空格行（看"空槽"是不是像个空位，而不是一个冒充空格的符号）
    snap("02_spaces", "py_bpmf", lambda a: [a._type_char(c) for c in "ba pa ma"])

    # 3) 数字键：看手指换到右手
    snap("03_row_top", "top_114117", lambda a: [a._type_char(c) for c in "ru ru"])

    # 3.5) 家长导入的题库：单词 + 长句子
    from tkid import courses
    st = app.store.add_content_set(
        "水果单词",
        ["apple", "banana", "orange", "pear", "grape", "lemon", "peach", "mango"],
        repeats=2)
    st2 = app.store.add_content_set(
        "英语短句",
        ["i like my little cat", "the sun is very bright today",
         "we go to school by bus"],
        repeats=2)
    courses.rebuild(app.store.content_sets, app._max_cols)
    app.refresh_tree()
    u1 = [l for l in courses.LESSONS if l.get("source_set") == st["id"]]
    u2 = [l for l in courses.LESSONS if l.get("source_set") == st2["id"]]
    snap("08_user_words", u1[0]["id"], lambda a: [a._type_char(c) for c in "app"])
    snap("09_user_sentence", u2[0]["id"],
         lambda a: [a._type_char(c) for c in "i like"])

    # 4) 游戏课
    snap("04_game", "home_final_g", None)

    # 5) 认识键盘说明页
    snap("05_intro", "intro", None)

    # 6) 番茄运行中
    app._open_lesson("home_102106")
    app.toggle_pomodoro()
    snap("06_pomodoro", None, None)

    # 7) 休息锁屏
    app.pomo["end"] = 0
    app.root.update()
    import time
    time.sleep(0.4)
    app.root.update()
    snap("07_lock", None, None)
    app._stop_pomodoro()

    # 12) 空格显示方式：空槽 vs 纯空白（看打过的空格变浅绿、光标落在空格上是黄框）
    app.store.set("space_mode", "slot")
    snap("12_space_slot", "py_bpmf", lambda a: [a._type_char(c) for c in "ba ba "])
    app.store.set("space_mode", "blank")
    snap("13_space_blank", "py_bpmf", lambda a: [a._type_char(c) for c in "ba ba "])
    app.store.set("space_mode", "slot")

    # 10) 家长面板 -> 我的内容
    import tkinter as tk
    from tkid import dialogs
    tk.Misc.wait_window = lambda self, *a, **k: None      # 不让它阻塞
    panel = dialogs.parent_panel(app.root, app.store)

    def find_nb(w):
        for c in w.winfo_children():
            if c.winfo_class() == "TNotebook":
                return c
            r = find_nb(c)
            if r:
                return r
        return None

    nb = find_nb(panel)
    if nb:
        nb.select(1)
    panel.update()
    time.sleep(0.4)
    panel.update()
    w, h = grab(panel.winfo_id(), os.path.join(OUT, "10_parent_content.png"))
    print("  %-18s %dx%d" % ("10_parent_content", w, h), flush=True)

    # 15) 家长面板 -> 时间管理（番茄节奏 + 每日额度）
    if nb:
        nb.select(2)
    panel.update()
    time.sleep(0.4)
    panel.update()
    w, h = grab(panel.winfo_id(), os.path.join(OUT, "15_parent_time.png"))
    print("  %-18s %dx%d" % ("15_parent_time", w, h), flush=True)

    # 14) 家长面板 -> 设置（看"空格怎么显示"开关）
    if nb:
        nb.select(3)
    panel.update()
    time.sleep(0.4)
    panel.update()
    w, h = grab(panel.winfo_id(), os.path.join(OUT, "14_parent_settings.png"))
    print("  %-18s %dx%d" % ("14_parent_settings", w, h), flush=True)

    # 11) 导入对话框
    def open_import():
        dialogs.content_set_dialog(panel, app.store,
                                   init={"name": "英语短句", "repeats": 2,
                                         "text_raw": "i like my little cat\n"
                                                     "the sun is very bright today\n"
                                                     "we go to school by bus\n"
                                                     "look at the bird!"})

    open_import()

    def all_tops(w, acc):
        for c in w.winfo_children():
            if c.winfo_class() == "Toplevel":
                acc.append(c)
            all_tops(c, acc)
        return acc

    tops = [t for t in all_tops(app.root, []) if t is not panel]
    if tops:
        d2 = tops[-1]
        d2.update()
        time.sleep(0.4)
        d2.update()
        w, h = grab(d2.winfo_id(), os.path.join(OUT, "11_import_dialog.png"))
        print("  %-18s %dx%d" % ("11_import_dialog", w, h), flush=True)
    else:
        print("  !! 没找到导入对话框", flush=True)

    # 关掉家长面板和所有子窗口，回到主界面
    for t in all_tops(app.root, []):
        try:
            t.grab_release()
        except Exception:
            pass
        t.destroy()
    app.root.update()
    time.sleep(0.35)
    app.root.update()

    # 16) 今日额度用完的锁屏（暖色，跟番茄休息的冷色区分）
    app.pomo.update(state="off", end=0.0)
    app.store.set_daily_limit(True, 1)
    app.store.reset_usage_today()
    app.store.add_usage(60)
    app._limit_locked = False
    app._update_limit_ui()
    app.root.update()
    snap("16_limit_lock", "home_102106", None)

    # 17) 家长加时对话框
    dialogs.limit_grant_dialog(app.root, app.store, 3600)
    tops = [t for t in all_tops(app.root, []) if t is not panel]
    if tops:
        d3 = tops[-1]
        d3.update()
        time.sleep(0.4)
        d3.update()
        w, h = grab(d3.winfo_id(), os.path.join(OUT, "17_grant_dialog.png"))
        print("  %-18s %dx%d" % ("17_grant_dialog", w, h), flush=True)
        try:
            d3.grab_release()
        except Exception:
            pass
        d3.destroy()
    else:
        print("  !! 没找到加时对话框", flush=True)

    # 18) 顶栏剩余时间（快用完了 -> 橙色）
    app._limit_locked = False
    app._hide_lock()
    app.store.set_daily_limit(True, 20)
    app.store.reset_usage_today()
    app.store.add_usage(20 * 60 - 8 * 60)      # 只剩 8 分钟
    app._update_limit_ui()
    snap("18_topbar_limit", "home_102106", lambda a: [a._type_char(c) for c in "ff jj"])
    app.store.set_daily_limit(False, 120)
    app.store.reset_usage_today()
    app._update_limit_ui()

    print("done", flush=True)
    app.root.destroy()


if __name__ == "__main__":
    main()
