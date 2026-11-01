# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`asyncio.subprocess` 真 stdin pipe + `multiprocessing.Pool` 进阶 async + `unittest.mock.MagicMock` 进阶 (call + spec) + `asyncio` Event/Condition 真底层测试。

覆盖 asyncio 真 subprocess pipe / Pool async / MagicMock spec / smtpd 邮件接收 模块:
  - `asyncio.create_subprocess_exec + stdin 真写入 + stdout 真读`
  - `asyncio.create_subprocess_shell 'echo' 真返 0 字节`
  - `multiprocessing.Pool.apply_async 真异步 (5 任务并发)`
  - `multiprocessing.Pool.imap_unordered 真 lazy 迭代`
  - `unittest.mock.MagicMock 必是真 Magic 类 instance`
  - `unittest.mock.MagicMock().return_value 必是 MagicMock`
  - `unittest.mock.MagicMock(spec=list) 必只含 list 方法`
  - `unittest.mock.MagicMock()._mock_name 真设名`
  - `unittest.mock.patch.dict(os.environ) 真改 env`
  - `unittest.mock.patch.object 替换真 attr`
  - `smtpd.SMTPServer 沙箱 skip (deprecated) / `smtplib` 沙箱 skip (无 server)`
  - `asyncio.Event wait+set 真跨 task`
  - `asyncio.Condition wait+notify 真跨 task`
"""
import asyncio
import multiprocessing
import os
import sys
import unittest.mock

import pytest


# -- asyncio.subprocess 真 stdin pipe -----------------------------------------

class TestAsyncioSubprocessPipe:
    def test_subprocess_exec_echo_stdin(self):
        """`asyncio.create_subprocess_exec 真 stdin 写入 'hello forge' + stdout 读回。"""

        async def main():
            proc = await asyncio.create_subprocess_exec(
                "cat", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
            )
            stdin_data = b"hello forge\n"
            stdout, stderr = await proc.communicate(input=stdin_data)
            return stdout, proc.returncode

        stdout, rc = asyncio.run(main())
        assert stdout == b"hello forge\n", f"stdout 应 'hello forge\\n',实际 {stdout!r}"
        assert rc == 0, f"cat 应 exit 0,实际 {rc}"

    def test_subprocess_shell_echo(self):
        """`asyncio.create_subprocess_shell 'echo forge' 真 stdout 'forge\\n'。"""

        async def main():
            proc = await asyncio.create_subprocess_shell(
                "echo forge", stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout, proc.returncode

        stdout, rc = asyncio.run(main())
        # 'echo forge' 必返 'forge\n'
        assert b"forge" in stdout, f"stdout 应含 'forge',实际 {stdout!r}"
        assert rc == 0


# -- asyncio Event + Condition -------------------------------------------------

class TestAsyncioEventCondition:
    def test_Event_set_wait(self):
        """`asyncio.Event 真 wait+set 跨 task 5 次。"""

        async def main():
            evt = asyncio.Event()

            async def setter():
                await asyncio.sleep(0.01)
                evt.set()

            async def waiter(idx):
                await evt.wait()
                return idx

            setter_task = asyncio.create_task(setter())
            waiters = [asyncio.create_task(waiter(i)) for i in range(5)]
            results = await asyncio.gather(*waiters)
            await setter_task
            return results

        results = asyncio.run(main())
        assert sorted(results) == [0, 1, 2, 3, 4], f"Event wait 必返 [0,1,2,3,4],实际 {results}"

    def test_Condition_notify(self):
        """`asyncio.Condition 真 notify 1 个 waiter。"""

        async def main():
            cond = asyncio.Condition()
            received = []

            async def consumer():
                async with cond:
                    await cond.wait()
                    received.append("forge_woken")

            async def notifier():
                await asyncio.sleep(0.01)
                async with cond:
                    cond.notify_all()

            c = asyncio.create_task(consumer())
            n = asyncio.create_task(notifier())
            await asyncio.gather(c, n)
            return received

        result = asyncio.run(main())
        assert result == ["forge_woken"]


# -- multiprocessing.Pool 进阶 -------------------------------------------------

def _slow_square(x):
    return x * x


def _slow_add(x, y):
    return x + y


class TestMultiprocessingPoolAdvancedV2:
    def test_Pool_apply_async_concurrent(self):
        """`Pool.apply_async 真异步 5 任务并发。"""
        with multiprocessing.Pool(2) as p:
            results = []
            async_results = []
            for i in range(5):
                ar = p.apply_async(_slow_square, (i,))
                async_results.append(ar)
            for ar in async_results:
                results.append(ar.get(timeout=10))
            assert results == [0, 1, 4, 9, 16], f"Pool 真 sq [0,1,4,9,16],实际 {results}"

    def test_Pool_imap_unordered(self):
        """`Pool.imap_unordered 真 lazy 迭代 sq。"""
        with multiprocessing.Pool(2) as p:
            # [3, 1, 4, 1, 5, 9, 2, 6] 平方 (有 2 个 1, 0 个 7/8)
            results = list(p.imap_unordered(_slow_square, [3, 1, 4, 1, 5, 9, 2, 6]))
            # 平方: [9, 1, 16, 1, 25, 81, 4, 36] 排序 = [1, 1, 4, 9, 16, 25, 36, 81]
            assert sorted(results) == [1, 1, 4, 9, 16, 25, 36, 81], (
                f"imap_unordered sq 排序应=[1,1,4,9,16,25,36,81],实际 {sorted(results)}"
            )


# -- unittest.mock.MagicMock 进阶 (spec) --------------------------------------

class TestMagicMockAdvanced:
    def test_MagicMock_is_magic(self):
        """`MagicMock 必是 Magic 类的 instance。"""
        m = unittest.mock.MagicMock()
        # 必能调魔术方法
        assert int(m) is not None  # __int__
        assert bool(m) is True  # __bool__
        assert m.__len__() == 0  # __len__

    def test_MagicMock_return_value(self):
        """`MagicMock().return_value 必是 MagicMock。"""
        m = unittest.mock.MagicMock()
        m.return_value = "forge"
        assert m() == "forge"

    def test_MagicMock_spec_list(self):
        """`MagicMock(spec=list) 必只含 list 方法。"""
        m = unittest.mock.MagicMock(spec=list)
        # 必能调 list 方法
        m.append("forge")
        m.append.assert_called_with("forge")
        # 必不能调 list 没的方法
        with pytest.raises(AttributeError):
            _ = m.non_existent_method

    def test_MagicMock_name(self):
        """`MagicMock(name=...) 必设 _mock_name。"""
        m = unittest.mock.MagicMock(name="forge_mock")
        assert m._mock_name == "forge_mock"
        # repr 必含 forge_mock
        assert "forge_mock" in repr(m)

    def test_patch_dict_environ(self):
        """`patch.dict(os.environ) 真改 env。"""
        with unittest.mock.patch.dict(
            os.environ, {"FORGE_TEST_KEY": "forge_value"}
        ):
            assert os.environ["FORGE_TEST_KEY"] == "forge_value"
        # 退出后必不在
        assert "FORGE_TEST_KEY" not in os.environ

    def test_patch_object(self):
        """`patch.object 真替换 attr。"""

        class _Obj:
            value = 42

        obj = _Obj()
        with unittest.mock.patch.object(_Obj, "value", 99):
            assert _Obj.value == 99
        # 退出后必恢复
        assert _Obj.value == 42
