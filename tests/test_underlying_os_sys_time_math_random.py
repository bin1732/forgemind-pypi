# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""`os` / `sys` / `time` / `math` / `random` 真底层测试。

- os:真的做文件与目录操作、进程与环境
- sys:真的查解释器状态与模块
- time:真的取时间与测量耗时
- math:真的做数值计算
- random:真的产生随机数并能复现

覆盖 os 6 + sys 6 + time 6 + math 6 + random 6 + 真底层测试。
"""

import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest


# ======================== os ========================


class TestOs:
    """操作系统接口"""

    def test_getcwd(self):
        """能取到当前目录"""
        assert isinstance(os.getcwd(), str)
        assert Path(os.getcwd()).is_dir()

    def test_listdir_and_scandir(self, tmp_path):
        """真的列出目录内容"""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        names = os.listdir(tmp_path)
        assert "a.txt" in names
        with os.scandir(tmp_path) as entries:
            assert any(entry.name == "a.txt" for entry in entries)

    def test_rename(self, tmp_path):
        """真的改文件名"""
        source = tmp_path / "a.txt"
        source.write_text("x", encoding="utf-8")
        target = tmp_path / "b.txt"
        os.rename(source, target)
        assert target.exists()
        assert not source.exists()

    def test_remove_and_unlink(self, tmp_path):
        """真的删文件"""
        target = tmp_path / "forge.txt"
        target.write_text("x", encoding="utf-8")
        os.unlink(target)
        assert not target.exists()

    def test_makedirs(self, tmp_path):
        """真的建多级目录"""
        target = tmp_path / "a" / "b" / "c"
        os.makedirs(target)
        assert target.is_dir()
        # 重复建不报错
        os.makedirs(target, exist_ok=True)

    def test_environ(self):
        """能读写环境变量"""
        os.environ["FORGE_OS_TEST"] = "forge"
        try:
            assert os.environ["FORGE_OS_TEST"] == "forge"
            assert os.getenv("FORGE_OS_TEST") == "forge"
        finally:
            os.environ.pop("FORGE_OS_TEST", None)

    def test_stat(self, tmp_path):
        """真的取到文件状态"""
        target = tmp_path / "forge.txt"
        target.write_text("forge", encoding="utf-8")
        info = os.stat(target)
        assert info.st_size == 5
        assert os.path.exists(target)

    def test_run_command(self):
        """真的跑一条命令"""
        result = subprocess.run(
            [sys.executable, "-c", "print('forge-os')"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0
        assert "forge-os" in result.stdout


# ======================== sys ========================


class TestSys:
    """解释器状态"""

    def test_version(self):
        """能取到版本号"""
        assert sys.version_info.major == 3
        assert isinstance(sys.version, str)

    def test_executable(self):
        """能取到解释器路径"""
        assert Path(sys.executable).exists()

    def test_path_entry(self):
        """搜索路径里有可用的项"""
        assert isinstance(sys.path, list)
        assert any(isinstance(item, str) for item in sys.path)

    def test_builtin_module(self):
        """能按名取到内建模块"""
        module = sys.modules.get("sys")
        assert module is sys

    def test_getsizeof(self):
        """能取对象占用的大小"""
        assert sys.getsizeof(b"forge") > 0
        assert sys.getsizeof("forge") > 0

    def test_platform(self):
        """能取到平台标识"""
        assert isinstance(sys.platform, str)
        assert sys.platform

    def test_recursion_limit(self):
        """递归上限可读可改"""
        original = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(original + 100)
            assert sys.getrecursionlimit() == original + 100
        finally:
            sys.setrecursionlimit(original)


# ======================== time ========================


class TestTime:
    """时间"""

    def test_time_is_float(self):
        """当前时间是浮点秒"""
        value = time.time()
        assert isinstance(value, float)
        assert value > 0

    def test_monotonic_increases(self):
        """单调时钟不回退"""
        first = time.monotonic()
        time.sleep(0.01)
        assert time.monotonic() >= first

    def test_perf_counter(self):
        """高性能计时器可用"""
        assert time.perf_counter() > 0

    def test_process_time(self):
        """进程耗时可读"""
        assert time.process_time() >= 0

    def test_localtime_struct(self):
        """本地时间能转成结构"""
        struct = time.localtime(0)
        assert struct.tm_year in (1969, 1970)

    def test_gmtime_struct(self):
        """世界时能转成结构"""
        struct = time.gmtime(0)
        assert struct.tm_year == 1970

    def test_strftime(self):
        """时间能格式化"""
        text = time.strftime("%Y-%m-%d", time.localtime(0))
        assert len(text) == 10

    def test_sleep_returns_none(self):
        """睡眠接口返回空"""
        assert time.sleep(0.001) is None


# ======================== math ========================


class TestMath:
    """数值计算"""

    def test_sqrt(self):
        """平方根"""
        assert math.sqrt(16) == 4.0
        assert math.isclose(math.sqrt(2), 1.4142135623730951)

    def test_isclose(self):
        """近似比较"""
        assert math.isclose(0.1 + 0.2, 0.3) is True
        assert math.isclose(1.0, 1.1) is False

    def test_isnan_and_isinf(self):
        """能判断非数与无穷"""
        assert math.isnan(float("nan")) is True
        assert math.isinf(float("inf")) is True
        assert math.isfinite(1.0) is True

    def test_gcd_and_lcm(self):
        """最大公约数与最小公倍数"""
        assert math.gcd(12, 18) == 6
        assert math.lcm(4, 6) == 12

    def test_factorial(self):
        """阶乘"""
        assert math.factorial(5) == 120

    def test_combinations_and_permutations(self):
        """组合数与排列数"""
        assert math.comb(5, 2) == 10
        assert math.perm(5, 2) == 20

    def test_fsum(self):
        """精确求和"""
        assert math.fsum([0.1] * 10) == 1.0

    def test_trunc_and_floor(self):
        """取整"""
        assert math.trunc(3.7) == 3
        assert math.floor(-3.2) == -4
        assert math.ceil(3.2) == 4


# ======================== random ========================


class TestRandom:
    """随机数"""

    def test_random_in_range(self):
        """随机数落在给定区间"""
        for _ in range(50):
            value = random.random()
            assert 0.0 <= value < 1.0

    def test_randint(self):
        """随机整数在闭区间内"""
        for _ in range(50):
            value = random.randint(3, 7)
            assert 3 <= value <= 7

    def test_choice(self):
        """从序列里取一个"""
        assert random.choice(["a", "b"]) in ("a", "b")

    def test_shuffle_is_reproducible(self):
        """固定种子后洗牌结果可复现"""
        first = list(range(10))
        second = list(range(10))
        random.seed(42)
        random.shuffle(first)
        random.seed(42)
        random.shuffle(second)
        assert first == second

    def test_seed_reproduces(self):
        """固定种子后随机数可复现"""
        random.seed(1234)
        first = [random.random() for _ in range(5)]
        random.seed(1234)
        second = [random.random() for _ in range(5)]
        assert first == second

    def test_sample(self):
        """能取不重复的样本"""
        sample = random.sample(range(20), 5)
        assert len(sample) == 5
        assert len(set(sample)) == 5

    def test_randrange(self):
        """按步长取随机数"""
        for _ in range(20):
            value = random.randrange(0, 10, 2)
            assert value % 2 == 0
            assert 0 <= value < 10

    def test_choices_with_weights(self):
        """按权重取样"""
        values = random.choices(["a", "b"], weights=[1, 0], k=5)
        assert values == ["a"] * 5
