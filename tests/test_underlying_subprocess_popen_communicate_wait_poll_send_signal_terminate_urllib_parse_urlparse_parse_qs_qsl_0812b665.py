# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`subprocess 进阶 (Popen.communicate+wait+poll+send_signal+terminate)` + `urllib.parse 进阶 (urlparse+parse_qs+parse_qsl+urlencode+urljoin+quote+unquote)` + `json 进阶 (dumps+loads+indent+OrderedDict+JSONEncoder+JSONDecoder)` + 真底层测试。

覆盖 subprocess 5 真 + urllib.parse 7 真 + json 4 真 (共 16 真测试) 模块:
  - `subprocess.Popen communicate 'forge_args'`
  - `subprocess.Popen wait rc=0`
  - `subprocess.Popen poll rc=0`
  - `subprocess.Popen send_signal SIGUSR1`
  - `subprocess.Popen terminate`
  - `urllib.parse.urlparse scheme 'http'`
  - `urllib.parse.parse_qs 'forge=1'`
  - `urllib.parse.parse_qsl 'forge=1'`
  - `urllib.parse.urlencode 'forge'`
  - `urllib.parse.urljoin 'a/b' 'c'`
  - `urllib.parse.quote ' '`
  - `urllib.parse.unquote '%20'`
  - `json.dumps indent=2`
  - `json.loads dict`
  - `json OrderedDict round-trip`
  - `json JSONEncoder+Decoder`
"""
import collections
import json
import os
import signal
import subprocess
import urllib.parse

import pytest


# -- subprocess 进阶 (Popen communicate+wait+poll+send_signal+terminate) ---

class TestSubprocessPopenCommunicateWaitPollSendSignalTerminateAdvance:
    def test_communicate(self):
        """`subprocess.Popen 'echo' 'forge_args' communicate 必 stdout b'forge_args'。"""
        p = subprocess.Popen(
            ["echo", "forge_args"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        stdout, _ = p.communicate(input=b"", timeout=5)
        # 必含 b'forge_args'
        assert b"forge_args" in stdout

    def test_wait(self):
        """`subprocess.Popen wait 必 returncode 0。"""
        p = subprocess.Popen(["true"])
        rc = p.wait(timeout=5)
        assert rc == 0

    def test_poll(self):
        """`subprocess.Popen poll 必 returncode 0。"""
        p = subprocess.Popen(["true"])
        p.wait(timeout=5)
        assert p.poll() == 0

    def test_send_signal(self):
        """`subprocess.Popen send_signal SIGUSR1 必不抛。"""
        p = subprocess.Popen(["sleep", "10"])
        try:
            p.send_signal(signal.SIGUSR1)
            assert True
        finally:
            p.terminate()
            p.wait(timeout=5)

    def test_terminate(self):
        """`subprocess.Popen terminate 必不抛。"""
        p = subprocess.Popen(["sleep", "10"])
        p.terminate()
        p.wait(timeout=5)
        assert True


# -- urllib.parse 进阶 (urlparse+parse_qs+parse_qsl+urlencode+urljoin+quote+unquote) ---

class TestUrllibParseAdvanceV3:
    def test_urlparse(self):
        """`urllib.parse.urlparse scheme 'http'。"""
        r = urllib.parse.urlparse("http://forge.example.com/forge")
        # 必 scheme 'http'
        assert r.scheme == "http"
        # 必 netloc
        assert r.netloc == "forge.example.com"

    def test_parse_qs(self):
        """`urllib.parse.parse_qs 'forge=1'。"""
        result = urllib.parse.parse_qs("forge=1&forge=2")
        assert "forge" in result
        assert "1" in result["forge"]

    def test_parse_qsl(self):
        """`urllib.parse.parse_qsl 'forge=1'。"""
        result = urllib.parse.parse_qsl("forge=1&other=2")
        assert isinstance(result, list)
        assert len(result) == 2
        assert ("forge", "1") in result

    def test_urlencode(self):
        """`urllib.parse.urlencode 'forge'。"""
        result = urllib.parse.urlencode({"name": "forge"})
        assert "name=forge" in result

    def test_urljoin(self):
        """`urllib.parse.urljoin 'a/b' 'c'。"""
        result = urllib.parse.urljoin("http://forge.example.com/a/b", "c")
        assert result == "http://forge.example.com/a/c"

    def test_quote(self):
        """`urllib.parse.quote ' '。"""
        result = urllib.parse.quote("hello world")
        assert result == "hello%20world"

    def test_unquote(self):
        """`urllib.parse.unquote '%20'。"""
        result = urllib.parse.unquote("hello%20world")
        assert result == "hello world"


# -- json 进阶 (dumps+loads+indent+OrderedDict+JSONEncoder+JSONDecoder) ---

class TestJsonAdvanceV3:
    def test_dumps_indent(self):
        """`json.dumps indent=2。"""
        d = {"name": "forge", "value": 42}
        result = json.dumps(d, indent=2)
        assert isinstance(result, str)
        assert "name" in result
        assert "forge" in result
        assert "\n" in result

    def test_loads(self):
        """`json.loads dict。"""
        data = '{"forge": 42, "name": "value"}'
        result = json.loads(data)
        assert isinstance(result, dict)
        assert result["forge"] == 42

    def test_OrderedDict_round_trip(self):
        """`json OrderedDict round-trip。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        encoded = json.dumps(od)
        decoded = json.loads(encoded)
        assert decoded == dict(od)
        assert len(decoded) == 3

    def test_JSONEncoder_decode(self):
        """`json JSONEncoder+JSONDecoder。"""
        enc = json.JSONEncoder()
        encoded = enc.encode({"forge": 42})
        assert "forge" in encoded
        decoded = json.JSONDecoder().decode(encoded)
        assert decoded["forge"] == 42
