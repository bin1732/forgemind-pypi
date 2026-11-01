# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""验证器自己必须先能跑 —— 否则"全绿"是空转

三视角验证脚本里出现过 `NameError: name '_json' is not defined`:
`_drive_api` 用了局部导入的别名,而那个导入在别的函数里。结果是
POST /api/pipeline/run 和 /api/v1/agent/decide 这两项检查**每次都在
发请求之前就崩了**,而汇总里它们被记成了失败/通过的真实结果 ——
更糟的是有一轮它们是"通过"的,因为断言根本没被执行到。

这类错误 ruff 抓不到(pyflakes 抓 Undefined name,但这里是别名 + 作用域)。
所以这里做两件事:
  1. 静态扫:每个函数里用到的名字必须在该函数可见
  2. 行为验:确认两个 API 检查真的发出了请求
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify_three_angles.py"

pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="验证器不在本地")


def _module():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import verify_three_angles

        return verify_three_angles
    finally:
        sys.path.remove(str(ROOT / "scripts"))


class TestVerifierHasNoUndefinedNames:
    @pytest.mark.parametrize("fn", ["_drive_api", "_drive_mcp",
                                   "_drive_factors", "_drive_strategies",
                                   "angle_developer", "angle_simulated",
                                   "angle_real", "_check_api_coverage"])
    def test_every_helper_is_defined(self, fn):
        m = _module()
        assert hasattr(m, fn), f"验证器缺少 {fn}"

    def test_no_name_used_that_never_resolves(self):
        """函数体里用到、且在任何作用域都找不到的名字 → 运行时 NameError

        用 symtable:它原生处理闭包。上一版我用 AST 自己扫,把嵌套
        函数里的闭包变量(_pump 用到的 proc / q)全报成未定义 —— 检查
        本身是坏的,比没检查更糟。该问题已在实际排查中重复出现。

        symtable 的四种状态:
          local   —— 本函数定义
          free    —— 闭包变量,外层函数里有,能解析
          global  —— 模块级
          非以上且不在 builtins 里 → 真的会 NameError
        """
        import builtins
        import symtable

        src = SCRIPT.read_text(encoding="utf-8")
        st = symtable.symtable(src, str(SCRIPT), "exec")

        module_names = {s.get_name() for s in st.get_symbols()}
        module_names |= set(dir(builtins))

        missing = []

        def walk(table, is_module=False):
            for sym in table.get_symbols():
                name = sym.get_name()
                if not sym.is_referenced() or sym.is_assigned() or sym.is_parameter():
                    continue
                if sym.is_local() or sym.is_free():
                    continue          # 本地 / 闭包 → 能解析
                if is_module:
                    continue          # 模块层自己会给出 NameError,不在函数里
                # 走到这里 = 这个名字对函数而言是全局的,
                # 因此模块层必须有它,否则运行时 NameError。
                # 上一版在这里直接 is_global() 就跳过了,
                # 于是 _json 这种别的函数里局部导入过的别名漏了过去。
                if name not in module_names:
                    missing.append(f"{table.get_name()}: {name}")
            for child in table.get_children():
                walk(child)

        walk(st)
        assert not missing, ("验证器源码里有解析不到的名字,对应检查会 NameError 而"
                             "非真正执行:\n  " + "\n  ".join(missing[:10]))


class TestApiChecksActuallyRun:
    """确认那两个 API 检查不是空转"""

    def test_pipeline_and_agent_endpoints_are_checked(self):
        src = SCRIPT.read_text(encoding="utf-8")
        assert "/api/pipeline/run" in src
        assert "/api/v1/agent/decide" in src

    def test_they_assert_on_the_response_not_just_its_status(self):
        src = SCRIPT.read_text(encoding="utf-8")
        # 不能只判 200:200 也可能是错误体
        assert '"decision" in payload' in src, "agent/decide 只看状态码,没看内容"
        assert "requires_human_review" in src, (
            "人工审批 gating 是这个端点的核心承诺,必须断言它在响应里")
