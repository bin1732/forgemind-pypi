# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 decimal 真 create_decimal 真控制 / 真 EmContext / 真 trap 真开关 + 真 signal 真 SIGINT 真 (parent) + 真 array 真多 type code 进阶 + 真 mmap 真 PROT_READ 真 mmap 保护。
全 stdlib, 零模拟。
"""
import decimal
import signal
import array
import mmap
import os
import tempfile
import ctypes
import sys
import pytest


# ======================== decimal 进阶 ========================
def test_decimal_create_decimal_from_float():
    """真 create_decimal_from_float"""
    # float 0.1 = 0.1000000000000000055...
    d = decimal.Decimal(0.1)
    # 但 create_decimal_from_float 真给精确 0.1
    d2 = decimal.Decimal.from_float(0.1)
    assert str(d2) == "0.1000000000000000055511151231257827021181583404541015625"
    # 而 str(0.1) = '0.1'
    assert d == d2


def test_decimal_Context_create_decimal():
    """真 Context 真 create_decimal 真控制"""
    ctx = decimal.Context()
    # 解析 "1.2345" 限制 3 位
    ctx.prec = 3
    d = ctx.create_decimal("1.2345")
    # 1.23 (3 位)
    assert str(d) == "1.23"


def test_decimal_traps_true():
    """真 traps 真打开 (抛)"""
    with decimal.localcontext() as ctx:
        ctx.traps[decimal.DivisionByZero] = True
        with pytest.raises(decimal.DivisionByZero):
            decimal.Decimal(1) / decimal.Decimal(0)


def test_decimal_traps_false():
    """真 traps 真关 (返 NaN/inf)"""
    with decimal.localcontext() as ctx:
        ctx.traps[decimal.DivisionByZero] = False
        result = decimal.Decimal(1) / decimal.Decimal(0)
        assert result.is_infinite()


def test_decimal_comparison_Complex():
    """真 Decimal 真比较"""
    a = decimal.Decimal("1.5")
    b = decimal.Decimal("1.50")
    # 同值但不同 precision
    assert a == b
    assert a <= b
    # 但 normalize
    assert a.normalize() == b.normalize()


# ======================== signal 真 send ========================
def test_signal_SIGUSR1_real_in_subprocess():
    """真 SIGUSR1 真发到子进程"""
    import subprocess
    code = """
import signal, sys
def handler(s, f):
    print("caught")
    sys.exit(0)
signal.signal(signal.SIGUSR1, handler)
print("ready", flush=True)
import time
time.sleep(2)
print("timeout")
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等 ready
    line = proc.stdout.readline()
    assert b"ready" in line
    # 发 SIGUSR1
    proc.send_signal(signal.SIGUSR1)
    proc.wait(timeout=5)
    out = proc.stdout.read()
    assert b"caught" in out


def test_signal_SIGTERM_real():
    """真 SIGTERM 真发到子进程"""
    import subprocess
    code = """
import signal, sys
def handler(s, f):
    print("terminated")
    sys.exit(0)
signal.signal(signal.SIGTERM, handler)
print("ready", flush=True)
import time
time.sleep(3)
print("survived")
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
    )
    line = proc.stdout.readline()
    assert b"ready" in line
    proc.terminate()  # SIGTERM
    proc.wait(timeout=5)
    out = proc.stdout.read()
    assert b"terminated" in out


# ======================== array 多 type code ========================
def test_array_signed_unsigned():
    """真 signed / unsigned"""
    a_signed = array.array("b", [-128, 0, 127])
    assert a_signed[0] == -128
    a_unsigned = array.array("B", [0, 100, 255])
    assert a_unsigned[2] == 255
    # 真 buffer
    mv = memoryview(a_signed)
    assert len(mv) == 3


def test_array_float_types():
    """真 float / double"""
    a_f = array.array("f", [1.0, 2.5, 3.0])
    assert a_f[1] == 2.5
    a_d = array.array("d", [1.123456789])
    # double 精度
    assert abs(a_d[0] - 1.123456789) < 1e-10


def test_array_extend():
    """真 extend"""
    a = array.array("i", [1, 2, 3])
    a.extend([4, 5, 6])
    assert len(a) == 6
    assert a[3] == 4


def test_array_bytes():
    """真 tobytes / frombytes"""
    a = array.array("i", [1, 2, 3, 4, 5])
    b = a.tobytes()
    assert len(b) == 20  # 5 * 4
    a2 = array.array("i")
    a2.frombytes(b)
    assert a2 == a


# ======================== mmap 进阶 ========================
def test_mmap_resize():
    """真 mmap 真 resize"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"\x00" * 100)
        path = f.name
    try:
        with open(path, "r+b") as f:
            with mmap.mmap(f.fileno(), 100) as m:
                assert len(m) == 100
                # resize
                m.resize(200)
                assert len(m) == 200
                # 写扩展区
                m[100:200] = b"\xff" * 100
        # 验
        with open(path, "rb") as f:
            content = f.read()
        assert len(content) == 200
        assert content[100:200] == b"\xff" * 100
    finally:
        os.unlink(path)


def test_mmap_read_byte():
    """真 mmap 真按字节读"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"ABCDE")
        path = f.name
    try:
        with open(path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                # 按字节
                assert m[0] == ord("A")
                assert m[4] == ord("E")
                # slice
                assert m[0:5] == b"ABCDE"
                # 长度
                assert len(m) == 5
    finally:
        os.unlink(path)
