# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""发布构件对账器:资产名认得出、发布说明对得上。

两处都静默漏过一次:

- 资产名的版本号形态只认 "2026.9.3",不认 "2026.9.3.post61" —— 带 post
  号的独立二进制于是不被当成资产,文档里点名它们根本不核对。
- 发布说明没有纳入对账 —— 页面上留着的字与线上实际有的构件对不对得上,
  没有人问。

这里把两个判据各钉一个方向:对的放过,错的报出来。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_published_assets as cpa  # noqa: E402


class TestIsAsset:
    """资产名的识别:带 post 号的独立二进制也得认出来"""

    def test_versioned_binaries_are_assets(self):
        for name in (
            "forgemind-2026.9.3.post61-linux",
            "forgemind-2026.9.3.post61-macos",
            "forgemind-2026.9.3.post61-windows-x64.exe",
        ):
            assert cpa.is_asset(name), name

    def test_wheel_and_sdist_are_assets(self):
        assert cpa.is_asset("forgemind-2026.9.3.post61-py3-none-any.whl")
        assert cpa.is_asset("forgemind-2026.9.3.post61.tar.gz")

    def test_ordinary_words_are_not_assets(self):
        for name in ("forgemind", "README.md", "forgemind-demo"):
            assert not cpa.is_asset(name), name


class TestCheckReleaseBody:
    """发布说明:说的与线上实际有的要对得上"""

    def _body(self, version: str, names: list[str]) -> str:
        lines = "\n".join(f"- `{n}` — 构件" for n in names)
        return f"# ForgeMind {version}\n\n## Downloads\n\n{lines}\n"

    def test_matching_body_passes(self):
        names = ["forgemind-1.0-py3-none-any.whl", "forgemind-1.0-linux"]
        problems = cpa.check_release_body(self._body("1.0", names), set(names), "1.0")
        assert problems == [], problems

    def test_missing_asset_is_reported(self):
        names = ["forgemind-1.0-py3-none-any.whl", "forgemind-1.0-linux"]
        body = self._body("1.0", names[:1])
        problems = cpa.check_release_body(body, set(names), "1.0")
        assert len(problems) == 1, problems
        assert "forgemind-1.0-linux" in problems[0]

    def test_unknown_asset_is_reported(self):
        names = ["forgemind-1.0-py3-none-any.whl"]
        body = self._body("1.0", names + ["forgemind-1.0-macos"])
        problems = cpa.check_release_body(body, set(names), "1.0")
        assert len(problems) == 1, problems
        assert "forgemind-1.0-macos" in problems[0]

    def test_stale_version_is_reported(self):
        names = ["forgemind-1.0-py3-none-any.whl"]
        problems = cpa.check_release_body(self._body("0.9", names), set(names), "1.0")
        assert len(problems) == 1, problems
        assert "0.9" in problems[0] and "1.0" in problems[0]

    def test_order_does_not_matter(self):
        names = ["forgemind-1.0-py3-none-any.whl", "forgemind-1.0-linux"]
        body = self._body("1.0", list(reversed(names)))
        problems = cpa.check_release_body(body, set(names), "1.0")
        assert problems == [], problems


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
