# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 socket 真 getaddrinfo 真 + 真 socket 真 getnameinfo + 真 decimal 真 + 真 logging 真 basicConfig + 真 tokenize 真 IndentationError 真 + 真 mimetypes 真 mime 真测。
全 stdlib, 零模拟。
"""
import socket
import decimal
import logging
import tokenize
import mimetypes
import io
import pytest


# ======================== socket 真 ========================
def test_socket_getaddrinfo_localhost():
    """真 getaddrinfo localhost 真"""
    results = socket.getaddrinfo("localhost", None)
    # 至少 1 个
    assert len(results) > 0
    # 5-tuple
    for r in results:
        assert len(r) == 5
        # (family, type, proto, canonname, sockaddr)
        family, stype, proto, cname, addr = r
        assert family in (socket.AF_INET, socket.AF_INET6)


def test_socket_getnameinfo():
    """真 getnameinfo 真"""
    # 127.0.0.1:80
    host, port = socket.getnameinfo(("127.0.0.1", 80), socket.NI_NUMERICSERV)
    # host 是 '127.0.0.1' 或 'localhost' (sandbox)
    assert host in ("127.0.0.1", "localhost")
    # port 是 '80'
    assert port == "80"


def test_socket_gethostbyname():
    """真 gethostbyname 真"""
    ip = socket.gethostbyname("localhost")
    # 127.0.0.1 或 ::1
    assert ip == "127.0.0.1" or ip.startswith("::")


def test_socket_gethostname():
    """真 gethostname 真"""
    h = socket.gethostname()
    # 非空
    assert len(h) > 0


# ======================== decimal 真 ========================
def test_decimal_complex_sqrt():
    """真 decimal 真 sqrt 真"""
    with decimal.localcontext() as ctx:
        ctx.prec = 50
        # sqrt(2)
        s = ctx.sqrt(decimal.Decimal(2))
        # 1.4142...
        assert decimal.Decimal("1.4142") < s < decimal.Decimal("1.4143")
        # s^2 应 = 2
        diff = s * s - decimal.Decimal(2)
        # 精度内
        assert abs(diff) < decimal.Decimal("0.0000001")


def test_decimal_log10():
    """真 log10 真"""
    with decimal.localcontext() as ctx:
        ctx.prec = 30
        # log10(100) = 2
        result = decimal.Decimal(100).log10()
        assert abs(result - decimal.Decimal(2)) < decimal.Decimal("0.0001")


def test_decimal_ln_e():
    """真 ln(e) = 1 真"""
    with decimal.localcontext() as ctx:
        ctx.prec = 30
        e = ctx.exp(decimal.Decimal(1))
        # ln(e) = 1
        ln_e = e.ln()
        assert abs(ln_e - decimal.Decimal(1)) < decimal.Decimal("0.0001")


def test_decimal_to_integral_exact():
    """真 to_integral_exact 真不同 rounding"""
    with decimal.localcontext() as ctx:
        # 不同 rounding
        ctx.rounding = decimal.ROUND_HALF_EVEN
        assert decimal.Decimal("2.5").to_integral_value() == 2
        assert decimal.Decimal("3.5").to_integral_value() == 4
        ctx.rounding = decimal.ROUND_HALF_UP
        assert decimal.Decimal("2.5").to_integral_value() == 3


def test_decimal_fma():
    """真 fma 真 fused multiply-add"""
    with decimal.localcontext() as ctx:
        ctx.prec = 20
        # fma(a, b, c) = a * b + c (单 rounding)
        result = ctx.fma(decimal.Decimal("2"), decimal.Decimal("3"), decimal.Decimal("1"))
        # 2*3 + 1 = 7
        assert result == decimal.Decimal("7")


# ======================== logging basicConfig ========================
def test_logging_basicConfig():
    """真 basicConfig 真配"""
    import io
    buf = io.StringIO()
    # 配
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=buf,
        force=True,
    )
    # 配后 log
    test_logger = logging.getLogger("test_basic_config")
    test_logger.info("hello")
    output = buf.getvalue()
    assert "INFO" in output
    assert "hello" in output


def test_logging_basicConfig_no_force():
    """真 basicConfig 配 root logger"""
    import io
    # basicConfig force=True 改 root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=io.StringIO(),
        force=True,
    )
    # root logger level 改 INFO
    assert logging.root.level == logging.INFO
    # 至少 1 个 handler
    assert len(logging.root.handlers) >= 1


# ======================== tokenize 真 ========================
def test_tokenize_IndentationError_mixed_indent():
    """真 mixed indent 真 IndentationError"""
    # 4 空格 + tab
    bad_code = "def f():\n    x = 1\n\t y = 2"
    # 解析 IndentationError
    with pytest.raises((IndentationError, TabError)):
        compile(bad_code, "<test>", "exec")


def test_tokenize_unicode_strings():
    """真 unicode string 真"""
    code = 'msg = "中文字符"'
    tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    # 含 STRING
    assert any(t.type == tokenize.STRING for t in tokens)
    # string content
    strings = [t.string for t in tokens if t.type == tokenize.STRING]
    assert "中文字符" in strings[0]


# ======================== mimetypes 真 ========================
def test_mimetypes_guess_type_url():
    """真 guess_type URL 真"""
    # URL
    mt, encoding = mimetypes.guess_type("https://example.com/index.html")
    assert mt == "text/html"
    # CSS
    mt2, enc2 = mimetypes.guess_type("style.css")
    assert mt2 == "text/css"
    # JS
    mt3, enc3 = mimetypes.guess_type("script.js")
    assert mt3 in ("application/javascript", "text/javascript")


def test_mimetypes_guess_extension():
    """真 guess_extension 真"""
    # 已知 type
    ext = mimetypes.guess_extension("image/png")
    assert ext == ".png"
    # unknown
    ext2 = mimetypes.guess_extension("application/x-unknown-type-xyz")
    assert ext2 is None
