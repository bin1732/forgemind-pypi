# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 tempfile 进阶 (SpooledTemporaryFile / TemporaryDirectory 真) + 真 zlib 进阶 (compressobj 真 链) + 真 copy 进阶 (replace 真) + 真 base64 进阶 (b85) + 真 asyncio 真 (TimeoutError 真) + 真 binascii 真.
全 stdlib, 零模拟。
"""
import tempfile
import zlib
import copy
import base64
import asyncio
import binascii
import os
import pytest


# ======================== tempfile 进阶 ========================
def test_tempfile_SpooledTemporaryFile():
    """真 SpooledTemporaryFile 进阶"""
    # max_size=100 (超过就 roll to disk)
    with tempfile.SpooledTemporaryFile(max_size=100) as f:
        # 写 < 100
        f.write(b"small")
        # 读
        f.seek(0)
        assert f.read() == b"small"
        # 写 > 100 (应 roll to disk)
        f.seek(0, 2)  # end
        f.write(b"x" * 200)
        # read
        f.seek(0)
        data = f.read()
        # 必有 hello + 200x
        assert b"small" in data
        assert b"x" * 200 in data


def test_tempfile_TemporaryDirectory_real():
    """真 TemporaryDirectory 真清理"""
    with tempfile.TemporaryDirectory() as d:
        # 在 dir 中创 file
        f_path = os.path.join(d, "test.txt")
        with open(f_path, "w") as f:
            f.write("data")
        # 必在
        assert os.path.exists(f_path)
    # 退出后, dir 清理
    assert not os.path.exists(d)


# ======================== zlib 进阶 ========================
def test_zlib_compressobj_chain():
    """真 compressobj 真链"""
    co = zlib.compressobj(level=6)
    # 分段
    p1 = co.compress(b"hello ")
    p2 = co.compress(b"world")
    p3 = co.flush()
    # 拼
    compressed = p1 + p2 + p3
    # 解
    decompressed = zlib.decompress(compressed)
    assert decompressed == b"hello world"


def test_zlib_wbits():
    """真 wbits 真"""
    # wbits=15 (max) + 32 (gzip) = 47
    data = b"hello world"
    compressed = zlib.compress(data, level=6, wbits=15)
    # decompress
    decompressed = zlib.decompress(compressed, wbits=15)
    assert decompressed == data


def test_zlib_compressobj_decompressobj():
    """真 compressobj + decompressobj 真链"""
    co = zlib.compressobj()
    compressed = co.compress(b"foo") + co.flush()
    # 链 decompress
    do = zlib.decompressobj()
    decompressed = do.decompress(compressed) + do.flush()
    assert decompressed == b"foo"


# ======================== copy 进阶 ========================
def test_copy_replace():
    """真 copy.replace 真"""
    # Python 3.13+ 新增
    if hasattr(copy, "replace"):
        result = copy.replace(1, 2)
        assert result == 2
    else:
        # fallback 测试深 copy
        data = [1, 2, 3]
        copied = copy.deepcopy(data)
        assert copied == data
        assert copied is not data


# ======================== base64 进阶 ========================
def test_base64_b85encode():
    """真 b85encode 真"""
    data = b"hello"
    encoded = base64.b85encode(data)
    # round-trip
    decoded = base64.b85decode(encoded)
    assert decoded == data


def test_base64_a85encode():
    """真 a85encode 真"""
    data = b"hello"
    encoded = base64.a85encode(data)
    # round-trip
    decoded = base64.a85decode(encoded)
    assert decoded == data


# ======================== asyncio 进阶 ========================
def test_asyncio_TimeoutError():
    """真 asyncio TimeoutError 真"""
    async def main():
        try:
            # 等待 10s
            await asyncio.wait_for(asyncio.sleep(10), timeout=0.05)
        except asyncio.TimeoutError:
            return "timeout"
        return "no timeout"

    result = asyncio.run(main())
    assert result == "timeout"


def test_asyncio_gather_results():
    """真 gather 真 results"""
    async def main():
        async def task(x):
            return x * 2

        results = await asyncio.gather(task(1), task(2), task(3))
        assert results == [2, 4, 6]

    asyncio.run(main())


def test_asyncio_wait_completed():
    """真 wait 真"""
    async def main():
        tasks = [asyncio.create_task(asyncio.sleep(0.01)) for _ in range(3)]
        done, pending = await asyncio.wait(tasks, timeout=1.0)
        # 3 done
        assert len(done) == 3
        assert len(pending) == 0

    asyncio.run(main())


# ======================== binascii 进阶 ========================
def test_binascii_hexlify_unhexlify():
    """真 hexlify/unhexlify 真 round-trip"""
    data = b"\x00\x01\x02\xff"
    hex_str = binascii.hexlify(data)
    # 000102ff
    assert hex_str == b"000102ff"
    # unhexlify
    decoded = binascii.unhexlify(hex_str)
    assert decoded == data


def test_binascii_crc32():
    """真 binascii.crc32 真"""
    c = binascii.crc32(b"hello")
    # 必 ≥ 0
    assert 0 <= c < 0x100000000


def test_binascii_a2b_uu_b2a_uu():
    """真 a2b_uu / b2a_uu 真 round-trip"""
    data = b"hello"
    encoded = binascii.b2a_uu(data)
    # 必以 newline 结尾
    assert encoded.endswith(b"\n")
    decoded = binascii.a2b_uu(encoded)
    assert decoded == data
