from __future__ import annotations

import unittest

from ptrade_quant.config import SignalConfig
from ptrade_quant.models import Level, PositionSnapshot, QuoteSnapshot
from ptrade_quant.normalizers import normalize_quote
from ptrade_quant.signals import RealtimeSignalEngine


class NormalizeQuoteTests(unittest.TestCase):
    def test_normalize_quote_handles_string_ladder(self) -> None:
        quote = normalize_quote(
            "600000.SS",
            {
                "tick": {
                    "last_price": 10.05,
                    "bid_grp": ["[[10.04, 1000], [10.03, 500]]"],
                    "ask_grp": ["[[10.05, 800], [10.06, 700]]"],
                }
            },
        )

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.last_price, 10.05)
        self.assertEqual(quote.bid[0].price, 10.04)
        self.assertEqual(quote.ask[0].volume, 800.0)


class SignalEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RealtimeSignalEngine(SignalConfig())

    def test_generates_buy_when_flow_and_momentum_align(self) -> None:
        quote1 = QuoteSnapshot(
            symbol="600000.SS",
            timestamp="09:30:00",
            last_price=10.00,
            bid=[Level(9.99, 1000), Level(9.98, 900)],
            ask=[Level(10.00, 500), Level(10.01, 400)],
        )
        quote2 = QuoteSnapshot(
            symbol="600000.SS",
            timestamp="09:30:03",
            last_price=10.06,
            bid=[Level(10.05, 3000), Level(10.04, 2500)],
            ask=[Level(10.06, 600), Level(10.07, 500)],
        )

        self.engine.process(quote1, None, now_epoch=1.0)
        decision = self.engine.process(quote2, None, now_epoch=100.0)

        self.assertEqual(decision.action, "BUY")

    def test_generates_sell_on_stop_loss(self) -> None:
        position = PositionSnapshot(
            symbol="600000.SS",
            quantity=1000,
            available_quantity=1000,
            cost_basis=10.0,
        )
        quote1 = QuoteSnapshot(
            symbol="600000.SS",
            timestamp="09:30:00",
            last_price=10.00,
            bid=[Level(9.99, 1000)],
            ask=[Level(10.00, 800)],
        )
        quote2 = QuoteSnapshot(
            symbol="600000.SS",
            timestamp="09:31:00",
            last_price=9.75,
            bid=[Level(9.74, 900)],
            ask=[Level(9.75, 950)],
        )

        self.engine.process(quote1, position, now_epoch=1.0)
        decision = self.engine.process(quote2, position, now_epoch=100.0)

        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.reason, "stop_loss")


if __name__ == "__main__":
    unittest.main()
