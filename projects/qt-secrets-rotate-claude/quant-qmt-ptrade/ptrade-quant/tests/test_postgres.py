from __future__ import annotations

import json
import unittest

from ptrade_quant.config import PostgresConfig
from ptrade_quant.models import Level
from ptrade_quant.postgres import _json_ready, _payload_count, _top_of_book


class PostgresConfigTests(unittest.TestCase):
    def test_default_watchlist_table_priority_prefers_ptrade_table(self) -> None:
        config = PostgresConfig()
        self.assertEqual(config.watchlist_table_priority, ["watchlist_ptrade", "watchlist"])


class PostgresHelperTests(unittest.TestCase):
    def test_top_of_book_extracts_first_level(self) -> None:
        price, volume = _top_of_book([Level(price=10.01, volume=1200), Level(price=10.00, volume=900)])
        self.assertEqual(price, 10.01)
        self.assertEqual(volume, 1200)

    def test_top_of_book_handles_empty_levels(self) -> None:
        price, volume = _top_of_book([])
        self.assertIsNone(price)
        self.assertIsNone(volume)

    def test_json_ready_handles_nested_mapping(self) -> None:
        payload = {"600519.SS": [{"price": 10.0, "qty": 1000}]}
        converted = _json_ready(payload)
        self.assertEqual(json.dumps(converted, ensure_ascii=False), '{"600519.SS": [{"price": 10.0, "qty": 1000}]}')

    def test_payload_count_prefers_symbol_bucket(self) -> None:
        payload = {"600519.SS": [1, 2, 3], "other": [4]}
        self.assertEqual(_payload_count(payload, "600519.SS"), 3)


if __name__ == "__main__":
    unittest.main()
