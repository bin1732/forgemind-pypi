# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""脚本被当模块导入时,不许动全局的导入路径。

这不是洁癖,是一条真踩过的坑:某个脚本在模块级把仓根插进 sys.path,
用例导入它的时候,源码树就压过了装好的发行包 —— "跑在发布出去的
wheel 上"那一档,悄悄测回了源码树,而且全绿。

这种错看不出来:用例通过、作业通过,唯独那一档声称要验的东西没被验。
所以由机器盯着:导入每个脚本,看谁动了路径。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# 在子进程里逐个导入脚本:它们会改 sys.path,得隔离开,免得影响本次运行。
#
# 量的是**增量**:环境里可能本来就有仓根(常规档下正是这样),那是
# 本来就在,不是脚本干的。
_PROBE = """
import importlib.util, os, sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()

polluters = []
for path in sorted((repo / "scripts").glob("*.py")):
    if path.name.startswith("_"):
        continue
    before = sys.path.count(str(repo))
    spec = importlib.util.spec_from_file_location("probe_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        # 导入失败不算污染 —— 脚本本身的问题由别的检查管
        continue
    if sys.path.count(str(repo)) > before:
        polluters.append(path.name)
print("POLLUTERS:" + "|".join(polluters))
"""


def test_importing_scripts_does_not_add_the_source_tree_to_the_path():
    """脚本被导入后,不许往导入路径里塞仓根"""
    # 清干净的环境:PYTHONPATH 可能带着仓根(常规档下正是如此),
    # PYTHONSAFEPATH 让当前目录也不进路径 —— 基准得是干净的,增量才准。
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONSAFEPATH"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(REPO)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert result.returncode == 0, result.stderr[-800:]
    # 脚本被导入时自己会打印些东西,污染名单只认标记行
    marker = [
        line for line in result.stdout.splitlines() if line.startswith("POLLUTERS:")
    ]
    assert marker, f"探针没有给出结果:\n{result.stdout[-400:]}"
    names = [n for n in marker[0].split(":", 1)[1].split("|") if n]
    assert not names, (
        f"这些脚本被导入时把源码树塞进了导入路径:{names} —— "
        "它们会让'跑在发布出去的 wheel 上'那一档悄悄测回源码树"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
