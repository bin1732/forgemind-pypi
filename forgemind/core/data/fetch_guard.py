# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""取数调用的超时保护。

第三方行情接口不暴露超时参数,而这些接口在受限网络下可能连接建起来
却不回数据。没有超时的话,一次取数就能把整条流水线挂住 —— 卡住比取
不到更难排查:它既不报错也不结束,用户只能干等。

两道防线:
  * socket 的默认超时,管住"连上了但不回数据"这种读挂起;
  * 守护线程的硬墙,管住 DNS 解析或建连本身卡死 —— 那种挂起 socket
    的默认超时管不到,因为它发生在 socket 建立之前。

守护线程不会阻止解释器退出,所以即使某个调用真的卡死,进程照样能结束,
只是丢掉那个结果。
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

#: 取数调用的默认超时秒数
DEFAULT_FETCH_TIMEOUT = 15.0


def call_with_timeout(func: Callable[[], T], timeout: float = DEFAULT_FETCH_TIMEOUT) -> T:
    """带超时的调用。

    超时表现为 TimeoutError(即 socket.timeout 的父类),调用方可以按
    抓取失败处理。
    """
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    outcome: dict[str, object] = {}

    def runner() -> None:
        try:
            outcome["value"] = func()
        except BaseException as exc:  # noqa: BLE001
            outcome["error"] = exc

    try:
        worker = threading.Thread(target=runner, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            raise TimeoutError(f"取数调用超过 {timeout} 秒未返回(DNS 解析或建连卡住)")
        if "error" in outcome:
            raise outcome["error"]  # type: ignore[misc]
        return outcome["value"]  # type: ignore[return-value]
    finally:
        socket.setdefaulttimeout(previous)
