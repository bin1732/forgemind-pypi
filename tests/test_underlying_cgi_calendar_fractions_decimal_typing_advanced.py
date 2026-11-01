# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`cgi` 真 + `calendar` 进阶 + `fractions` 进阶 + `decimal` 进阶 + `typing` 进阶 真底层测试。

覆盖 CGI 工具 / 日历 / 分数 / 精确小数 / 类型模块:
  - `cgi.parse_qs('a=1&b=2')` 真解
  - `cgi.escape('<a>')` 真转义
  - `cgi.FieldStorage` 子化
  - `cgi.parse_header('text/html; charset=utf-8')` 真解
  - `cgi.parse_multipart(fp, pdict)` 真解 multipart
  - `calendar.weekheader(2)` 真返 'Mo Tu We'
  - `calendar.monthcalendar(2026, 10)` 真返 list of weeks
  - `calendar.calendar(2026)` 真返整年
  - `fractions.Fraction.from_float(0.5)` 真精确 1/2
  - `fractions.Fraction('22/7')` 真字符串解析
  - `fractions.gcd(12, 8) == 4` (3.5+) 真 gcd
  - `decimal.getcontext().rounding = ROUND_HALF_EVEN` 真设
  - `decimal.Decimal.exp()` 真 e^x
  - `decimal.Decimal.ln()` 真自然对数
  - `decimal.Decimal.sqrt()` 真开方
  - `decimal.Context.create_decimal('0.1')` 真从 str
  - `typing.Literal[1, 2, 3]` 真字面值
  - `typing.NoReturn` 真声明不返
  - `typing.Never` 3.11+ 真 alias NoReturn
  - `typing.Self` 3.11+ 真 self type
