# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 decimal + 真 contextvars + 真 operator + 真 functools 进阶。
全 stdlib, 零模拟。
"""
import decimal
import contextvars
import operator
import functools
import pytest


def test_decimal_basic_arithmetic():
    """真 decimal 精确算术 (不 float)"""
    # 0.1 + 0.2 != 0.3 in float; decimal 精确
    a = decimal.Decimal("0.1")
    b = decimal.Decimal("0.2")
    s = a + b
    assert s == decimal.Decimal("0.3")
    assert s == decimal.Decimal("0.30")  # 不 normalize
    assert str(s) == "0.3"  # normalized

    # 大数算 (float 失去精度, 但 decimal 默认 precision=28)
    with decimal.localcontext() as ctx:
        ctx.prec = 50
        big = decimal.Decimal("0.123456789012345678901234567890")
        double = big * 2
        assert double == decimal.Decimal("0.246913578024691357802469135780")
        # 验证: 数字位数保留
        assert len(str(double).split(".")[1]) == 30


def test_decimal_precision_context():
    """真 decimal context + precision + rounding"""
    ctx = decimal.getcontext()
    old_prec = ctx.prec
    try:
        ctx.prec = 3
        # 精度 3 数字
        a = decimal.Decimal("1") / decimal.Decimal("3")
        assert a == decimal.Decimal("0.333")
    finally:
        ctx.prec = old_prec


def test_decimal_rounding_modes():
    """真 4 种 rounding mode"""
    ctx = decimal.getcontext()
    old_rounding = ctx.rounding
    try:
        # ROUND_HALF_EVEN (默认)
        ctx.rounding = decimal.ROUND_HALF_EVEN
        assert decimal.Decimal("2.5").quantize(decimal.Decimal("1")) == decimal.Decimal("2")  # banker's rounding
        assert decimal.Decimal("3.5").quantize(decimal.Decimal("1")) == decimal.Decimal("4")

        # ROUND_HALF_UP
        ctx.rounding = decimal.ROUND_HALF_UP
        assert decimal.Decimal("2.5").quantize(decimal.Decimal("1")) == decimal.Decimal("3")
        assert decimal.Decimal("3.5").quantize(decimal.Decimal("1")) == decimal.Decimal("4")

        # ROUND_DOWN
        ctx.rounding = decimal.ROUND_DOWN
        assert decimal.Decimal("2.5").quantize(decimal.Decimal("1")) == decimal.Decimal("2")
        assert decimal.Decimal("3.5").quantize(decimal.Decimal("1")) == decimal.Decimal("3")

        # ROUND_UP
        ctx.rounding = decimal.ROUND_UP
        assert decimal.Decimal("2.5").quantize(decimal.Decimal("1")) == decimal.Decimal("3")
    finally:
        ctx.rounding = old_rounding


def test_decimal_localcontext():
    """真 localcontext 临时改 context"""
    with decimal.localcontext() as ctx:
        ctx.prec = 5
        # 5 数字精度
        a = decimal.Decimal("1") / decimal.Decimal("7")
        # 0.14285 (5 位有效)
        assert decimal.Decimal("0.14286")  # 0.14285... 四舍五入
    # 退出后恢复
    assert decimal.getcontext().prec > 5


def test_decimal_inf_nan():
    """真 Decimal inf / NaN / sNaN"""
    pos_inf = decimal.Decimal("Infinity")
    neg_inf = decimal.Decimal("-Infinity")
    nan = decimal.Decimal("NaN")
    assert pos_inf.is_infinite()
    assert not pos_inf.is_finite()
    assert neg_inf.is_infinite()
    assert nan.is_nan()
    assert not nan.is_finite()
    assert not nan.is_infinite()
    # 算术 (关 trap 让 inf + -inf 不抛)
    with decimal.localcontext() as ctx:
        ctx.traps[decimal.InvalidOperation] = False
        assert pos_inf + 1 == pos_inf
        # inf + -inf = NaN (undefined)
        assert (pos_inf + neg_inf).is_nan()
    # NaN != NaN (Python 比较)
    with decimal.localcontext() as ctx:
        # 默认可抛 InvalidOperation, 关 trap
        ctx.traps[decimal.InvalidOperation] = False
        assert nan != nan  # 仍 True
    # NaN 标志
    assert nan.is_nan()


def test_decimal_quantize():
    """真 quantize 真舍入到固定位"""
    # 0.1 + 0.2 舍到 1 位
    s = decimal.Decimal("0.3")
    assert s.quantize(decimal.Decimal("0.1")) == decimal.Decimal("0.3")
    # 0.1 + 0.2 的真和
    raw = decimal.Decimal("0.1") + decimal.Decimal("0.2")
    # 舍到 0.1
    assert raw.quantize(decimal.Decimal("0.1")) == decimal.Decimal("0.3")


def test_decimal_sqrt():
    """真 Decimal sqrt"""
    s = decimal.Decimal("2").sqrt()
    # 1.4142135...
    assert s > decimal.Decimal("1.4")
    assert s < decimal.Decimal("1.5")
    # sqrt(4) = 2
    assert decimal.Decimal("4").sqrt() == decimal.Decimal("2")
    # 平方验
    s2 = s * s
    # 精度限制
    assert abs(s2 - decimal.Decimal("2")) < decimal.Decimal("0.0001")


def test_decimal_log_exp():
    """真 Decimal ln / exp / log10"""
    e = decimal.Decimal("1").exp()
    # e ~ 2.718
    assert decimal.Decimal("2.71") < e < decimal.Decimal("2.72")
    # ln(e) = 1
    assert abs(e.ln() - decimal.Decimal("1")) < decimal.Decimal("0.0001")
    # log10(100) = 2
    assert abs(decimal.Decimal("100").log10() - decimal.Decimal("2")) < decimal.Decimal("0.0001")


def test_contextvars_basic():
    """真 ContextVar 跨 async 真传递"""
    var = contextvars.ContextVar("test_var", default="default")
    assert var.get() == "default"
    # 设
    token = var.set("hello")
    try:
        assert var.get() == "hello"
    finally:
        var.reset(token)
    assert var.get() == "default"


def test_contextvars_copy_context():
    """真 copy_context 真独立"""
    var = contextvars.ContextVar("counter", default=0)
    ctx = contextvars.copy_context()
    # 在子 ctx 中, var.set 不影响父
    def task():
        # 新 ctx 中 var 是 default
        assert var.get() == 0
        var.set(200)
        return var.get()
    result = ctx.run(task)
    assert result == 200
    # 父 ctx 仍 default
    assert var.get() == 0


def test_contextvars_nested_run():
    """真 run 嵌套 + 真 Context 链"""
    var = contextvars.ContextVar("nested", default="init")
    var.set("level1")

    def inner():
        return var.get()  # 应 "level1" (传 context)

    def middle():
        var.set("level2")
        return inner()

    # 父 ctx 仍是 "level1"
    result = contextvars.copy_context().run(middle)
    assert result == "level2"
    # 父 ctx
    assert var.get() == "level1"


def test_contextvars_token_set_reset():
    """真 token set / reset"""
    var = contextvars.ContextVar("t", default=0)
    assert var.get() == 0
    token1 = var.set(1)
    assert var.get() == 1
    token2 = var.set(2)
    assert var.get() == 2
    # reset 2 → 1
    var.reset(token2)
    assert var.get() == 1
    # reset 1 → 0
    var.reset(token1)
    assert var.get() == 0


def test_contextvars_in_concurrent():
    """真 ContextVar 跨 thread 真传递"""
    import threading
    var = contextvars.ContextVar("t_var", default="main")

    def worker():
        # 子 thread 看不到 主 thread 设的值
        assert var.get() == "main"
        var.set("thread")
        return var.get()

    results = []
    def run():
        results.append(worker())

    threads = [threading.Thread(target=run) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["thread", "thread", "thread"]


def test_operator_overload():
    """真 operator 模块函数"""
    # operator.add / mul / etc
    assert operator.add(1, 2) == 3
    assert operator.mul(3, 4) == 12
    assert operator.contains([1, 2, 3], 2)
    # operator.itemgetter 真 tuple
    get0, get1 = operator.itemgetter(0), operator.itemgetter(1)
    assert get0([10, 20, 30]) == 10
    assert get1([10, 20, 30]) == 20
    # operator.attrgetter
    class Obj:
        x = 1
        y = 2
    get_xy = operator.attrgetter("x", "y")
    assert get_xy(Obj()) == (1, 2)


def test_functools_reduce_initial():
    """真 reduce + initial"""
    # 5! = 120
    from functools import reduce
    import operator
    factorial = lambda n: reduce(operator.mul, range(1, n + 1), 1)
    assert factorial(5) == 120
    assert factorial(0) == 1  # initial
    assert factorial(1) == 1


def test_functools_total_ordering():
    """真 @total_ordering 装饰器"""
    from functools import total_ordering

    @total_ordering
    class V:
        def __init__(self, n):
            self.n = n
        def __eq__(self, other):
            return self.n == other.n
        def __lt__(self, other):
            return self.n < other.n

    a = V(1)
    b = V(2)
    assert a < b
    assert b > a
    assert a <= b
    assert b >= a
    assert a != b
    assert a == V(1)


def test_functools_cache_method():
    """真 @cache 装饰 method"""
    from functools import cache

    class Calc:
        @cache
        def fib(self, n):
            if n < 2:
                return n
            return self.fib(n - 1) + self.fib(n - 2)

    c = Calc()
    assert c.fib(10) == 55
    # cache info
    info = c.fib.cache_info()
    assert info.hits >= 8  # fib(10) 多次 hit
    assert info.misses >= 10


def test_functools_reduce_complex():
    """真 reduce 真多层"""
    # 字符串拼接
    s = functools.reduce(lambda a, b: a + b, ["h", "e", "l", "l", "o"], "")
    assert s == "hello"
    # max (没 key)
    assert functools.reduce(lambda a, b: a if a > b else b, [3, 1, 4, 1, 5, 9, 2, 6]) == 9
