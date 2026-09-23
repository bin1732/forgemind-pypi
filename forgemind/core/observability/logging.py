# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import sys
import logging
import structlog
from typing import Any

from forgemind.core.config.settings import get_settings


def setup_logging() -> None:
    """全局日志初始化"""
    settings = get_settings()
    
    # stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    
    # structlog 配置
    shared_processors = [
        # 上下文变量
        structlog.contextvars.merge_contextvars,
        # 时间戳
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 日志级别
        structlog.processors.add_log_level,
        # 调用栈
        structlog.processors.StackInfoRenderer(),
        # 异常格式化
        structlog.processors.format_exc_info,
    ]
    
    if settings.log_format == "json":
        # 生产:JSON
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # 开发:彩色 console
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """获取 logger"""
    return structlog.get_logger(name, **initial_values)


# 模块级 logger
logger = get_logger("forgemind")


# 错误码体系(全局)
class ErrorCode:
    """错误码常量"""
    # 1000-1999: 系统错误
    INTERNAL_ERROR = 1000
    CONFIG_ERROR = 1001
    DB_CONNECTION_ERROR = 1002
    BROKER_CONNECTION_ERROR = 1003
    
    # 2000-2999: 数据错误
    DATA_NOT_FOUND = 2000
    DATA_INVALID = 2001
    DATA_STALE = 2002
    PARITY_FAILED = 2003
    
    # 3000-3999: 策略错误
    STRATEGY_INVALID = 3000
    STRATEGY_COMPILE_ERROR = 3001
    STRATEGY_RUNTIME_ERROR = 3002
    STRATEGY_BLACKLIST_HIT = 3003
    
    # 4000-4999: 风控错误
    RISK_DAILY_LOSS_LIMIT = 4000
    RISK_POSITION_LIMIT = 4001
    RISK_DAILY_ORDER_LIMIT = 4002
    RISK_CANCEL_RATIO = 4003
    KILL_SWITCH_TRIGGERED = 4099
    
    # 5000-5999: 合规错误
    COMPLIANCE_KYC_FAILED = 5000
    COMPLIANCE_BLACKLIST = 5001
    COMPLIANCE_REPORT_REQUIRED = 5002
    
    # 6000-6999: Broker 错误
    BROKER_ORDER_REJECTED = 6000
    BROKER_DISCONNECTED = 6001
    BROKER_TIMEOUT = 6002
    
    # 7000-7999: AI Agent 错误
    AGENT_INVALID_OUTPUT = 7000
    AGENT_HUMAN_REVIEW_REQUIRED = 7001
    AGENT_ROUTER_FAILED = 7002


class ForgeMindError(Exception):
    """基异常"""
    code: int = ErrorCode.INTERNAL_ERROR
    status_code: int = 500
    
    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details
        logger.error(
            "error_raised",
            error_class=self.__class__.__name__,
            error_code=self.code,
            message=message,
            **details,
        )


class ConfigError(ForgeMindError):
    code = ErrorCode.CONFIG_ERROR
    status_code = 500


class DataError(ForgeMindError):
    code = ErrorCode.DATA_INVALID
    status_code = 422


class StrategyError(ForgeMindError):
    code = ErrorCode.STRATEGY_INVALID
    status_code = 422


class RiskError(ForgeMindError):
    code = ErrorCode.RISK_DAILY_LOSS_LIMIT
    status_code = 403


class BrokerError(ForgeMindError):
    code = ErrorCode.BROKER_ORDER_REJECTED
    status_code = 502


class AgentError(ForgeMindError):
    code = ErrorCode.AGENT_INVALID_OUTPUT
    status_code = 503