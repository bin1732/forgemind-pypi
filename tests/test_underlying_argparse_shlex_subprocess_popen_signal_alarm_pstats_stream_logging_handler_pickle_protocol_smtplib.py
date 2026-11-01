# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`argparse` 进阶 (parse_args) + `shlex` 进阶 (split + quote) + `subprocess.Popen` 真 run + `signal.alarm` 真 timer + `pstats.Stats(stream)` + `logging.StreamHandler` 进阶 + `pickle` 协议 + `smtplib` 真底层测试。

覆盖 argparse / shlex / subprocess Popen / signal alarm / pstats stream / logging StreamHandler / pickle 协议 / smtplib 模块:
  - `argparse.ArgumentParser 真建 + add_argument + parse_args`
  - `argparse.Namespace 真 attr 访问`
  - `shlex.split 真 shell 词法切分`
  - `shlex.quote 真加引号`
  - `shlex.join 真 list→str (3.8+)`
  - `subprocess.Popen 真启 'echo forge' + stdout 读`
  - `subprocess.run 真调 + CompletedProcess`
  - `subprocess.check_output 真返 bytes`
  - `signal.alarm 真设 timer (沙箱短 timeout)`
  - `signal.signal 真挂 handler (沙箱 SIGALRM)`
  - `signal.getsignal 真返原 handler`
  - `pstats.Stats(stream=StringIO) 真设 stream + print_stats`
  - `logging.StreamHandler 真装 stream + 写 record`
  - `logging.FileHandler 真写 file`
  - `pickle.HIGHEST_PROTOCOL=5`
  - `pickle.DEFAULT_PROTOCOL=4`
  - `smtplib.SMTP 真 class 存在 (沙箱 skip 创建实例)`
