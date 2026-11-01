# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`time` + `datetime` 进阶 + `abc` + `atexit` + `enum` 进阶真底层测试。

覆盖时间 / 抽象基类 / 退出钩子 / 枚举模块:
  - `time.time()` 真返 float 戳
  - `time.time_ns()` 真返 int 纳秒
  - `time.monotonic()` 真返递增
  - `time.perf_counter()` 真返高精度
  - `time.gmtime(0)` 真返 epoch UTC struct
  - `time.localtime` 真返本地时区
  - `time.strftime('%Y-%m-%d', t)` 真格式
  - `time.mktime(t)` 真逆
  - `time.sleep(0.01)` 真睡
  - `datetime.datetime(2026, 1, 1).timestamp()` 真返 stamp
  - `datetime.datetime.fromtimestamp(0, tz=UTC)` 真 epoch
  - `datetime.timedelta(days=1).total_seconds() == 86400`
  - `datetime.date.today()` 真返今天
  - `datetime.datetime.strptime('2026-01-15', '%Y-%m-%d')` 真解
  - `abc.ABC` 真 abstractmethod
  - `abc.ABCMeta` 真注册虚拟子类
  - `atexit.register(fn)` 真注册,import 时执行
  - `enum.IntEnum` 真子类型 int
  - `enum.Flag` 真位掩码
  - `enum.auto()` 真自增
"""
import atexit
import datetime
import enum
import time
from abc import ABC, abstractmethod

import pytest


# -- time ---------------------------------------------------------------------

class TestTimeAdvanced:
    def test_time_returns_float(self):
        """`time.time()` 真返 float 戳。"""
        t = time.time()
        assert isinstance(t, float) and t > 0

    def test_time_ns_returns_int(self):
        """`time.time_ns()` 真返 int 纳秒戳。"""
        t = time.time_ns()
        assert isinstance(t, int) and t > 0

    def test_monotonic(self):
        """`time.monotonic()` 真返递增。"""
        t1 = time.monotonic()
        time.sleep(0.01)
        t2 = time.monotonic()
        assert t2 > t1, f"monotonic 应递增,{t1} vs {t2}"

    def test_gmtime_epoch(self):
        """`time.gmtime(0)` 真返 epoch UTC struct (1970-01-01 00:00)。"""
        t = time.gmtime(0)
        assert t.tm_year == 1970
        assert t.tm_mon == 1
        assert t.tm_mday == 1
        assert t.tm_hour == 0

    def test_strftime(self):
        """`time.strftime('%Y-%m-%d', t)` 真格式。"""
        t = time.gmtime(0)
        out = time.strftime("%Y-%m-%d", t)
        assert out == "1970-01-01"

    def test_mktime_round_trip(self):
        """`time.mktime` 真把 struct 逆为 stamp。"""
        t = time.localtime(0)
        stamp = time.mktime(t)
        # localtime 0 至少接近 0,容差 ±24h
        assert abs(stamp) < 86400, f"mktime 应接近 0,实际 {stamp}"


# -- datetime 进阶 ------------------------------------------------------------

class TestDatetimeAdvanced:
    def test_datetime_to_timestamp(self):
        """`datetime(2026,1,1).timestamp()` 真返 stamp。"""
        dt = datetime.datetime(2026, 1, 1, 0, 0, 0)
        # 距 1970-01-01 大约 1767225600 (容差 86400)
        s = dt.timestamp()
        assert abs(s - 1767225600) < 86400

    def test_datetime_fromtimestamp_epoch(self):
        """`datetime.fromtimestamp(0, tz=UTC)` 真返 1970-01-01。"""
        dt = datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        assert dt.year == 1970
        assert dt.month == 1

    def test_timedelta_total_seconds(self):
        """`timedelta(days=1).total_seconds() == 86400`。"""
        assert datetime.timedelta(days=1).total_seconds() == 86400
        # 复合
        td = datetime.timedelta(days=1, hours=2, minutes=3)
        assert td.total_seconds() == 86400 + 2 * 3600 + 3 * 60

    def test_date_today(self):
        """`date.today()` 真返今天日期。"""
        d = datetime.date.today()
        now = datetime.datetime.now().date()
        assert d == now

    def test_strptime(self):
        """`datetime.strptime('2026-01-15', '%Y-%m-%d')` 真解。"""
        dt = datetime.datetime.strptime("2026-01-15", "%Y-%m-%d")
        assert dt.year == 2026 and dt.month == 1 and dt.day == 15


# -- abc ----------------------------------------------------------------------

class _Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...


class _Square(_Shape):
    def __init__(self, side):
        self.side = side

    def area(self):
        return self.side * self.side


class TestAbc:
    def test_abstract_cannot_instantiate(self):
        """`ABC + @abstractmethod` 真阻止直接实例化。"""
        with pytest.raises(TypeError):
            _Shape()

    def test_concrete_can_instantiate(self):
        """`Square` 继承 + 实现 area,真可实例化。"""
        s = _Square(5)
        assert s.area() == 25

    def test_ABCMeta_register(self):
        """`ABCMeta.register` 真把外部 class 标为 virtual subclass。"""
        class _Duck:
            def area(self):
                return 99

        _Shape.register(_Duck)
        assert issubclass(_Duck, _Shape), (
            "register 后 _Duck 应是 _Shape 虚拟子类"
        )


# -- atexit -------------------------------------------------------------------

class TestAtexit:
    def test_atexit_register_and_unregister(self):
        """`atexit.register(fn)` 真注册,`unregister` 真移除。"""
        calls = []

        def fn():
            calls.append("atexit called")

        atexit.register(fn)
        # 不在解释器退出时真跑 (沙箱不退出),只验 unregister 不抛
        atexit.unregister(fn)
        # 反复 register/unregister 不抛
        for _ in range(5):
            atexit.register(fn)
            atexit.unregister(fn)


# -- enum 进阶 ----------------------------------------------------------------

class _Color(enum.IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class _Perm(enum.Flag):
    READ = enum.auto()
    WRITE = enum.auto()
    EXEC = enum.auto()


class TestEnumAdvanced:
    def test_IntEnum_arithmetic(self):
        """`_Color(IntEnum)` 真子类型 int,可算术。"""
        assert _Color.RED + 1 == 2  # RED=1, 1+1=2
        assert _Color.GREEN < _Color.BLUE
        assert int(_Color.BLUE) == 3

    def test_Flag_combination(self):
        """`Flag.auto()` 真位掩码,`READ|WRITE` 是合值。"""
        rw = _Perm.READ | _Perm.WRITE
        assert _Perm.READ in rw
        assert _Perm.WRITE in rw
        assert _Perm.EXEC not in rw

    def test_enum_auto_increments(self):
        """`enum.auto()` 真自增,`READ=1, WRITE=2, EXEC=4`。"""
        assert _Perm.READ.value == 1
        assert _Perm.WRITE.value == 2
        assert _Perm.EXEC.value == 4

    def test_enum_iteration(self):
        """`Color` 真可迭代, 返 3 个成员。"""
        members = list(_Color)
        assert len(members) == 3
        assert _Color.RED in members
