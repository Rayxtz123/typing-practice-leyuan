# -*- coding: utf-8 -*-
"""一键打包成单文件 exe。

做三件事：
  1. 重画图标 app.ico
  2. PyInstaller 打包（onefile / 无控制台 / 排除用不到的重量级库）
  3. 把 exe 从 dist/ 复制到项目根目录，双击就能用

直接运行：python tools/build_exe.py
或双击：打包exe.bat
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "打字练习乐园"
ICON = os.path.join(ROOT, "app.ico")

EXCLUDES = [
    "numpy", "pandas", "matplotlib", "scipy", "PIL", "PyQt5", "PyQt6",
    "PySide2", "PySide6", "IPython", "notebook", "jupyter", "pytest",
]


def run(cmd, **kw):
    print("» " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, **kw)
    if r.returncode != 0:
        raise SystemExit("命令失败，退出码 %d" % r.returncode)


def main():
    # 1) 图标
    run([sys.executable, os.path.join(HERE, "make_icon.py")])

    # 2) 打包
    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", NAME,
           "--icon", ICON,                      # 必须是绝对路径，相对路径会被解析到 workpath
           "--distpath", os.path.join(ROOT, "dist"),
           "--workpath", os.path.join(ROOT, "build"),
           "--specpath", os.path.join(ROOT, "build")]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd.append("main.py")
    run(cmd)

    # 3) 拷到根目录
    src = os.path.join(ROOT, "dist", NAME + ".exe")
    dst = os.path.join(ROOT, NAME + ".exe")
    if not os.path.exists(src):
        raise SystemExit("没找到产出：" + src)
    shutil.copy2(src, dst)
    size = os.path.getsize(dst) / 1024 / 1024
    print("\n完成 -> %s  (%.1f MB)" % (dst, size))
    print("提示：build/ 和 dist/ 是中间产物，可以随时删掉，不影响 exe 运行。")

    # 4) 顺手核一遍 exe 自检
    print("\n跑一遍 exe 自检 ...")
    log = os.path.join(ROOT, "selftest.log")
    if os.path.exists(log):
        os.remove(log)
    subprocess.run([dst, "--debug"], cwd=ROOT)
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8") as f:
            txt = f.read()
        print(txt)
        os.remove(log)
        print("自检结果：" + ("通过" if "SELFTEST OK" in txt else "未通过，请检查"))
    else:
        print("没生成 selftest.log，exe 可能启动就挂了")


if __name__ == "__main__":
    main()
