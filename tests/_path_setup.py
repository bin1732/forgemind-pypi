# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""测试导入路径的统一开关。

同一批用例有两种跑法,要求正好相反:

- 常规流水线在源码树上跑。改了代码,测试必须测新代码 —— 环境里装着的
  旧副本不能抢走 import,否则"我改了代码但测试结果没变",排查很久。
- "跑在发布出去的 wheel 上"那一档要验的恰恰是**用户装到手上的那份**。
  那时不能把源码树顶到前面,否则测的还是源码,那一档就白跑了。

所以路径怎么摆只在这里决定一次,各测试文件不再各插一遍 —— 分开插,
迟早有一处忘了改,那一处的用例就在测错误的对象。
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# 仓根。tests/ 的上一级。
REPO_ROOT = Path(__file__).resolve().parent.parent

# 置 1 时:源码树不进 sys.path,import 命中的是环境里装好的发行包。
INSTALLED_PACKAGE_ENV = "FORGEMIND_TEST_INSTALLED_PACKAGE"


def testing_installed_package() -> bool:
    """这一档是不是要验装出来的那份发行包。"""
    return os.environ.get(INSTALLED_PACKAGE_ENV) == "1"


def prefer_source_tree() -> None:
    """让 import 命中源码树 —— 除非这一档要验装出来的那份。

    子进程要一起改:只改当前进程的 sys.path 没用。测试里 spawn 出来的
    子进程会重新初始化 sys.path,于是又 import 到环境里那份 —— 本地
    开发时是旧副本,发布档里是源码树,两种都会让结果失去意义。
    """
    if testing_installed_package():
        return
    root = str(REPO_ROOT)
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [root, os.environ.get("PYTHONPATH", "")],
    ).rstrip(os.pathsep)


def lock_installed_package() -> None:
    """把装出来的那份发行包钉进 sys.modules。

    源码树一旦在 sys.path 里,后面任何 `import forgemind` 都会先命中它 ——
    测试文件自己插的路径、内联脚本插的路径,都盖得过装好的发行包。
    先 import 一次,Python 之后命中 sys.modules 就不再去找,那一批用例
    测的才是真正装出来的那份。

    这一步顺带把"测的是哪一份"变成机器能核对的事实:import 命中的路径
    不是源码树,否则直接报错,而不是让整档测试在测错的对象下全绿。
    """
    root = str(REPO_ROOT)
    # 摘掉仓根再 import:否则 `python -m pytest` 把当前目录塞进路径,
    # import 会命中源码树,这一档就白跑了。
    kept = []
    for entry in sys.path:
        if entry in ("", root):
            continue
        try:
            if Path(entry).resolve() == REPO_ROOT:
                continue
        except OSError:
            pass
        kept.append(entry)
    sys.path[:] = kept

    try:
        module = importlib.import_module("forgemind")
    except ImportError as exc:
        raise RuntimeError(
            "这一档要验装出来的那份发行包,但 import forgemind 失败 —— "
            "确认发行包已经装进当前环境"
        ) from exc

    where = Path(module.__file__).resolve()
    if REPO_ROOT in where.parents:
        raise RuntimeError(
            f"import forgemind 命中的是源码树({where}),不是装出来的发行包"
        )
    sys.modules["forgemind"] = module

    # 子进程也不许把当前目录算进路径。子进程在仓根里跑时,`python -c`
    # 默认把 cwd 塞进 sys.path —— 那样它照样会 import 到源码树。
    # 读解释器启动选项的环境变量对当前进程已经晚了,对子进程正好。
    os.environ["PYTHONSAFEPATH"] = "1"


def child_env(base: dict | None = None, **extra: str) -> dict:
    """子进程的环境:默认把源码树放在最前。

    子进程会重新初始化 sys.path,只改当前进程没有用。源码树优先是默认
    行为;"验装出来的那份"那一档不这么做 —— 那时子进程也该 import 到
    装好的发行包,否则那一档里有一部分用例仍在测源码。

    一定带上 PYTHONSAFEPATH:子进程在仓根里跑时,cwd 默认会被塞进
    sys.path,那样它 import 到的还是源码树 —— 路径就白控了。
    """
    env = dict(os.environ if base is None else base)
    if not testing_installed_package():
        env["PYTHONPATH"] = os.pathsep.join(
            [str(REPO_ROOT), env.get("PYTHONPATH", "")],
        ).rstrip(os.pathsep)
    env["PYTHONSAFEPATH"] = "1"
    env.update(extra)
    return env


def inline_path_setup() -> str:
    """内联脚本里用来定位包的那一句。

    源码树优先时把仓根顶到前面;"验装出来的那份"那档不这么做 ——
    那时子进程本来就该 import 到装好的发行包。
    """
    if testing_installed_package():
        return ""
    return f"sys.path.insert(0, {str(REPO_ROOT)!r});"

