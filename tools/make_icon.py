# -*- coding: utf-8 -*-
"""生成 app.ico（键盘图标）。改配色/形状就改这个文件，然后重跑。"""

import os
from PIL import Image, ImageDraw

BG = (47, 111, 237, 255)      # 主题蓝
BG2 = (31, 86, 196, 255)
KEY = (255, 255, 255, 255)
CAP = (255, 215, 106, 255)    # 黄底高亮键（呼应打字界面里的"当前字"）
SPACE = (214, 226, 245, 255)

S = 1024                       # 先在 1024 画，再缩下去，边缘干净
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角底板
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=BG)

# 键盘外框
kx0, ky0, kx1, ky1 = int(S * 0.13), int(S * 0.30), int(S * 0.87), int(S * 0.72)
d.rounded_rectangle([kx0, ky0, kx1, ky1], radius=int(S * 0.05), fill=KEY)

# 键位：3 行
cols, rows = 7, 3
pad = int(S * 0.028)
inner_x0, inner_y0 = kx0 + pad, ky0 + pad
inner_x1, inner_y1 = kx1 - pad, ky1 - pad
space_h = int((inner_y1 - inner_y0 - (rows - 1) * pad) * 0.20)

gap = pad
cell_w = (inner_x1 - inner_x0 - (cols - 1) * gap) // cols
cell_h = (inner_y1 - inner_y0 - (rows - 1) * gap - space_h - gap) // rows

HILITE = (1, 3)                # 高亮第 2 行第 4 个键（像"下一个键"）
for r in range(rows):
    for c in range(cols):
        x0 = inner_x0 + c * (cell_w + gap)
        y0 = inner_y0 + r * (cell_h + gap)
        fill = CAP if (r, c) == HILITE else BG2
        d.rounded_rectangle([x0, y0, x0 + cell_w, y0 + cell_h],
                            radius=max(3, int(cell_h * 0.22)), fill=fill)

# 空格键
sy0 = inner_y0 + rows * (cell_h + gap)
sx0 = inner_x0 + int((inner_x1 - inner_x0) * 0.22)
sx1 = inner_x1 - int((inner_x1 - inner_x0) * 0.22)
d.rounded_rectangle([sx0, sy0, sx1, sy0 + space_h],
                    radius=max(3, int(space_h * 0.3)), fill=BG2)

# 键盘下方两颗小圆点（f / j 的定位凸点，呼应界面的指法配色）
for dx in (-1, 1):
    cx = S // 2 + dx * int(S * 0.042)
    cy = int(S * 0.815)
    d.ellipse([cx - int(S * 0.019), cy - int(S * 0.019),
               cx + int(S * 0.019), cy + int(S * 0.019)], fill=CAP)

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.ico")
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
img.save(out, format="ICO", sizes=sizes)
print("icon ->", out)

png = os.path.join(os.path.dirname(out), "app_icon_preview.png")
img.resize((256, 256), Image.LANCZOS).save(png)
print("preview ->", png)
