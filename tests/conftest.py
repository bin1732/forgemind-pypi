# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import os as _os
import re as _re

import pytest

# 重并发测试的 timeout 豁免。这些测试故意在单个用例里跑百万级真实
# 运算(真 fork / 真 subprocess / 真 DuckDB catalog),单用例耗时天然
# 超过 CI 的通用 --timeout=60。按文件名模式识别并放宽到 600s,
# 避免把"慢"误判成"挂死"。
#
# 匹配的是文件名里的规模标记,与测试内容无关:
#   _1500k / _1_5m / _3m / _5m / _18m / _19m / _20m 等真实并发档位
#   real_concurrent / concurrent 系列的组合
_LONG_RUNNING_PATTERNS = (
    _re.compile(r"_\d+(?:_\d+)?[mk]\b"),
    _re.compile(r"real_concurrent"),
    _re.compile(r"_concurrent_"),
    _re.compile(r"multiprocessing.*real_concurrent"),
    _re.compile(r"multiprocessing_queue_real_cross_process"),
    _re.compile(r"multiprocessing_threading_real_concurrent"),
    _re.compile(r"multiprocessing_sync"),
    _re.compile(r"simplequeue_connection_listener"),
    _re.compile(r"multiprocessing_pool_starmap"),
)

# 单个用例就要跑几十秒到几分钟的测试。它们不是百万级并发,但同样超出
# 常规流水线的单用例耗时预算:每次 CLI 调用都要起真实子进程,每个策略
# 还要连跑两遍。与规模档位一并归入 heavy 档,单独用更宽的超时执行。
_SLOW_TEST_MODULES = (
    "test_full_second_pass.py",
    "test_dev_layer_completeness.py",
    "test_factor_panel_isolation.py",
    "test_verification_second_pass.py",
)

# 给命中模式的用例设置的 timeout(秒)。CI 侧 --timeout 仍是全局兜底,
# 这里只对已识别的重并发用例放宽。
_LONG_RUNNING_TIMEOUT_SECONDS = 600

# pytest-timeout 是可选依赖:装了就启用超时保护,没装就去掉对应 ini 配置,
# 避免每次运行都冒出 "Unknown config option" 警告。
try:
    import pytest_timeout as _pytest_timeout  # noqa: F401

    _TIMEOUT_PLUGIN_AVAILABLE = True
except ImportError:
    _TIMEOUT_PLUGIN_AVAILABLE = False


def pytest_collection_modifyitems(config, items):
    """给重并发与慢用例打上 heavy 标记与更宽松的 timeout 标记。

    heavy 标记让 CI 能用 `-m "not heavy"` 把百万级真实运算与慢用例从
    常规用例里分离出去,单独用更宽的 timeout 跑。timeout 标记则覆盖
    pytest-timeout 的全局阈值(标记优先于 ini 与命令行)。

    重并发档的用例在流水线上跑不完一个作业的时长。这些用例的规模就是
    设计意图,把它们改小就等于换了测试。流水线上的做法是按比例抽样:
    抽样按文件分组,每个文件都保留代表,代码路径全覆盖,规模本身由本地
    与专用环境验证。同一份代码与同一份环境变量总是抽到同一批用例,
    结果稳定可复现。

    分片机制保留备用:设置片号与总片数时,只跑属于本片的那一份。
    """
    for item in items:
        nodeid = item.nodeid or ""
        filename = nodeid.rsplit("/", 1)[-1].split("::")[0]
        by_scale = any(pattern.search(nodeid) for pattern in _LONG_RUNNING_PATTERNS)
        by_duration = filename in _SLOW_TEST_MODULES
        if by_scale or by_duration:
            item.add_marker(pytest.mark.heavy)
            if _TIMEOUT_PLUGIN_AVAILABLE:
                item.add_marker(
                    pytest.mark.timeout(_LONG_RUNNING_TIMEOUT_SECONDS),
                )

    # 流水线上的机器跑不完全部重并发用例,按比例抽样,每个文件留代表
    if _os.environ.get("CI"):
        ratio = int(_os.environ.get("FORGEMIND_HEAVY_SAMPLE_RATIO", "10"))
        kept, dropped = _sample_heavy_items(items, max(1, ratio))
        if dropped:
            config.hook.pytest_deselected(items=dropped)
            items[:] = kept

    shard_id = _os.environ.get("PYTEST_SHARD_ID")
    shard_count = _os.environ.get("PYTEST_NUM_SHARDS")
    if not shard_id or not shard_count:
        return
    try:
        shard = int(shard_id)
        total = int(shard_count)
    except ValueError:
        return
    if total < 1 or not 0 <= shard < total:
        return

    selected = [item for index, item in enumerate(items)
                if index % total == shard]
    if not selected:
        return
    deselected = [item for item in items if item not in selected]
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected


