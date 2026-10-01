# -*- coding: utf-8 -*-
"""
MC 实例数据转移工具  v1.1
==========================

该程序由 deepseek 和 sd_dt 编写。

用途：把「老实例」文件夹里的玩家数据（配置 / 资源包 / 存档 / 投影 / 截图 / 光影 /
     小地图 / options.txt / 服务器列表）覆盖到「新实例」文件夹，
     新实例里的模组、版本、启动器文件不会被删除。

界面共三个按钮：
    ① 选择老实例文件夹
    ② 选择新实例文件夹
    ③ 开始转移数据（覆盖新实例）

如果老实例里缺少默认列表中的某些文件夹，或者发现了默认列表之外的玩家数据
（Voxy / Distant Horizons 远景缓存、JourneyMap、OptiFine 设置、截图 …），
程序会先概述功能并弹窗询问是否把这些内容加入本次转移列表。

打包：python build.py                      （推荐，含自检、图标、改名）
自检：python mc_transfer.py --selftest     （不开界面，跑一遍完整的转移逻辑）
冒烟：python mc_transfer.py --smoke        （打开界面 1.5 秒后自动关闭）
"""

import os
import queue
import shutil
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "MC 实例数据转移工具"
APP_VERSION = "1.1"
APP_AUTHOR = "deepseek 和 sd_dt"
APP_AUTHOR_NOTE = "该程序由 %s 编写" % APP_AUTHOR

# ---------------------------------------------------------------------------
# 转移列表定义
# ---------------------------------------------------------------------------

# 默认转移列表（一定会转移，不再询问）
#   (名称, 类型, 说明——这一项到底是什么、转移过去会有什么效果)
DEFAULT_ITEMS = [
    ("config", "dir",
     "所有模组的配置文件：模组开关、按键绑定、画面/音效选项、机器与玩法设置。"
     "转移后新实例的模组设置会变成老实例那一套"),
    ("resourcepacks", "dir",
     "资源包文件本体（材质、贴图、字体、音效包）与已启用清单。"
     "转移后进游戏用的还是老实例那套材质"),
    ("saves", "dir",
     "单人存档：地图、进度、背包、成就。存档里还带着远景数据——"
     "Distant Horizons 在 saves/存档名/data/DistantHorizons.sqlite，"
     "Voxy 在 saves/存档名/voxy"),
    ("schematics", "dir",
     "投影 / 蓝图文件：Litematica、WorldEdit、投影模组用的建筑图纸"
     "（.litematic / .schem 等）"),
    ("screenshots", "dir",
     "游戏截图：游戏里按 F2 保存的图片"),
    ("shaderpacks", "dir",
     "光影包文件本体（Iris / OptiFine 加载的 .zip 光影）。"
     "注意「用哪个光影」记在 optionsshaders.txt 或 iris.properties 里"),
    ("xaero", "dir",
     "Xaero 小地图 / 世界地图数据：已探索区域的地图缓存、路径点、地图显示设置"),
    ("options.txt", "file",
     "原版游戏主设置：语言、音量、按键绑定、视距、画面质量、"
     "资源包与数据包启用列表"),
    ("servers.dat", "file",
     "多人游戏服务器列表：添加过的服务器地址、名称、收藏状态（不含账号密码）"),
]

# 默认列表之外的玩家信息 / 常见遗漏项（转移前弹窗询问，勾选后才转移）
#   (名称, 类型, 说明——这一项到底是什么、转移过去会有什么效果, 是否默认勾选)
OPTIONAL_ITEMS = [
    ("journeymap", "dir",
     "JourneyMap 地图数据：已探索区域地图缓存与路径点。"
     "它和 xaero 是两套不同的地图模组，看你实际用哪个", True),
    ("XaeroPlus", "dir",
     "XaeroPlus 增强数据：传送点、路径点分组、服务器切换记录等扩展内容", True),
    (".voxy", "dir",
     "【Voxy 远景 LOD 缓存】多人服务器上已生成的超远视距地形，按服务器分目录。"
     "转移后不用重新跑图就能立刻看到远景，不转移只是需要重新生成；"
     "体积可能有好几个 GB（单人存档的 Voxy 数据在 saves 里，随 saves 一起转移）", True),
    ("Distant_Horizons_server_data", "dir",
     "【Distant Horizons 远景 LOD 缓存】多人服务器已生成的远景数据，"
     "按服务器名分目录（内部还有 dim_overworld 等维度子目录）。"
     "体积一般比 Voxy 小；单人存档的 DH 数据在 saves/存档名/data 里，随 saves 转移", True),
    ("optionsof.txt", "file",
     "OptiFine 专属视频设置：光影开关、视距、抗锯齿、性能选项"
     "（装了 OptiFine 才有这个文件）", True),
    ("optionsshaders.txt", "file",
     "OptiFine 当前使用的光影包及光影内部参数（决定进游戏默认开哪个光影）", True),
    ("iris.properties", "file",
     "Iris 光影设置：当前光影包、光影选项开关（装了 Iris 才有这个文件）", True),
    ("replay_recordings", "dir",
     "ReplayMod 录像文件（.mcpr）：以前的游戏回放，转移后可继续观看和导出", True),
    ("CustomSkinLoader", "dir",
     "自定义皮肤加载器：皮肤站加载顺序配置 + 已下载的皮肤缓存", True),
    ("tacz", "dir",
     "TaCZ 枪械包数据：自定义枪械、配件、皮肤与资源包索引", True),
    ("command_history.txt", "file",
     "聊天框输入历史：按 ↑ 键能翻出来的那些命令记录", True),
    ("essential", "dir",
     "Essential 模组数据：好友列表、外观 / 披风、账号相关缓存", False),
    ("mods", "dir",
     "模组本体（.jar 文件）。转移后新实例会加载老实例的模组，"
     "若游戏版本或加载器不同可能直接启动崩溃，一般不建议勾选", False),
    ("defaultconfigs", "dir",
     "整合包默认配置模板：只在新建存档 / 首次生成配置时套用。"
     "覆盖新实例可能改变默认玩法，一般不必转移", False),
    ("PCL", "dir",
     "PCL 启动器自己的设置与缓存（启动器文件，不是游戏存档数据）", False),
    ("hmcl.json", "file",
     "HMCL 启动器的设置文件（启动器自己的配置，不是游戏存档数据）", False),
]

LIST_TEXT = "、".join(n for n, _k, _d in DEFAULT_ITEMS)
LIST_DIRS = "、".join(n for n, k, _d in DEFAULT_ITEMS if k == "dir")
LIST_FILES = "、".join(n for n, k, _d in DEFAULT_ITEMS if k == "file")
LIST_LINES = ("    文件夹：%s\n    文件：  %s" % (LIST_DIRS, LIST_FILES))


class TransferCancelled(Exception):
    """用户手动取消转移。"""


# ---------------------------------------------------------------------------
# 路径 / 文件工具（支持 Windows 超长路径）
# ---------------------------------------------------------------------------

def lp(path):
    """路径过长时加上 \\\\?\\ 前缀，避免 Windows 260 字符限制。"""
    if os.name != "nt" or not path:
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        return p
    if len(p) < 230:
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def path_exists(p):
    try:
        return os.path.exists(lp(p))
    except OSError:
        return False


