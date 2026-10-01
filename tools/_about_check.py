# -*- coding: utf-8 -*-
"""临时校验脚本：从源码打开「关于」窗口并截图（不进 exe）。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, HERE)
import _shots as s
import mc_transfer as m

m.enable_dpi()
app = m.App()
app.geometry("900x620+40+40")


def capture():
    hwnd, title = s.find_window("关于", timeout=10)
    print("找到窗口：%s" % title)
    if hwnd:
        s.shot(hwnd, os.path.join(HERE, "_shot_about.png"))
    app.destroy()


app.after(700, app.show_about)
app.after(3000, capture)
app.mainloop()
print("完成")
