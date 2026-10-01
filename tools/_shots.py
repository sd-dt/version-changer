# -*- coding: utf-8 -*-
"""测试辅助脚本：启动打包好的 exe，把窗口置顶后截图，再结束进程。"""
import ctypes
import ctypes.wintypes as wt
import subprocess
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import time

from PIL import Image, ImageGrab

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

EXE = os.path.join(HERE, "dist", "MC实例数据转移工具.exe")
user32 = ctypes.windll.user32
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def find_window(title_part, timeout=25):
    """Tk 会额外创建一个位于 (-32000,-32000) 的同名隐藏窗口，只取屏幕内面积最大的那个。"""
    def scan():
        best = None

        def cb(hwnd, _l):
            nonlocal best
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_part not in buf.value:
                return True
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if r.left < -10000 or w < 100 or h < 100:
                return True
            if best is None or w * h > best[2]:
                best = (hwnd, buf.value, w * h)
            return True

        user32.EnumWindows(CB(cb), 0)
        return best

    end = time.time() + timeout
    while time.time() < end:
        got = scan()
        if got:
            return got[0], got[1]
        time.sleep(0.3)
    return None, None


gdi32 = ctypes.windll.gdi32
user32.GetWindowDC.argtypes = [ctypes.c_void_p]
user32.GetWindowDC.restype = ctypes.c_void_p
user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
gdi32.GetDIBits.restype = ctypes.c_int


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


def shot(hwnd, out):
    """用 PrintWindow 直接抓窗口内容，不抢焦点、不移动窗口、不怕被遮挡。"""
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w < 100 or h < 100:
        return False

    hdc = user32.GetWindowDC(hwnd)
    mfc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mfc, bmp)
    try:
        ok = user32.PrintWindow(hwnd, mfc, 2)      # PW_RENDERFULLCONTENT
        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth = w
        bih.biHeight = -h                          # 负数 = 自上而下
        bih.biPlanes = 1
        bih.biBitCount = 32
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mfc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mfc)
        user32.ReleaseDC(hwnd, hdc)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    if not ok or img.getextrema() == ((0, 0), (0, 0), (0, 0)):
        # 个别窗口 PrintWindow 抓不到内容时退回抓屏幕
        img = ImageGrab.grab(bbox=(max(rect.left, 0), max(rect.top, 0),
                                   min(rect.right, user32.GetSystemMetrics(0)),
                                   min(rect.bottom, user32.GetSystemMetrics(1))))
    img.save(out)
    print("已保存 %s  (%dx%d)" % (out, img.width, img.height))
    return True


def kill_tree(proc):
    """PyInstaller onefile 会派生子进程，必须整棵进程树一起结束。"""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True, check=False)
    try:
        proc.kill()
    except Exception:
        pass
    time.sleep(0.8)


def run(args, title_part, out, wait=3.0, tries=6):
    """Tk 启动瞬间可能先把影子窗口放到屏幕内，所以整轮「找窗口→截图」要能重试。"""
    proc = subprocess.Popen([EXE] + args)
    try:
        for _attempt in range(tries):
            hwnd, title = find_window(title_part, timeout=8)
            if not hwnd:
                continue
            time.sleep(wait)
            if shot(hwnd, out):
                return True
            time.sleep(0.6)
        print("未找到窗口：%s" % title_part)
        return False
    finally:
        kill_tree(proc)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "main"):
        run([], "MC 实例数据转移工具", os.path.join(HERE, "_shot_main.png"), 2.0)
    if which in ("all", "dialog"):
        run(["--demo"], "转移前确认", os.path.join(HERE, "_shot_dialog.png"), 4.0)
    if which in ("all", "list"):
        run(["--demo-list"], "转移清单", os.path.join(HERE, "_shot_list.png"), 4.0)
