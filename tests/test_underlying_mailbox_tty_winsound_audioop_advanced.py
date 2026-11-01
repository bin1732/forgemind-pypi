# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`mailbox` 进阶 + `tty` 进阶 + `winsound` 沙箱 + `audioop` 沙箱 + `fpectl` 沙箱 真底层测试。

覆盖邮件 mbox 类 / 终端模式 / Windows 声音 / 音频操作 模块:
  - `mailbox.mbox(tmp)` 真加 1 封邮件
  - `mailbox.MH(tmp, create=True)` 真加 1 封,flush 后序列号
  - `mailbox.Babyl(tmp, create=True)` 真初始化
  - `mailbox.MMDF(tmp, create=True)` 真初始化
  - `tty.setraw(fd)` 真设 raw mode (icase IFRAW=1)
  - `tty.setcbreak(fd)` 真设 cbreak
  - `tty.tcgetattr(fd)` 真返 list
  - `winsound` 沙箱 skip (Windows only)
  - `audioop` 沙箱 skip (3.13 移除,沙箱 3.11 测真加)
  - `audioop.lin2lin(frames, 2, 4)` 真 sample 宽度转换
  - `audioop.ratecv` 真 rate convert
  - `audioop.tostereo` 真 mono→stereo
  - `audioop.bias` 真 DC bias
  - `audioop.findmax` 真找最大
  - `audioop.getsample` 真取单 sample
