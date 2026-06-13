"""
统一配置管理 - P0-3 修复
所有敏感配置从环境变量读取，有默认值兜底。
"""

import os

_pg_host = os.getenv("PG_HOST", "/var/run/postgresql")
_pg_use_socket = _pg_host.startswith("/")

PG_CONFIG = {
    "host": _pg_host,
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", "limit123"),
    "dbname": os.getenv("PG_DBNAME", "quant"),
    **({} if _pg_use_socket else {"port": int(os.getenv("PG_PORT", "5432"))}),
}
