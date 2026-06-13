"""pytest conftest -- shared fixtures for quant test suite."""
import sys
from pathlib import Path

import pytest

# Add project root to sys.path so all modules are importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------

def _pg_config_from_env():
    """Read PostgreSQL connection parameters from environment variables,
    mirroring the defaults in config.py."""
    import os

    host = os.getenv("PG_HOST", "/var/run/postgresql")
    use_socket = host.startswith("/")
    cfg = {
        "host": host,
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.getenv("PG_PASSWORD", "limit123"),
        "dbname": os.getenv("PG_DBNAME", "quant"),
    }
    if not use_socket:
        cfg["port"] = int(os.getenv("PG_PORT", "5432"))
    return cfg


@pytest.fixture(scope="session")
def db_connection():
    """Yield a live psycopg connection to PostgreSQL.

    The connection is reused across all tests in the session and closed
    on teardown.  If psycopg is not installed or the database is
    unreachable the entire test is automatically skipped.
    """
    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg not installed -- skipping DB tests")

    cfg = _pg_config_from_env()
    try:
        conn = psycopg.connect(**cfg)
    except Exception as exc:
        pytest.skip(f"Cannot connect to PostgreSQL: {exc}")

    yield conn

    conn.close()