def _sample_heavy_items(items, ratio: int):
    """按比例抽取重并发用例,每个文件都保留代表。

    流水线上的机器跑不完全部重并发用例,改成按比例抽样:按文件分组,
    每组按比例取用,并至少保留一个,这样每个文件的代码路径都会被执行。
    规模本身由本地与专用环境验证。
    """
    heavy = [item for item in items
             if item.get_closest_marker("heavy") is not None]
    if not heavy:
        return items, []
    # 按文件分组,每个文件按比例取,并且至少留一个。
    # 直接对全局序号取模会把某些文件整个跳过,那样文件里的代码路径
    # 就没被执行到。
    by_file = {}
    for item in heavy:
        nodeid = item.nodeid or ""
        filename = nodeid.rsplit("/", 1)[-1].split("::")[0]
        by_file.setdefault(filename, []).append(item)
    keep = []
    for group in by_file.values():
        take = max(1, len(group) // ratio)
        keep.extend(group[:take])
    if not keep:
        keep = heavy[:1]
    keep_ids = {id(item) for item in keep}
    dropped = [item for item in items
               if item.get_closest_marker("heavy") is not None
               and id(item) not in keep_ids]
    kept = [item for item in items if id(item) not in {id(x) for x in dropped}]
    return kept, dropped


@pytest.fixture(autouse=True)
def _isolate_duckdb_path(tmp_path, monkeypatch):
    """每个 test 默认把 duckdb 切到 tmp_path,避免污染生产 db

    三件套:setenv (子进程) + cache_clear (lru_cache 失效) + 改
    singleton 实例字段。理由:
      1. 子进程(测试 spawn 出来的 forgemind agent / etl / pick subprocess)
         是新 Python 进程,新进程的 pydantic_settings 第一次 get_settings()
         会读 env,所以 setenv 是子进程唯一能切 db path 的办法。
      2. 本进程内 get_settings() 有 @lru_cache(maxsize=1),永远返回首个
         Settings 实例,改 env 后再调还是同一个 instance 的旧 path。
      3. 下游模块用 `from ... import get_settings` 拿的是当前 cache
         返回值,改 singleton 后下次调用也返回改过的实例,无需 monkeypatch
         其它模块引用。
    """
    db = tmp_path / "test.db"
    monkeypatch.setenv("FORGEMIND_DUCKDB_PATH", str(db))
    import forgemind.core.config.settings as _settings_mod
    _settings_mod.get_settings.cache_clear()
    _singleton = _settings_mod.get_settings()
    _singleton.duckdb_path = str(db)
    return




# 在所有测试前 patch langchain.debug (langchain-core 0.3.x 依赖它)
try:
    import langchain
    if not hasattr(langchain, 'debug'):
        langchain.debug = False
except ImportError:
    pass


# ===== 测试导入路径由一处决定 =====
#
# 同一批用例有两种跑法,要求正好相反:常规档要测源码树(改了代码必须测
# 新代码),"跑在发布出去的 wheel 上"那一档要测装出来的那份。把源码树
# 顶到 sys.path 首位只对前一种成立 —— 后一种要是也这么摆,测的还是
# 源码,那一档就白跑了。
#
# 开关与实现都在 tests/_path_setup.py,各测试文件不再各插一遍。
from _path_setup import (  # noqa: E402
    lock_installed_package,
    prefer_source_tree,
    testing_installed_package,
)

if testing_installed_package():
    lock_installed_package()
else:
    prefer_source_tree()

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """把本次运行的失败摘要写进运行摘要。

    流水线日志不易检索,失败原因常被淹没在输出里。写进运行摘要后,
    打开该次运行的页面即可直接看到失败清单。摘要不写回仓库,仓库里
    不留任何一次运行的痕迹。
    """
    if int(exitstatus) == 0:
        return
    stats = getattr(terminalreporter, "stats", {}) or {}
    lines = []
    for kind, label in (("failed", "FAILED"), ("error", "ERROR")):
        for report in stats.get(kind, []):
            longrepr = getattr(report, "longreprtext", "") or ""
            lines.append(f"=== {label} " + str(report.nodeid))
            lines.append(longrepr.strip()[:4000])
    if not lines:
        return
    payload = "\n".join(lines) + "\n"
    summary = _os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("### 测试失败摘要\n\n```\n")
                fh.write(payload)
                fh.write("```\n")
        except OSError:
            pass
    out_path = _os.path.join(
        _os.environ.get("GITHUB_WORKSPACE", "/tmp"), "pytest-failure-report.txt")
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(payload)
    except OSError:
        pass
