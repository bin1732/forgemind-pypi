# Security Policy

## Supported Versions

| Version | Supported          | Notes               |
| ------- | ------------------ | ------------------- |
| 2026.09 | ✅ Latest           | Initial open source |

## Reporting a Vulnerability

如果你发现安全漏洞,**请不要在 GitHub Issues 里公开**。

请通过以下方式私下联系我:

- **GitHub Security Advisories**: https://github.com/bin1732/ForgeMind/security/advisories/new
- **Email**: (GitHub Security Advisory 里填写)

我会在 **48 小时内** 确认收到,并在 **7 天内** 给出处理计划。

## 安全原则

- ForgeMind **不内置券商 SDK**,不持有用户资金
- **不发送用户数据到第三方** (除用户配置的 LLM API)
- 所有 API secret 只从环境变量读取,从不硬编码
- `pip install -e .` 时不执行网络请求
- 本地数据(DuckDB)默认存储在 `./data/`,可配置路径

## 已知限制

- AKShare / tushare 数据仅用于研究,不对准确性负责
- 不保证 LLM 生成的交易信号有效性
- 本项目**不构成投资建议**