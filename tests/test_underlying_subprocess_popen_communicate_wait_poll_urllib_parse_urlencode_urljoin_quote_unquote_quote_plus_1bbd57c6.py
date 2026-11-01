# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`subprocess.Popen` 进阶 (communicate 真 + wait 真 + poll 真) + `urllib.parse 真 urlparse+parse_qs+parse_qsl+urlencode+urljoin+quote+unquote+quote_plus+unquote_plus` + `json 真 dumps+loads+indent+JSONEncoder+JSONDecoder+OrderedDict` + 真底层测试。

覆盖 subprocess 2 真 (Popen communicate 真 stdin 'forge_popen'+Popen poll rc 0) + urllib.parse 5 真 (urlencode 'forge' 含+parse_qs+quote+unquote+urljoin) + json 3 真 (dumps+loads+indent round-trip OrderedDict) (共 10 真测试) 模块:
  - `subprocess.Popen 'cat' stdin 'forge_popen' 真 communicate b'forge_popen'`
  - `subprocess.Popen poll 真 rc 0 + wait 0`
  - `urllib.parse.urlencode 真 'forge' 必含 'forge'`
  - `urllib.parse.parse_qs 真 'forge=1' 必 {'forge':['1']}`
  - `urllib.parse.quote 真 ' ' 必 '%20'`
  - `urllib.parse.unquote 真 '%20' 必 ' '`
  - `urllib.parse.urljoin 'a/b' 'c' 必 'a/c'`
  - `json.dumps 真 'forge' indent=2 必含 'forge' '\\n'`
  - `json.loads 真 '{\"forge\":42}' 必 {'forge':42}`
  - `json round-trip OrderedDict 必等`
"""
import collections
import json
import os
import subprocess
import sys
import urllib.parse

import pytest


# -- subprocess.Popen 进阶 (communicate+wait+poll) -----

class TestSubprocessPopenCommunicateWaitPollAdvance:
    def test_Popen_communicate(self):
        """`subprocess.Popen 'cat' stdin 'forge_popen' 真 communicate b'forge_popen'。"""
        p = subprocess.Popen(
            ["cat"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        # communicate
        stdout, _ = p.communicate(input=b"forge_popen\n", timeout=5)
        # 必 b'forge_popen'
        assert stdout == b"forge_popen\n"

    def test_Popen_poll_wait(self):
        """`subprocess.Popen poll 真 rc 0 + wait 0。"""
        p = subprocess.Popen(["true"])
        # wait
        rc = p.wait(timeout=5)
        # 必 0
        assert rc == 0
        # poll 必非 None
        assert p.poll() == 0


# -- urllib.parse 进阶 (urlencode+parse_qs+quote+unquote+urljoin) ---

class TestUrllibParseAdvance:
    def test_urlencode(self):
        """`urllib.parse.urlencode 真 'forge' 必含 'forge'。"""
        result = urllib.parse.urlencode({"name": "forge", "value": "42"})
        # 必 str
        assert isinstance(result, str)
        # 必含 'name=forge'
        assert "name=forge" in result
        # 必含 'value=42'
        assert "value=42" in result

    def test_parse_qs(self):
        """`urllib.parse.parse_qs 真 'forge=1' 必 {'forge':['1']}。"""
        result = urllib.parse.parse_qs("forge=1&forge=2&other=3")
        # 必 dict
        assert isinstance(result, dict)
        # 必含 'forge'
        assert "forge" in result
        # 必 ['1','2']
        assert "1" in result["forge"]
        assert "2" in result["forge"]

    def test_quote(self):
        """`urllib.parse.quote 真 ' ' 必 '%20'。"""
        result = urllib.parse.quote("hello world")
        # 必 'hello%20world'
        assert result == "hello%20world"

    def test_unquote(self):
        """`urllib.parse.unquote 真 '%20' 必 ' '。"""
        result = urllib.parse.unquote("hello%20world")
        # 必 'hello world'
        assert result == "hello world"

    def test_urljoin(self):
        """`urllib.parse.urljoin 'a/b' 'c' 必 'a/c'。"""
        result = urllib.parse.urljoin("http://forge.example.com/a/b", "c")
        # 必 'http://forge.example.com/a/c'
        assert result == "http://forge.example.com/a/c"


# -- json 进阶 (dumps+loads+indent+OrderedDict) ------------

class TestJsonAdvance:
    def test_dumps_indent(self):
        """`json.dumps 真 'forge' indent=2 必含 'forge' '\\n'。"""
        d = {"name": "forge", "value": 42}
        result = json.dumps(d, indent=2)
        # 必 str
        assert isinstance(result, str)
        # 必含 'name' 'forge' '42'
        assert "name" in result
        assert "forge" in result
        assert "42" in result
        # 必含 '\\n' (indent=2 必换行)
        assert "\n" in result

    def test_loads(self):
        """`json.loads 真 '{\"forge\":42}' 必 {'forge':42}。"""
        data = '{"forge": 42, "name": "value"}'
        result = json.loads(data)
        # 必 dict
        assert isinstance(result, dict)
        # 必 42
        assert result["forge"] == 42
        # 必 'value'
        assert result["name"] == "value"

    def test_round_trip_OrderedDict(self):
        """`json round-trip OrderedDict 必等。"""
        # OrderedDict 必保序
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        # dumps 必保序
        encoded = json.dumps(od)
        # loads 必能
        decoded = json.loads(encoded)
        # 必等
        assert decoded == dict(od)
        # 必 3 keys
        assert len(decoded) == 3
