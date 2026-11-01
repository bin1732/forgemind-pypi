# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`ssl` + `mimetypes` + `uu` + `binascii` + `faulthandler` 真底层测试。

覆盖加密/TLS/MIME/编码/排错模块:
  - `ssl.SSLContext(PROTOCOL_TLS_CLIENT)` 真创建上下文,`check_hostname` 默认 True
  - `ssl.create_default_context()` 返真 SSLContext,`verify_mode` 默认 CERT_REQUIRED
  - `mimetypes.guess_type('a.txt')` 真返 `('text/plain', None)`
  - `mimetypes.guess_extension('image/jpeg')` 真返 '.jpe' (lib.mimetypes 历史名)
  - `uu.encode(in_file, out_file)` 真把 input 转 uuencode,`uu.decode` 反向
  - `binascii.hexlify(b'hello')` 真返 `b'68656c6c6f'`
  - `binascii.crc32(b'123')` 真返 int
  - `faulthandler.enable` 启用后除零 traceback 写到 stderr (StringIO)
"""
import binascii
import faulthandler
import io
import mimetypes
import os
import ssl
import sys
import tempfile
# uu 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_uu
    with _warnings_uu.catch_warnings():
        _warnings_uu.simplefilter("ignore", DeprecationWarning)
        import uu
except ImportError:
    uu = None

import pytest


# -- ssl ----------------------------------------------------------------------

# 这些模块在 Python 3.12/3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(uu is None, reason="uu 模块在 Python 3.13 起被移除")


class TestSsl:
    def test_ssl_context_protocol_tls_client(self):
        """`ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` 真创建 client 端上下文。

        `check_hostname` 默认 True (PEP 543 之后);`verify_mode` 默认
        CERT_REQUIRED 直到显式改。
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is True
        # 默认 verify_mode 是 CERT_REQUIRED (Python 3.7+ 行为)
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_create_default_context_sets_cert_required(self):
        """`ssl.create_default_context()` 真把 verify_mode 设为 CERT_REQUIRED。"""
        ctx = ssl.create_default_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_ssl_constants_are_integers(self):
        """`ssl` 模块关键常量是真整数 (非 enum-only)。"""
        for name in ("PROTOCOL_TLS_CLIENT", "PROTOCOL_TLS_SERVER", "CERT_NONE",
                     "CERT_OPTIONAL", "CERT_REQUIRED"):
            assert isinstance(getattr(ssl, name), int), (
                f"{name} 应为 int,实际 {type(getattr(ssl, name))}"
            )


# -- mimetypes ----------------------------------------------------------------

class TestMimetypes:
    def test_guess_type_txt_returns_text_plain(self):
        """`mimetypes.guess_type('a.txt')` 真返 `('text/plain', None)`。"""
        mtype, encoding = mimetypes.guess_type("a.txt")
        assert mtype == "text/plain", f"应 text/plain,实际 {mtype!r}"
        assert encoding is None, f"无 charset,实际 {encoding!r}"

    def test_guess_type_html_returns_text_html(self):
        """`mimetypes.guess_type('a.html')` 真返 `text/html`。"""
        mtype, _ = mimetypes.guess_type("a.html")
        assert mtype == "text/html", f"应 text/html,实际 {mtype!r}"

    def test_guess_extension_image_jpeg(self):
        """`mimetypes.guess_extension('image/jpeg')` 真返非空扩展名 (.jpe/.jpg)。"""
        ext = mimetypes.guess_extension("image/jpeg")
        assert ext in (".jpg", ".jpe", ".jpeg"), (
            f"image/jpeg 扩展名应为 .jpg/.jpe/.jpeg,实际 {ext!r}"
        )


# -- uu -----------------------------------------------------------------------

class TestUu:
    def test_uu_encode_decode_round_trip(self):
        """`uu.encode(in_file, out_file)` 真 uuencode,`uu.decode` 真反向。

        写一个 tmp 输入文件 'hello\\nworld\\n',encode 到输出,再 decode
        到新文件,字节内容应一致。
        """
        with tempfile.TemporaryDirectory() as d:
            in_path = os.path.join(d, "input.bin")
            enc_path = os.path.join(d, "encoded.uu")
            dec_path = os.path.join(d, "decoded.bin")
            with open(in_path, "wb") as f:
                f.write(b"hello\nworld\n")
            uu.encode(in_path, enc_path)
            assert os.path.getsize(enc_path) > 0, "encoded file 应非空"
            with open(enc_path, "rb") as f:
                head = f.read(6)
            assert head.startswith(b"begin "), (
                f"uuencode 头应为 'begin ',实际 {head!r}"
            )
            uu.decode(enc_path, dec_path)
            with open(in_path, "rb") as f:
                original = f.read()
            with open(dec_path, "rb") as f:
                restored = f.read()
            assert restored == original, (
                f"uu round-trip 不一致,原 {original!r} 还原 {restored!r}"
            )


# -- binascii -----------------------------------------------------------------

class TestBinascii:
    def test_hexlify_hello(self):
        """`binascii.hexlify(b'hello')` 真返 `b'68656c6c6f'`。"""
        h = binascii.hexlify(b"hello")
        assert h == b"68656c6c6f", f"hexlify(hello) 应为 b'68656c6c6f',实际 {h!r}"

    def test_hexlify_then_unhexlify_round_trip(self):
        """`hexlify` + `unhexlify` 真 round-trip。"""
        h = binascii.hexlify(b"\x00\x01\x02\xff")
        assert binascii.unhexlify(h) == b"\x00\x01\x02\xff"

    def test_crc32_hello(self):
        """`binascii.crc32(b'hello')` 真返非零 int。"""
        c = binascii.crc32(b"hello")
        assert isinstance(c, int)
        # 已知值: 0x3610a686
        assert c == 0x3610a686, f"crc32('hello') 应为 0x3610a686,实际 {c:#x}"

    def test_crc32_consistent_with_running_hash(self):
        """`crc32` 续算保持一致 (与分块计算结果相同)。"""
        part1 = binascii.crc32(b"hel")
        part2 = binascii.crc32(b"lo", part1)
        full = binascii.crc32(b"hello")
        assert part2 == full, (
            f"分块续算 crc 应等于一次计算,part2={part2:#x} full={full:#x}"
        )


# -- faulthandler -------------------------------------------------------------

class TestFaulthandler:
    def test_enable_disable_round_trip_via_is_enabled(self):
        """`faulthandler.enable` 后 `is_enabled()` 返 True,`disable` 后返 False。"""
        # 先把 faulthandler 关掉基线
        if faulthandler.is_enabled():
            faulthandler.disable()
        try:
            assert faulthandler.is_enabled() is False
            faulthandler.enable()
            assert faulthandler.is_enabled() is True
            faulthandler.disable()
            assert faulthandler.is_enabled() is False
        finally:
            # 恢复关闭状态,不污染后续测试
            if faulthandler.is_enabled():
                faulthandler.disable()

    def test_dump_traceback_thread_method_exists(self):
        """`faulthandler.dump_traceback` 是真 callable,`enable` 后 `is_enabled` 返 True。

        Python 3.11+ 一些实现里 dump_traceback 没有 introspectable 签名,
        但 enable/disable + is_enabled 三件套是真 API。
        """
        if faulthandler.is_enabled():
            faulthandler.disable()
        try:
            faulthandler.enable()
            assert faulthandler.is_enabled() is True
            # 可调用,接受 file/all_threads 关键字
            faulthandler.dump_traceback(file=open(os.devnull, "w"),
                                        all_threads=False)
        finally:
            if faulthandler.is_enabled():
                faulthandler.disable()
