# Copyright (c) 2026 灵感引擎工坊 (bin1732)
# SPDX-License-Identifier: Apache-2.0

import sys
import os

# 在所有测试前 patch langchain.debug (langchain-core 0.3.x 依赖它)
try:
    import langchain
    if not hasattr(langchain, 'debug'):
        langchain.debug = False
except ImportError:
    pass
