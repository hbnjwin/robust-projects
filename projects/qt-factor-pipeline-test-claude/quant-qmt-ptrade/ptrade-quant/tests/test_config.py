from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ptrade_quant.config import load_runtime_config, normalize_symbol


class SymbolNormalizationTests(unittest.TestCase):
    def test_normalize_symbol_maps_shenzhen_and_shanghai_suffixes(self) -> None:
        self.assertEqual(normalize_symbol("600519.SH"), "600519.SS")
        self.assertEqual(normalize_symbol("600519.XSHG"), "600519.SS")
        self.assertEqual(normalize_symbol("000001.XSHE"), "000001.SZ")
        self.assertEqual(normalize_symbol("430001.BJ"), "430001.BJ")

    def test_load_runtime_config_normalizes_and_deduplicates_watchlist(self) -> None:
        payload = {
            "watchlist": ["600519.SH", "600519.SS", "000001.XSHE", " "],
            "signal": {},
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "live_config.json"
            config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            config = load_runtime_config(config_path)

        self.assertEqual(config.watchlist, ["000001.SZ", "600519.SS"])


if __name__ == "__main__":
    unittest.main()
