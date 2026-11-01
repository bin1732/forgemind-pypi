# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""错误提示里让人装的 extra 必须真的存在

真实的坏体验:用户撞到 LLM 报错,提示里写着

    pip install 'forgemind[llm]'

他照做,pip 回:

    WARNING: forgemind 2026.9.3 does not provide the extra 'llm'

**按提示自救这条路本身是断的。** 提示把人送去一个不存在的 extra,
比没有提示更糟 —— 它看起来像有解法。

pyproject 里的 extra 分组应覆盖 llm,
而源码里有 6 处引用它。

这条测试把"提示里出现的每个 forgemind[xxx]"都拿去和 pyproject 的
extras 对照,以后再写错会当场红。
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "forgemind"


@pytest.fixture(scope="module")
def extras() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(data["project"].get("optional-dependencies", {}))


@pytest.fixture(scope="module")
def referenced() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for p in PKG.rglob("*.py"):
        if "build" in p.parts:
            continue
        for m in re.finditer(r"forgemind\[([a-z_]+)\]", p.read_text(encoding="utf-8")):
            hits.setdefault(m.group(1), []).append(p.relative_to(ROOT).as_posix())
    return hits


class TestEveryReferencedExtraExists:
    def test_some_references_are_found(self, referenced):
        assert referenced, "没扫到任何 forgemind[...] 引用,扫描逻辑坏了"

    def test_all_referenced_extras_are_declared(self, referenced, extras):
        missing = {k: v for k, v in referenced.items() if k not in extras}
        assert not missing, (
            "这些 extra 在提示里被推荐,但 pyproject 里没有定义:\n"
            + "\n".join(f"  forgemind[{k}]  ← {len(v)} 处:{v[0]}"
                        for k, v in missing.items())
            + f"\n  已定义:{sorted(extras)}")

    @pytest.mark.parametrize("name", ["cn", "llm", "ml", "multimodal"])
    def test_the_ones_we_promote_exist(self, name, extras):
        assert name in extras, f"提示里在用 forgemind[{name}],但没定义"


class TestSuggestedCommandsActuallyRun:
    """提示里的命令要真能跑 —— 和 extra 同一类问题的另一种形式

    错误提示最坏的失败模式不是"没提示",而是"提示把人导向一条
    跑不通的命令":用户照做,失败,再照做,还是失败。
    """

    @pytest.mark.parametrize("cmd", [
        ["info"],
        ["router-demo"],
        ["signal"],
        ["backtest", "--list-strategies"],
        ["backtest", "--strategy", "ma_cross", "--start", "2024-01-01",
         "--end", "2024-02-01"],
        ["etl", "--help"],
        ["pick", "--help"],
        ["agent", "--help"],
    ])
    def test_command_exits_cleanly(self, cmd):
        import subprocess
        import sys

        from forgemind.cli import build_parser

        # 先确认参数确实被解析器接受(argparse 对 --help 会抛 SystemExit(0),
        # 那是正常行为,不是失败)
        try:
            build_parser().parse_args(cmd)
        except SystemExit as e:
            assert e.code in (0, None), f"参数被拒绝: {cmd} -> {e.code}"

        p = subprocess.run(
            [sys.executable, "-m", "forgemind.cli", *cmd],
            capture_output=True, text=True, timeout=300,
            env={**__import__("os").environ, "FORGEMIND_LOG_LEVEL": "WARNING"},
        )
        assert p.returncode == 0, (
            f"提示里推荐的命令跑不通: forgemind {' '.join(cmd)}\n"
            f"{(p.stdout + p.stderr)[-300:]}")
        assert "Traceback" not in p.stdout + p.stderr, (
            f"forgemind {' '.join(cmd)} 抛了裸异常")
