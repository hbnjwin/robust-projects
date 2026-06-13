import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.providers.mock import MockMarketDataProvider
from qmt_broker.security_master import PostgresSecurityMasterStore, SecurityMasterSyncOptions, sync_security_master


class FakeSecurityMasterStore(PostgresSecurityMasterStore):
    def __init__(self) -> None:
        super().__init__("postgresql://fake")
        self.rows = []

    def upsert_records(self, rows):  # type: ignore[no-untyped-def]
        self.rows.extend(list(rows))
        return len(self.rows)


class SecurityMasterTest(unittest.TestCase):
    def test_sync_security_master_merges_sector_symbols_and_detail(self) -> None:
        provider = MockMarketDataProvider()
        store = FakeSecurityMasterStore()
        result = sync_security_master(
            provider,
            store,
            SecurityMasterSyncOptions(sectors=("沪A", "深A"), include_detail=True, dry_run=False),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["symbol_count"], 4)
        self.assertEqual(result["written"], 4)
        self.assertEqual(store.rows[0]["import_source"], "mock")
        self.assertIn("sector_names", store.rows[0])


if __name__ == "__main__":
    unittest.main()