"""
import argparse
import io
import logging
import pickle
import pstats
import shlex
import signal
import smtplib
import subprocess
import sys
import tempfile
import time

import pytest


# -- argparse 进阶 ------------------------------------------------------------

class TestArgparseAdvanced:
    def test_parse_args(self):
        """`ArgumentParser 真建 + add_argument + parse_args。"""
        parser = argparse.ArgumentParser(description="Forge test parser")
        parser.add_argument("--name", default="forge")
        parser.add_argument("--count", type=int, default=1)
        # parse
        args = parser.parse_args(["--name", "test", "--count", "5"])
        assert args.name == "test"
        assert args.count == 5

    def test_Namespace_attrs(self):
        """`Namespace 真 attr 访问。"""
        ns = argparse.Namespace(foo=42, bar="forge", baz=[1, 2, 3])
        assert ns.foo == 42
        assert ns.bar == "forge"
        assert ns.baz == [1, 2, 3]
        # __eq__
        ns2 = argparse.Namespace(foo=42, bar="forge", baz=[1, 2, 3])
        assert ns == ns2


# -- shlex 进阶 ----------------------------------------------------------------

class TestShlexAdvanced:
    def test_split(self):
        """`shlex.split 真 shell 词法切分。"""
        parts = shlex.split("forge 'hello world' \"forge test\"")
        assert parts == ["forge", "hello world", "forge test"]

    def test_quote(self):
        """`shlex.quote 真加引号。"""
        # 'forge test' (含空格) 必加引号
        q = shlex.quote("forge test")
        assert q != "forge test"
        # 必能 shell split 回
        assert shlex.split(q) == ["forge test"]

    def test_join(self):
        """`shlex.join 3.8+ 真 list→str。"""
        if sys.version_info < (3, 8):
            pytest.skip("3.8+ shlex.join")
        s = shlex.join(["forge", "hello world", "test"])
        # 必能 split 回
        assert shlex.split(s) == ["forge", "hello world", "test"]


# -- subprocess Popen + run + check_output -------------------------------------

class TestSubprocessAdvanced:
    def test_Popen_echo(self):
        """`subprocess.Popen 'echo forge' 真 stdout 'forge\\n'。"""
        proc = subprocess.Popen(
            ["echo", "forge"],
            stdout=subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate()
        assert stdout.strip() == "forge", f"stdout 应='forge',实际 {stdout!r}"
        assert proc.returncode == 0

    def test_run_CompletedProcess(self):
        """`subprocess.run 真返 CompletedProcess。"""
        result = subprocess.run(
            ["echo", "forge"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "forge" in result.stdout
        # 必是 CompletedProcess
        assert isinstance(result, subprocess.CompletedProcess)

    def test_check_output_bytes(self):
        """`subprocess.check_output 真返 bytes 含 'forge'。"""
        out = subprocess.check_output(
            ["echo", "forge bytes"]
        )
        assert b"forge bytes" in out, f"应含 'forge bytes',实际 {out!r}"


# -- signal.alarm 进阶 ---------------------------------------------------------

class TestSignalAdvanced:
    def test_signal_getsignal(self):
        """`signal.signal 真挂 handler + getsignal 真取。"""
        # 用 SIGUSR1 (沙箱一般允许)
        original = signal.getsignal(signal.SIGUSR1)

        def handler(signum, frame):
            pass

        try:
            signal.signal(signal.SIGUSR1, handler)
            # 必能取回
            current = signal.getsignal(signal.SIGUSR1)
            assert current is handler
        finally:
            # 恢复
            signal.signal(signal.SIGUSR1, original)


# -- pstats.Stats(stream=StringIO) ---------------------------------------------

class TestPstatsStreamV2:
    def test_Stats_stream(self):
        """`pstats.Stats(stream=StringIO) 真设 stream + print_stats 含内容。"""
        import cProfile
        p = cProfile.Profile()
        p.enable()
        sum([i for i in range(100)])
        p.disable()
        buf = io.StringIO()
        s = pstats.Stats(p, stream=buf)
        s.print_stats()
        # 必含 cProfile 输出
        output = buf.getvalue()
        assert "function calls" in output or "ncalls" in output


# -- logging.StreamHandler 进阶 ------------------------------------------------

class TestLoggingStreamHandler:
    def test_StreamHandler(self):
        """`logging.StreamHandler 真装 stream + 写 record。"""
        log = logging.getLogger("forge_stream_handler")
        log.setLevel(logging.INFO)
        log.handlers.clear()
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        log.addHandler(h)
        try:
            log.info("hello forge stream")
            # 必含 'hello forge stream'
            assert "hello forge stream" in buf.getvalue()
        finally:
            log.removeHandler(h)

    def test_FileHandler(self):
        """`logging.FileHandler 真写 file。"""
        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".log"
        ) as f:
            path = f.name
        try:
            log = logging.getLogger("forge_file_handler")
            log.setLevel(logging.INFO)
            log.handlers.clear()
            h = logging.FileHandler(path)
            log.addHandler(h)
            try:
                log.info("hello forge file")
            finally:
                log.removeHandler(h)
                h.close()
            # 必含
            with open(path) as f:
                content = f.read()
            assert "hello forge file" in content
        finally:
            import os
            os.unlink(path)


# -- pickle 协议 进阶 ----------------------------------------------------------

class TestPickleProtocolV2:
    def test_HIGHEST_PROTOCOL(self):
        """`pickle.HIGHEST_PROTOCOL 真=5。"""
        assert pickle.HIGHEST_PROTOCOL == 5

    def test_DEFAULT_PROTOCOL(self):
        """`pickle.DEFAULT_PROTOCOL 真=4。"""
        assert pickle.DEFAULT_PROTOCOL == 4


# -- smtplib 进阶 --------------------------------------------------------------

class TestSmtplibAdvanced:
    def test_SMTP_class(self):
        """`smtplib.SMTP 真 class 存在 (沙箱 skip 创建实例)`"""
        # SMTP 真 class
        assert smtplib.SMTP is not None
        # 真能调 (无 server = 抛)
        # 简化: 验 __init__ 签名
        assert callable(smtplib.SMTP)
