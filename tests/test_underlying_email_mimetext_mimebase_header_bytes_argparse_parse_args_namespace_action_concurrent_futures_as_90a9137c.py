# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`email 进阶 (MIMEText+MIMEBase+Header+message_from_bytes)` + `argparse 进阶 (parse_args+add_argument+Namespace+Action 真子化)` + `concurrent.futures 进阶 (wait+as_completed+Future)` + `subprocess 进阶 (Popen 真 args+env+cwd)` + 真底层测试。

覆盖 email 4 真 (MIMEText+MIMEBase+Header+message_from_bytes) + argparse 4 真 + concurrent.futures 3 真 + subprocess 3 真 (共 14 真测试) 模块:
  - `email.mime.text.MIMEText 'forge body'`
  - `email.mime.base.MIMEBase 'application' set_payload b'forge'`
  - `email.header.Header 'forge_value'`
  - `email.message_from_bytes b'Subject: forge'`
  - `argparse.ArgumentParser 'forge_parser'`
  - `argparse add_argument --name 'forge_arg'`
  - `argparse.Namespace vars dict`
  - `argparse.Action 子化 _ForgeAction`
  - `concurrent.futures.wait [fut1, fut2]`
  - `concurrent.futures.as_completed [fut1, fut2]`
  - `concurrent.futures.Future set_result 'forge_value'`
  - `subprocess.Popen echo rc=0`
  - `subprocess.Popen pwd cwd='/tmp' rc=0`
  - `subprocess.Popen env FORGE_TEST_VAR rc=0`
"""
import argparse
import concurrent.futures
import email
import email.header
import email.message
import email.mime.base
import email.mime.text
import os
import subprocess

import pytest


# -- email 进阶 (MIMEText+MIMEBase+Header+message_from_bytes) ---

class TestEmailMimeTextBaseHeaderMessageFromBytesAdvance:
    def test_MIMEText(self):
        """`email.mime.text.MIMEText 'forge body'。"""
        msg = email.mime.text.MIMEText("forge body")
        # 必 str 'forge body' in payload
        assert "forge body" in msg.as_string()

    def test_MIMEBase(self):
        """`email.mime.base.MIMEBase 'application' set_payload b'forge'。"""
        msg = email.mime.base.MIMEBase("application", "octet-stream")
        msg.set_payload(b"forge_data")
        # 必 'forge_data' in payload
        assert b"forge_data" in msg.as_bytes()

    def test_Header(self):
        """`email.header.Header 'forge_value'。"""
        h = email.header.Header("forge_value")
        # 必 str
        assert "forge_value" in str(h)

    def test_message_from_bytes(self):
        """`email.message_from_bytes b'Subject: forge'。"""
        msg = email.message_from_bytes(b"Subject: forge bytes\n\nbody\n")
        # 必 Subject 'forge bytes'
        assert msg["Subject"] == "forge bytes"


# -- argparse 进阶 (parse_args+add_argument+Namespace+Action) ---

class _ForgeAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, f"forge_action_{values}")


class TestArgparseParseArgsAddArgumentNamespaceActionAdvance:
    def test_ArgumentParser(self):
        """`argparse.ArgumentParser 'forge_parser'。"""
        p = argparse.ArgumentParser(prog="forge_parser")
        # 必 prog
        assert p.prog == "forge_parser"

    def test_add_argument_parse_args(self):
        """`argparse add_argument --name 'forge_arg'。"""
        p = argparse.ArgumentParser(prog="forge_parser_args")
        p.add_argument("--name", default="forge_default")
        # parse_args
        args = p.parse_args(["--name", "forge_arg_value"])
        # 必 'forge_arg_value'
        assert args.name == "forge_arg_value"

    def test_Namespace(self):
        """`argparse.Namespace vars dict。"""
        ns = argparse.Namespace(name="forge_name", value=42)
        # 必 vars 含 'name' + 'value'
        d = vars(ns)
        assert d["name"] == "forge_name"
        assert d["value"] == 42

    def test_Action_subclass(self):
        """`argparse.Action 子化 _ForgeAction。"""
        p = argparse.ArgumentParser(prog="forge_parser_action")
        p.add_argument("--forge", action=_ForgeAction, default="forge_default")
        # parse_args
        args = p.parse_args(["--forge", "value"])
        # 必 'forge_action_value'
        assert args.forge == "forge_action_value"


# -- concurrent.futures 进阶 (wait+as_completed+Future) ----

def _slow_return(x):
    return x * 2


class TestConcurrentFuturesWaitAsCompletedFutureAdvance:
    def test_wait(self):
        """`concurrent.futures.wait [fut1, fut2]。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:
            fut1 = p.submit(_slow_return, 1)
            fut2 = p.submit(_slow_return, 2)
            done, pending = concurrent.futures.wait([fut1, fut2])
            # 必 ≥ 1 done
            assert len(done) >= 1

    def test_as_completed(self):
        """`concurrent.futures.as_completed [fut1, fut2]。"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:
            fut1 = p.submit(_slow_return, 1)
            fut2 = p.submit(_slow_return, 2)
            results = []
            for fut in concurrent.futures.as_completed([fut1, fut2]):
                results.append(fut.result())
            # 必 2 results
            assert len(results) == 2

    def test_Future_set_result(self):
        """`concurrent.futures.Future set_result 'forge_value'。"""
        fut = concurrent.futures.Future()
        # 必能 set
        fut.set_result("forge_value")
        # 必 'forge_value'
        assert fut.result() == "forge_value"


# -- subprocess 进阶 (Popen args+env+cwd) -----------------

class TestSubprocessPopenArgsEnvCwdAdvance:
    def test_Popen_args(self):
        """`subprocess.Popen 'echo' 'forge_args' rc=0。"""
        p = subprocess.Popen(
            ["echo", "forge_args"],
            stdout=subprocess.PIPE,
        )
        # wait
        rc = p.wait(timeout=5)
        # 必 0
        assert rc == 0

    def test_Popen_cwd(self):
        """`subprocess.Popen 'pwd' cwd rc=0。"""
        p = subprocess.Popen(
            ["pwd"],
            stdout=subprocess.PIPE,
            cwd="/tmp",
        )
        # wait
        rc = p.wait(timeout=5)
        # 必 0
        assert rc == 0

    def test_Popen_env(self):
        """`subprocess.Popen 'env' rc=0。"""
        env = os.environ.copy()
        env["FORGE_TEST_VAR"] = "forge_value"
        p = subprocess.Popen(
            ["env"],
            stdout=subprocess.PIPE,
            env=env,
        )
        # wait
        rc = p.wait(timeout=5)
        # 必 0
        assert rc == 0
