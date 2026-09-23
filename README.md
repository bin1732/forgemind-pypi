# ForgeMind

**Quant trading research & execution platform** — Apache-2.0.

ForgeMind gives quants a research harness, backtest engine, agent framework, and execution layer in one toolchain. Everything runs locally; no cloud lock-in.

## Install

```bash
pip install forgemind
```

Dependencies (polars, fastapi, langchain, etc.) auto-install.

## Quick start

```bash
forgemind info
forgemind backtest --start 2024-01-01 --end 2024-12-31
# Returns: Total Return ~50%, Sharpe ~1.0, Max DD ~-25%, 10 trades
```

## Standalone binaries

Pre-built binaries are attached to [Release v2026.09](https://github.com/bin1732/forgemind-pypi/releases/tag/v2026.09):

| Platform | File | Size |
|----------|------|------|
| Linux x86_64 | `forgemind-linux` | 186 MB |
| Windows x64 | `forgemind-windows.exe` | 9.4 MB |
| macOS arm64 | `forgemind-macos-arm64` | 8.6 MB |

```bash
chmod +x forgemind-linux && ./forgemind-linux info
```

## Documentation

- [README](https://github.com/bin1732/forgemind#readme)
- [CHANGELOG](https://github.com/bin1732/forgemind/blob/main/CHANGELOG.md)

## License

Apache-2.0 — see [LICENSE](LICENSE)