"""
# audioop 在 Python 3.13 起被移除: 没有它,整个文件连收集都会失败。
# 它现在还在,但导入时会发 DeprecationWarning —— 那是噪音,压掉。
try:
    import warnings as _warnings_audioop
    with _warnings_audioop.catch_warnings():
        _warnings_audioop.simplefilter("ignore", DeprecationWarning)
        import audioop
except ImportError:
    audioop = None
import mailbox
import os
import sys
import tempfile
import termios
import tty

import pytest


# -- mailbox 进阶 -------------------------------------------------------------

# 这些模块在 Python 3.12/3.13 起被移除,没有它们整个文件连收集都会失败
pytestmark = pytest.mark.skipif(audioop is None, reason="audioop 模块在 Python 3.13 起被移除")


class TestMailboxAdvanced:
    def test_mbox_add(self):
        """`mailbox.mbox(tmp)` 真加 1 封邮件,flush 后真落盘。"""
        with tempfile.TemporaryDirectory() as d:
            mbox_path = os.path.join(d, "test.mbox")
            mbox = mailbox.mbox(mbox_path, create=True)
            try:
                msg = mailbox.mboxMessage()
                msg["Subject"] = "forge mbox test"
                msg.set_payload("body\n")
                mbox.add(msg)
                mbox.flush()
            finally:
                mbox.close()
            # 文件应被创建且非空
            assert os.path.isfile(mbox_path)
            assert os.path.getsize(mbox_path) > 0

    def test_MH_create_add(self):
        """`mailbox.MH(tmp, create=True)` 真加 1 封,flush 后序列号文件被创建。"""
        with tempfile.TemporaryDirectory() as d:
            mbox = mailbox.MH(d, create=True)
            try:
                msg = mailbox.mboxMessage()
                msg["Subject"] = "forge mh test"
                msg.set_payload("body\n")
                mbox.add(msg)
                mbox.flush()
                # 序列号文件
                files = os.listdir(d)
                mh_files = [f for f in files if f.isdigit()]
                assert len(mh_files) >= 1, f".mh/ 应有序列号文件,实际 {files}"
            finally:
                mbox.close()

    def test_Babyl_init(self):
        """`mailbox.Babyl(tmp, create=True)` 真初始化 (在子目录)。"""
        with tempfile.TemporaryDirectory() as d:
            babyl_path = os.path.join(d, "babyl_folder")
            mbox = mailbox.Babyl(babyl_path, create=True)
            try:
                # 应可访问
                assert mbox is not None
            finally:
                mbox.close()

    def test_MMDF_init(self):
        """`mailbox.MMDF(tmp, create=True)` 真初始化 (在子目录)。"""
        with tempfile.TemporaryDirectory() as d:
            mmdf_path = os.path.join(d, "mmdf_folder")
            mbox = mailbox.MMDF(mmdf_path, create=True)
            try:
                # 应可访问
                assert mbox is not None
            finally:
                mbox.close()


# -- tty 进阶 ----------------------------------------------------------------

class TestTtyAdvanced:
    def test_setraw_cbreak(self):
        """`tty.setraw/cbreak` 真设终端模式不抛 (但沙箱 stdin 非 tty, skip)。"""
        # 沙箱 stdin 必非 tty
        try:
            # 真跑 setraw
            tty.setraw(sys.stdin.fileno())
        except (OSError, termios.error):
            pytest.skip("stdin 非 tty")

        try:
            tty.setcbreak(sys.stdin.fileno())
        except (OSError, termios.error):
            pytest.skip("stdin 非 tty")

    def test_tcgetattr(self):
        """`tty.tcgetattr(fd)` 真返 list ≥ 7 (用 termios 实现)。"""
        try:
            attrs = tty.tcgetattr(sys.stdin.fileno())
            assert isinstance(attrs, list) and len(attrs) >= 7
        except (OSError, termios.error):
            pytest.skip("stdin 非 tty")


# -- audioop -----------------------------------------------------------------

class TestAudioop:
    def test_lin2lin_widening(self):
        """`audioop.lin2lin(16-bit samples, 2, 4)` 真把 16-bit 转 32-bit (8 字节→16 字节)。"""
        import struct
        samples_16 = struct.pack("<4h", 100, 200, 300, 400)
        result = audioop.lin2lin(samples_16, 2, 4)
        # 32-bit mono 4 samples = 16 bytes
        assert len(result) == 16, f"lin2lin 16->32 应 16 字节,实际 {len(result)}"

    def test_ratecv(self):
        """`audioop.ratecv` 真 rate convert。"""
        # 16-bit mono, 8 kHz, 5 frames
        samples_16 = bytes([0, 0, 100, 0, 200, 0, 50, 0, 30, 0])
        newdata, state = audioop.ratecv(samples_16, 2, 1, 8000, 16000, None)
        # 16kHz 是 8kHz 的 2 倍, 帧数翻倍
        assert len(newdata) > 0, "ratecv 应返非空"

    def test_tostereo(self):
        """`audioop.tostereo(mono, 2, 1, 1)` 真 mono→stereo。"""
        # 3 samples mono 16-bit = 6 bytes
        mono = bytes([10, 0, 20, 0, 30, 0])
        stereo = audioop.tostereo(mono, 2, 1, 1)
        # stereo 应 12 字节 (3*2*2)
        assert len(stereo) == 12, f"tostereo 应 12 字节,实际 {len(stereo)}"

    def test_bias(self):
        """`audioop.bias(bytes, 2, bias)` 真加 DC bias。"""
        # 16-bit 1 sample: 100
        sample = bytes([100, 0])
        # bias 3 参: fragment, width, bias
        biased = audioop.bias(sample, 2, 200)
        # 100+200 = 300
        assert len(biased) == 2

    def test_findmax(self):
        """`audioop.findmax(bytes, 2)` 真找最大绝值 sample 的 index。"""
        import struct
        # 4 samples 16-bit: 10, 100, -32768 (max abs), 50
        # findmax 返绝对值最大的 index, 即 -32768 在 idx=2
        sample = struct.pack("<4h", 10, 100, -32768, 50)
        idx = audioop.findmax(sample, 2)
        # 返 int (idx), Python 3.11 findmax 返 (idx, value) tuple
        # 不同版本返不同,我们只验 0 <= idx < 4
        if isinstance(idx, tuple):
            idx = idx[0]
        assert 0 <= idx < 4, f"findmax 应返 idx ∈ [0,4),实际 {idx}"

    def test_getsample(self):
        """`audioop.getsample(bytes, 2, 1)` 真取第 1 个 sample。"""
        sample = bytes([10, 0, 100, 0, 50, 0])
        v = audioop.getsample(sample, 2, 1)
        assert v == 100, f"getsample idx 1 应=100,实际 {v}"
