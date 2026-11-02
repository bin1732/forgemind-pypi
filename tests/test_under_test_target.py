# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""这一档测的到底是哪一份代码,必须机器能核对。

同一批用例有两种跑法,要求正好相反:

- 常规档在源码树上跑 —— 改了代码,测试必须测新代码。
- "跑在发布出去的 wheel 上"那一档在装出来的发行包上跑 —— 那一档要验
  的恰恰是用户装到手上的那份。

弄反了不会报错,只会安静地测错的对象,然后全绿。这条用例把"测的是
哪一份"变成机器能核对的事实:import 命中的路径要与这一档声明的目标
一致,对不上就报错。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _path_setup import (
    REPO_ROOT,
    child_env,
    is_installed_package,
    source_package_path,
    testing_installed_package,
)


def _assert_target(where: Path, source: str) -> None:
    if testing_installed_package():
        # 装出来的发行包:落在 site-packages 里,且不是仓里那个源码包。
        # 判据不能只看"是不是在仓根底下" —— 流水线上的虚拟环境就建在
        # 仓里,按仓根判会把装好的发行包误判成源码树。
        assert is_installed_package(where), (
            f"这一档要测装出来的发行包,{source}命中的却是 {where}"
        )
        assert where != source_package_path(), (
            f"这一档要测装出来的发行包,{source}命中的却是仓里的源码包:{where}"
        )
    else:
        assert where == source_package_path(), (
            f"常规档要测源码树,{source}命中的却是 {where}"
        )


class TestUnderTestTarget:
    def test_import_hits_the_declared_target(self):
        """当前进程 import 的必须是这一档声明的那一份"""
        import forgemind

        _assert_target(Path(forgemind.__file__).resolve(), "import")

    def test_subprocess_hits_the_declared_target(self):
        """子进程也要命中同一份

        子进程会重新初始化导入路径,是最容易跑偏的一环 —— 主进程对了,
        子进程照样可能 import 到源码树,而那一批断言就白跑了。
        """
        out = subprocess.run(
            [sys.executable, "-c", "import forgemind; print(forgemind.__file__)"],
            capture_output=True,
            text=True,
            timeout=120,
            env=child_env(),
        )
        assert out.returncode == 0, out.stderr[-400:]
        lines = [line for line in out.stdout.strip().splitlines() if line.strip()]
        assert lines, f"子进程没有输出包路径:\n{out.stdout}\n{out.stderr}"
        _assert_target(Path(lines[-1]).resolve(), "子进程的 import")

    def test_switch_actually_changes_something(self):
        """开关必须真的改变结果 —— 一个恒真的开关等于没有开关"""
        if testing_installed_package():
            assert str(REPO_ROOT) not in sys.path, (
                "这一档里源码树不能留在导入路径上,否则 import 会命中它"
            )
        else:
            assert str(REPO_ROOT) in sys.path, (
                "常规档要把源码树放进导入路径,否则测的是环境里的旧副本"
            )
