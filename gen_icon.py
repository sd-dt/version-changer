# -*- coding: utf-8 -*-
"""生成程序图标 app.ico（草方块绿底 + 双向箭头，表示数据转移）。"""
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角底板（草方块绿）
d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=48, fill=(76, 153, 60, 255))
# 顶部泥土/草地分层
d.rounded_rectangle([8, 8, SIZE - 8, 96], radius=48, fill=(104, 190, 78, 255))
d.rectangle([8, 62, SIZE - 8, 96], fill=(104, 190, 78, 255))
d.rectangle([8, 96, SIZE - 8, 118], fill=(122, 84, 52, 255))

# 双向箭头（白色）
# 上箭头 → 右
d.polygon([(52, 132), (148, 132), (148, 116), (188, 145), (148, 174), (148, 158), (52, 158)],
          fill=(255, 255, 255, 255))
# 下箭头 ← 左
d.polygon([(204, 224), (108, 224), (108, 240), (68, 211), (108, 182), (108, 198), (204, 198)],
          fill=(255, 255, 255, 235))

img.save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                           (128, 128), (256, 256)])
print("app.ico 已生成")
