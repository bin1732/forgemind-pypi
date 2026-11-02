# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""确认核心模块可以导入。

导入链覆盖了提供方、MCP 服务与回测引擎,这三处是各条对外路径的起点。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 优先用本仓库的源码树。环境里若装过同名旧副本,导入会捡到旧代码,
# 检查的就不是本仓库的东西了。
#
# 只在直接跑的时候放:被用例当模块导入时也放的话,源码树会压过装好的
# 发行包 —— "跑在发布出去的 wheel 上"那一档就悄悄测回源码树了。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if __name__ == "__main__" and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    """导入核心模块,返回进程退出码。"""
    from forgemind.core.ai.providers import ProviderType, create_provider
    from forgemind.core.backtest.engine import SimpleBacktestEngine
    from forgemind.mcp.server import ForgeMindMCPServer

    for obj in (create_provider, ProviderType, SimpleBacktestEngine, ForgeMindMCPServer):
        if obj is None:
            print("核心模块导入结果为空", file=sys.stderr)
            return 1

    print("核心模块导入正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