def is_dir(p):
    try:
        return os.path.isdir(lp(p))
    except OSError:
        return False


def is_file(p):
    try:
        return os.path.isfile(lp(p))
    except OSError:
        return False


def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%d %s" % (int(n), unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def ui_scale(widget):
    """界面缩放系数：96 DPI（100% 缩放）时为 1.0。"""
    try:
        return float(widget.tk.call("tk", "scaling")) / 1.3333333
    except Exception:                                          # noqa: BLE001
        return 1.0


UI_FONT = ("Microsoft YaHei UI", 10)


def autosize(win, base_w, base_h, min_w, min_h):
    """按需要的尺寸 + 屏幕大小决定窗口尺寸，避免高分屏下内容被裁切。"""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = max(base_w, min(win.winfo_reqwidth(), sw - 60))
    h = max(base_h, min(win.winfo_reqheight(), sh - 120))
    w = min(w, sw - 40)
    h = min(h, sh - 100)
    win.geometry("%dx%d" % (w, h))
    win.minsize(min(w, min_w), min(h, min_h))
    return w, h


def walk_dir(root):
    """遍历目录，产出 (相对目录, [文件名], 错误信息)。"""
    root_lp = lp(root)
    stack = [""]
    while stack:
        rel = stack.pop()
        cur = os.path.join(root_lp, rel) if rel else root_lp
        files = []
        err = None
        try:
            with os.scandir(cur) as it:
                entries = list(it)
            for e in entries:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(os.path.join(rel, e.name) if rel else e.name)
                    elif e.is_file(follow_symlinks=False):
                        files.append(e.name)
                except OSError:
                    continue
        except OSError as exc:
            err = str(exc)
        yield rel, files, err


def count_files(root):
    """统计文件夹内的文件数量与总字节数（完整遍历，用于进度条与最终汇总）。"""
    total = 0
    size = 0
    root_lp = lp(root)
    for rel, files, err in walk_dir(root):
        if err:
            continue
        for name in files:
            total += 1
            try:
                size += os.path.getsize(os.path.join(root_lp, rel, name) if rel
                                        else os.path.join(root_lp, name))
            except OSError:
                pass
    return total, size


def quick_size(path, max_files=3000, max_seconds=0.5):
    """快速估算体积，用于弹窗里给每项标体积。

    超大目录（例如几 GB 的 Voxy/DH 缓存）不会扫到底，
    返回 (字节数, 文件数, 是否被截断)。
    """
    if is_file(path):
        return _size_of(path), 1, False
    total = 0
    count = 0
    truncated = False
    started = time.time()
    stack = [lp(path)]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError:
                        continue
        except OSError:
            continue
        if count >= max_files or time.time() - started > max_seconds:
            truncated = True
            break
    return total, count, truncated


def size_note(path, kind):
    """给列表项生成「文件夹，约 1.2 GB」这样的体积说明。"""
    kind_text = "文件夹" if kind == "dir" else "文件"
    if kind == "dir" and not is_dir(path):
        return kind_text
    if kind == "file" and not is_file(path):
        return kind_text
    total, count, truncated = quick_size(path)
    if kind == "file":
        return "%s，%s" % (kind_text, human_size(total))
    if truncated:
        return "%s，≥ %s（未扫完）" % (kind_text, human_size(total))
    return "%s，约 %s / %d 个文件" % (kind_text, human_size(total), count)


def _force_writable(path):
    """目标文件是只读时，先去掉只读属性再覆盖。"""
    try:
        os.chmod(lp(path), os.stat(lp(path)).st_mode | 0o200)
    except OSError:
        pass


VERIFY_LIMIT = 4 * 1024 * 1024        # 4 MB 以内的文件做完整内容比对后才跳过


def files_identical(a, b, limit=VERIFY_LIMIT):
    """判断两个文件是否真的内容相同。

    只有「大小相同 + 修改时间相同」才去做内容比对，避免大文件夹每次全量读取；
    超过 limit 的文件一律不跳过（宁可多写一次，也不能漏覆盖）。
    """
    try:
        sa = os.stat(lp(a))
        sb = os.stat(lp(b))
    except OSError:
        return False
    if sa.st_size != sb.st_size or int(sa.st_mtime) != int(sb.st_mtime):
        return False
    if sa.st_size > limit:
        return False
    try:
        with open(lp(a), "rb") as fa, open(lp(b), "rb") as fb:
            while True:
                ca = fa.read(256 * 1024)
                cb = fb.read(256 * 1024)
                if ca != cb:
                    return False
                if not ca:
                    return True
    except OSError:
        return False


def copy_one_file(src, dst, stats, skip_same=True, on_file=None):
    """复制单个文件；目标已存在则覆盖。"""
    try:
        if path_exists(dst):
            if skip_same and files_identical(src, dst):
                stats["same"] += 1
                if on_file:
                    on_file()
                return
            _force_writable(dst)
            shutil.copy2(lp(src), lp(dst))
            stats["over"] += 1
            stats["bytes"] += _size_of(src)
        else:
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(lp(parent), exist_ok=True)
            shutil.copy2(lp(src), lp(dst))
            stats["new"] += 1
            stats["bytes"] += _size_of(src)
        if on_file:
            on_file()
    except Exception as exc:                                   # noqa: BLE001
        stats["failed"] += 1
        stats["errors"].append("复制失败：%s → %s（%s）" % (src, dst, exc))
        if on_file:
            on_file()


def _size_of(p):
    try:
        return os.path.getsize(lp(p))
    except OSError:
        return 0


def copy_item(src_item, dst_item, stats, skip_same=True, on_file=None,
              on_log=None, cancel=None):
    """把 src_item（文件或文件夹）合并复制到 dst_item。

    文件夹采用「合并覆盖」：同名文件被覆盖，新实例里独有的文件保留不删。
    """
    if cancel is not None and cancel.is_set():
        raise TransferCancelled()

    # 源是文件夹，目标是文件 → 删掉目标文件
    if is_dir(src_item):
        if is_file(dst_item):
            try:
                os.remove(lp(dst_item))
                if on_log:
                    on_log("提示：目标位置 %s 原本是文件，已删除后按文件夹转移。" % dst_item)
            except OSError as exc:
                stats["failed"] += 1
                stats["errors"].append("无法删除同名文件：%s（%s）" % (dst_item, exc))
                return
        os.makedirs(lp(dst_item), exist_ok=True)
        for rel, files, err in walk_dir(src_item):
            if cancel is not None and cancel.is_set():
                raise TransferCancelled()
            if err:
                stats["failed"] += 1
                bad = os.path.join(src_item, rel) if rel else src_item
                stats["errors"].append("读取文件夹失败：%s（%s）" % (bad, err))
                if on_log:
                    on_log("读取文件夹失败：%s（%s）" % (bad, err))
                continue
            if rel:
                try:
                    os.makedirs(os.path.join(lp(dst_item), rel), exist_ok=True)
                except OSError as exc:
                    stats["failed"] += 1
                    stats["errors"].append("创建文件夹失败：%s（%s）"
                                           % (os.path.join(dst_item, rel), exc))
                    continue
            for name in files:
                if cancel is not None and cancel.is_set():
                    raise TransferCancelled()
                s = os.path.join(src_item, rel, name) if rel else os.path.join(src_item, name)
                d = os.path.join(dst_item, rel, name) if rel else os.path.join(dst_item, name)
                copy_one_file(s, d, stats, skip_same=skip_same, on_file=on_file)
    else:
        # 源是文件
        if is_dir(dst_item):
            try:
                shutil.rmtree(lp(dst_item))
                if on_log:
                    on_log("提示：目标位置 %s 原本是文件夹，已删除后按文件转移。" % dst_item)
            except OSError as exc:
                stats["failed"] += 1
                stats["errors"].append("无法删除同名文件夹：%s（%s）" % (dst_item, exc))
                return
        copy_one_file(src_item, dst_item, stats, skip_same=skip_same, on_file=on_file)


