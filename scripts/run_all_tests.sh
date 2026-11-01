#!/usr/bin/env bash
# 跑**全部**测试文件,不做任何排除。
#
# 曾经的教训:用 `grep -v multimodal_storage` 排除重文件以省内存,
# 结果我改了 EmbeddingsModel.embed 的行为之后,那些被排除的文件里
# 一直藏着失败的测试,连续好几轮"全绿"都是假的。
# 三视角验证必须能发现这一类问题,所以这里不允许排除。
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-/workspace/.venv/bin/python}"
exec "$PY" -m pytest tests/ -q -p no:cacheprovider -m "not slow" --tb=line "$@"
