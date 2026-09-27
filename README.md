# ForgeMind

**Quant trading research & execution platform** — Apache-2.0.

ForgeMind gives quants a research harness, backtest engine, agent framework, and execution layer in one toolchain. Everything runs locally; no cloud lock-in.

## Install

### via PyPI (GitHub Pages index)

```bash
pip install --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/forgemind/ forgemind
```

### with ML extras (PyTorch CPU)

```bash
pip install forgemind[ml] --extra-index-url https://download.pytorch.org/whl/cpu --extra-index-url https://bin1732.github.io/forgemind-pypi/pypi/simple/forgemind/
```

Dependencies (polars, fastapi, langchain, etc.) auto-install.

## Quick start

```bash
forgemind info
forgemind backtest --start 2024-01-01 --end 2024-12-31
```

## Standalone binaries

Pre-built binaries for every push to the [Continuous release](https://github.com/bin1732/forgemind-pypi/releases/tag/continuous):

| Platform    | File                          | Size  |
|-------------|-------------------------------|-------|
| Linux x86_64  | `forgemind-linux`           | 563 MB |
| macOS arm64   | `forgemind-macos`           | 162 MB |
| Windows x64   | `forgemind-windows-x64.exe` | 193 MB |

```bash
# Linux
curl -L -o forgemind https://github.com/bin1732/forgemind-pypi/releases/download/continuous/forgemind-linux
chmod +x forgemind && ./forgemind info

# macOS
curl -L -o forgemind https://github.com/bin1732/forgemind-pypi/releases/download/continuous/forgemind-macos
chmod +x forgemind && ./forgemind info

# Windows (PowerShell)
Invoke-WebRequest -Uri https://github.com/bin1732/forgemind-pypi/releases/download/continuous/forgemind-windows-x64.exe -OutFile forgemind.exe
.\\forgemind.exe info
```

## Documentation

- [Source README](https://github.com/bin1732/forgemind#readme)
- [CHANGELOG](https://github.com/bin1732/forgemind/blob/main/CHANGELOG.md)
- [Manifest](releases/builds/manifest.json)

## License

Apache-2.0 — see [LICENSE](LICENSE)
