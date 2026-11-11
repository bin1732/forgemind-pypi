# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""生成 GitHub Release 的正文。

正文里的版本号与构件清单都来自这次发布本身 —— 版本号是发布用的那个,
构件清单是这次真传上去的那些。构件清单不是固定在模板里的:固定的那份
迟早与线上对不上,而对不上的时候,页面上写的与用户能下载到的不是同一批
东西。

正文在**每次发布后都重写一遍**。只在创建 Release 时写一次的话,正文会
永远停在上一次创建时的那一版 —— 用户看到的是"这份发布说自己是某个旧
版本",而页面上挂着的是新构件。
"""

from __future__ import annotations

import sys

TEMPLATE = """# ForgeMind {version}

Published by the release workflow of the public repository.

## Install

```bash
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind
```

## Downloads

{assets}

## Verify

```bash
forgemind demo
```

It runs one backtest on real historical prices and prints the return, the
Sharpe ratio, the drawdown and the number of trades. The numbers are what
the strategy actually made on that period — a losing period is reported as
a loss, not rounded away.

## Changes

See [CHANGELOG.md](https://github.com/bin1732/forgemind-pypi/blob/main/CHANGELOG.md).

## License

Apache-2.0
"""

# 构件名后缀 → 这一份是什么。写不出来的一律只报文件名,不编用途。
ASSET_KINDS = (
    (".whl", "Python wheel (universal)"),
    (".tar.gz", "Source distribution"),
    ("-linux", "Linux x86_64 standalone binary"),
    ("-macos", "macOS standalone binary"),
    ("-windows-x64.exe", "Windows x64 standalone binary"),
)


def describe_asset(name: str) -> str:
    """这个构件是什么。"""
    for suffix, description in ASSET_KINDS:
        if name.endswith(suffix):
            return description
    return "Build artifact"


def build_body(version: str, assets: list[str]) -> str:
    """正文。构件清单按传上去的顺序列,一个不落。"""
    if assets:
        lines = [f"- `{name}` — {describe_asset(name)}" for name in assets]
    else:
        lines = ["(no artifact uploaded)"]
    return TEMPLATE.format(version=version, assets="\n".join(lines))


def main(argv: list[str]) -> int:
    """把正文写到标准输出。"""
    if len(argv) < 2:
        print("用法: build_release_body.py <版本号> [构件名...]", file=sys.stderr)
        return 2
    sys.stdout.write(build_body(argv[1], list(argv[2:])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
