# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""package.json 与 package-lock.json 必须同步

真实事故:给桌面端接后端时往 package.json 加了 `@tauri-apps/api`,
`npm install` 也更新了本地 lock —— 但**只推了 package.json,漏推了
package-lock.json**。

本地一切正常(3 视角验证、tsc、Jest、生产构建全过),
只有 CI 的 `npm ci` 报:

    npm error `npm ci` can only install packages when your package.json and
    package-lock.json are in sync.
    npm error Missing: @tauri-apps/api@2.12.1 from lock file

三平台桌面构建全红,而本地无法复现 —— 这类"只在 CI 炸"的依赖问题
必须有本地守卫,否则只能靠人记得两个文件一起推。
"""

import json
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "forgemind-ui"


def _load(name: str) -> dict:
    return json.loads((UI / name).read_text(encoding="utf-8"))


class TestLockfileMatchesPackageJson:
    def test_every_dependency_is_declared_in_the_lockfile(self):
        pkg = _load("package.json")
        lock = _load("package-lock.json")
        declared = pkg.get("dependencies", {})
        locked_root = lock["packages"][""].get("dependencies", {})
        missing = {k: v for k, v in declared.items() if k not in locked_root}
        assert not missing, (
            f"package.json 里有、lock 的根依赖里没有:{missing}。"
            "CI 的 `npm ci` 会因此失败,而本地完全正常。")

    def test_lock_resolves_every_declared_dependency(self):
        pkg = _load("package.json")
        lock = _load("package-lock.json")
        for name in pkg.get("dependencies", {}):
            entry = lock["packages"].get(f"node_modules/{name}")
            assert entry, f"lock 里没有 {name} 的解析条目"
            assert entry.get("version"), f"{name} 在 lock 里没有版本号"

    def test_lockfile_exists_and_is_valid_json(self):
        assert (UI / "package-lock.json").exists()
        json.loads((UI / "package-lock.json").read_text(encoding="utf-8"))


class TestCriticalRuntimeDepsAreDeclared:
    """接后端必须有这两个 —— 少一个前端就物理上无法 invoke"""

    def test_tauri_api_is_a_dependency(self):
        deps = _load("package.json").get("dependencies", {})
        assert "@tauri-apps/api" in deps, (
            "前端要调 #[tauri::command] 就必须能 import @tauri-apps/api")

    def test_tauri_api_is_actually_imported(self):
        src = (UI / "lib" / "tauri.ts").read_text(encoding="utf-8")
        assert "@tauri-apps/api" in src
