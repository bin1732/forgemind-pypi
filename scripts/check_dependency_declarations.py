# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""核对依赖声明与源码实际 import 是否一致。

扫描范围是 `forgemind/` 包与 `scripts/` 下的工具脚本 —— 脚本在流水线里
要跑,它们 import 的第三方包同样得声明,否则贡献者按文档装完开发依赖,
一跑这些脚本就 ImportError。

两个方向都查:
  1. import 到的第三方包,必须已在 dependencies 或某个 extra 里声明
  2. dependencies 里的每个包,源码必须真的用到;确实不直接 import 的,
     必须在 DECLARED_WITHOUT_DIRECT_IMPORT 里写明理由

import 名与发行包名不一致的(比如 sklearn / scikit-learn),由
IMPORT_TO_DISTRIBUTION 显式给出。映射表用静态字面量而不是查当前环境,
这样在任何机器上跑出来的结论都一样:环境里装没装这个包不影响判定。

用法:
    python scripts/check_dependency_declarations.py
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "forgemind"
# 仓库自带的工具脚本:它们在流水线里要跑,import 的第三方包也得声明,
# 否则贡献者按文档装完开发依赖,一跑这些脚本就 ImportError。
SCRIPTS = REPO / "scripts"

# import 顶层名 -> 发行包名
IMPORT_TO_DISTRIBUTION = {
    "PIL": "pillow",
    "akshare": "akshare",
    "anthropic": "anthropic",
    "asyncpg": "asyncpg",
    "catboost": "catboost",
    "clickhouse_driver": "clickhouse-driver",
    "duckdb": "duckdb",
    "fastapi": "fastapi",
    "httpx": "httpx",
    "joblib": "joblib",
    "langchain": "langchain",
    "langchain_core": "langchain-core",
    "langgraph": "langgraph",
    "lightgbm": "lightgbm",
    "nats": "nats-py",
    "numpy": "numpy",
    "openai": "openai",
    "packaging": "packaging",
    "playwright": "playwright",
    "pandas": "pandas",
    "polars": "polars",
    "pyarrow": "pyarrow",
    "yaml": "pyyaml",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "pypdf": "pypdf",
    "pytesseract": "pytesseract",
    "redis": "redis",
    "scipy": "scipy",
    "sentence_transformers": "sentence-transformers",
    "shap": "shap",
    "sklearn": "scikit-learn",
    "structlog": "structlog",
    "torch": "torch",
    "tushare": "tushare",
    "uvicorn": "uvicorn",
    "whisper": "openai-whisper",
    "xgboost": "xgboost",
}

# 声明了但源码不直接 import 的包,以及这样声明的理由
DECLARED_WITHOUT_DIRECT_IMPORT = {
    "pyarrow": "polars 的 DataFrame.to_pandas() 在运行期需要它",
    "langchain": "版本约束:langchain 1.x 与 langchain-core<1 冲突,"
    "且 langchain-core 会读取 langchain.debug",
}


def distribution_name(spec: str) -> str:
    """'uvicorn[standard]>=0.32.1,<999' -> 'uvicorn'"""
    name = spec.split("[", 1)[0]
    for sep in (">=", "<=", "==", "~=", "!=", ">", "<"):
        name = name.split(sep, 1)[0]
    return name.strip().lower()


def load_declared() -> tuple[set[str], dict[str, set[str]]]:
    with (REPO / "pyproject.toml").open("rb") as fh:
        project = tomllib.load(fh)["project"]
    main = {distribution_name(d) for d in project.get("dependencies", [])}
    extras = {
        name: {distribution_name(d) for d in deps}
        for name, deps in project.get("optional-dependencies", {}).items()
    }
    return main, extras


def collect_imports(path: Path) -> set[str]:
    """取一个文件里 import 到的所有第三方顶层模块名。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, ValueError):
        return set()

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # 相对导入(带 level)指向本包内部,不算第三方
            if node.level or not node.module:
                continue
            modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            # 字符串式动态导入:importlib.import_module("x") / importorskip("x")
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in {"import_module", "importorskip", "find_spec"}:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        modules.add(arg.value.split(".")[0])
    return modules


def main() -> int:
    main_deps, extras = load_declared()
    all_declared = set(main_deps)
    for deps in extras.values():
        all_declared |= deps

    imported: set[str] = set()
    files = sorted(SRC.rglob("*.py")) + sorted(SCRIPTS.glob("*.py"))
    for path in files:
        imported |= collect_imports(path)

    stdlib = set(sys.stdlib_module_names)
    # 本仓自己的模块:包本体,以及 scripts/ 下各脚本互相导入
    first_party = {"forgemind", SCRIPTS.name}
    first_party |= {p.stem for p in SCRIPTS.glob("*.py")}

    problems: list[str] = []

    # 方向一:源码用了但没声明
    for module in sorted(imported):
        if module in stdlib or module in first_party:
            continue
        dist = IMPORT_TO_DISTRIBUTION.get(module)
        if dist is None:
            problems.append(
                f"第三方 import {module!r} 不在映射表里,无法判定归属;"
                f"请在 scripts/check_dependency_declarations.py 补充"
            )
            continue
        if dist not in all_declared:
            problems.append(f"源码 import 了 {module!r}({dist}),但依赖声明里没有它")

    # 方向二:声明了但源码没用
    used_dists = {IMPORT_TO_DISTRIBUTION[m] for m in imported if m in IMPORT_TO_DISTRIBUTION}
    for dist in sorted(main_deps):
        if dist in used_dists:
            continue
        reason = DECLARED_WITHOUT_DIRECT_IMPORT.get(dist)
        if reason is None:
            problems.append(
                f"依赖声明里有 {dist!r},但源码没有 import 它;"
                f"若确属必需,请在 DECLARED_WITHOUT_DIRECT_IMPORT 里写明理由"
            )

    # extra 里的包也应当在源码里有对应的 import
    for name, deps in sorted(extras.items()):
        if name == "dev":
            continue  # dev 只服务于测试与工具链
        for dist in sorted(deps):
            if dist not in used_dists:
                problems.append(f"extra [{name}] 里的 {dist!r} 在源码里没有对应的 import")

    if problems:
        print("依赖声明与实际 import 不一致:", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1

    extra_pkgs = set()
    for deps in extras.values():
        extra_pkgs |= deps
    print(
        f"依赖声明一致:主依赖 {len(main_deps)} 个,"
        f"extras {len(extras)} 组共 {len(extra_pkgs)} 个包,"
        f"源码与脚本 import 的第三方包 {len(used_dists)} 个"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
