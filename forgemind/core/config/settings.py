# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def data_path(*parts: str) -> Path:
    """数据目录下的一个路径 —— 跟着设置里的 data_dir 走。

    服务进程(桌面端的 sidecar)不该把数据写在当前目录:那可能是只读的
    安装目录。统一走 data_dir,桌面端把它指到用户自己的地方就跟着走。
    """
    return Path(get_settings().data_dir).joinpath(*parts)


def _pkg_version() -> str:
    """版本号单一真源:包内 __version__ → importlib.metadata 兜底

    关键观察:`from forgemind import __version__` 总是从**当前**
    Python 解释器实际加载的 forgemind 包里取 init.py 字符串:
      - 装 wheel:从 site-packages/forgemind/__init__.py(wheel 内置)
      - 开发模式(源码):从 sys.path 首位源码树里的 forgemind/__init__.py
    这两个必须保持一致(wheel build 脚本要 sed 替换成 pyproject 版本)。

    `importlib.metadata.version()` 只读 dist-info,不能区分源码运行
    与已装包,可能优先命中旧版 dist-info,把运行时实际加载的代码盖掉。
    metadata 仅作兜底。

    优先读包内 `__version__` (真实运行的代码),回退到 metadata (用于
    在 `__version__` 不可用时报告).
    """
    try:
        from forgemind import __version__

        return __version__
    except Exception:  # pragma: no cover - 极端导入顺序
        pass
    try:
        from importlib.metadata import version as _im_version

        return _im_version("forgemind")
    except Exception:
        return "unknown"


class Settings(BaseSettings):
    """主配置"""

    model_config = SettingsConfigDict(
        env_prefix="FORGEMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    env: Literal["dev", "staging", "prod"] = "dev"
    mode: Literal["server", "desktop", "cli"] = "server"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    data_dir: str = "./data"
    version: str = Field(default_factory=lambda: _pkg_version())

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_secret_key: str = Field(
        default="dev-only-insecure-key-do-not-use-in-prod!!",
        min_length=32,
    )

    @field_validator("api_secret_key")
    @classmethod
    def _validate_secret_key(cls, v: str, info) -> str:
        """生产环境必须显式设置 API_SECRET_KEY,不能使用 dev 默认值"""
        env = info.data.get("env", "dev")
        dev_default = "dev-only-insecure-key-do-not-use-in-prod!!"
        if env in ("prod", "production") and v == dev_default:
            raise ValueError(
                "生产环境禁止使用 dev 默认 api_secret_key,"
                "请通过 FORGEMIND_API_SECRET_KEY 环境变量设置强随机密钥"
            )
        return v

    api_jwt_alg: str = "HS256"
    api_jwt_expire_hours: int = 24
    api_cors_origins: str | list[str] = Field(
        default_factory=lambda: "*"
    )  # 桌面端 webview 不受 CORS,但允许浏览器调试,默认全开

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v):
        """接受任意大小写的环境变量写法

        规范化大小写:shell 用户常写小写,这里统一转成大写,
        避免 pydantic ValidationError 抛一整页堆栈。
        """
        if isinstance(v, str):
            return v.strip().upper()
        return v

    # PG
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "forgemind"
    pg_password: str = "forgemind"
    pg_database: str = "forgemind"
    pg_pool_size: int = 10
    pg_max_overflow: int = 20

    # ClickHouse
    ch_host: str = "localhost"
    ch_port: int = 9000
    ch_http_port: int = 8123
    ch_user: str = "forgemind"
    ch_password: str = "forgemind"
    ch_database: str = "forgemind"

    # Valkey
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # NATS
    nats_url: str = "nats://localhost:4222"
    nats_cluster_name: str = "forgemind-cluster"

    # DuckDB —— 默认从 data_dir 派生。
    #
    # 以前它写死 "./data/duckdb/main.db",于是只改 data_dir 的话库不会跟着
    # 走:桌面端把数据目录指到用户目录,库却还落在当前目录 —— 两处指着不同
    # 的地方,面板读到的就是另一个库(空的)。显式设 FORGEMIND_DUCKDB_PATH
    # 仍然优先。
    duckdb_path: str = ""

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "forgemind"
    minio_secret_key: str = "forgemind"
    minio_bucket: str = "forgemind"

    # Vault
    vault_addr: str = "http://localhost:8200"
    vault_token: str = "dev-only-token"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    qwen_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    mistral_api_key: str = ""

    # Brokers: ForgeMind 不内置券商 SDK(v1.0 起完全解耦)
    # 用户用 vnpy / nautilus_trader / 自己 broker SDK 执行信号
    # 见 §24 L7 信号输出层

    # Data
    tushare_token: str = ""

    # Feature Store
    feature_ic_alert_threshold: float = 0.02
    feature_offline_online_parity_threshold: float = 0.01

    # Observability
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

    # Desktop
    desktop_api_port: int = 8008

    @model_validator(mode="after")
    def _derive_duckdb_path(self) -> "Settings":
        if not self.duckdb_path:
            # object.__setattr__: 绕开赋值校验,免得又触发一次自己
            object.__setattr__(self, "duckdb_path", str(Path(self.data_dir) / "duckdb" / "main.db"))
        return self

    @property
    def pg_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def __repr__(self) -> str:
        return f"<Settings env={self.env} mode={self.mode} version={self.version}>"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例 — 整个 app 一份"""
    return Settings()
