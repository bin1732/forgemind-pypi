# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
测试剩余静态数据:

1. pipeline-status 底部 "v2026.09 · Tauri 2.x" 静态版本号
   修:用 call("get_system_status") 拉真 version

2. strategy-panel 底部 "{N} 个策略 · 0 运行中" 误导文案
   0 运行中看着像"想跑就能跑",实际是策略注册表静态(status 一律 stopped)
   修:显示"清单 X 个策略 · 未挂载运行(注册表不等于运行实例)"

回归测试防复活。
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPELINE = REPO / "forgemind-ui" / "components" / "pipeline-status.tsx"
STRATEGY = REPO / "forgemind-ui" / "components" / "strategy-panel.tsx"


def test_pipeline_status_version_is_dynamic():
    """pipeline-status 不能写死 v2026.09,必须 systemStatus 真值"""
    src = PIPELINE.read_text(encoding="utf-8")
    assert ">v2026.09 · Tauri 2.x<" not in src, (
        "pipeline-status 仍写死 v2026.09 · Tauri 2.x;改用 systemStatus.version"
    )
    assert "systemStatus" in src, (
        "pipeline-status 必须从 get_system_status 拉真 version"
    )


def test_strategy_panel_no_misleading_running_count():
    """strategy-panel 底部不能误导性写 '0 运行中'(status 一律 stopped)"""
    src = STRATEGY.read_text(encoding="utf-8")
    # 旧: "总计: {N} 个策略 · {M} 运行中"
    # 移除注释,只查渲染代码
    import re
    code_only = re.sub(r"/\*[\s\S]*?\*/", "", src)
    assert "运行中" not in code_only, (
        "strategy-panel 仍含'运行中'计数(误导,status 一律 stopped)"
    )
    assert "未挂载运行" in src, (
        "strategy-panel 底部应显示'未挂载运行'"
    )
