# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

"""
ForgeMind API 服务入口

支持 CLI 启动:
    python -m forgemind.api.main --host 127.0.0.1 --port 8008

用于 Tauri 桌面端 sidecar 模式。
"""
from __future__ import annotations

import argparse
import sys

# 延迟导入，避免在 --help 时触发全量 import
def main():
    parser = argparse.ArgumentParser(
        prog="forgemind.api",
        description="ForgeMind API server",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--workers", type=int, default=1, help="Worker count (default: 1, production use uvicorn directly)")
    args = parser.parse_args()

    import uvicorn
    from forgemind.api.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level="info",
    )


if __name__ == "__main__":
    main()
