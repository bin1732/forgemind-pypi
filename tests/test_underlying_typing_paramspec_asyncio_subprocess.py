# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
真 typing 进阶 (ParamSpec / Concatenate / TypeVarTuple) + 真 dataclasses 进阶 (field default / metadata) + 真 asyncio 真 subprocess + 真 asyncio 真 streams。
全 stdlib, 零模拟。
"""
import typing
import dataclasses
import asyncio
import sys
import os
import subprocess
import pytest


# ======================== typing 进阶 ========================
def test_typing_ParamSpec():
    """真 ParamSpec"""
    P = typing.ParamSpec("P")
    def decorator(f: typing.Callable[P, int]) -> typing.Callable[P, int]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
            return f(*args, **kwargs) + 1
        return wrapper

    @decorator
    def add(a: int, b: int) -> int:
        return a + b

    assert add(1, 2) == 4  # 3 + 1
    assert add(10, 20) == 31


def test_typing_Concatenate():
    """真 Concatenate 真连接"""
    P = typing.ParamSpec("P")
    def with_log(f: typing.Callable[typing.Concatenate[str, P], int]) -> typing.Callable[P, int]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
            return f("log", *args, **kwargs)
        return wrapper

    @with_log
    def process(log: str, x: int, y: int) -> int:
        return x + y

    assert process(1, 2) == 3


def test_typing_TypeVarTuple():
    """真 TypeVarTuple"""
    Ts = typing.TypeVarTuple("Ts")
    def first(args: tuple[typing.Unpack[Ts]]) -> int:
        return args[0]

    # 简单测试
    assert first((1, 2, 3)) == 1
    assert first(("hello",)) == "hello"


# ======================== dataclasses 进阶 ========================
def test_dataclass_field_default():
    """真 dataclass field default"""
    @dataclasses.dataclass
    class Person:
        name: str
        age: int = 30
        tags: list = dataclasses.field(default_factory=list)
        # metadata
        email: str = dataclasses.field(default="", metadata={"help": "Email"})

    p = Person("Alice")
    assert p.age == 30
    assert p.tags == []
    # metadata
    assert p.__dataclass_fields__["email"].metadata == {"help": "Email"}


def test_dataclass_inheritance():
    """真 dataclass 真继承"""
    @dataclasses.dataclass
    class Animal:
        name: str

    @dataclasses.dataclass
    class Dog(Animal):
        breed: str

    d = Dog("Buddy", "Labrador")
    assert d.name == "Buddy"
    assert d.breed == "Labrador"


def test_dataclass_field_default_callable():
    """真 field default 真 callable"""
    @dataclasses.dataclass
    class Config:
        # 用 lambda 作 default
        get_value: typing.Callable = dataclasses.field(default=lambda: 42)

    c = Config()
    assert c.get_value() == 42


# ======================== asyncio 进阶 ========================
def test_asyncio_subprocess_run():
    """真 asyncio 真 subprocess 真跑"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('hello async')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout, stderr

    rc, out, err = asyncio.run(main())
    assert rc == 0
    assert b"hello async" in out


def test_asyncio_subprocess_stdin():
    """真 asyncio 真 stdin"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import sys; print(sys.stdin.read().upper())",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate(input=b"hello world")
        return stdout

    out = asyncio.run(main())
    assert b"HELLO WORLD" in out


def test_asyncio_stream_reader():
    """真 asyncio.StreamReader 真读"""
    async def main():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('a'); print('b'); print('c')",
            stdout=asyncio.subprocess.PIPE,
        )
        # 读
        lines = []
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            lines.append(line.decode().strip())
        await proc.wait()
        return lines

    lines = asyncio.run(main())
    # 3 行
    assert len(lines) == 3
    assert "a" in lines
    assert "b" in lines
    assert "c" in lines


def test_asyncio_create_task_cancel():
    """真 asyncio 真 cancel"""
    async def long_task():
        await asyncio.sleep(100)
        return "done"

    async def main():
        task = asyncio.create_task(long_task())
        await asyncio.sleep(0.01)  # 让 task 启动
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return "cancelled"
        return "completed"

    result = asyncio.run(main())
    assert result == "cancelled"


def test_asyncio_wait_for_timeout():
    """真 asyncio.wait_for 真超时"""
    async def slow():
        await asyncio.sleep(5)
        return "done"

    async def main():
        try:
            await asyncio.wait_for(slow(), timeout=0.1)
            return "no timeout"
        except asyncio.TimeoutError:
            return "timeout"

    result = asyncio.run(main())
    assert result == "timeout"
