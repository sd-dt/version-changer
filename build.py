# -*- coding: utf-8 -*-
"""一键打包脚本：自检 → 生成图标 → PyInstaller 打包 → 改名成中文 exe。

由「重新打包.bat」调用，也可以直接 `python build.py` 运行。
改名放在 Python 里做，避免 cmd 的代码页把中文文件名搞乱。
"""

import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = "MC实例数据转移工具.exe"
BUILT = "MCInstanceTransfer.exe"


def run(cmd):
    print("\n>>> " + " ".join(cmd), flush=True)
    code = subprocess.run(cmd, cwd=HERE).returncode
    if code != 0:
        print("\n[失败] 上面的命令退出码为 %d，打包中止。" % code)
        sys.exit(code)


def main():
    os.chdir(HERE)
    print("=" * 52)
    print("  MC 实例数据转移工具 —— 一键重新打包")
    print("=" * 52)

    print("\n[1/4] 检查打包依赖 pyinstaller / pillow …")
    run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
         "pyinstaller", "pillow"])

    print("\n[2/4] 运行逻辑自检 …")
    run([sys.executable, "mc_transfer.py", "--selftest"])

    print("\n[3/4] 生成程序图标 …")
    run([sys.executable, "gen_icon.py"])

    print("\n[4/4] 打包 exe（约需 10~60 秒）…")
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile",
         "--windowed", "--icon", "app.ico", "--version-file", "version_info.txt",
         "--name", "MCInstanceTransfer", "mc_transfer.py"])

    dist = os.path.join(HERE, "dist")
    src = os.path.join(dist, BUILT)
    dst = os.path.join(dist, TARGET)
    if not os.path.exists(src):
        print("\n[失败] 没有找到打包产物：%s" % src)
        sys.exit(1)

    # 先把新产物改名，再清掉 dist 里的历史产物
    # （含以前因代码页问题产生的乱码名文件，但不能误删刚打好的这个）
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(src, dst)

    for old in glob.glob(os.path.join(dist, "*.exe")):
        if os.path.normcase(old) != os.path.normcase(dst):
            try:
                os.remove(old)
            except OSError:
                pass

    shutil.rmtree(os.path.join(HERE, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(HERE, "__pycache__"), ignore_errors=True)

    size = os.path.getsize(dst) / 1024.0 / 1024.0
    print("\n" + "=" * 52)
    print("  打包完成：%s" % dst)
    print("  大小：%.1f MB   双击即可运行" % size)
    print("=" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