def new_stats():
    return {"new": 0, "over": 0, "same": 0, "failed": 0, "bytes": 0, "errors": []}


def merge_stats(target, src):
    for k in ("new", "over", "same", "failed", "bytes"):
        target[k] += src[k]
    target["errors"].extend(src["errors"])


# ---------------------------------------------------------------------------
# 扫描：找出存在的默认项 / 缺失的默认项 / 额外的玩家数据
# ---------------------------------------------------------------------------

def item_path(root, name):
    return os.path.join(root, name)


def scan_instance(path):
    """返回 (present, missing, extras)。

    present: [(名称, 类型, 说明), ...]      老实例里存在、可以直接转移的默认项
    missing: [(名称, 类型, 说明, 原因), ...] 默认列表里老实例中找不到的项
    extras:  [(名称, 类型, 说明, 默认勾选), ...] 默认列表之外发现的玩家数据
    """
    present, missing = [], []
    for name, kind, desc in DEFAULT_ITEMS:
        p = item_path(path, name)
        if kind == "dir":
            ok = is_dir(p)
        else:
            ok = is_file(p)
        if ok:
            present.append((name, kind, desc))
        else:
            reason = "类型不符" if path_exists(p) else "不存在"
            missing.append((name, kind, desc, reason))

    extras = []
    for name, kind, desc, default_on in OPTIONAL_ITEMS:
        p = item_path(path, name)
        ok = is_dir(p) if kind == "dir" else is_file(p)
        if ok:
            extras.append((name, kind, desc, default_on))
    return present, missing, extras


def count_items(root, items):
    """统计一组条目（文件或文件夹）的文件总数与字节数。"""
    total, size = 0, 0
    for item in items:
        name, kind = item[0], item[1]
        p = item_path(root, name)
        if kind == "dir":
            n, b = count_files(p)
            total += n
            size += b
        elif is_file(p):
            total += 1
            size += _size_of(p)
    return total, size


def looks_like_instance(path):
    if not path or not is_dir(path):
        return 0
    score = 0
    for name, _kind, _desc in DEFAULT_ITEMS:
        if path_exists(item_path(path, name)):
            score += 1
    for name, _kind, _desc, _on in OPTIONAL_ITEMS:
        if path_exists(item_path(path, name)):
            score += 1
    return score


def normalize_instance_path(path):
    """用户可能选了包含 .minecraft 的上一层目录，这里自动下钻一层。"""
    if not path:
        return path, None
    if looks_like_instance(path) > 0:
        return path, None
    inner = os.path.join(path, ".minecraft")
    if is_dir(inner) and looks_like_instance(inner) > 0:
        return inner, "所选目录里没有实例文件，已自动改用子目录：%s" % inner
    return path, None


# ---------------------------------------------------------------------------
# 转移线程
# ---------------------------------------------------------------------------

class TransferRunner(threading.Thread):
    def __init__(self, src, dst, items, do_backup, msg_q, cancel):
        super().__init__(daemon=True)
        self.src = src
        self.dst = dst
        self.items = items                       # [(名称, 类型, 说明), ...]
        self.do_backup = do_backup
        self.q = msg_q
        self.cancel = cancel

    # --- 给 GUI 发消息 -------------------------------------------------
    def log(self, text):
        self.q.put(("log", text))

    def phase(self, text, indeterminate=False):
        self.q.put(("phase", (text, indeterminate)))

    def progress(self, done, total):
        self.q.put(("progress", (done, total)))

    # --- 主流程 ---------------------------------------------------------
    def run(self):
        started = time.time()
        stats = new_stats()
        try:
            self.phase("正在统计文件…", True)
            total, total_size = count_items(self.src, self.items)
            self.log("本次转移 %d 项，共 %d 个文件（约 %s）。"
                     % (len(self.items), total, human_size(total_size)))

            done = 0

            def on_file():
                nonlocal done
                done += 1
                self.progress(done, max(total, 1))

            # ---------- 1. 备份 ----------
            backup_dir = None
            if self.do_backup:
                todo = [it for it in self.items
                        if path_exists(item_path(self.dst, it[0]))]
                if todo:
                    backup_dir = os.path.join(
                        self.dst, "_转移备份_" + time.strftime("%Y%m%d_%H%M%S"))
                    n = 1
                    while path_exists(backup_dir):
                        backup_dir = os.path.join(
                            self.dst,
                            "_转移备份_%s_%d" % (time.strftime("%Y%m%d_%H%M%S"), n))
                        n += 1
                    self.phase("正在备份新实例中将被覆盖的内容…", True)
                    self.log("开始备份新实例中将被覆盖的 %d 项 → %s" % (len(todo), backup_dir))
                    bstats = new_stats()
                    for name, kind, _desc in todo:
                        if self.cancel.is_set():
                            raise TransferCancelled()
                        copy_item(item_path(self.dst, name),
                                  os.path.join(backup_dir, name),
                                  bstats, skip_same=False,
                                  on_log=self.log, cancel=self.cancel)
                    merge_stats(stats, bstats)
                    self.log("备份完成：%d 个文件（约 %s）。"
                             % (bstats["new"], human_size(bstats["bytes"])))
                else:
                    self.log("新实例里没有与转移列表同名的内容，无需备份。")

            # ---------- 2. 覆盖转移 ----------
            self.phase("正在转移数据…", False)
            per_item = []
            for name, kind, _desc in self.items:
                if self.cancel.is_set():
                    raise TransferCancelled()
                s = item_path(self.src, name)
                d = item_path(self.dst, name)
                istats = new_stats()
                self.log("→ 转移 %s（%s）" % (name, "文件夹" if kind == "dir" else "文件"))
                copy_item(s, d, istats, skip_same=True, on_file=on_file,
                          on_log=self.log, cancel=self.cancel)
                merge_stats(stats, istats)
                per_item.append((name, istats))
                if istats["failed"]:
                    self.log("   %s：新增 %d，覆盖 %d，相同跳过 %d，失败 %d"
                             % (name, istats["new"], istats["over"],
                                istats["same"], istats["failed"]))
                else:
                    self.log("   %s：新增 %d，覆盖 %d，相同跳过 %d"
                             % (name, istats["new"], istats["over"], istats["same"]))

            elapsed = time.time() - started
            summary = {
                "stats": stats,
                "per_item": per_item,
                "backup_dir": backup_dir,
                "elapsed": elapsed,
                "file_count": total,
                "size": total_size,
            }
            self.progress(total, max(total, 1))
            self.q.put(("done", summary))

        except TransferCancelled:
            self.log("已取消（已经复制的内容不会回滚）。")
            self.q.put(("cancelled", stats))
        except Exception:                                       # noqa: BLE001
            self.q.put(("error", traceback.format_exc()))


