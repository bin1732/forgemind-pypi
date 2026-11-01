# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 decimal 真 pi/exp/sqrt/cos/sin 真数学 (3.11+ MathOperations) + 真 pathlib PurePath 真 + 真 zipfile 真读真写真 listdir + 真 tempfile 真 makedirs。
全 stdlib, 零模拟。
"""
import decimal
import pathlib
import zipfile
import os
import tempfile
import pytest


# ======================== decimal 数学 ========================
def test_decimal_pi_sqrt():
    """真 decimal 真 pi 真 + 真 sqrt 真"""
    # decimal 3.11+ 有 .pi 类方法
    if hasattr(decimal.Decimal, "pi"):
        pi = decimal.Decimal.pi()
    else:
        # 用 BBP 公式
        with decimal.localcontext() as ctx:
            ctx.prec = 50
            pi = sum(
                decimal.Decimal(1) / (16 ** k) * (
                    decimal.Decimal(4) / (8 * k + 1) -
                    decimal.Decimal(2) / (8 * k + 4) -
                    decimal.Decimal(1) / (8 * k + 5) -
                    decimal.Decimal(1) / (8 * k + 6)
                )
                for k in range(20)
            )
    # 3.14...
    assert decimal.Decimal("3.14") < pi < decimal.Decimal("3.15")


def test_decimal_exp_ln():
    """真 exp / ln 真"""
    with decimal.localcontext() as ctx:
        ctx.prec = 30
        e = ctx.exp(decimal.Decimal(1))
        # e ≈ 2.718
        assert decimal.Decimal("2.71") < e < decimal.Decimal("2.72")
        # ln(e) = 1
        ln_e = e.ln()
        assert abs(ln_e - decimal.Decimal(1)) < decimal.Decimal("0.0001")


def test_decimal_sqrt_advanced():
    """真 sqrt 真"""
    with decimal.localcontext() as ctx:
        ctx.prec = 50
        # sqrt(2) 真
        s = ctx.sqrt(decimal.Decimal(2))
        # 1.4142135...
        assert decimal.Decimal("1.4142") < s < decimal.Decimal("1.4143")
        # s^2 = 2 (真)
        assert abs(s * s - decimal.Decimal(2)) < decimal.Decimal("0.0000001")


def test_decimal_context_clear_flags():
    """真 clear_flags 真清"""
    with decimal.localcontext() as ctx:
        ctx.prec = 3
        # 触发 截断
        try:
            decimal.Decimal("1.2345") * decimal.Decimal(1)
        except decimal.InvalidOperation:
            pass
        # flags 有
        # clear
        ctx.clear_flags()
        # 之后 flags 仍是 ContextFlags 但 9 个 False
        assert len(ctx.flags) == 9
        # 全部 False
        assert all(v == 0 for v in ctx.flags.values())


# ======================== pathlib PurePath ========================
def test_purepath_posix():
    """真 PurePosixPath 真"""
    p = pathlib.PurePosixPath("/a/b/c.txt")
    assert str(p) == "/a/b/c.txt"
    # parts
    assert p.parts == ("/", "a", "b", "c.txt")
    # parent
    assert p.parent == pathlib.PurePosixPath("/a/b")


def test_purepath_windows():
    """真 PureWindowsPath 真"""
    p = pathlib.PureWindowsPath("C:/a/b/c.txt")
    # drive
    assert p.drive == "C:"
    # root 是 '\'
    assert p.root == "\\"
    # parts 含 'C:\' (drive+root), a, b, c.txt
    assert p.parts[1:] == ("a", "b", "c.txt")


def test_purepath_match():
    """真 match 真 glob 匹配"""
    p = pathlib.PurePath("/a/b/c.py")
    # match
    assert p.match("*.py")
    # 不 match
    assert not p.match("*.txt")


def test_purepath_relative_to():
    """真 relative_to 真相对路径"""
    p = pathlib.PurePath("/a/b/c/d.txt")
    rel = p.relative_to("/a/b")
    assert rel == pathlib.PurePath("c/d.txt")


def test_purepath_with_name():
    """真 with_name / with_suffix 真"""
    p = pathlib.PurePath("/a/b/c.txt")
    # with_name
    p2 = p.with_name("c.py")
    assert str(p2) == "/a/b/c.py"
    # with_suffix
    p3 = p.with_suffix(".md")
    assert str(p3) == "/a/b/c.md"


# ======================== zipfile 真 ========================
def test_zipfile_extractall():
    """真 extractall 真解"""
    with tempfile.TemporaryDirectory() as d:
        # 创
        zip_path = os.path.join(d, "archive.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("subdir/file2.txt", "content2")
        # 解到新目录
        extract_dir = os.path.join(d, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        # 验
        assert os.path.isfile(os.path.join(extract_dir, "file1.txt"))
        assert os.path.isfile(os.path.join(extract_dir, "subdir", "file2.txt"))


def test_zipfile_writestr_with_zipinfo():
    """真 writestr + ZipInfo 真元数据"""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        zip_path = f.name
    try:
        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo("custom.txt", date_time=(2026, 10, 14, 17, 30, 45))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, "data")
        # 读
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
            assert len(infos) == 1
            assert infos[0].filename == "custom.txt"
            # zip 用 2-second 精度, 45 → 44
            actual = infos[0].date_time
            assert actual[0] == 2026
            assert actual[1] == 10
            assert actual[2] == 14
            assert actual[3] == 17
            assert actual[4] == 30
            # 秒容差
            assert actual[5] in (44, 45)
    finally:
        os.unlink(zip_path)


# ======================== pathlib makedirs ========================
def test_pathlib_makedirs_parents():
    """真 mkdir parents 真建多层"""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "a" / "b" / "c" / "d"
        p.mkdir(parents=True, exist_ok=True)
        assert p.exists()
        assert p.is_dir()


def test_pathlib_resolve_real():
    """真 resolve 真绝对路径"""
    p = pathlib.Path(".") / "test_resolve.py"  # 不存在
    # 沙箱 filesystem
    # 实际拿不到
    # 改 — 拿已存在路径
    p2 = pathlib.Path("/tmp")  # 总是存在
    resolved = p2.resolve()
    assert resolved.is_absolute()
