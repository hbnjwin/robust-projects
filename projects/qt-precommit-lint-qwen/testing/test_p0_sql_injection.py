"""
测试 P0-2: SQL 注入修复验证
检查所有文件是否已移除 f-string SQL 拼接，改为参数化查询。
"""

import sys
import os
import re
import ast

sys.path.insert(0, "/home/tulin/quant")

# 需要检查的文件列表
SQLITE_FILES = [
    "main.py",
    "walk_forward.py",
    "run_upgrade.py",
    "optimize_ma.py",
    "run_portfolio.py",
    "run_portfolio_risk.py",
    "run_portfolio_rebalance.py",
    "run_portfolio_vol_weight.py",
    "run_portfolio_hedge.py",
]

PSYCOPG_FILES = [
    "live/data_loader.py",
]

BASE = "/home/tulin/quant"

# 危险模式：f-string 中包含 SQL 关键字
DANGEROUS_PATTERNS = [
    re.compile(r"""f["'].*(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM).*\{.*\}.*["']""", re.IGNORECASE),
    re.compile(r'''f""".*(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM).*\{.*\}.*"""''', re.IGNORECASE | re.DOTALL),
]


def check_no_fstring_sql(filepath):
    """检查文件中没有 f-string SQL 拼接"""
    with open(filepath, "r") as f:
        content = f.read()

    for pattern in DANGEROUS_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            return False, f"发现 f-string SQL: {matches[0][:80]}..."
    return True, "无 f-string SQL"


def check_has_params(filepath, placeholder):
    """检查文件中使用了参数化查询"""
    with open(filepath, "r") as f:
        content = f.read()

    if "read_sql" in content:
        if "params=" in content or "params =" in content:
            return True, f"使用了 params= 参数化查询"
        # 有些文件可能没有 read_sql（如纯 execute）
        return False, "read_sql 未使用 params="

    # 对于不使用 read_sql 的文件，检查是否有参数化 execute
    if placeholder in content:
        return True, f"使用了 {placeholder} 占位符"

    return True, "无 SQL 查询需要检查"


def check_config_import(filepath):
    """检查 P0-3: 是否从 config.py 导入 PG_CONFIG"""
    with open(filepath, "r") as f:
        content = f.read()

    if "PG_CONFIG" not in content:
        return True, "不涉及 PG_CONFIG"

    if "from config import PG_CONFIG" in content:
        return True, "已从 config 导入"

    # 检查是否还有硬编码的密码
    if '"limit123"' in content or "'limit123'" in content:
        return False, "仍有硬编码密码"

    return True, "PG_CONFIG 来源正常"


def test_sqlite_files():
    print("=== 测试 SQLite 文件参数化 (? 占位符) ===")
    all_pass = True

    for fname in SQLITE_FILES:
        fpath = os.path.join(BASE, fname)
        ok1, msg1 = check_no_fstring_sql(fpath)
        ok2, msg2 = check_has_params(fpath, "?")

        status = "✅" if (ok1 and ok2) else "❌"
        print(f"  {status} {fname}: {msg1} | {msg2}")

        if not ok1 or not ok2:
            all_pass = False

    assert all_pass, "FAIL: 部分 SQLite 文件仍有 SQL 注入风险"
    print("  SQLite 文件全部通过\n")


def test_psycopg_files():
    print("=== 测试 psycopg 文件参数化 (%s 占位符) ===")
    all_pass = True

    for fname in PSYCOPG_FILES:
        fpath = os.path.join(BASE, fname)
        ok1, msg1 = check_no_fstring_sql(fpath)
        ok2, msg2 = check_has_params(fpath, "%s")

        status = "✅" if (ok1 and ok2) else "❌"
        print(f"  {status} {fname}: {msg1} | {msg2}")

        if not ok1 or not ok2:
            all_pass = False

    assert all_pass, "FAIL: 部分 psycopg 文件仍有 SQL 注入风险"
    print("  psycopg 文件全部通过\n")


def test_no_hardcoded_password():
    print("=== 测试 P0-3: 无硬编码密码 ===")
    all_pass = True

    pg_files = [
        "live/data_loader.py",
        "factor/build_core_factors.py",
        "update_data_pg.py",
        "run_backtest_pg.py",
        "data/import_full_market_copy.py",
        "data/import_full_market_akshare.py",
    ]

    for fname in pg_files:
        fpath = os.path.join(BASE, fname)
        ok, msg = check_config_import(fpath)
        status = "✅" if ok else "❌"
        print(f"  {status} {fname}: {msg}")
        if not ok:
            all_pass = False

    # 检查 config.py 存在且从环境变量读取
    config_path = os.path.join(BASE, "config.py")
    assert os.path.exists(config_path), "FAIL: config.py 不存在"
    with open(config_path) as f:
        content = f.read()
    assert "os.getenv" in content, "FAIL: config.py 未使用环境变量"
    print(f"  ✅ config.py: 使用环境变量读取配置")

    assert all_pass, "FAIL: 部分文件仍有硬编码密码"
    print("  硬编码密码检查全部通过\n")


if __name__ == "__main__":
    test_sqlite_files()
    test_psycopg_files()
    test_no_hardcoded_password()
    print("=" * 50)
    print("P0-2 (SQL注入) + P0-3 (硬编码密码) 全部测试通过 ✅")
