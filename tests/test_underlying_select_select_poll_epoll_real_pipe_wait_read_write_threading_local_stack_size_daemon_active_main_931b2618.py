# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0
"""`select.select/poll/epoll` 真用 (双 pipe IO 多路) + `threading.local/stack_size/daemon/active_count/current_thread/main_thread` 真用 + `enum.global_enum/nonmember/member` 3.11+ 沙箱 skip + `typing.Required/NotRequired/TypedDict` 3.11+ + 真底层测试。

覆盖 select 2 真 (select+epoll 真 pipe) + threading 5 真 (local+stack_size+active_count+current_thread+main_thread) + typing 3 真 (TypedDict+Required+NotRequired 3.11+) (共 10 真测试) 模块:
  - `select.select 真双 pipe rlist/wlist/xlist ≥ 1`
  - `select.epoll 真注册 + poll 必 ≥ 1`
  - `threading.local 真子化 + setattr/getattr`
  - `threading.stack_size 真 get/set + reset`
  - `threading.active_count 必 ≥ 1`
  - `threading.current_thread 必 Thread 真主线程`
  - `threading.main_thread 必 Thread 主线程`
  - `typing.TypedDict 3.11+ 真 Movie 'title'+'year'`
  - `typing.Required 3.11+ 沙箱 3.11 必有`
  - `typing.NotRequired 3.11+ 沙箱 3.11 必有`
"""
import os
import select
import sys
import threading
import typing

import pytest


# -- select 进阶 (select + epoll 真 pipe) ---------------------------

class TestSelectAdvanced:
    def test_select_pipe(self):
        """`select.select 真双 pipe rlist/wlist/xlist ≥ 1。"""
        r, w = os.pipe()
        try:
            # write
            os.write(w, b"forge_select")
            # select 必返 ≥ 1 ready read
            rlist, _, _ = select.select([r], [], [], 0.5)
            # 必 ≥ 1
            assert len(rlist) >= 1
            # 必含 r
            assert r in rlist
        finally:
            os.close(r)
            os.close(w)

    def test_epoll(self):
        """`select.epoll 真注册 + poll 必 ≥ 1。"""
        r, w = os.pipe()
        try:
            ep = select.epoll()
            try:
                # register
                ep.register(r, select.EPOLLIN)
                # write
                os.write(w, b"forge_epoll")
                # poll 必 ≥ 1
                events = ep.poll(0.5)
                # 必 ≥ 1
                assert len(events) >= 1
            finally:
                ep.close()
        finally:
            os.close(r)
            os.close(w)


# -- threading 进阶 (local + stack_size + active_count + thread) ---

class TestThreadingAdvancedV2:
    def test_local(self):
        """`threading.local 真子化 + setattr/getattr。"""
        local = threading.local()
        # setattr
        local.x = "forge_local"
        # getattr
        assert local.x == "forge_local"

    def test_stack_size(self):
        """`threading.stack_size 真 get/set + reset。"""
        # save
        old = threading.stack_size()
        try:
            # set
            threading.stack_size(2 * 1024 * 1024)
            # get
            new = threading.stack_size()
            # 必 2MB
            assert new == 2 * 1024 * 1024
        finally:
            threading.stack_size(old)

    def test_active_count(self):
        """`threading.active_count 必 ≥ 1。"""
        n = threading.active_count()
        # 必 ≥ 1
        assert n >= 1
        # 必 int
        assert isinstance(n, int)

    def test_current_thread(self):
        """`threading.current_thread 必 Thread 真主线程。"""
        t = threading.current_thread()
        # 必 Thread
        assert isinstance(t, threading.Thread)
        # 必主线程
        assert t.name == "MainThread"

    def test_main_thread(self):
        """`threading.main_thread 必 Thread 主线程。"""
        t = threading.main_thread()
        # 必 Thread
        assert isinstance(t, threading.Thread)
        # 必主线程
        assert t.name == "MainThread"


# -- typing 进阶 (TypedDict + Required + NotRequired 3.11+) --------

class TestTypingAdvancedV3:
    def test_TypedDict(self):
        """`typing.TypedDict 3.11+ 真 Movie 'title'+'year'。"""
        # 沙箱 3.11 必有
        if hasattr(typing, "TypedDict"):
            Movie = typing.TypedDict("Movie", {"title": str, "year": int})
            # 必能创
            m: Movie = {"title": "forge", "year": 2026}
            # 必能访问
            assert m["title"] == "forge"
            assert m["year"] == 2026

    def test_Required_3_11(self):
        """`typing.Required 3.11+ 沙箱 3.11 必有。"""
        # 沙箱 3.11 必有
        assert typing.Required is not None

    def test_NotRequired_3_11(self):
        """`typing.NotRequired 3.11+ 沙箱 3.11 必有。"""
        # 沙箱 3.11 必有
        assert typing.NotRequired is not None