# ---------------------------------------------------------------------------
# 可滚动容器
# ---------------------------------------------------------------------------

class ScrollFrame(ttk.Frame):
    def __init__(self, master, height=260, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0, bg="#ffffff")
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda _e: self._unbind_wheel())

    def _on_inner(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ---------------------------------------------------------------------------
# 转移前确认窗口（缺项 + 额外玩家数据询问）
# ---------------------------------------------------------------------------

class ConfirmDialog(tk.Toplevel):
    """概述功能，列出缺失项，并询问是否把额外发现的玩家数据加入转移列表。"""

    def __init__(self, master, src, present, missing, extras):
        super().__init__(master)
        self.title("转移前确认 —— 请选择要加入转移列表的内容")
        self.transient(master)
        self.resizable(True, True)
        self.ui = getattr(master, "ui", ui_scale(self))
        wrap = int(720 * self.ui)
        self.action = None                 # "go" / "cancel"
        self.chosen = []                   # 额外项名称列表
        self.vars = {}

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # 底部按钮栏先占位，避免内容过长时被挤出窗口
        bar = ttk.Frame(root)
        bar.pack(side="bottom", fill="x")

        ttk.Label(root, text="本工具的功能概述",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        desc = ("本工具会把「老实例」里的下列 %d 项内容【覆盖】到「新实例」。\n"
                "新实例中的模组（mods）、版本（versions）、启动器文件不会被删除：\n%s\n"
                "文件夹采用合并覆盖：同名文件被覆盖，新实例里独有的文件保留。"
                % (len(DEFAULT_ITEMS), LIST_LINES))
        ttk.Label(root, text=desc, justify="left",
                  wraplength=wrap).pack(anchor="w", fill="x", pady=(2, 8))

        ttk.Label(root, text="① 需要你决定：以下是默认列表之外的玩家信息，"
                            "勾选的会一起转移（括号里是它在老实例里的实际体积）"
                  if extras else "① 默认列表之外的玩家信息：没有发现额外的内容",
                  justify="left", wraplength=wrap, foreground="#004a8a",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", fill="x")

        body = ScrollFrame(root, height=int(360 * self.ui))
        body.pack(fill="both", expand=True, pady=(8, 8))

        # ---- 一、额外发现的玩家数据（需要用户勾选，放在最上面最显眼） ----
        if extras:
            for name, kind, d, default_on in extras:
                var = tk.BooleanVar(value=default_on)
                self.vars[name] = var
                ttk.Checkbutton(body.inner,
                                text="[%s] %s（%s）\n     %s"
                                     % ("默认勾选" if default_on else "默认不勾选",
                                        name, size_note(item_path(src, name), kind), d),
                                variable=var).pack(anchor="w", padx=(16, 0), pady=1)
            ttk.Label(body.inner,
                      text="    没有勾选的内容不会被动到；不需要的直接取消勾选即可。"
                           "点下面的「只转移默认列表」则这些全部不转移。",
                      justify="left", wraplength=wrap - 20,
                      foreground="#555555").pack(anchor="w", fill="x", pady=(2, 10))
            ttk.Separator(body.inner, orient="horizontal").pack(fill="x", pady=(2, 8))

        # ---- 二、缺失的默认项 ----
        if missing:
            ttk.Label(body.inner, text="② 老实例中【没有找到】的默认项（本次会自动跳过）",
                      font=("Microsoft YaHei UI", 10, "bold"),
                      foreground="#b00000").pack(anchor="w", pady=(0, 2))
            for name, kind, d, reason in missing:
                ttk.Label(body.inner,
                          text="    · %s（%s）—— %s，%s"
                               % (name, "文件夹" if kind == "dir" else "文件", d, reason),
                          justify="left", wraplength=wrap - 20).pack(anchor="w", fill="x")
            ttk.Label(body.inner,
                      text="    说明：若它们其实在所选目录的.minecraft子目录里，"
                           "请返回重新选择「老实例文件夹」。",
                      justify="left", wraplength=wrap - 20,
                      foreground="#8a5a00").pack(anchor="w", fill="x", pady=(2, 10))
            ttk.Separator(body.inner, orient="horizontal").pack(fill="x", pady=(2, 8))

        # ---- 三、默认项的逐项作用说明 ----
        ttk.Label(body.inner, text="③ 将直接转移的默认项（%d 项，逐项作用）：" % len(present),
                  font=("Microsoft YaHei UI", 10, "bold"),
                  foreground="#1a6b1a").pack(anchor="w", pady=(0, 2))
        if present:
            for name, kind, d in present:
                ttk.Label(body.inner,
                          text="    · %s（%s）\n          %s"
                               % (name, size_note(item_path(src, name), kind), d),
                          justify="left", wraplength=wrap - 20,
                          foreground="#1a6b1a").pack(anchor="w", fill="x", pady=1)
        else:
            ttk.Label(body.inner, text="    （无）", foreground="#1a6b1a").pack(anchor="w")

        ttk.Button(bar, text="加入勾选内容并开始转移",
                   command=self._go).pack(side="left")
        ttk.Button(bar, text="只转移默认列表",
                   command=self._default_only).pack(side="left", padx=8)
        ttk.Button(bar, text="取消",
                   command=self._cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        autosize(self, int(760 * self.ui), int(560 * self.ui),
                 int(600 * self.ui), int(420 * self.ui))
        self._center(master)
        self.wait_window(self)

    def _center(self, master):
        self.update_idletasks()
        try:
            w, h = self.winfo_width(), self.winfo_height()
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - h) // 3
            self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        except tk.TclError:
            pass

    def _go(self):
        self.chosen = [n for n, v in self.vars.items() if v.get()]
        self.action = "go"
        self.destroy()

    def _default_only(self):
        self.chosen = []
        self.action = "go"
        self.destroy()

    def _cancel(self):
        self.action = None
        self.destroy()


# ---------------------------------------------------------------------------
# 只读清单窗口（每项是什么、有什么用、在老实例里多大）
# ---------------------------------------------------------------------------

class ListDialog(tk.Toplevel):
    """把默认项与询问项连同各自的实际作用和体积列出来，方便随时查看。"""

    def __init__(self, master, src=""):
        super().__init__(master)
        self.title("转移清单 —— 每一项都是什么、有什么用")
        self.transient(master)
        self.resizable(True, True)
        ui = getattr(master, "ui", ui_scale(self))
        wrap = int(720 * ui)
        has_src = bool(src) and is_dir(src)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # 底部按钮栏先占位，避免清单过长时把「关闭」挤出窗口
        bar = ttk.Frame(root)
        bar.pack(side="bottom", fill="x")

        ttk.Label(root, text="默认转移列表：每次都会转移（共 %d 项）" % len(DEFAULT_ITEMS),
                  font=("Microsoft YaHei UI", 11, "bold"),
                  foreground="#1a6b1a").pack(anchor="w")
        ttk.Label(root,
                  text=("括号里是在「%s」里的实际体积。" % src) if has_src
                  else "（还没选老实例文件夹，先不显示体积）",
                  justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 6))

        body = ScrollFrame(root, height=int(420 * ui))
        body.pack(fill="both", expand=True, pady=(0, 8))

        for name, kind, d in DEFAULT_ITEMS:
            ttk.Label(body.inner,
                      text="· %s（%s）\n      %s"
                           % (name, size_note(item_path(src, name), kind) if has_src
                              else ("文件夹" if kind == "dir" else "文件"), d),
                      justify="left", wraplength=wrap - 20,
                      foreground="#1a6b1a").pack(anchor="w", fill="x", pady=2)

        ttk.Separator(body.inner, orient="horizontal").pack(fill="x", pady=(8, 8))

        ttk.Label(body.inner,
                  text="其它玩家信息：转移前弹窗询问，勾选后才转移（共 %d 项）"
                       % len(OPTIONAL_ITEMS),
                  font=("Microsoft YaHei UI", 11, "bold"),
                  foreground="#004a8a").pack(anchor="w", pady=(0, 4))
        for name, kind, d, default_on in OPTIONAL_ITEMS:
            ttk.Label(body.inner,
                      text="· [%s] %s（%s）\n      %s"
                           % ("默认勾选" if default_on else "默认不勾选", name,
                              size_note(item_path(src, name), kind) if has_src
                              else ("文件夹" if kind == "dir" else "文件"), d),
                      justify="left", wraplength=wrap - 20,
                      foreground="#004a8a").pack(anchor="w", fill="x", pady=2)

        ttk.Button(bar, text="关闭", command=self.destroy).pack(side="right")
        ttk.Label(bar, text="%s　|　改动清单：编辑 mc_transfer.py 里的 DEFAULT_ITEMS / "
                            "OPTIONAL_ITEMS" % APP_AUTHOR_NOTE,
                  foreground="#777777").pack(side="left")

        autosize(self, int(760 * ui), int(620 * ui), int(620 * ui), int(460 * ui))
        self._center(master)

    def _center(self, master):
        self.update_idletasks()
        try:
            w, h = self.winfo_width(), self.winfo_height()
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - h) // 4
            self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 主界面
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s v%s" % (APP_TITLE, APP_VERSION))
        self.option_add("*Font", UI_FONT)
        try:
            ttk.Style(self).configure(".", font=UI_FONT)
        except tk.TclError:
            pass

        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.backup_var = tk.BooleanVar(value=True)
        self.ask_var = tk.BooleanVar(value=True)

        self.msg_q = queue.Queue()
        self.cancel_flag = threading.Event()
        self.worker = None
        self.transferring = False

        self._build()
        self.update_idletasks()
        autosize(self, int(880 * self.ui), int(660 * self.ui),
                 int(680 * self.ui), int(520 * self.ui))
        self.bind("<Configure>", self._on_resize)
        self.after(80, self._pump)
        self.log("欢迎使用 %s v%s（%s）。" % (APP_TITLE, APP_VERSION, APP_AUTHOR_NOTE))
        self.log("使用顺序：① 选择老实例文件夹 → ② 选择新实例文件夹 → ③ 开始转移数据。")
        self.log("默认转移列表：%s" % LIST_TEXT)

    def _on_resize(self, event):
        """窗口变窄时让顶部说明文字自动换行，避免被裁切。"""
        if event.widget is not self:
            return
        wrap = max(int(320 * self.ui), event.width - int(40 * self.ui))
        for lbl in getattr(self, "head_labels", []):
            lbl.configure(wraplength=wrap)

    # ---------------- 界面 ----------------
    def _build(self):
        self.ui = ui_scale(self)
        wrap = int(760 * self.ui)

        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        ttk.Label(top, text="%s  v%s" % (APP_TITLE, APP_VERSION),
                  font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        ttk.Label(top, text=APP_AUTHOR_NOTE,
                  foreground="#666666").pack(anchor="w", pady=(0, 2))
        self.head_labels = []
        for text in (
            "把老实例的玩家数据覆盖到新实例（默认 %d 项）：\n%s。" % (len(DEFAULT_ITEMS),
                                                                     LIST_LINES),
            "模组（mods）、versions、启动器文件不会被修改；文件夹为合并覆盖，"
            "新实例里独有的文件不会被删除。",
        ):
            lbl = ttk.Label(top, text=text, justify="left", wraplength=wrap)
            lbl.pack(anchor="w", fill="x")
            self.head_labels.append(lbl)

        box = ttk.LabelFrame(self, text=" 第一步 / 第二步：选择两个实例文件夹 ", padding=10)
        box.pack(fill="x", padx=12, pady=8)

        ttk.Label(box, text="老实例（源）：").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(box, textvariable=self.src_var).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(box, text="① 选择老实例文件夹", width=20,
                   command=self.choose_src).grid(row=0, column=2)

        ttk.Label(box, text="新实例（目标）：").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(box, textvariable=self.dst_var).grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(box, text="② 选择新实例文件夹", width=20,
                   command=self.choose_dst).grid(row=1, column=2)
        box.columnconfigure(1, weight=1)

        act = ttk.Frame(self, padding=(12, 0))
        act.pack(fill="x")
        self.go_btn = ttk.Button(act, text="③ 开始转移数据（覆盖新实例）",
                                 command=self.on_transfer)
        self.go_btn.pack(side="left", ipadx=14, ipady=6)
        self.cancel_btn = ttk.Button(act, text="中止本次转移", command=self.on_cancel,
                                     state="disabled")
        self.cancel_btn.pack(side="left", padx=10)

        opts = ttk.Frame(self, padding=(12, 2))
        opts.pack(fill="x")
        ttk.Checkbutton(opts, text="转移前自动备份新实例中将被覆盖的内容",
                        variable=self.backup_var).pack(side="left")
        ttk.Checkbutton(opts, text="转移前询问缺失项与额外玩家数据",
                        variable=self.ask_var).pack(side="left", padx=18)
        ttk.Button(opts, text="查看每项作用", command=self.show_lists).pack(side="left")
        ttk.Button(opts, text="关于", command=self.show_about).pack(side="left", padx=8)

        prog = ttk.Frame(self, padding=(12, 8, 12, 0))
        prog.pack(fill="x")
        self.phase_var = tk.StringVar(value="就绪")
        ttk.Label(prog, textvariable=self.phase_var).pack(anchor="w")
        self.bar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=4)

        logbox = ttk.LabelFrame(self, text=" 运行日志 ", padding=6)
        logbox.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.log_text = tk.Text(logbox, height=14, wrap="word", state="disabled",
                                bg="#fbfbfb")
        sb = ttk.Scrollbar(logbox, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ---------------- 日志 / 消息 ----------------
    def log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "[%s] %s\n" % (time.strftime("%H:%M:%S"), text))
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _pump(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "phase":
                    text, indet = payload
                    self.phase_var.set(text)
                    self.bar.configure(mode="indeterminate" if indet else "determinate")
                    if indet:
                        self.bar.start(60)
                    else:
                        self.bar.stop()
                elif kind == "progress":
                    done, total = payload
                    self.bar.stop()
                    self.bar.configure(mode="determinate", maximum=max(total, 1),
                                       value=done)
                elif kind == "done":
                    self._on_done(payload)
                elif kind == "cancelled":
                    self._finish()
                    self.phase_var.set("已取消")
                elif kind == "error":
                    self._finish()
                    self.phase_var.set("出错")
                    self.log(payload)
                    messagebox.showerror("出错了", payload)
        except queue.Empty:
            pass
        self.after(60, self._pump)

    def _finish(self):
        self.transferring = False
        self.go_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.bar.stop()
        try:
            self.bar.configure(mode="determinate")
        except tk.TclError:
            pass

    def _on_done(self, summary):
        self._finish()
        self.phase_var.set("完成")
        st = summary["stats"]
        self.log("=" * 60)
        self.log("转移完成，用时 %.1f 秒。" % summary["elapsed"])
        self.log("新增文件 %d 个，覆盖文件 %d 个，内容相同跳过 %d 个，失败 %d 个，共写入约 %s。"
                 % (st["new"], st["over"], st["same"], st["failed"],
                    human_size(st["bytes"])))
        if summary["backup_dir"]:
            self.log("新实例被覆盖内容的备份：%s" % summary["backup_dir"])
        if st["errors"]:
            self.log("以下 %d 项未能完成：" % len(st["errors"]))
            for e in st["errors"][:200]:
                self.log("   ! " + e)
        self.log("=" * 60)

        msg = ("转移完成！\n\n"
               "新增文件：%d 个\n覆盖文件：%d 个\n内容相同跳过：%d 个\n失败：%d 个\n"
               "共写入约 %s，用时 %.1f 秒。" % (st["new"], st["over"], st["same"],
                                                st["failed"], human_size(st["bytes"]),
                                                summary["elapsed"]))
        if summary["backup_dir"]:
            msg += "\n\n被覆盖内容的备份：\n%s" % summary["backup_dir"]
        if st["failed"]:
            msg += "\n\n有 %d 个文件失败，详情见日志（常见原因：文件被游戏或启动器占用）。" % st["failed"]
        messagebox.showinfo("转移完成", msg)

        if messagebox.askyesno("打开文件夹", "是否打开新实例文件夹？"):
            self._open_dir(self.dst_var.get().strip())

    # ---------------- 选择文件夹 ----------------
    def choose_src(self):
        p = filedialog.askdirectory(title="请选择【老实例】文件夹（原实例的游戏目录）")
        if not p:
            return
        p = os.path.normpath(p)
        p, note = normalize_instance_path(p)
        self.src_var.set(p)
        if note:
            self.log(note)
        present, missing, extras = scan_instance(p)
        self.log("已选择老实例：%s" % p)
        self.log("   默认项找到 %d/%d：%s" % (len(present), len(DEFAULT_ITEMS),
                                              "、".join(n for n, _k, _d in present) or "无"))
        if missing:
            self.log("   缺失：%s（转移时会弹窗提醒）"
                     % "、".join("%s(%s)" % (n, r) for n, _k, _d, r in missing))
        if extras:
            self.log("   额外发现的玩家数据：%s（转移时会询问是否加入）"
                     % "、".join(n for n, _k, _d, _on in extras))

    def choose_dst(self):
        p = filedialog.askdirectory(title="请选择【新实例】文件夹（要转移进去的游戏目录）")
        if not p:
            return
        p = os.path.normpath(p)
        p, note = normalize_instance_path(p)
        self.dst_var.set(p)
        if note:
            self.log(note)
        self.log("已选择新实例：%s" % p)

    def show_lists(self):
        """打开只读清单，逐条说明每一项是什么、有什么用、多大。"""
        dlg = getattr(self, "list_dlg", None)
        if dlg is not None and dlg.winfo_exists():
            dlg.lift()
            dlg.focus_set()
            return
        self.list_dlg = ListDialog(self, self.src_var.get().strip())

    def show_about(self):
        """关于：版本与作者声明。"""
        messagebox.showinfo(
            "关于",
            "%s  v%s\n\n"
            "%s。\n\n"
            "用途：把「老实例」的玩家数据（默认 %d 项：config、resourcepacks、saves、"
            "schematics、screenshots、shaderpacks、xaero、options.txt、servers.dat）"
            "合并覆盖到「新实例」，并在转移前询问是否一并转移其它 %d 项玩家数据"
            "（含 Voxy / Distant Horizons 远景缓存）。\n\n"
            "转移前自动备份，碰不到的模组与版本不会被改动。"
            % (APP_TITLE, APP_VERSION, APP_AUTHOR_NOTE,
               len(DEFAULT_ITEMS), len(OPTIONAL_ITEMS)))

    # ---------------- 开始转移 ----------------
    def on_transfer(self):
        if self.transferring:
            messagebox.showinfo("请稍等", "上一次转移还在进行中。")
            return
        src = self.src_var.get().strip().strip('"')
        dst = self.dst_var.get().strip().strip('"')
        if not src or not dst:
            messagebox.showwarning("还差一步", "请先选择老实例文件夹和新实例文件夹。")
            return
        src = os.path.normpath(src)
        dst = os.path.normpath(dst)
        if not is_dir(src):
            messagebox.showerror("路径错误", "老实例文件夹不存在或不是一个文件夹：\n%s" % src)
            return
        if not is_dir(dst):
            messagebox.showerror("路径错误", "新实例文件夹不存在或不是一个文件夹：\n%s" % dst)
            return
        if os.path.normcase(src) == os.path.normcase(dst):
            messagebox.showerror("路径错误", "老实例和新实例是同一个文件夹，不需要转移。")
            return
        try:
            common = os.path.commonpath([os.path.abspath(src), os.path.abspath(dst)])
            if os.path.normcase(common) in (os.path.normcase(os.path.abspath(src)),
                                            os.path.normcase(os.path.abspath(dst))):
                messagebox.showerror("路径错误",
                                     "两个文件夹存在包含关系（一个在另一个里面），"
                                     "为避免无限复制已阻止。")
                return
        except ValueError:
            pass

        present, missing, extras = scan_instance(src)
        if not present:
            messagebox.showerror(
                "没有找到可转移的内容",
                "在老实例文件夹里没有找到默认转移列表中的任何一项：\n\n%s\n\n"
                "请确认选择的是游戏目录（通常名为 .minecraft，或启动器的版本隔离目录）。\n"
                "当前选择：%s" % (LIST_TEXT, src))
            return

        items = list(present)

        if self.ask_var.get() and (missing or extras):
            dlg = ConfirmDialog(self, src, present, missing, extras)
            if dlg.action != "go":
                self.log("用户取消了转移。")
                return
            if dlg.chosen:
                chosen_set = set(dlg.chosen)
                for name, kind, desc, _on in extras:
                    if name in chosen_set:
                        items.append((name, kind, desc))
                self.log("已把以下内容加入本次转移列表：%s" % "、".join(dlg.chosen))
            else:
                self.log("本次只转移默认列表内容。")
            if missing:
                self.log("以下默认项在老实例中未找到，已跳过：%s"
                         % "、".join(n for n, _k, _d, _r in missing))
        elif missing:
            self.log("以下默认项在老实例中未找到，已跳过：%s"
                     % "、".join(n for n, _k, _d, _r in missing))

        # 用快速估算给出体积（大缓存的完整遍历放到后台线程里做）
        est_size = 0
        est_files = 0
        est_exact = True
        for it in items:
            b, n, trunc = quick_size(item_path(src, it[0]),
                                     max_files=20000, max_seconds=2.0)
            est_size += b
            est_files += n
            est_exact = est_exact and not trunc
        ok = messagebox.askyesno(
            "确认转移",
            "即将把老实例的下列内容覆盖到新实例：\n\n"
            "老实例：%s\n新实例：%s\n\n"
            "转移项（%d 项）：%s\n"
            "共%s %d 个文件，%s %s。\n\n"
            "%s\n\n文件夹为合并覆盖（新实例独有的文件保留）。是否继续？"
            % (src, dst, len(items), "、".join(i[0] for i in items),
               "" if est_exact else "至少", est_files,
               "约" if est_exact else "≥", human_size(est_size),
               "转移前会备份新实例中将被覆盖的内容。" if self.backup_var.get()
               else "注意：未开启备份，覆盖后无法恢复。"))
        if not ok:
            return

        self.cancel_flag.clear()
        self.transferring = True
        self.go_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.log("-" * 60)
        self.log("开始转移：%s → %s" % (src, dst))
        self.worker = TransferRunner(src, dst, items, self.backup_var.get(),
                                     self.msg_q, self.cancel_flag)
        self.worker.start()

    def on_cancel(self):
        if self.transferring:
            self.cancel_flag.set()
            self.log("已请求中止，正在等待当前文件复制结束…")
            self.phase_var.set("正在中止…")

    def _open_dir(self, path):
        try:
            if os.name == "nt":
                os.startfile(path)                             # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:                               # noqa: BLE001
            messagebox.showwarning("打不开", "无法打开文件夹：%s" % exc)


# ---------------------------------------------------------------------------
# 自检（不开界面，验证扫描与转移逻辑）
# ---------------------------------------------------------------------------

def selftest():
    import tempfile

    ok = True

    def check(cond, text):
        nonlocal ok
        print(("  [通过] " if cond else "  [失败] ") + text)
        if not cond:
            ok = False

    base = tempfile.mkdtemp(prefix="mcxfer_")
    src = os.path.join(base, "老实例")
    dst = os.path.join(base, "新实例")

    def w(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    print("自检开始，临时目录：%s" % base)

    # 老实例：默认列表缺 schematics / xaero / screenshots，多出若干玩家数据
    w(os.path.join(src, "config", "a.toml"), "新配置")
    w(os.path.join(src, "config", "sub", "b.toml"), "子目录配置")
    w(os.path.join(src, "saves", "world", "level.dat"), "存档数据")
    w(os.path.join(src, "resourcepacks", "pack.zip"), "资源包")
    w(os.path.join(src, "shaderpacks", "shader.zip"), "光影")
    w(os.path.join(src, "options.txt"), "老实例的 options")
    w(os.path.join(src, "servers.dat"), "服务器列表")
    w(os.path.join(src, "journeymap", "waypoints.json"), "路径点")
    w(os.path.join(src, ".voxy", "server1", "lods.db"), "voxy 远景数据")
    w(os.path.join(src, "Distant_Horizons_server_data", "Srv", "dim_overworld", "d.sqlite"),
      "dh 远景数据")
    w(os.path.join(src, "mods", "x.jar"), "模组")

    # 新实例：有旧的 config/options.txt，也有自己独有的文件
    w(os.path.join(dst, "config", "a.toml"), "旧配置")
    w(os.path.join(dst, "config", "keep.toml"), "新实例独有")
    w(os.path.join(dst, "options.txt"), "新实例的 options")
    w(os.path.join(dst, "saves", "other", "level.dat"), "新实例自己的存档")

    present, missing, extras = scan_instance(src)
    pn = [n for n, _k, _d in present]
    mn = [n for n, _k, _d, _r in missing]
    en = [n for n, _k, _d, _o in extras]

    check(set(pn) == {"config", "resourcepacks", "saves", "shaderpacks",
                      "options.txt", "servers.dat"},
          "默认项识别正确：%s" % pn)
    check(set(mn) == {"schematics", "xaero", "screenshots"}, "缺失项识别正确：%s" % mn)
    check(set(en) == {"journeymap", ".voxy", "Distant_Horizons_server_data", "mods"},
          "额外玩家数据识别正确：%s" % en)
    opt_names = [o[0] for o in OPTIONAL_ITEMS]
    check("servers.dat" not in opt_names and "screenshots" not in opt_names
          and len(DEFAULT_ITEMS) == 9,
          "servers.dat / screenshots 已并入默认列表（默认 %d 项，询问 %d 项）"
          % (len(DEFAULT_ITEMS), len(OPTIONAL_ITEMS)))
    opt_map = {o[0]: o for o in OPTIONAL_ITEMS}
    check(len(OPTIONAL_ITEMS) == 16
          and ".voxy" in opt_map and "Distant_Horizons_server_data" in opt_map
          and opt_map[".voxy"][3] and opt_map["Distant_Horizons_server_data"][3],
          "Voxy / Distant Horizons 远景缓存已加入询问列表且默认勾选")
    check(len(opt_map[".voxy"][2]) > 30 and len(opt_map["mods"][2]) > 30,
          "每一项都带有作用说明（抽查 voxy / mods 说明长度）")
    note = size_note(item_path(src, ".voxy"), "dir")
    check("约" in note or "≥" in note, "弹窗体积说明可用：%s" % note)

    items = list(present) + [(n, k, d) for n, k, d, _o in extras if n != "mods"]
    stats = new_stats()
    for name, kind, _d in items:
        copy_item(item_path(src, name), item_path(dst, name), stats, skip_same=True)

    def r(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    check(r(os.path.join(dst, "config", "a.toml")) == "新配置", "config/a.toml 已覆盖")
    check(r(os.path.join(dst, "config", "sub", "b.toml")) == "子目录配置", "子目录文件已新增")
    check(os.path.exists(os.path.join(dst, "config", "keep.toml")), "新实例独有文件未被删除")
    check(r(os.path.join(dst, "options.txt")) == "老实例的 options", "options.txt 已覆盖")
    check(r(os.path.join(dst, "saves", "world", "level.dat")) == "存档数据", "存档已转移")
    check(os.path.exists(os.path.join(dst, "saves", "other", "level.dat")), "新实例存档保留")
    check(r(os.path.join(dst, "servers.dat")) == "服务器列表", "默认项 servers.dat 已转移")
    check(r(os.path.join(dst, ".voxy", "server1", "lods.db")) == "voxy 远景数据",
          "勾选的 .voxy 远景缓存已转移")
    check(r(os.path.join(dst, "Distant_Horizons_server_data", "Srv", "dim_overworld",
                         "d.sqlite")) == "dh 远景数据",
          "勾选的 Distant_Horizons_server_data 已转移")
    check(not os.path.exists(os.path.join(dst, "mods")), "未勾选的 mods 未被转移")
    check(not os.path.exists(os.path.join(dst, "schematics")), "缺失项被安全跳过")
    check(stats["failed"] == 0, "无失败文件（失败 %d）" % stats["failed"])

    # 幂等：再跑一次应全部命中「内容相同跳过」
    stats2 = new_stats()
    for name, kind, _d in items:
        copy_item(item_path(src, name), item_path(dst, name), stats2, skip_same=True)
    check(stats2["failed"] == 0 and stats2["over"] == 0,
          "重复转移安全（覆盖 %d，失败 %d）" % (stats2["over"], stats2["failed"]))

    # 反向：新实例里没有的默认项不会报错
    stats3 = new_stats()
    copy_item(item_path(src, "schematics"), item_path(dst, "schematics"), stats3,
              skip_same=True)
    check(not os.path.exists(os.path.join(dst, "schematics")), "源缺失时不产生空目录")

    # 陷阱测试：大小与修改时间完全相同、但内容不同的文件必须被覆盖
    t1 = os.path.join(base, "t1")
    t2 = os.path.join(base, "t2")
    os.makedirs(t1, exist_ok=True)
    os.makedirs(t2, exist_ok=True)
    sizes = (1024, VERIFY_LIMIT + 4096)
    for size in sizes:
        pa = os.path.join(t1, "f_%d.bin" % size)
        pb = os.path.join(t2, "f_%d.bin" % size)
        with open(pa, "wb") as f:
            f.write(b"A" * size)
        with open(pb, "wb") as f:
            f.write(b"B" * size)
        os.utime(pa, (1700000000, 1700000000))
        os.utime(pb, (1700000000, 1700000000))
    st4 = new_stats()
    copy_item(t1, t2, st4, skip_same=True)
    good = True
    for size in sizes:
        with open(os.path.join(t2, "f_%d.bin" % size), "rb") as f:
            good = good and f.read(1) == b"A"
    check(good, "大小与时间相同但内容不同时，仍然正确覆盖")

    st5 = new_stats()
    copy_item(t1, t2, st5, skip_same=True)
    check(st5["same"] == 1 and st5["over"] == 1,
          "内容真相同的文件跳过、超大文件保守重写（跳过 %d，覆盖 %d）"
          % (st5["same"], st5["over"]))

    # 后台线程 + 备份 的完整流程
    rsrc = os.path.join(base, "runner_old")
    rdst = os.path.join(base, "runner_new")
    w(os.path.join(rsrc, "config", "a.toml"), "老配置")
    w(os.path.join(rsrc, "options.txt"), "老 OPTIONS")
    w(os.path.join(rdst, "config", "a.toml"), "新配置")
    w(os.path.join(rdst, "config", "only_new.toml"), "新实例独有")
    items = [("config", "dir", "配置"), ("options.txt", "file", "设置")]

    def drain(q):
        out = []
        while True:
            try:
                out.append(q.get_nowait())
            except queue.Empty:
                return out

    q = queue.Queue()
    runner = TransferRunner(rsrc, rdst, items, True, q, threading.Event())
    runner.start()
    runner.join(120)
    msgs = drain(q)
    kinds = [k for k, _p in msgs]
    check("done" in kinds, "后台转移线程正常结束（消息：%s）" % sorted(set(kinds)))
    if "done" in kinds:
        summary = [p for k, p in msgs if k == "done"][0]
        check(summary["stats"]["failed"] == 0, "后台转移无失败文件")
        bdir = summary["backup_dir"]
        check(bool(bdir) and os.path.exists(os.path.join(bdir, "config", "a.toml")),
              "覆盖前已备份新实例的原文件")
        if bdir:
            check(r(os.path.join(bdir, "config", "a.toml")) == "新配置", "备份内容正确")
        check(r(os.path.join(rdst, "config", "a.toml")) == "老配置", "后台转移已覆盖配置")
        check(r(os.path.join(rdst, "options.txt")) == "老 OPTIONS", "后台转移已覆盖 options.txt")
        check(os.path.exists(os.path.join(rdst, "config", "only_new.toml")),
              "新实例独有的文件保留")

    q2 = queue.Queue()
    ev = threading.Event()
    ev.set()
    runner2 = TransferRunner(rsrc, rdst, items, False, q2, ev)
    runner2.start()
    runner2.join(60)
    check("cancelled" in [k for k, _p in drain(q2)], "取消标志能中止转移")

    print("自检结果：%s" % ("全部通过" if ok else "存在失败项"))
    shutil.rmtree(base, ignore_errors=True)
    return ok


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def enable_dpi():
    if os.name != "nt":
        return
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:                                          # noqa: BLE001
        pass


def run_demo(app, mode="dialog"):
    """内部自测：生成两个示例实例，填入路径并弹出确认窗口（--demo / --demo-list）。"""
    import tempfile

    base = tempfile.mkdtemp(prefix="mcxfer_demo_")
    src = os.path.join(base, "老实例")
    dst = os.path.join(base, "新实例")

    def w(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    for name, kind, _d in DEFAULT_ITEMS:
        if name in ("schematics", "xaero", "screenshots"):   # 故意留几项缺失，验证缺项提示
            continue
        w(os.path.join(src, name, "示例.txt") if kind == "dir"
          else os.path.join(src, name), "示例内容")
    w(os.path.join(src, "journeymap", "waypoints.json"), "路径点")
    w(os.path.join(src, "iris.properties"), "iris 设置")
    w(os.path.join(src, "replay_recordings", "r.mp4"), "录像")
    w(os.path.join(src, "mods", "示例模组.jar"), "模组")
    # 造两个像样的远景缓存，让体积标注有东西可显示
    voxy_dir = os.path.join(src, ".voxy", "SMP")
    dh_dir = os.path.join(src, "Distant_Horizons_server_data", "SMP", "dim_overworld")
    os.makedirs(voxy_dir, exist_ok=True)
    os.makedirs(dh_dir, exist_ok=True)
    for i in range(3):
        with open(os.path.join(voxy_dir, "lods_%d.db" % i), "wb") as f:
            f.write(b"\0" * (700 * 1024))
        with open(os.path.join(dh_dir, "lod_%d.sqlite" % i), "wb") as f:
            f.write(b"\0" * (400 * 1024))
    w(os.path.join(dst, "options.txt"), "新实例原有设置")
    w(os.path.join(dst, "config", "keep.toml"), "新实例独有配置")

    app.src_var.set(src)
    app.dst_var.set(dst)
    app.log("演示模式：已生成示例实例并自动填入两个路径。")
    present, missing, extras = scan_instance(src)
    if mode == "list":
        app.after(700, app.show_lists)
    else:
        app.after(700, lambda: ConfirmDialog(app, src, present, missing, extras))


def main():
    argv = sys.argv[1:]
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

    if "--selftest" in argv:
        return 0 if selftest() else 1

    enable_dpi()
    app = App()
    if "--demo" in argv:
        app.after(300, lambda: run_demo(app))
    if "--demo-list" in argv:
        app.after(300, lambda: run_demo(app, "list"))
    if "--smoke" in argv:
        app.after(1500, app.destroy)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