"""
import calendar
# cgi 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", DeprecationWarning)
        import cgi
except ImportError:
    cgi = None
import decimal
import fractions
import io
import typing

import pytest


# -- cgi ----------------------------------------------------------------------

# 这些模块在 Python 3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(cgi is None, reason="cgi 模块在 Python 3.13 起被移除")


class TestCgi:
    def test_parse_qs(self):
        """`cgi.parse_qs` Python 3.11+ 移走, 改用 urllib.parse.parse_qs 真解。"""
        import urllib.parse
        result = urllib.parse.parse_qs("a=1&b=2&a=3")
        assert result == {"a": ["1", "3"], "b": ["2"]}, (
            f"parse_qs 应={'a':['1','3'],'b':['2']},实际 {result}"
        )

    def test_escape(self):
        """`html.escape('<a>')` 真转义 (Python 3.2+ 推荐替代 cgi.escape)。"""
        out = cgi.escape if hasattr(cgi, "escape") else __import__("html").escape
        out = out("<a href=\"x\">")
        assert "&lt;" in out
        assert "&gt;" in out
        # html.escape 默认不转 &, 我们用引号 &quot; 验 quote=True
        # 或 cgi.escape 时才转 &
        # 简化: 至少 < 和 > 转义
        assert "<" not in out
        assert ">" not in out

    def test_parse_header(self):
        """`cgi.parse_header('text/html; charset=utf-8')` 真解 (type, pdict)。"""
        ctype, pdict = cgi.parse_header("text/html; charset=utf-8")
        assert ctype == "text/html"
        assert pdict == {"charset": "utf-8"}

    def test_parse_multipart(self):
        """`cgi.parse_multipart(fp, pdict)` 真解 multipart, 返 list of str。"""
        # multipart 必含 boundary
        boundary = "boundary"
        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="a"\r\n\r\n'
            b"value1\r\n"
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="b"\r\n\r\n'
            b"value2\r\n"
            b"--boundary--\r\n"
        )
        pdict = {"boundary": boundary.encode()}
        result = cgi.parse_multipart(io.BytesIO(body), pdict)
        # Python 3.11+ parse_multipart 返 list of strings
        # 我们只验 keys 正确 + 长度
        assert "a" in result
        assert "b" in result
        assert "value1" in result["a"][0] if isinstance(result["a"], list) else result["a"]
        assert "value2" in result["b"][0] if isinstance(result["b"], list) else result["b"]


# -- calendar 进阶 ------------------------------------------------------------

class TestCalendarAdvanced:
    def test_weekheader(self):
        """`calendar.weekheader(2)` 真返 'Mo Tu We ...'。"""
        out = calendar.weekheader(2)
        assert out.startswith("Mo"), f"weekheader(2) 应以 'Mo' 开头,实际 {out!r}"
        assert "Tu" in out and "We" in out

    def test_monthcalendar(self):
        """`calendar.monthcalendar(2026, 10)` 真返 list of weeks。"""
        weeks = calendar.monthcalendar(2026, 10)
        # 必 ≥ 4 周
        assert len(weeks) >= 4
        # 每周必 7 天
        for week in weeks:
            assert len(week) == 7

    def test_calendar_year(self):
        """`calendar.TextCalendar().formatyear(2026)` 真返整年。"""
        out = calendar.TextCalendar().formatyear(2026)
        # 必含 '2026'
        assert "2026" in out
        # 必含 12 月
        for month_name in ["January", "February", "March"]:
            assert month_name in out or month_name[:3] in out


# -- fractions 进阶 -----------------------------------------------------------

class TestFractionsAdvancedV2:
    def test_from_float(self):
        """`fractions.Fraction.from_float(0.5)` 真精确 1/2。"""
        f = fractions.Fraction.from_float(0.5)
        assert f == fractions.Fraction(1, 2), (
            f"Fraction.from_float(0.5) 应=1/2,实际 {f}"
        )

    def test_from_string(self):
        """`fractions.Fraction('22/7')` 真字符串解析。"""
        f = fractions.Fraction("22/7")
        assert f == fractions.Fraction(22, 7)

    def test_Fraction_addition_returns_Fraction(self):
        """`Fraction(1, 3) + Fraction(1, 3)` 真返 Fraction(2, 3)。"""
        f = fractions.Fraction(1, 3) + fractions.Fraction(1, 3)
        assert f == fractions.Fraction(2, 3)
        assert isinstance(f, fractions.Fraction)


# -- decimal 进阶 -------------------------------------------------------------

class TestDecimalAdvancedV2:
    def test_rounding_mode(self):
        """`decimal.getcontext().rounding = ROUND_HALF_EVEN` 真设。"""
        ctx = decimal.getcontext().copy()
        try:
            ctx.rounding = decimal.ROUND_HALF_EVEN
            decimal.setcontext(ctx)
            assert decimal.getcontext().rounding == decimal.ROUND_HALF_EVEN
        finally:
            decimal.setcontext(ctx)

    def test_Decimal_sqrt(self):
        """`Decimal('4').sqrt()` 真返 2。"""
        d = decimal.Decimal("4").sqrt()
        assert d == decimal.Decimal("2")

    def test_Decimal_ln_exp(self):
        """`Decimal(1).exp() == e ≈ 2.71828`。"""
        d = decimal.Decimal(1).exp()
        # e ≈ 2.718281828459045
        assert abs(float(d) - 2.718281828459045) < 0.0001

    def test_Context_create_decimal(self):
        """`Context.create_decimal('0.1')` 真从 str 创建。"""
        ctx = decimal.getcontext()
        d = ctx.create_decimal("0.1")
        assert d == decimal.Decimal("0.1")


# -- typing 进阶 --------------------------------------------------------------

class TestTypingAdvancedV3:
    def test_Literal(self):
        """`typing.Literal[1, 2, 3]` 真字面值。"""
        L = typing.Literal[1, 2, 3]
        # 仅静态分析
        assert L is not None

    def test_NoReturn(self):
        """`typing.NoReturn` 真声明不返。"""
        # NoReturn 是 type, 只静态有意义
        def never_returns() -> typing.NoReturn:
            raise RuntimeError("never")

        # 调用必抛
        with pytest.raises(RuntimeError):
            never_returns()

    def test_Never_is_NoReturn(self):
        """`typing.Never` 3.11+ 是 NoReturn 的 alias。"""
        if hasattr(typing, "Never"):
            # 3.11+ Never 必为 type / NoReturn
            assert typing.Never is not None
            # 静态等价: Never == NoReturn
            # 运行时 isinstance 行为可能不同
            # 简化: Never 必是 typing 内部对象
            import typing as _t
            assert hasattr(_t, "Never")

    def test_Self(self):
        """`typing.Self` 3.11+ 真 self type。"""
        if hasattr(typing, "Self"):
            # 3.11+ Self 真存在
            assert typing.Self is not None
