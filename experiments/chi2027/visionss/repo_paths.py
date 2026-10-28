"""
repo_paths — 定位仓库根目录。

pics/、Depth-Anything-V2/（含权重）、experiment_runs/ 只在本机的仓库根目录，不进 Git。
实验代码在 experiments/chi2027/ 下，不能靠"往上几层"去找它们：
先看环境变量 LINGTOUCH_ROOT；没设就从本文件所在目录向上找第一个含 .git 的目录。

用法:
    from repo_paths import REPO_ROOT
    REPO_ROOT / "pics" / "ascii" / "empty1.jpg"
"""

import os
from pathlib import Path


def find_repo_root():
    env = os.environ.get("LINGTOUCH_ROOT")
    if env:
        root = Path(env).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError(f"LINGTOUCH_ROOT={env} 不是一个目录")
        return root
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("向上找不到含 .git 的仓库根目录；请把环境变量 LINGTOUCH_ROOT 设为仓库根目录")


REPO_ROOT = find_repo_root()
