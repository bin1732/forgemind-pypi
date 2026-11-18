# Copyright (c) 2026 灵感引擎工坊 (bin1732) | SPDX-License-Identifier: Apache-2.0
"""异常该对外面说成什么 —— 一处判断,各处引用。

命令行、HTTP 接口与 MCP 三条通道都要把失败说成人话,同时不把内部实现
漏出去:异常类名、本机路径、整条 SQL、栈回溯。这些是给排查用的,不是给
调用方用的。

三处各写一遍的话,改一处就会漏另一处 —— 这个模块就是那个"一处"。
"""

from __future__ import annotations

import re
from typing import Any

#: 内部痕迹:出现在用户可见文本里就说明有东西漏出去了。
#:
#: - 栈回溯:整条调用链,排查用。
#: - 异常类名:内部实现的名字,调用方该看的是稳定错误码。
#: - SQL 片段:表名与列名是内部结构。
#: - 本机路径:用户自己的机器布局,不该出现在给别人的响应里。
#: - 数据文件:同样是本机布局,而且还能顺带认出用户的数据在哪。
_INTERNAL_TRACES: tuple[re.Pattern[str], ...] = (
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\b\w*(?:Error|Exception)\b"),
    re.compile(r"\b(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE)\b", re.I),
    re.compile(r"(?:/home/|/root/|/Users/|/tmp/|/var/folders/|/private/var/)"),
    re.compile(r"\b[A-Za-z]:\\"),
    re.compile(r"\S+\.(?:duckdb|parquet|sqlite3?|csv)\b", re.I),
)


def looks_internal(text: str) -> bool:
    """这段文本里有没有内部痕迹。"""
    return any(p.search(text) for p in _INTERNAL_TRACES)


def is_our_own_error(exc: BaseException) -> bool:
    """这个异常是我们自己抛的,还是第三方库抛的。

    自己抛的异常文本是写给人听的("symbol 不能为空"),放进给调用方的正文
    里有用 —— 调用方据此改参数。第三方库的原始报错里有本机路径、内部表名
    与整条 SQL,那些是内部实现。

    内置异常(builtins)算我们自己的:参数校验抛的就是它们,而第三方拿
    它们装内部信息的做法少见。
    """
    module = type(exc).__module__ or ""
    return module.startswith("forgemind") or module == "builtins"


def failure_detail(exc: BaseException, *, source: str = "") -> str:
    """这个异常该对外面说成什么。

    三种,各有各的说法:

    - 资源类(库被占着 / 存储写不进去):那是"环境暂时用不了",调用方该
      去处理环境,而不是换个参数重试。
    - 我们自己抛的人话(如"symbol 不能为空"):原文留着 —— 调用方据此
      改参数,只说"失败了"对它没有任何用。
    - 第三方库抛的:只说"原因见服务日志"。原始报错里有本机路径、内部
      表名与整条 SQL,那些是内部实现,不该出现在响应正文里。

    `source` 是这条通道的名字(命令行 / 接口 / MCP),只进日志,不出现在
    正文里。
    """
    from forgemind.core.data.storage import is_resource_error, resource_unavailable_reason

    if is_resource_error(exc):
        return resource_unavailable_reason(exc)
    if is_our_own_error(exc):
        return str(exc).strip() or "没有更多细节"

    from forgemind.core.observability.logging import logger

    logger.error("external_failure", source=source, error_type=type(exc).__name__)
    logger.debug("external_failure_detail", source=source, error=str(exc))
    return "原因见服务日志"


def safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    """诊断上下文里哪些能回吐给调用方。

    数字、布尔与短句可以;带内部痕迹的、嵌套的、对象一律丢掉。丢掉比
    改写好:改写会让人以为拿到的是原文。
    """
    out: dict[str, Any] = {}
    for key, value in (details or {}).items():
        name = str(key)
        if looks_internal(name):
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            out[name] = value
        elif isinstance(value, str):
            if value and len(value) <= 200 and not looks_internal(value):
                out[name] = value
    return out
