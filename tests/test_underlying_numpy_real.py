# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 numpy: 真算、真 BLAS、真数组、真线性代数、真 random、真字节序。
"""
import os
import sys
import time
import struct
import pytest
import tempfile
import subprocess

import numpy as np


def test_numpy_create_zero_and_ones():
    z = np.zeros((3, 4))
    assert z.shape == (3, 4)
    assert z.dtype == np.float64
    assert (z == 0).all()
    assert z.flags.c_contiguous

    o = np.ones((2, 3), dtype=np.int32)
    assert o.dtype == np.int32
    assert o.sum() == 6

    e = np.empty((2, 2))
    assert e.shape == (2, 2)


def test_numpy_arange_linspace():
    a = np.arange(10)
    assert a.tolist() == list(range(10))

    ls = np.linspace(0, 1, 5)
    assert ls[0] == 0.0
    assert ls[-1] == 1.0
    assert len(ls) == 5
    assert abs(ls[2] - 0.5) < 1e-9


def test_numpy_ufunc_real_c():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 20.0, 30.0, 40.0])
    assert (a + b).tolist() == [11, 22, 33, 44]
    assert (a * b).tolist() == [10, 40, 90, 160]
    assert abs(np.sin(np.pi / 2) - 1.0) < 1e-10
    assert abs(np.exp(0) - 1) < 1e-10
    assert np.sqrt(4) == 2.0


def test_numpy_dot_matmul():
    a = np.array([[1, 2], [3, 4]], dtype=np.float64)
    b = np.array([[5, 6], [7, 8]], dtype=np.float64)
    assert (a @ b).tolist() == [[19, 22], [43, 50]]
    v = np.array([1, 2, 3], dtype=np.float64)
    w = np.array([4, 5, 6], dtype=np.float64)
    assert np.dot(v, w) == 32

    big = np.random.RandomState(42).randn(256, 256)
    start = time.time()
    result = big @ big
    elapsed = time.time() - start
    assert result.shape == (256, 256)
    assert elapsed < 10


def test_numpy_broadcasting():
    a = np.array([[1], [2], [3]])
    b = np.array([10, 20, 30])
    result = a + b
    expected = np.array([[11, 21, 31], [12, 22, 32], [13, 23, 33]])
    assert np.array_equal(result, expected)


def test_numpy_indexing_slicing():
    a = np.arange(20).reshape(4, 5)
    assert a[1, 2] == 7
    assert a[0].tolist() == [0, 1, 2, 3, 4]
    assert a[:, 0].tolist() == [0, 5, 10, 15]
    assert a[1:3, 2:4].tolist() == [[7, 8], [12, 13]]

    a2 = np.array([1, 2, 3, 4, 5])
    mask = a2 > 3
    assert mask.tolist() == [False, False, False, True, True]
    assert a2[mask].tolist() == [4, 5]


def test_numpy_linalg_inv_det():
    a = np.array([[1.0, 2.0], [3.0, 5.0]], dtype=np.float64)
    inv = np.linalg.inv(a)
    assert np.allclose(a @ inv, np.eye(2), atol=1e-10)
    det = np.linalg.det(a)
    assert abs(det - (-1)) < 1e-10


def test_numpy_fft_real():
    n = 1024
    t = np.arange(n) / n
    sig = np.sin(2 * np.pi * 1 * t)
    fft = np.fft.fft(sig)
    magnitudes = np.abs(fft[:n//2])
    peak_bin = np.argmax(magnitudes[1:]) + 1
    assert peak_bin == 1


def test_numpy_random_real():
    rng = np.random.default_rng(42)
    s = rng.integers(0, 100, size=1000)
    assert len(s) == 1000
    assert s.min() >= 0
    assert s.max() < 100
    rng2 = np.random.default_rng(42)
    s2 = rng2.integers(0, 100, size=1000)
    assert np.array_equal(s, s2)


def test_numpy_byteswap_endian():
    a = np.array([1, 2, 3, 4], dtype=np.int32)
    raw_native = a.tobytes()
    a_swapped = a.byteswap()
    raw_swapped = a_swapped.tobytes()
    if sys.byteorder == "little":
        assert raw_native[0:4] == struct.pack("<I", 1)
        assert raw_swapped[0:4] == struct.pack(">I", 1)


def test_numpy_save_load_npy():
    a = np.arange(100, dtype=np.float64).reshape(10, 10)
    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as f:
        path = f.name
    try:
        np.save(path, a)
        loaded = np.load(path)
        assert np.array_equal(a, loaded)
    finally:
        os.unlink(path)


def test_numpy_memmap_large_file():
    arr = np.arange(100_000, dtype=np.float64)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        path = f.name
    try:
        arr.tofile(path)
        mm = np.memmap(path, dtype=np.float64, mode="r", shape=(100_000,))
        assert mm.sum() == arr.sum()
        del mm
    finally:
        os.unlink(path)


def test_numpy_strides_negative():
    a = np.arange(10)
    rev = a[::-1]
    assert rev.tolist() == list(range(9, -1, -1))
    assert np.shares_memory(a, rev)
    a[0] = 99
    assert rev[-1] == 99


def test_numpy_concatenate_stack():
    a = np.array([1, 2, 3])
    b = np.array([4, 5, 6])
    assert np.concatenate([a, b]).tolist() == [1, 2, 3, 4, 5, 6]
    s = np.stack([a, b])
    assert s.shape == (2, 3)


def test_numpy_where_unique():
    a = np.array([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5])
    idx = np.where(a > 3)
    assert (a[idx] > 3).all()
    u = np.unique(a)
    assert u.tolist() == sorted(set(a.tolist()))


def test_numpy_subprocess_real_blas():
    code = "import numpy as np; a = np.random.RandomState(0).randn(64, 64); b = a @ a; print('DIAG', b[0,0])"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "DIAG" in result.stdout
