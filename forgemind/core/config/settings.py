# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

from functools import lru_cache
from typing import Literal, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    version: str = "2026.09.0"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_secret_key: str = Field(
        default="dev-only-insecure-key-do-not-use-in-prod!!",
        min_length=32,
    )
    api_jwt_alg: str = "HS256"
    api_jwt_expire_hours: int = 24
    api_cors_origins: Union[str, List[str]] = Field(default_factory=lambda: "http://localhost:3000,tauri://localhost")

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
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
    
    # DuckDB
    duckdb_path: str = "./data/duckdb/main.db"
    
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