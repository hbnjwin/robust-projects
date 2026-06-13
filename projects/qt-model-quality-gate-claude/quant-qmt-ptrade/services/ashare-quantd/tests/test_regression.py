from datetime import timedelta
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, settings  # type: ignore
from app.models import (  # type: ignore
    AdviceRequest,
    BrokerAccountSummary,
    BrokerCancelRequest,
    BrokerKillSwitchState,
    BrokerKillSwitchRequest,
    BrokerOrderRequest,
    Bar,
    BrokerOrdersResponse,
    BarsResponse,
    BrokerPosition,
    BrokerPositionsResponse,
    Confidence,
    ImpactDirection,
    Indicators,
    IntelIngestRequest,
    IntelReport,
    IntelSchedulerStatus,
    IntelSectorContext,
    IntelSummary,
    LimitStatus,
    Magnitude,
    MarketDecisionStatus,
    MarketProviderStatus,
    NewsItem,
    PaperOrderResponse,
    Quote,
    ProviderCheck,
    RiskCheckRequest,
    SourceTier,
    TradingStatus,
    WatchlistStatus,
    WatchlistItemRequest,
)
import app.main as main_module  # type: ignore
from app.services import (  # type: ignore
    AdviceService,
    BrokerAdapterService,
    IntelEventStore,
    IntelHistoryService,
    IntelService,
    MarketProviderFacade,
    ProviderError,
    RiskService,
    WatchlistService,
    _provider_error_code,
    _parse_trade_time,
    _now,
)


class FakeIntel:
    effective_provider = "fake_intel"

    def get_report(self, symbol, sector, lookback_hours):
        now = _now()
        event = NewsItem(
            id=f"fake:{symbol or sector}",
            title="收到监管问询并提示风险",
            summary="收到监管问询并提示风险",
            source_name="巨潮资讯",
            source_url="https://example.com/event",
            source_tier=SourceTier.OFFICIAL,
            published_at=now,
            symbols=[symbol] if symbol else [],
            sectors=[sector] if sector else [],
            themes=[],
            event_type="company_disclosure",
            sentiment="negative",
            impact_direction=ImpactDirection.BEARISH,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.HIGH,
        )
        return IntelReport(
            scope={"symbol": symbol, "sector": sector},
            as_of=now,
            headline_events=[event],
            policy_events=[],
            disclosure_events=[event],
            sector_context=IntelSectorContext(
                net_direction=ImpactDirection.MIXED,
                confidence=Confidence.MEDIUM,
            ),
            summary=IntelSummary(top_catalysts=[], top_risks=[]),
        )


class FakeMarket:
    def __init__(self, change_pct: float = 9.68):
        self.change_pct = change_pct

    def get_quote(self, symbol):
        now = _now()
        return Quote(
            symbol=symbol,
            name=symbol,
            last=10.2,
            open=9.8,
            high=10.3,
            low=9.7,
            prev_close=9.3,
            change=0.9,
            change_pct=self.change_pct,
            volume=100000,
            amount=1020000.0,
            turnover_ratio=1.0,
            amplitude_pct=6.0,
            limit_status=LimitStatus.NORMAL,
            trading_status=TradingStatus.TRADING,
            market_time=now,
            source="akshare_spot_em",
            received_at=now,
        )


class FakeIndicators:
    def get_indicators(self, symbol, interval, sets):
        return Indicators(
            symbol=symbol,
            interval=interval,
            latest={"ma20": 9.8, "macd_hist": 0.5, "rsi14": 21.0},
        )


class FakeRisk:
    def check(self, request):
        from app.models import RiskCheckResponse  # type: ignore

        return RiskCheckResponse(status="approved", checks=[], approval_required=False)


class FakePaper:
    def submit_order(self, request):
        return PaperOrderResponse(
            order_id="paper_ord_test",
            status="accepted",
            submitted_at=_now(),
            fill_price=10.1,
            fill_quantity=100,
            requested_quantity=100,
            detail="filled",
        )


