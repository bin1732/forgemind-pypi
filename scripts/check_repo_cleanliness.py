# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""扫描仓库里的残留。

两个仓对"干净"的要求不一样:私人仓是源码真源,公开仓只放用户层内容。
这个脚本按各自的标准检查,发现残留时以非零退出码结束,可以直接挂进
流水线。

检查项:
  * 开发过程的复盘措辞 —— 交付物里不该出现指向开发过程的话
  * 构建产物与诊断产物
  * 过期副本与索引幽灵条目
  * 许可证头缺失
  * 工作区是否有未提交的改动

用法:
    python scripts/check_repo_cleanliness.py <仓库路径> [--public]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 交付物里不该出现的复盘措辞
REGRESSION_PHRASES = (
    "此前",
    "早期版本",
    "修正前",
    "这一轮",
    "上一轮",
    "写死的",
    "这条 fix",
    "这次修复",
    "临时方案",
    # 可见层自检里点名的那些
    "之前是",
    "曾经的 bug",
    "曾经的",
    "踩坑",
    "理论上",
    "挖到",
    "捎带",
    "轮改",
    "轮发现",
    "TODO",
    "FIXME",
)

# 构建产物与诊断产物
ARTIFACT_PATTERNS = (
    "ci-diagnostics",
    "ci-status.json",
    "pytest-failure-report",
    ".coverage",
    ".pytest_cache",
    "__pycache__",
    ".egg-info",
    "dist/",
    "build/",
)

# 许可证头
HEADER_MARK = "SPDX-License-Identifier: Apache-2.0"

# 公开仓不该出现的东西
PUBLIC_FORBIDDEN = (
    "forgemind/core/",
    "forgemind/mcp/",
    "forgemind/api/",
    "forgemind/cli.py",
    "tests/test_",
)

# 这两个脚本自带检测词表,不能被当成残留
SELF_EXEMPT = (
    "scripts/check_repo_cleanliness.py",
    "scripts/clean_wording.py",
    # 自检文档本身要说明检查范围,会引用到检测词
    "docs/AUDIT_3_DIMENSIONS.md",
    # 这两个文件自带检查词表
    "scripts/verify3.py",
    "tests/test_underlying_git_history.py",
    # 这两个脚本的说明里会引用检测词
    "scripts/check_ui_data_driven.py",
    "scripts/check_audit_references.py",
)


def _run_git(repo: Path, *args: str) -> str:
    """在仓库里跑一条 git 命令,返回输出。"""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout


def _tracked_files(repo: Path) -> list[Path]:
    """列出被版本控制的文件。"""
    out = _run_git(repo, "ls-files")
    return [repo / line for line in out.splitlines() if line.strip()]


def _worktree_lines(repo: Path) -> list[str]:
    """列出工作区里未提交的改动。"""
    out = _run_git(repo, "status", "--porcelain")
    return [line for line in out.splitlines() if line.strip()]


def check_regression_phrasing(repo: Path, files: list[Path]) -> list[str]:
    """检查源码与文档里有没有开发过程的复盘措辞。"""
    problems = []
    for path in files:
        if path.suffix not in (
            ".py",
            ".rs",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".md",
            ".toml",
            ".yml",
            ".yaml",
            ".txt",
        ):
            continue
        if str(path.relative_to(repo)) in SELF_EXEMPT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for phrase in REGRESSION_PHRASES:
                if phrase in line:
                    rel = path.relative_to(repo)
                    problems.append(f"{rel}:{number} 出现复盘措辞 {phrase!r}")
    return problems


def check_artifacts(repo: Path) -> list[str]:
    """检查仓库里有没有构建产物与诊断产物。"""
    problems = []
    for name in _worktree_lines(repo):
        for pattern in ARTIFACT_PATTERNS:
            if pattern in name:
                problems.append(f"未跟踪的产物文件: {name}")
                break
    tracked = _run_git(repo, "ls-files")
    for line in tracked.splitlines():
        for pattern in ARTIFACT_PATTERNS:
            if pattern in line and not line.endswith((".md", ".yml", ".yaml", ".toml")):
                problems.append(f"被跟踪的产物文件: {line}")
                break
    return problems


def check_license_headers(repo: Path, files: list[Path]) -> list[str]:
    """检查 Python 源文件是否带许可证头。"""
    problems = []
    for path in files:
        if path.suffix != ".py":
            continue
        try:
            head = path.read_text(encoding="utf-8")[:600]
        except (OSError, UnicodeDecodeError):
            continue
        if HEADER_MARK not in head:
            problems.append(f"{path.relative_to(repo)} 缺少许可证头")
    return problems


