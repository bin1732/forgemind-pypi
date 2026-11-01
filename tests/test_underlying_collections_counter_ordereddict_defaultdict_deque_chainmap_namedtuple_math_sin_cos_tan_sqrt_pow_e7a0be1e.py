# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`collections 进阶 (Counter+OrderedDict+defaultdict+deque+ChainMap+namedtuple)` + `math 进阶 (sin+cos+tan+sqrt+pow)` + `re 进阶 (match+search+fullmatch+findall)` + `asyncio.subprocess 进阶 (create_subprocess_exec+communicate+send_signal)` + 真底层测试。

覆盖 collections 6 真 + math 5 真 + re 4 真 + asyncio.subprocess 3 真 (共 18 真测试) 模块:
  - `collections.Counter 'forge_forge' 频 2`
  - `collections.OrderedDict 保序 [z, a, m]`
  - `collections.defaultdict 'forge_default'`
  - `collections.deque append+appendleft`
  - `collections.ChainMap child 'forge_child'`
  - `collections.namedtuple _ForgePt (42, 'forge')`
  - `math.sin 0 = 0.0`
  - `math.cos 0 = 1.0`
  - `math.tan 0 = 0.0`
  - `math.sqrt 4 = 2.0`
  - `math.pow 2 10 = 1024.0`
  - `re.match 'forge' 必 match`
  - `re.search 'forge' 必 match`
  - `re.fullmatch 'forge' 必 match`
  - `re.findall 'forge' ≥ 1`
  - `asyncio.create_subprocess_exec 'echo forge_sub'`
  - `asyncio.create_subprocess_exec 'cat' stdin 'forge_sub_cat'`
  - `asyncio.create_subprocess_exec 'sleep' send_signal SIGUSR1`
"""
import asyncio
import collections
import math
import re
import signal

import pytest


# -- collections 进阶 (Counter+OrderedDict+defaultdict+deque+ChainMap+namedtuple) ---

class TestCollectionsAdvanceV2:
    def test_Counter(self):
        """`collections.Counter 'forge_forge' 频 2。"""
        c = collections.Counter("forge_forge")
        assert c["f"] == 2
        assert c["o"] == 2

    def test_OrderedDict(self):
        """`collections.OrderedDict 保序 [z, a, m]。"""
        od = collections.OrderedDict()
        od["z"] = 1
        od["a"] = 2
        od["m"] = 3
        assert list(od.keys()) == ["z", "a", "m"]

    def test_defaultdict(self):
        """`collections.defaultdict 'forge_default'。"""
        dd = collections.defaultdict(lambda: "forge_default")
        assert dd["nonexistent"] == "forge_default"

    def test_deque(self):
        """`collections.deque append+appendleft。"""
        dq = collections.deque()
        dq.append("forge_right")
        dq.appendleft("forge_left")
        assert dq[0] == "forge_left"

    def test_ChainMap(self):
        """`collections.ChainMap child 'forge_child'。"""
        parent = {"a": "parent_value"}
        child = {"b": "forge_child"}
        cm = collections.ChainMap(child, parent)
        assert cm["b"] == "forge_child"

    def test_namedtuple(self):
        """`collections.namedtuple _ForgePt (42, 'forge')。"""
        _ForgePt = collections.namedtuple("_ForgePt", ["x", "y"])
        pt = _ForgePt(42, "forge")
        assert pt.x == 42
        assert pt.y == "forge"


# -- math 进阶 (sin+cos+tan+sqrt+pow) ------------------

class TestMathAdvanceV2:
    def test_sin_0(self):
        """`math.sin 0 = 0.0。"""
        result = math.sin(0)
        assert abs(result - 0.0) < 1e-10

    def test_cos_0(self):
        """`math.cos 0 = 1.0。"""
        result = math.cos(0)
        assert abs(result - 1.0) < 1e-10

    def test_tan_0(self):
        """`math.tan 0 = 0.0。"""
        result = math.tan(0)
        assert abs(result - 0.0) < 1e-10

    def test_sqrt_4(self):
        """`math.sqrt 4 = 2.0。"""
        result = math.sqrt(4)
        assert result == 2.0

    def test_pow(self):
        """`math.pow 2 10 = 1024.0。"""
        result = math.pow(2, 10)
        assert result == 1024.0


# -- re 进阶 (match+search+fullmatch+findall) ---------

class TestReAdvanceV3:
    def test_match(self):
        """`re.match 'forge' 必 match。"""
        m = re.match("forge", "forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_search(self):
        """`re.search 'forge' 必 match。"""
        m = re.search("forge", "value_forge_value")
        assert m is not None
        assert m.group() == "forge"

    def test_fullmatch(self):
        """`re.fullmatch 'forge' 必 match。"""
        m = re.fullmatch("forge", "forge")
        assert m is not None
        assert m.group() == "forge"

    def test_findall(self):
        """`re.findall 'forge' ≥ 1。"""
        result = re.findall("forge", "forge_value_forge_test")
        assert len(result) >= 1
        assert result == ["forge", "forge"]


# -- asyncio.subprocess 进阶 (create_subprocess_exec+communicate+send_signal) ---

class TestAsyncioSubprocessCreateSubprocessExecAdvanceV3:
    def test_create_subprocess_exec_echo(self):
        """`asyncio.create_subprocess_exec 'echo forge_sub' 必含 'forge_sub'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "echo", "forge_sub",
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        assert b"forge_sub" in stdout

    def test_create_subprocess_exec_cat(self):
        """`asyncio.create_subprocess_exec 'cat' stdin 'forge_sub_cat' 必含 'forge_sub_cat'。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            proc.stdin.write(b"forge_sub_cat\n")
            await proc.stdin.drain()
            proc.stdin.close()
            stdout, _ = await proc.communicate()
            return stdout

        stdout = asyncio.run(main())
        assert b"forge_sub_cat" in stdout

    def test_create_subprocess_exec_send_signal(self):
        """`asyncio.create_subprocess_exec 'sleep' send_signal SIGUSR1 必不抛。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "sleep", "10",
            )
            try:
                proc.send_signal(signal.SIGUSR1)
                return True
            finally:
                proc.terminate()
                await proc.wait()

        result = asyncio.run(main())
        assert result is True
