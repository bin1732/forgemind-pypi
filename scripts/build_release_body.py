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
{retained}
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


#: 页面上为什么还留着上一版的构件。
#:
#: pip 会缓存包索引,缓存里那份可能还指着上一版。那个版本的构件被删了,
#: 缓存过的机器 pip install 就是"找不到分发文件"。留着它,那次安装就还
#: 能成 —— 装到上一版,而不是装不上。
RETAINED_NOTE = (
    "The previous release's package file is still listed here on purpose. "
    "pip caches the package index, so a machine that installed an earlier "
    "version may still be reading that cached index. Keeping the file means "
    "that install still succeeds instead of failing with \"No matching "
    "distribution found\"."
)


def build_body(version: str, assets: list[str], retained: list[str] | None = None) -> str:
    """正文。构件清单按传上去的顺序列,一个不落。

    retained 是**这次没传、但特意留在页面上的**构件(上一版的)。它们也要
    列出来:页面上看得见的东西,说明里没提,读者就不知道那是什么、能不能
    用。
    """
    if assets:
        lines = [f"- `{name}` — {describe_asset(name)}" for name in assets]
    else:
        lines = ["(no artifact uploaded)"]
    if retained:
        kept = "\n".join(f"- `{name}` — {describe_asset(name)}" for name in retained)
        retained_block = f"\n### Also still available\n\n{kept}\n\n{RETAINED_NOTE}\n"
    else:
        retained_block = ""
    return TEMPLATE.format(version=version, assets="\n".join(lines), retained=retained_block)


def main(argv: list[str]) -> int:
    """把正文写到标准输出。

    用法: build_release_body.py <版本号> [构件名...] [--retained 保留的构件名...]
    """
    args = list(argv[1:])
    retained: list[str] = []
    if "--retained" in args:
        cut = args.index("--retained")
        args, retained = args[:cut], args[cut + 1 :]
    if not args:
        print(
            "用法: build_release_body.py <版本号> [构件名...] [--retained 保留的构件名...]",
            file=sys.stderr,
        )
        return 2
    sys.stdout.write(build_body(args[0], args[1:], retained=retained))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
