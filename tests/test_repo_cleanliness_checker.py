# Copyright (c) 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""残留扫描器自己得可靠。

它盯的是仓库里不该出现的东西 —— 构建产物、凭据、复盘措辞、坏字符。
这些检查一旦失效,仓库会慢慢积灰而没人知道:检查还在跑,只是不再报。

所以这里逐条验:喂进去的坏样本它得报出来,干净的样本它不许误报。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_repo_cleanliness as cleanliness  # noqa: E402


class TestMojibakeCheck:
    """替换字符(U+FFFD)是编码被打断的痕迹,读者看到的是方块或问号"""

    def _file(self, tmp_path: pathlib.Path, name: str, text: str) -> pathlib.Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_replacement_character_is_reported(self, tmp_path):
        """带坏字符的文件要报出来

        坏字符用 chr(0xFFFD) 构造:文件里不能出现字面的替换字符 ——
        那正是这条检查要报的东西,自己带一个就永远报自己。
        """
        bad_char = chr(0xFFFD)
        bad = self._file(tmp_path, "a.py", f"x = '好的' + '{bad_char}' + '话'\n")
        problems = cleanliness.check_mojibake(tmp_path, [bad])
        assert len(problems) == 1, problems
        assert "a.py" in problems[0]

    def test_clean_file_is_not_reported(self, tmp_path):
        """干净的文件不许误报"""
        good = self._file(tmp_path, "b.py", "x = '好的话'\n")
        assert cleanliness.check_mojibake(tmp_path, [good]) == []

    def test_repository_has_no_mojibake(self):
        """仓里现在没有坏字符"""
        import subprocess

        tracked = subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.split()
        files = [REPO / f for f in tracked if (REPO / f).is_file()]
        problems = cleanliness.check_mojibake(REPO, files)
        assert not problems, problems


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
