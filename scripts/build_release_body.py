# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""生成 GitHub Release 的正文。

正文里的版本号来自标签名,内容本身保持固定,单独放在脚本里便于检查
措辞,也不受工作流 YAML 缩进的影响。
"""

from __future__ import annotations

import sys

TEMPLATE = """# ForgeMind {version}

See [CHANGELOG.md](https://github.com/bin1732/forgemind-pypi/blob/main/CHANGELOG.md) for details.

## Install
```
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/ forgemind
```

装好之后,一条命令就能看到真实结果:
```
forgemind demo
```

## License
Apache-2.0
"""


def main(argv: list[str]) -> int:
    """把正文写到标准输出。"""
    if len(argv) != 2:
        print("用法: build_release_body.py <版本号>", file=sys.stderr)
        return 2
    sys.stdout.write(TEMPLATE.format(version=argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