def check_public_layout(repo: Path, files: list[Path]) -> list[str]:
    """公开仓不该带源码与测试。"""
    problems = []
    for path in files:
        rel = str(path.relative_to(repo))
        for pattern in PUBLIC_FORBIDDEN:
            if rel.startswith(pattern) or pattern in rel:
                problems.append(f"公开仓不应包含: {rel}")
                break
    return problems


# 仓库根目录允许出现的文件。根目录是用户第一眼看到的地方,一份过期的
# 发布说明放在那儿,比放在 docs/ 里碍眼得多 —— 里面写着的用例数与流水线
# 状态很快就过期了,而没人会再去更新它。
ALLOWED_ROOT_FILES = {
    ".codespellignore",
    ".env.example",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".vulture.toml",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "pip-audit.toml",
    "pyproject.toml",
    # 两个仓的代码风格配置都在根目录,位置一致。
    "ruff.toml",
    # 镜像作业把私人仓的源码检到这个目录 —— 它是流水线跑出来的工作目录,
    # 不是仓库里的东西。留着它,那道残留扫描就永远红。
    "src",
    "requirements-ci.txt",
}


def check_root_files(repo: Path) -> list[str]:
    """仓库根目录只允许出现约定的文件。"""
    problems = []
    for path in _tracked_files(repo):
        rel = path.relative_to(repo)
        if len(rel.parts) != 1:
            continue
        name = rel.name
        if name in ALLOWED_ROOT_FILES:
            continue
        problems.append(f"根目录出现了不该有的文件: {rel}")
    return problems


def check_commit_messages(repo: Path, limit: int = 300) -> list[str]:
    """提交说明里也不该有开发过程的复盘措辞。

    工作区干净不代表历史干净 —— 提交说明同样是对外的文字。可见层自检里
    写着"commit 0 开发对话残留",这句话得有人守着,不然它只是一句没人
    核的声明。

    只看最近 limit 条:仓库的历史被重写过,早期的说明已经清理过;而
    最近这批正是新写的,措辞最容易带上开发对话的痕迹。
    """
    problems: list[str] = []
    out = _run_git(repo, "log", f"-{limit}", "--format=%H%x00%B%x00")
    if not out.strip():
        return problems
    chunks = out.split("\x00")
    # 格式是 sha, message, sha, message, ...
    for i in range(0, len(chunks) - 1, 2):
        sha = chunks[i].strip()
        message = chunks[i + 1]
        if not sha:
            continue
        # 记录禁用词清单本身的提交正经引用那些词 —— 它们在讲怎么清理这些
        # 词,自己被判成违规就成了悖论。重写历史时给它们加了这个标记。
        if "Phrase-List-Documentation:" in message:
            continue
        for phrase in REGRESSION_PHRASES:
            if phrase in message:
                problems.append(f"提交 {sha[:8]} 的说明里出现复盘措辞 {phrase!r}")
    return problems


def check_dirty_worktree(repo: Path) -> list[str]:
    """工作区应当没有未提交的改动。"""
    return [f"工作区有未提交改动: {line}" for line in _worktree_lines(repo)]


def main() -> int:
    """扫描仓库,返回进程退出码。"""
    parser = argparse.ArgumentParser(description="扫描仓库残留")
    parser.add_argument("repo", type=Path, nargs="?", default=None, help="仓库路径")
    parser.add_argument("--public", action="store_true", help="按公开仓的标准检查")
    args = parser.parse_args()

    # 路径可以不给:不给就查本脚本所在的那个仓。镜像工作流里公开仓被
    # checkout 到 public/,私人仓在 src/ —— 不给路径时本脚本属于哪一个,
    # 就查哪一个,不会查错对象还报绿。
    repo = (
        args.repo if args.repo is not None else Path(__file__).resolve().parent.parent
    ).resolve()
    if not (repo / ".git").exists():
        print(f"不是 git 仓库: {repo}", file=sys.stderr)
        return 2

    files = _tracked_files(repo)
    problems: list[str] = []
    problems += check_regression_phrasing(repo, files)
    problems += check_artifacts(repo)
    problems += check_root_files(repo)
    problems += check_license_headers(repo, files)
    problems += check_commit_messages(repo)
    if args.public:
        problems += check_public_layout(repo, files)
    problems += check_dirty_worktree(repo)

    if problems:
        print(f"{repo.name} 存在 {len(problems)} 处残留:")
        for item in problems:
            print(" -", item)
        return 1

    print(f"{repo.name} 干净: {len(files)} 个受版本控制的文件,无残留")
    return 0


if __name__ == "__main__":
    sys.exit(main())
