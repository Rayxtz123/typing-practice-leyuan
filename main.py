# -*- coding: utf-8 -*-
"""打字练习乐园 —— 入口。

用法：
    python main.py             正常启动
    python main.py --selftest  自检（构建界面后立即退出，不进入主循环）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tkid.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