class FakeDaemon:
    configured = True
    base_url = "http://127.0.0.1:19090"
    adapter_name = "qmt"

    def status(self):
        return {"status": "ok"}

    def submit_order(self, request):
        from app.models import BrokerOrderResponse  # type: ignore

        return BrokerOrderResponse(
            broker_order_id="daemon_ord_test",
            adapter_mode="qmt_bridge",
            dry_run=False,
            status="accepted",
            submitted_at=_now(),
            approval_required=False,
            risk_status="approved",
            routed_order_id="qmt_ord_001",
            fill_price=request.price,
            fill_quantity=0,
            detail="queued_at_daemon",
        )

    def cancel_order(self, request):
        from app.models import BrokerCancelResponse  # type: ignore

        return BrokerCancelResponse(
            broker_order_id=request.broker_order_id,
            adapter_mode="qmt_bridge",
            dry_run=False,
            status="accepted",
            canceled_at=_now(),
            approval_required=False,
            routed_order_id="qmt_ord_001",
            detail="cancel_forwarded",
        )

    def orders(self, account_id):
        from app.models import BrokerOrderRecord  # type: ignore

        return BrokerOrdersResponse(
            account_id=account_id,
            adapter_mode="qmt_bridge",
            status="ok",
            orders=[
                BrokerOrderRecord(
                    broker_order_id="daemon_ord_test",
                    account_id=account_id,
                    symbol="600519.SH",
                    side="buy",
                    order_type="limit",
                    price=10.0,
                    quantity=100,
                    status="queued",
                    submitted_at=_now(),
                    routed_order_id="qmt_ord_001",
                )
            ],
        )

    def positions(self, account_id):
        return BrokerPositionsResponse(
            account_id=account_id,
            adapter_mode="qmt_bridge",
            status="ok",
            positions=[
                BrokerPosition(
                    account_id=account_id,
                    symbol="600519.SH",
                    quantity=100,
                    avg_cost=10.0,
                    last_price=10.2,
                    market_value=1020.0,
                    unrealized_pnl=20.0,
                    unrealized_pnl_pct=2.0,
                    updated_at=_now(),
                )
            ],
        )

    def account(self, account_id):
        return BrokerAccountSummary(
            account_id=account_id,
            adapter_mode="qmt_bridge",
            status="ok",
            cash=100000.0,
            available_cash=98000.0,
            market_value=1020.0,
            equity=101020.0,
            positions_count=1,
            updated_at=_now(),
        )


class AShareQuantdRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.old_event_store = settings.intel_event_store_path
        self.old_watchlist = settings.watchlist_path
        self.old_alerts = settings.watchlist_alerts_path
        self.old_broker_state = settings.broker_state_path
        self.old_broker_adapter = settings.broker_adapter
        self.old_broker_live_enabled = settings.broker_live_enabled
        self.old_broker_daemon_base_url = settings.broker_daemon_base_url
        settings.intel_event_store_path = f"{self.tmp.name}/intel-events.json"
        settings.watchlist_path = f"{self.tmp.name}/watchlist.json"
        settings.watchlist_alerts_path = f"{self.tmp.name}/watchlist-alerts.json"
        settings.broker_state_path = f"{self.tmp.name}/broker-state.json"
        settings.broker_adapter = "disabled"
        settings.broker_live_enabled = False
        settings.broker_daemon_base_url = "http://127.0.0.1:19090"

    def tearDown(self):
        settings.intel_event_store_path = self.old_event_store
        settings.watchlist_path = self.old_watchlist
        settings.watchlist_alerts_path = self.old_alerts
        settings.broker_state_path = self.old_broker_state
        settings.broker_adapter = self.old_broker_adapter
        settings.broker_live_enabled = self.old_broker_live_enabled
        settings.broker_daemon_base_url = self.old_broker_daemon_base_url
        self.tmp.cleanup()

    def test_intel_history_ingest_and_query(self):
        history = IntelHistoryService(FakeIntel(), IntelEventStore(settings.intel_event_store_path))
        response = history.ingest(IntelIngestRequest(symbol="600519.SH", lookback_hours=72))
        events = history.events("600519.SH", None, None, None, None, 720, 20)
        self.assertEqual(response.added_count, 1)
        self.assertEqual(events.filtered_events, 1)
        self.assertEqual(events.events[0].categories, ["disclosure", "headline"])

    def test_watchlist_scan_generates_alerts(self):
        watchlist = WatchlistService(FakeMarket(), FakeIntel(), FakeIndicators())
        watchlist.upsert_item(WatchlistItemRequest(symbol="600519.SH", sector="白酒"))
        status = watchlist.run_once()
        alerts = watchlist.alerts("600519.SH", None, 20)
        self.assertEqual(status.item_count, 1)
        self.assertGreaterEqual(status.alert_count, 1)
        self.assertIn("negative_official_event", [alert.kind for alert in alerts.alerts])

    def test_broker_adapter_modes(self):
        broker = BrokerAdapterService(FakeMarket(change_pct=1.0), FakeRisk(), FakePaper(), daemon=FakeDaemon())
        disabled = broker.submit_order(
            BrokerOrderRequest(
                account_id="paper-main",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
            )
        )
        broker.set_kill_switch(BrokerKillSwitchRequest(active=False, reason="unit-test"))
        settings.broker_adapter = "dry_run"
        dry_run = broker.submit_order(
            BrokerOrderRequest(
                account_id="paper-main",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
            )
        )
        settings.broker_adapter = "paper_bridge"
        bridged = broker.submit_order(
            BrokerOrderRequest(
                account_id="paper-main",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
            )
        )
        settings.broker_adapter = "qmt_bridge"
        qmt_disabled = broker.submit_order(
            BrokerOrderRequest(
                account_id="paper-main",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
                approval_token="approved-by-operator",
            )
        )
        settings.broker_live_enabled = True
        qmt_submit = broker.submit_order(
            BrokerOrderRequest(
                account_id="paper-main",
                symbol="600519.SH",
                side="buy",
                order_type="limit",
                price=10.0,
                quantity=100,
                approval_token="approved-by-operator",
            )
        )
        qmt_cancel = broker.cancel_order(BrokerCancelRequest(account_id="paper-main", broker_order_id="daemon_ord_test"))
        qmt_orders = broker.orders("paper-main")
        qmt_positions = broker.positions("paper-main")
        qmt_account = broker.account("paper-main")
        self.assertEqual(disabled.detail, "broker_kill_switch_active")
        self.assertEqual(dry_run.status, "accepted_dry_run")
        self.assertEqual(bridged.routed_order_id, "paper_ord_test")
        self.assertEqual(qmt_disabled.detail, "broker_live_disabled")
        self.assertEqual(qmt_submit.routed_order_id, "qmt_ord_001")
        self.assertEqual(qmt_cancel.detail, "cancel_forwarded")
        self.assertEqual(qmt_orders.orders[0].routed_order_id, "qmt_ord_001")
        self.assertEqual(qmt_positions.positions[0].symbol, "600519.SH")
        self.assertEqual(qmt_account.available_cash, 98000.0)

    def test_market_auto_mode_raises_when_no_live_provider_available(self):
        market = MarketProviderFacade()
        market.mode = "auto"
        market._tushare = None
        market._akshare = None

        self.assertEqual(market.effective_provider, "unavailable")
        status = market.provider_status("600519.SH")
        self.assertFalse(status.quote_ready)
        self.assertEqual(status.quote_block_reason, "provider_unavailable")
        self.assertFalse(status.intraday_ready)
        self.assertEqual(status.intraday_block_reason, "provider_unavailable")
        self.assertFalse(status.daily_ready)
        self.assertEqual(status.daily_block_reason, "provider_unavailable")
        with self.assertRaises(ProviderError):
            market.get_quote("600519.SH")
        with self.assertRaises(ProviderError):
            market.get_bars("600519.SH", "1d", 5)

    def test_market_unknown_mode_raises_instead_of_falling_back_to_mock(self):
        market = MarketProviderFacade()
        market.mode = "invalid_mode"

        with self.assertRaises(ProviderError):
            market.get_quote("600519.SH")
        with self.assertRaises(ProviderError):
            market.get_bars("600519.SH", "1d", 5)

    def test_intel_report_raises_when_no_official_data_exists(self):
        intel = IntelService()
        intel._tushare = None
        intel._gov_only_report = lambda symbol, sector, lookback_hours: None
        intel._official_symbol_report = lambda symbol, sector, lookback_hours: None

        self.assertEqual(intel.effective_provider, "cninfo+gov_cn_policy")
        with self.assertRaises(ProviderError):
            intel.get_report("600519.SH", None, 72)

    def test_settings_accepts_tushare_token_env_aliases(self):
        with patch.dict("os.environ", {"TUSHARE_TOKEN": "token-from-legacy-env"}, clear=False):
            cfg = Settings()

        self.assertEqual(cfg.tushare_token, "token-from-legacy-env")

    def test_provider_error_code_distinguishes_network_path_failures(self):
        detail = (
            "akshare minute bars failed: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): "
            "Max retries exceeded (Caused by ProxyError('Unable to connect to proxy', "
            "RemoteDisconnected('Remote end closed connection without response')))"
        )
        self.assertEqual(_provider_error_code(detail), "network_path_unavailable")

    def test_provider_status_summarizes_intraday_and_daily_readiness(self):
        market = MarketProviderFacade()
        checks = [
            ProviderCheck(name="quote_crawler", status="ok"),
            ProviderCheck(name="quote_rt_k", status="error", error_code="rate_limited"),
            ProviderCheck(name="quote_akshare", status="error", error_code="network_path_unavailable"),
            ProviderCheck(name="bars_1m_tushare", status="error", error_code="permission_denied"),
            ProviderCheck(name="bars_1m_akshare", status="error", error_code="network_path_unavailable"),
            ProviderCheck(name="bars_1d_tushare", status="ok"),
        ]

        status = market._provider_status_response("600519.SH", checks)

        self.assertTrue(status.quote_ready)
        self.assertIsNone(status.quote_block_reason)
        self.assertFalse(status.intraday_ready)
        self.assertEqual(status.intraday_block_reason, "permission_denied")
        self.assertTrue(status.daily_ready)
        self.assertIsNone(status.daily_block_reason)

    def test_ops_status_exposes_market_readiness_summary(self):
        class FakeMarketService:
            effective_provider = "tushare_primary+akshare_fallback"

            def decision_status(self):
                return MarketDecisionStatus(
                    provider_mode="auto",
                    effective_provider=self.effective_provider,
                    audit_window_seconds=300,
                    quote_recent_switch_count=1,
                    bars_recent_switch_count=0,
                    quote_selected_source="quote_crawler",
                    bars_selected_source="bars_1d_tushare",
                )

            def provider_status(self, symbol):
                return MarketProviderStatus(
                    provider_mode="auto",
                    effective_provider=self.effective_provider,
                    token_configured=True,
                    probe_symbol=symbol,
                    quote_ready=True,
                    intraday_ready=False,
                    intraday_block_reason="permission_denied",
                    daily_ready=True,
                    checks=[],
                )

        class FakeIntelSchedulerService:
            def status(self):
                return IntelSchedulerStatus(
                    enabled=True,
                    running=True,
                    interval_seconds=300,
                    target_count=1,
                    total_events=5,
                )

        class FakeWatchlistService:
            def status(self):
                return WatchlistStatus(
                    enabled=True,
                    running=True,
                    interval_seconds=300,
                    item_count=2,
                    alert_count=0,
                )

        class FakeBrokerService:
            def status(self):
                return main_module.BrokerStatusResponse(
                    adapter_mode="disabled",
                    live_enabled=False,
                    dry_run_only=False,
                    kill_switch=BrokerKillSwitchState(active=False, reason=None, updated_at=_now()),
                )

        with TemporaryDirectory() as temp_dir:
            ledger_path = Path(temp_dir) / "paper-ledger.json"
            ledger_path.write_text("{}", encoding="utf-8")
            with (
                patch.object(main_module, "market_service", FakeMarketService()),
                patch.object(main_module, "intel_scheduler_service", FakeIntelSchedulerService()),
                patch.object(main_module, "watchlist_service", FakeWatchlistService()),
                patch.object(main_module, "broker_service", FakeBrokerService()),
                patch.object(main_module.settings, "paper_ledger_path", str(ledger_path)),
                patch.object(main_module.settings, "paper_initial_cash", 100000.0),
            ):
                status = main_module.ops_status()

        market = next(item for item in status.subsystems if item.name == "market")
        self.assertEqual(status.overall_status, "degraded")
        self.assertEqual(market.status, "degraded")
        self.assertEqual(market.detail, "intraday_blocked:permission_denied")
        self.assertTrue(market.metrics["quote_ready"])
        self.assertFalse(market.metrics["intraday_ready"])
        self.assertEqual(market.metrics["intraday_block_reason"], "permission_denied")
        self.assertTrue(market.metrics["daily_ready"])

    def test_intel_feed_endpoints_return_structured_items(self):
        now = _now()
        event = NewsItem(
            id="official:600519.SH:1",
            title="关于签署合作协议的公告",
            summary="关于签署合作协议的公告",
            source_name="巨潮资讯",
            source_url="https://example.com/disclosure.pdf",
            source_tier=SourceTier.OFFICIAL,
            published_at=now,
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=["消费"],
            event_type="company_disclosure",
            sentiment="neutral",
            impact_direction=ImpactDirection.MIXED,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.HIGH,
        )

        class FakeIntelFeeds:
            def get_news(self, symbol, sector, lookback_hours, source_name=None, event_type=None):
                return [event]

            def get_policy(self, symbol, sector, lookback_hours):
                return [event.model_copy(update={"id": "policy:1", "source_name": "中国政府网", "event_type": "gov_policy_release"})]

            def get_disclosures(self, symbol, lookback_hours):
                return [event]

        with patch.object(main_module, "intel_service", FakeIntelFeeds()):
            news = main_module.intel_news(
                symbol="600519.SH",
                sector=None,
                source_name=None,
                event_type=None,
                lookback_hours=72,
                limit=10,
            )
            policy = main_module.intel_policy(symbol=None, sector="消费", official_only=True, lookback_hours=72, limit=10)
            disclosures = main_module.intel_disclosures(symbol="600519.SH", lookback_hours=72, limit=10)

        self.assertEqual(news.total_items, 1)
        self.assertEqual(news.scope["symbol"], "600519.SH")
        self.assertEqual(news.items[0].source_name, "巨潮资讯")
        self.assertEqual(policy.filters["official_only"], True)
        self.assertEqual(policy.items[0].source_name, "中国政府网")
        self.assertEqual(disclosures.scope["symbol"], "600519.SH")
        self.assertEqual(disclosures.items[0].event_type, "company_disclosure")

    def test_intel_news_requires_symbol_or_sector(self):
        with self.assertRaises(HTTPException) as ctx:
            main_module.intel_news(None, None, None, None, 72, 20)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "symbol or sector is required")

    def test_intel_get_disclosures_merges_cninfo_and_exchange_sources(self):
        intel = IntelService()
        now = _now()
        cninfo_event = NewsItem(
            id="cninfo:1",
            title="关于签署合作协议的公告",
            summary="关于签署合作协议的公告",
            source_name="巨潮资讯",
            source_url="https://example.com/cninfo.pdf",
            source_tier=SourceTier.OFFICIAL,
            published_at=now,
            symbols=["600519.SH"],
            sectors=[],
            themes=[],
            event_type="company_disclosure",
            sentiment="neutral",
            impact_direction=ImpactDirection.MIXED,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.HIGH,
        )
        sse_event = cninfo_event.model_copy(
            update={
                "id": "sse:1",
                "source_name": "上海证券交易所",
                "source_url": "https://example.com/sse.pdf",
                "published_at": now.replace(microsecond=0),
                "event_type": "exchange_disclosure_notice",
            }
        )
        szse_event = cninfo_event.model_copy(
            update={
                "id": "szse:1",
                "source_name": "深圳证券交易所",
                "source_url": "https://example.com/szse.pdf",
                "symbols": ["000001.SZ"],
                "event_type": "exchange_disclosure_notice",
            }
        )

        class FakeCninfo:
            def get_disclosures(self, symbol, lookback_hours):
                return [cninfo_event.model_copy(update={"symbols": [symbol]})]

        class FakeSse:
            def get_disclosures(self, symbol, lookback_hours):
                return [sse_event.model_copy(update={"symbols": [symbol]})]

        class FakeSzse:
            def get_disclosures(self, symbol, lookback_hours):
                return [szse_event.model_copy(update={"symbols": [symbol]})]

        intel._cninfo = FakeCninfo()
        intel._sse_disclosure = FakeSse()
        intel._szse_disclosure = FakeSzse()

        sh_items = intel.get_disclosures("600519.SH", 72)
        sz_items = intel.get_disclosures("000001.SZ", 72)

        self.assertEqual({item.source_name for item in sh_items}, {"巨潮资讯", "上海证券交易所"})
        self.assertEqual({item.source_name for item in sz_items}, {"巨潮资讯", "深圳证券交易所"})

    def test_parse_trade_time_accepts_fractional_seconds(self):
        parsed = _parse_trade_time("2026-03-13 00:00:00.0")

        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 3)
        self.assertEqual(parsed.day, 13)
        self.assertEqual(parsed.hour, 0)

    def test_intel_get_news_merges_headline_policy_and_disclosures(self):
        intel = IntelService()
        now = _now()
        irm_event = NewsItem(
            id="irm:1",
            title="投资者互动问答",
            summary="互动问答",
            source_name="SSE e互动",
            source_url="https://sns.sseinfo.com/",
            source_tier=SourceTier.OFFICIAL,
            published_at=now.replace(hour=9, minute=0, second=0, microsecond=0),
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=["消费"],
            event_type="investor_relations_qa",
            sentiment="neutral",
            impact_direction=ImpactDirection.NEUTRAL,
            impact_magnitude=Magnitude.LOW,
            confidence=Confidence.MEDIUM,
        )
        disclosure_event = irm_event.model_copy(
            update={
                "id": "cninfo:1",
                "title": "关于签署合作协议的公告",
                "source_name": "巨潮资讯",
                "source_url": "https://example.com/disclosure.pdf",
                "published_at": now.replace(hour=10, minute=0, second=0, microsecond=0),
                "event_type": "company_disclosure",
                "impact_direction": ImpactDirection.MIXED,
                "impact_magnitude": Magnitude.MEDIUM,
                "confidence": Confidence.HIGH,
            }
        )
        policy_event = irm_event.model_copy(
            update={
                "id": "govcn:1",
                "title": "政策解读标题",
                "source_name": "中国政府网",
                "source_url": "https://www.gov.cn/",
                "published_at": now.replace(hour=11, minute=0, second=0, microsecond=0),
                "event_type": "gov_policy_release",
                "impact_direction": ImpactDirection.MIXED,
                "impact_magnitude": Magnitude.MEDIUM,
            }
        )
        market_news_event = irm_event.model_copy(
            update={
                "id": "tushare_news:cls:1",
                "title": "公司所在板块出现利好催化",
                "summary": "财联社报道公司所在板块出现利好催化",
                "source_name": "财联社",
                "source_url": "https://www.cls.cn/",
                "source_tier": SourceTier.COMMERCIAL_MEDIA,
                "published_at": now.replace(hour=10, minute=30, second=0, microsecond=0),
                "event_type": "market_news",
                "impact_direction": ImpactDirection.MIXED,
                "impact_magnitude": Magnitude.MEDIUM,
            }
        )

        class FakeTushareIntel:
            def get_report(self, symbol, sector, lookback_hours):
                return IntelReport(
                    scope={"symbol": symbol, "sector": sector},
                    as_of=now,
                    headline_events=[irm_event],
                    policy_events=[],
                    disclosure_events=[irm_event],
                    sector_context=IntelSectorContext(
                        net_direction=ImpactDirection.NEUTRAL,
                        confidence=Confidence.MEDIUM,
                    ),
                    summary=IntelSummary(top_catalysts=[], top_risks=[]),
                )

            def get_news(self, symbol, sector, lookback_hours):
                return [market_news_event]

        class FakeCninfo:
            def get_disclosures(self, symbol, lookback_hours):
                return [disclosure_event]

        class FakeGovPolicy:
            def get_policy_events(self, scope_keywords, lookback_hours):
                return [policy_event]

        class EmptyExchange:
            def get_disclosures(self, symbol, lookback_hours):
                return []

        intel._tushare = FakeTushareIntel()
        intel._cninfo = FakeCninfo()
        intel._gov_policy = FakeGovPolicy()
        intel._sse_disclosure = EmptyExchange()
        intel._szse_disclosure = EmptyExchange()

        items = intel.get_news("600519.SH", None, 72)

        self.assertEqual(
            [item.source_name for item in items[:4]],
            ["中国政府网", "财联社", "巨潮资讯", "SSE e互动"],
        )
        self.assertEqual(items[1].event_type, "market_news")

    def test_intel_news_filters_by_source_name_and_event_type(self):
        intel = IntelService()
        now = _now()
        items = [
            NewsItem(
                id="irm:1",
                title="互动问答",
                summary="互动问答",
                source_name="SSE e互动",
                source_url="https://sns.sseinfo.com/",
                source_tier=SourceTier.OFFICIAL,
                published_at=now,
                symbols=["600519.SH"],
                sectors=[],
                themes=[],
                event_type="investor_relations_qa",
                sentiment="neutral",
                impact_direction=ImpactDirection.NEUTRAL,
                impact_magnitude=Magnitude.LOW,
                confidence=Confidence.MEDIUM,
            ),
            NewsItem(
                id="disc:1",
                title="公司公告",
                summary="公司公告",
                source_name="巨潮资讯",
                source_url="https://example.com/disclosure.pdf",
                source_tier=SourceTier.OFFICIAL,
                published_at=now,
                symbols=["600519.SH"],
                sectors=[],
                themes=[],
                event_type="company_disclosure",
                sentiment="neutral",
                impact_direction=ImpactDirection.MIXED,
                impact_magnitude=Magnitude.MEDIUM,
                confidence=Confidence.HIGH,
            ),
        ]

        filtered_by_source = intel._filter_news_items(items, source_name="巨潮资讯", event_type=None)
        filtered_by_event_type = intel._filter_news_items(items, source_name=None, event_type="investor_relations_qa")

        self.assertEqual([item.source_name for item in filtered_by_source], ["巨潮资讯"])
        self.assertEqual([item.event_type for item in filtered_by_event_type], ["investor_relations_qa"])

    def test_intel_get_news_degrades_when_tushare_market_news_unavailable(self):
        intel = IntelService()
        now = _now()
        irm_event = NewsItem(
            id="irm:1",
            title="互动问答",
            summary="互动问答",
            source_name="SSE e互动",
            source_url="https://sns.sseinfo.com/",
            source_tier=SourceTier.OFFICIAL,
            published_at=now,
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=[],
            event_type="investor_relations_qa",
            sentiment="neutral",
            impact_direction=ImpactDirection.NEUTRAL,
            impact_magnitude=Magnitude.LOW,
            confidence=Confidence.MEDIUM,
        )

        class FakeTushareIntel:
            def get_report(self, symbol, sector, lookback_hours):
                return IntelReport(
                    scope={"symbol": symbol, "sector": sector},
                    as_of=now,
                    headline_events=[irm_event],
                    policy_events=[],
                    disclosure_events=[irm_event],
                    sector_context=IntelSectorContext(
                        net_direction=ImpactDirection.NEUTRAL,
                        confidence=Confidence.MEDIUM,
                    ),
                    summary=IntelSummary(top_catalysts=[], top_risks=[]),
                )

            def get_news(self, symbol, sector, lookback_hours):
                raise ProviderError("tushare news fetch failed: permission denied")

        class FakeGovPolicy:
            def get_policy_events(self, scope_keywords, lookback_hours):
                return []

        class EmptyDisclosure:
            def get_disclosures(self, symbol, lookback_hours):
                return []

        intel._tushare = FakeTushareIntel()
        intel._gov_policy = FakeGovPolicy()
        intel._cninfo = EmptyDisclosure()
        intel._sse_disclosure = EmptyDisclosure()
        intel._szse_disclosure = EmptyDisclosure()

        items = intel.get_news("600519.SH", None, 72)

        self.assertEqual([item.source_name for item in items], ["SSE e互动"])

    def test_intel_report_appends_commercial_media_without_replacing_official_events(self):
        intel = IntelService()
        now = _now()
        official_event = NewsItem(
            id="irm:1",
            title="互动问答",
            summary="互动问答",
            source_name="SSE e互动",
            source_url="https://sns.sseinfo.com/",
            source_tier=SourceTier.OFFICIAL,
            published_at=now.replace(hour=9, minute=0, second=0, microsecond=0),
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=[],
            event_type="investor_relations_qa",
            sentiment="neutral",
            impact_direction=ImpactDirection.NEUTRAL,
            impact_magnitude=Magnitude.LOW,
            confidence=Confidence.MEDIUM,
        )
        market_news_event = official_event.model_copy(
            update={
                "id": "tushare_news:cls:1",
                "title": "财联社快讯",
                "summary": "财联社快讯",
                "source_name": "财联社",
                "source_url": "https://www.cls.cn/",
                "source_tier": SourceTier.COMMERCIAL_MEDIA,
                "published_at": now.replace(hour=10, minute=0, second=0, microsecond=0),
                "event_type": "market_news",
                "impact_direction": ImpactDirection.MIXED,
                "impact_magnitude": Magnitude.MEDIUM,
            }
        )

        class FakeTushareIntel:
            def get_report(self, symbol, sector, lookback_hours):
                return IntelReport(
                    scope={"symbol": symbol, "sector": sector},
                    as_of=now,
                    headline_events=[official_event],
                    policy_events=[],
                    disclosure_events=[],
                    sector_context=IntelSectorContext(
                        net_direction=ImpactDirection.NEUTRAL,
                        confidence=Confidence.MEDIUM,
                    ),
                    summary=IntelSummary(top_catalysts=[official_event.title], top_risks=[]),
                )

            def get_news(self, symbol, sector, lookback_hours):
                return [market_news_event]

        class EmptyOfficialSource:
            def get_policy_events(self, scope_keywords, lookback_hours):
                return []

            def get_disclosures(self, symbol, lookback_hours):
                return []

        intel._tushare = FakeTushareIntel()
        intel._gov_policy = EmptyOfficialSource()
        intel._cninfo = EmptyOfficialSource()
        intel._sse_disclosure = EmptyOfficialSource()
        intel._szse_disclosure = EmptyOfficialSource()

        report = intel.get_report("600519.SH", None, 72)

        self.assertEqual(
            [item.source_tier for item in report.headline_events[:2]],
            [SourceTier.OFFICIAL, SourceTier.COMMERCIAL_MEDIA],
        )
        self.assertEqual(report.headline_events[1].event_type, "market_news")

    def test_advice_generate_uses_commercial_media_as_secondary_catalyst(self):
        now = _now()
        official_event = NewsItem(
            id="disc:1",
            title="签署合作协议公告",
            summary="签署合作协议公告",
            source_name="巨潮资讯",
            source_url="https://example.com/disclosure.pdf",
            source_tier=SourceTier.OFFICIAL,
            published_at=now.replace(hour=9, minute=0, second=0, microsecond=0),
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=[],
            event_type="company_disclosure",
            sentiment="neutral",
            impact_direction=ImpactDirection.MIXED,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.HIGH,
        )
        market_news_event = official_event.model_copy(
            update={
                "id": "tushare_news:cls:1",
                "title": "财联社称白酒板块预期改善",
                "summary": "财联社称白酒板块预期改善",
                "source_name": "财联社",
                "source_url": "https://www.cls.cn/",
                "source_tier": SourceTier.COMMERCIAL_MEDIA,
                "published_at": now.replace(hour=10, minute=0, second=0, microsecond=0),
                "event_type": "market_news",
                "impact_direction": ImpactDirection.MIXED,
                "impact_magnitude": Magnitude.MEDIUM,
                "confidence": Confidence.MEDIUM,
            }
        )

        class FakeMarketService:
            def get_quote(self, symbol):
                return Quote(
                    symbol=symbol,
                    name=symbol,
                    last=10.2,
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    prev_close=10.0,
                    change=0.2,
                    change_pct=2.0,
                    volume=100000,
                    amount=1020000.0,
                    turnover_ratio=1.0,
                    amplitude_pct=4.0,
                    limit_status=LimitStatus.NORMAL,
                    trading_status=TradingStatus.TRADING,
                    market_time=now,
                    source="tushare_crawler_quote",
                    received_at=now,
                )

            def get_bars(self, symbol, interval, limit):
                bars = [
                    Bar(
                        ts=now - timedelta(days=25 - index),
                        open=9.5 + index * 0.02,
                        high=9.7 + index * 0.02,
                        low=9.4 + index * 0.02,
                        close=9.6 + index * 0.02,
                        volume=100000 + index * 1000,
                        amount=950000.0 + index * 12000,
                    )
                    for index in range(25)
                ]
                return BarsResponse(symbol=symbol, interval=interval, bars=bars, source="tushare")

        class FakeIndicatorsService:
            def get_indicators(self, symbol, interval, sets):
                return Indicators(
                    symbol=symbol,
                    interval=interval,
                    latest={
                        "close": 10.2,
                        "ma5": 10.05,
                        "ma10": 9.98,
                        "ma20": 9.8,
                        "macd_hist": 0.5,
                        "rsi14": 58.0,
                        "vol_ma20": 120000.0,
                        "atr_pct": 0.02,
                    },
                )

        class FakeIntelService:
            effective_provider = "test_intel"

            def get_report(self, symbol, sector, lookback_hours):
                return IntelReport(
                    scope={"symbol": symbol, "sector": sector},
                    as_of=now,
                    headline_events=[official_event, market_news_event],
                    policy_events=[],
                    disclosure_events=[official_event],
                    sector_context=IntelSectorContext(
                        net_direction=ImpactDirection.MIXED,
                        confidence=Confidence.MEDIUM,
                    ),
                    summary=IntelSummary(top_catalysts=[], top_risks=[]),
                )

        advice = AdviceService(FakeMarketService(), FakeIntelService(), FakeIndicatorsService())
        response = advice.generate(
            AdviceRequest(
                symbol="600519.SH",
                strategy_id="trend_pullback_v1",
                risk_profile="balanced",
                include_intel=True,
            )
        )

        self.assertEqual(
            [item.source_tier for item in response.catalysts],
            [SourceTier.OFFICIAL, SourceTier.COMMERCIAL_MEDIA],
        )
        self.assertIn("media_headline_unconfirmed", response.risk_flags)
        self.assertIn("recent_disclosure_review", response.risk_flags)

    def test_risk_check_warns_on_negative_commercial_media_without_official_confirmation(self):
        now = _now()
        market_news_event = NewsItem(
            id="tushare_news:sina:1",
            title="媒体称公司面临监管风险",
            summary="媒体称公司面临监管风险",
            source_name="新浪财经",
            source_url="https://finance.sina.com.cn/",
            source_tier=SourceTier.COMMERCIAL_MEDIA,
            published_at=now,
            symbols=["600519.SH"],
            sectors=["白酒"],
            themes=[],
            event_type="market_news",
            sentiment="negative",
            impact_direction=ImpactDirection.BEARISH,
            impact_magnitude=Magnitude.MEDIUM,
            confidence=Confidence.MEDIUM,
        )

        class FakeMarketService:
            def get_quote(self, symbol):
                return Quote(
                    symbol=symbol,
                    name=symbol,
                    last=10.2,
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    prev_close=10.0,
                    change=0.2,
                    change_pct=2.0,
                    volume=100000,
                    amount=1020000.0,
                    turnover_ratio=1.0,
                    amplitude_pct=4.0,
                    limit_status=LimitStatus.NORMAL,
                    trading_status=TradingStatus.TRADING,
                    market_time=now,
                    source="tushare_crawler_quote",
                    received_at=now,
                )

        class FakeIndicatorsService:
            def get_indicators(self, symbol, interval, sets):
                return Indicators(
                    symbol=symbol,
                    interval=interval,
                    latest={"rsi14": 55.0, "macd_hist": 0.1, "atr_pct": 0.02},
                )

        class FakeIntelService:
            def get_report(self, symbol, sector, lookback_hours):
                return IntelReport(
                    scope={"symbol": symbol, "sector": sector},
                    as_of=now,
                    headline_events=[market_news_event],
                    policy_events=[],
                    disclosure_events=[],
                    sector_context=IntelSectorContext(
                        net_direction=ImpactDirection.MIXED,
                        confidence=Confidence.MEDIUM,
                    ),
                    summary=IntelSummary(top_catalysts=[], top_risks=[]),
                )

        risk = RiskService(FakeMarketService(), FakeIntelService(), FakeIndicatorsService())
        response = risk.check(
            RiskCheckRequest(
                account_id="paper-main",
                strategy_id="risk_guard_v1",
                symbol="600519.SH",
                sector="白酒",
                side="buy",
                order_type="limit",
                price=10.2,
                quantity=100,
                account_equity=100000.0,
                current_position_value=0.0,
                pending_order_value=0.0,
                daily_order_count=1,
                portfolio_positions=[],
            )
        )

        event_window = next(check for check in response.checks if check.rule == "event_window")
        self.assertEqual(event_window.status, "warn")
        self.assertIn("负面媒体 headline", event_window.message)


if __name__ == "__main__":
    unittest.main()
