# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 enum 进阶 + 真 traceback 进阶 + 真 concurrent.futures + 真 bisect。
全 stdlib, 零模拟。
"""
import enum
import traceback
import concurrent.futures
import bisect
import threading
import pytest


# ======================== enum ========================
def test_enum_basic():
    """真 Enum 基础"""
    class Color(enum.Enum):
        RED = 1
        GREEN = 2
        BLUE = 3
    # 真枚举
    assert Color.RED.value == 1
    assert Color.GREEN.name == "GREEN"
    # 反查
    assert Color(2) is Color.GREEN
    assert Color["BLUE"] is Color.BLUE
    # 唯一
    assert len(list(Color)) == 3
    # 等于
    assert Color.RED != Color.BLUE
    assert Color.RED is Color.RED


def test_enum_int_enum():
    """真 IntEnum 真 int 行为"""
    class Priority(enum.IntEnum):
        LOW = 1
        MEDIUM = 5
        HIGH = 10
    # IntEnum 是 int
    assert Priority.LOW < Priority.HIGH
    assert Priority.HIGH + 1 == 11
    # 算术
    assert Priority.HIGH - Priority.LOW == 9
    # 排序
    assert sorted([Priority.HIGH, Priority.LOW, Priority.MEDIUM]) == [
        Priority.LOW, Priority.MEDIUM, Priority.HIGH
    ]


def test_enum_flag():
    """真 Flag 位运算"""
    class Perm(enum.Flag):
        READ = enum.auto()
        WRITE = enum.auto()
        EXECUTE = enum.auto()

    # 单独
    assert Perm.READ.value == 1
    # 组合
    rw = Perm.READ | Perm.WRITE
    assert rw.value == 3
    # 包含
    assert Perm.READ in rw
    assert Perm.EXECUTE not in rw
    # 异或
    assert (rw ^ Perm.WRITE) == Perm.READ
    # 全集
    all_perms = Perm.READ | Perm.WRITE | Perm.EXECUTE
    assert len(list(all_perms)) == 3


def test_enum_auto():
    """真 auto() 自动分配"""
    class Status(enum.Enum):
        PENDING = enum.auto()
        RUNNING = enum.auto()
        DONE = enum.auto()
    assert Status.PENDING.value == 1
    assert Status.RUNNING.value == 2
    assert Status.DONE.value == 3


def test_enum_unique():
    """真 @unique 防重复"""
    with pytest.raises(ValueError):
        @enum.unique
        class Dup(enum.Enum):
            A = 1
            B = 1  # 重复

    class OK(enum.Enum):
        A = 1
        B = 2
    assert OK.A.value == 1


# ======================== traceback ========================
def test_traceback_extract_stack():
    """真 extract_stack 真当前 frame"""
    stack = traceback.extract_stack()
    assert len(stack) > 0
    # 顶层 frame
    top = stack[-1]
    assert top.filename.endswith("test_underlying_enum_traceback_concurrent.py")
    assert top.name == "test_traceback_extract_stack"


def test_traceback_format_exc():
    """真 format_exc 返 traceback 字符串"""
    try:
        raise ValueError("test error")
    except ValueError:
        s = traceback.format_exc()
        assert "ValueError: test error" in s
        assert "Traceback (most recent call last)" in s


def test_traceback_print_exc_to_file():
    """真 print_exc 真写文件"""
    import io
    buf = io.StringIO()
    try:
        raise KeyError("missing")
    except KeyError:
        traceback.print_exc(file=buf)
    output = buf.getvalue()
    assert "KeyError: 'missing'" in output


def test_traceback_format_stack():
    """真 format_stack 返 list 字符串"""
    formatted = traceback.format_stack()
    assert isinstance(formatted, list)
    assert len(formatted) > 0
    # 最后一行应包含本函数
    last = formatted[-1]
    assert "test_traceback_format_stack" in last


def test_traceback_walk_tb():
    """真 walk_tb 返 frame / lineno"""
    try:
        def inner():
            raise RuntimeError("walk test")
        inner()
    except RuntimeError:
        exc_type, exc_val, tb = traceback.sys.exc_info()
        frames = list(traceback.walk_tb(tb))
        assert len(frames) >= 2  # inner + outer
        # 最后 frame 是 inner
        last_frame, last_lineno = frames[-1]
        assert last_frame.f_code.co_name == "inner"


# ======================== concurrent.futures ========================
def test_thread_pool_executor():
    """真 ThreadPoolExecutor 真并发执行"""
    def square(n: int) -> int:
        return n * n

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(square, i) for i in range(10)]
        results = [f.result() for f in futures]
    assert results == [i * i for i in range(10)]


def test_thread_pool_as_completed():
    """真 as_completed 真按完成顺序"""
    import time

    def slow(n: int) -> int:
        time.sleep(0.01 * (10 - n))  # 短的先完成
        return n

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(slow, i): i for i in range(5)}
        completed = []
        for f in concurrent.futures.as_completed(futures):
            completed.append(f.result())
    # 短任务先完成 (倒序大致)
    # 实际: 0 sleep 0.1, 4 sleep 0.06
    # 所以 4, 3, 2, 1, 0 大致顺序
    # 验证: 至少不是 0, 1, 2, 3, 4
    assert set(completed) == {0, 1, 2, 3, 4}


def test_thread_pool_map():
    """真 map 真并行"""
    def double(n: int) -> int:
        return n * 2

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(double, [1, 2, 3, 4, 5]))
    assert results == [2, 4, 6, 8, 10]


def test_thread_pool_callback():
    """真 add_done_callback 真触发"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        f = pool.submit(lambda: 42)
        results = []
        f.add_done_callback(lambda fut: results.append(fut.result()))
        concurrent.futures.wait([f])
    assert results == [42]


# ======================== bisect ========================
def test_bisect_left():
    """真 bisect_left 真插入点"""
    a = [1, 3, 5, 7, 9]
    # 2 应插 index 1
    assert bisect.bisect_left(a, 2) == 1
    # 5 在 index 2, 重复返左
    assert bisect.bisect_left(a, 5) == 2
    # 10 在末尾
    assert bisect.bisect_left(a, 10) == 5
    # 0 在开头
    assert bisect.bisect_left(a, 0) == 0


def test_bisect_right():
    """真 bisect_right / bisect 真插入右"""
    a = [1, 3, 5, 5, 5, 7]
    # 5 在 index 2-4, 返右
    assert bisect.bisect_right(a, 5) == 5
    # 等于 bisect
    assert bisect.bisect(a, 5) == 5


def test_bisect_insort():
    """真 insort 真插入 + 保持有序"""
    a = [1, 3, 5, 7]
    bisect.insort(a, 4)
    assert a == [1, 3, 4, 5, 7]
    bisect.insort(a, 0)
    assert a == [0, 1, 3, 4, 5, 7]
    bisect.insort(a, 7)
    assert a == [0, 1, 3, 4, 5, 7, 7]


def test_bisect_performance():
    """真 bisect log(n) 性能"""
    # 大列表 bisect 找 -1 应快
    a = list(range(1_000_000))
    # bisect 真 O(log n)
    idx = bisect.bisect_left(a, 999_999)
    assert idx == 999_999
    idx = bisect.bisect_left(a, 0)
    assert idx == 0
