# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 email 真 build / parse + 真 mimetypes 真 type 推断 + 真 uu + 真 base64 真 encode/decode + 真 quopri。
全 stdlib, 零模拟。
"""
import email
import email.message
import mimetypes
# uu 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_uu
    with _warnings_uu.catch_warnings():
        _warnings_uu.simplefilter("ignore", DeprecationWarning)
        import uu
except ImportError:
    uu = None
import base64
import quopri
import io
import os
import tempfile
import pytest


# ======================== email ========================
# 这些模块在 Python 3.12/3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(uu is None, reason="uu 模块在 Python 3.13 起被移除")


def test_email_build_simple():
    """真 email 真 build 简单邮件"""
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg.set_content("Hello, this is the body.\nLine 2.")
    # serialize
    s = msg.as_string()
    assert "Subject: Test" in s
    assert "From: alice@example.com" in s
    assert "Hello, this is the body." in s


def test_email_parse_simple():
    """真 email 真 parse 邮件"""
    raw = """From: alice@example.com
To: bob@example.com
Subject: Test

Hello body.
"""
    msg = email.message_from_string(raw)
    assert msg["From"] == "alice@example.com"
    assert msg["Subject"] == "Test"
    # 提取 body
    body = msg.get_payload()
    assert "Hello body." in body


def test_email_multipart():
    """真 multipart 真多 part"""
    msg = email.message.EmailMessage()
    msg["Subject"] = "Multipart"
    msg.set_content("Plain text body")
    msg.add_alternative("<p>HTML body</p>", subtype="html")
    # 序列化
    s = msg.as_string()
    # 含 multipart
    assert "multipart/alternative" in s
    assert "Plain text body" in s
    assert "<p>HTML body</p>" in s


# ======================== mimetypes ========================
def test_mimetypes_guess():
    """真 guess_type"""
    # 已知
    assert mimetypes.guess_type("test.html") == ("text/html", None)
    assert mimetypes.guess_type("image.png") == ("image/png", None)
    assert mimetypes.guess_type("doc.pdf") == ("application/pdf", None)
    # 未知
    assert mimetypes.guess_type("foo.xyz_unknown_ext") == (None, None)


def test_mimetypes_guess_all():
    """真 guess_all_extensions"""
    # text/html → ['.html', '.htm']
    exts = mimetypes.guess_all_extensions("text/html")
    assert ".html" in exts
    assert ".htm" in exts


def test_mimetypes_add_custom():
    """真 add_type 临时加"""
    mimetypes.add_type("application/vnd.custom", ".cust")
    assert mimetypes.guess_type("file.cust")[0] == "application/vnd.custom"


# ======================== base64 ========================
def test_base64_encode_decode():
    """真 base64 真 round-trip"""
    data = b"Hello, World! " * 100
    encoded = base64.b64encode(data)
    decoded = base64.b64decode(encoded)
    assert decoded == data


def test_base64_urlsafe():
    """真 urlsafe base64"""
    data = b"\xfb\xff\xfe\x00\xff"
    encoded = base64.urlsafe_b64encode(data)
    # 不含 + /
    assert b"+" not in encoded
    assert b"/" not in encoded
    # round-trip
    assert base64.urlsafe_b64decode(encoded) == data


def test_base64_b32_hex():
    """真 base32 / base16"""
    data = b"Hello"
    # base32
    encoded32 = base64.b32encode(data)
    assert base64.b32decode(encoded32) == data
    # base16 (hex)
    encoded16 = base64.b16encode(data)
    assert base64.b16decode(encoded16) == data


# ======================== quopri ========================
def test_quopri_encode_decode():
    """真 quoted-printable 真编码"""
    data = b"Hello, World!"
    encoded = quopri.encodestring(data)
    # round-trip
    decoded = quopri.decodestring(encoded)
    assert decoded == data


# ======================== uu ========================
def test_uu_roundtrip():
    """真 uu 真编码 round-trip"""
    with tempfile.TemporaryDirectory() as d:
        # 原文件
        original_path = os.path.join(d, "original.txt")
        with open(original_path, "wb") as f:
            f.write(b"Hello, World! " * 50)
        # 编码
        encoded_path = os.path.join(d, "encoded.uu")
        uu.encode(original_path, encoded_path)
        # 解码
        decoded_path = os.path.join(d, "decoded.txt")
        uu.decode(encoded_path, decoded_path)
        # 验证
        with open(decoded_path, "rb") as f:
            assert f.read() == b"Hello, World! " * 50
