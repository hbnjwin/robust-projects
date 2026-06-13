"""
conftest.py — pytest shared fixtures for quant-qmt-ptrade testing

Provides:
  - sys.path bootstrapping (project root)
  - db_connection fixture  (PostgreSQL, auto-skip when unavailable)
  - make_market_data helper fixture (synthetic行情数据)
"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# 1. Bootstrap: add project root to sys.path so `from core.xxx import ...` etc.
#    work without installing the package.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 2. PostgreSQL fixture — controlled by environment variables.
#
#    Env vars (with sensible defaults):
#      PG_HOST     default 127.0.0.1
#      PG_PORT     default 5432
#      PG_USER     default postgres
#      PG_PASSWORD default postgres
#      PG_DBNAME   default quant
#
#    If psycopg is not installed, or the connection fails, the fixture
#    calls pytest.skip() so the dependent test is *skipped* (not failed).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pg_available():
    """Return True if a live PostgreSQL connection can be established."""
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def db_connection(pg_available):
    """
    Yield a live psycopg connection for integration tests.

    Skips the test when:
      - psycopg is not installed
      - environment variable PG_SKIP=1 is set
      - the connection cannot be established (e.g. CI without PG)
    """
    if not pg_available:
        pytest.skip("psycopg is not installed — skipping DB tests")

    if os.environ.get("PG_SKIP", "").strip() in ("1", "true", "yes"):
        pytest.skip("PG_SKIP is set — skipping DB tests")

    import psycopg

    conn_params = dict(
        host=os.environ.get("PG_HOST", "127.0.0.1"),
        port=int(os.environ.get("PG_PORT", 5432)),
        user=os.environ.get("PG_USER", "postgres"),
        password=os.environ.get("PG_PASSWORD", "postgres"),
        dbname=os.environ.get("PG_DBNAME", "quant"),
    )

    try:
        conn = psycopg.connect(**conn_params)
    except Exception as exc:
        pytest.skip(f"Cannot connect to PostgreSQL ({exc}) — skipping DB tests")

    yield conn

    conn.close()


# ---------------------------------------------------------------------------
# 3. Synthetic market-data helper (shared across phase tests)
# ---------------------------------------------------------------------------
def _make_market_data(n_days=30, n_stocks=5, start="2024-01-01", seed=42):
    """
    Build a dict-of-dicts mimicking the real market-data layout:

        { "2024-01-01": { "000000.SZ": {"close", "volume", "prev_close"}, ... }, ... }
    """
    from datetime import datetime, timedelta

    rng = np.random.RandomState(seed)
    data: dict = {}
    base = {f"{i:06d}.SZ": 10.0 + i for i in range(n_stocks)}
    dt = datetime.strptime(start, "%Y-%m-%d")

    for d in range(n_days):
        date = (dt + timedelta(days=d)).strftime("%Y-%m-%d")
        day: dict = {}
        for code, price in base.items():
            prev = price
            close = round(prev * (1 + rng.normal(0, 0.01)), 2)
            close = max(close, 0.1)
            day[code] = {"close": close, "volume": 1_000_000, "prev_close": prev}
            base[code] = close
        data[date] = day

    return data


@pytest.fixture
def make_market_data():
    """Fixture exposing the helper so tests can call it with custom params."""
    return _make_market_data


@pytest.fixture
def sample_market_data():
    """Pre-built 30-day, 5-stock dataset for quick use."""
    return _make_market_data(n_days=30, n_stocks=5)
