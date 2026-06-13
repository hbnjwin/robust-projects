import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qmt_broker.tick_archive import PostgresTickArchive


class TickArchiveAggregationTest(unittest.TestCase):
    def test_aggregate_rows_to_1m_5m_and_15m_bars(self) -> None:
        archive = PostgresTickArchive("")
        rows = [
            {
                "tick_time_ms": 1773811800000,
                "last_price": 10.00,
                "volume": 100,
                "amount": 1000.0,
            },
            {
                "tick_time_ms": 1773811830000,
                "last_price": 10.10,
                "volume": 140,
                "amount": 1404.0,
            },
            {
                "tick_time_ms": 1773811920000,
                "last_price": 10.20,
                "volume": 180,
                "amount": 1816.0,
            },
            {
                "tick_time_ms": 1773812100000,
                "last_price": 10.05,
                "volume": 260,
                "amount": 2620.0,
            },
        ]

        one_minute = archive._aggregate_rows_to_bars(rows, 1, 20)
        self.assertEqual(len(one_minute), 3)
        self.assertEqual(one_minute[0]["open"], 10.00)
        self.assertEqual(one_minute[0]["close"], 10.10)
        self.assertEqual(one_minute[0]["volume"], 140)
        self.assertEqual(one_minute[1]["close"], 10.20)
        self.assertEqual(one_minute[2]["close"], 10.05)

        five_minute = archive._aggregate_rows_to_bars(rows, 5, 20)
        self.assertEqual(len(five_minute), 2)
        self.assertEqual(five_minute[0]["open"], 10.00)
        self.assertEqual(five_minute[0]["high"], 10.20)
        self.assertEqual(five_minute[0]["close"], 10.20)
        self.assertEqual(five_minute[1]["close"], 10.05)

        fifteen_minute = archive._aggregate_rows_to_bars(rows, 15, 20)
        self.assertEqual(len(fifteen_minute), 1)
        self.assertEqual(fifteen_minute[0]["open"], 10.00)
        self.assertEqual(fifteen_minute[0]["close"], 10.05)
        self.assertEqual(fifteen_minute[0]["volume"], 260)

    def test_build_feature_summary(self) -> None:
        archive = PostgresTickArchive("")
        rows = [
            {
                "tick_time_ms": 1773808200000,
                "last_price": 10.00,
                "volume": 100,
                "amount": 1000.0,
            },
            {
                "tick_time_ms": 1773810000000,
                "last_price": 10.30,
                "volume": 180,
                "amount": 1824.0,
            },
            {
                "tick_time_ms": 1773817200000,
                "last_price": 10.10,
                "volume": 260,
                "amount": 2632.0,
            },
            {
                "tick_time_ms": 1773819000000,
                "last_price": 10.40,
                "volume": 320,
                "amount": 3256.0,
            },
        ]

        summary = archive._build_feature_summary(rows, "600196.SH", "2026-03-18")
        self.assertEqual(summary["symbol"], "600196.SH")
        self.assertEqual(summary["trade_date"], "2026-03-18")
        self.assertEqual(summary["tick_count"], 4)
        self.assertEqual(summary["open"], 10.00)
        self.assertEqual(summary["close"], 10.40)
        self.assertEqual(summary["high"], 10.40)
        self.assertEqual(summary["low"], 10.00)
        self.assertEqual(summary["volume_total"], 320)
        self.assertEqual(summary["bar_count_15m"], 4)
        self.assertAlmostEqual(summary["day_return_pct"], 4.0)


if __name__ == "__main__":
    unittest.main()
