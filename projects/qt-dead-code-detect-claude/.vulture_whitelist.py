"""
Vulture whitelist -- false positives excluded from dead-code reports.

Each entry tells vulture the name IS used (by a framework, SDK, or test harness)
even though static analysis cannot see the call site.

Generated: 2026-06-13
"""

# ============================================================
# 1. PyTorch nn.Module.forward()
#    Called implicitly by Module.__call__(); vulture cannot trace it.
# ============================================================
forward  # noqa  -- used in 18+ model classes across gpu-train/, scripts/, services/, testing/

# ============================================================
# 2. Ptrade strategy lifecycle hooks
#    Called by the Ptrade execution runtime, not by user code.
# ============================================================
before_trading_start   # Ptrade hook: called at session open
handle_data            # Ptrade hook: called on every bar
on_order_response      # Ptrade hook: order status callback
on_trade_response      # Ptrade hook: trade fill callback
after_trading_end      # Ptrade hook: called at session close

# ============================================================
# 3. Sanic web framework lifecycle & route handlers
#    Registered via @app.listener / @app.route decorators.
# ============================================================
before_server_start    # Sanic listener
after_server_stop      # Sanic listener
req_json               # Sanic middleware / helper

# XtQuant Sanic apps -- route handlers (app_xtdata.py, quote_service.py)
get_a_index_etf
get_etf_option
get_a_future_contract
get_a_cffex_contract
get_global_future_contract
get_hk_index_comonent
download_kline_1m
download_basic_data
quote_tick
subscribe_kline_hs300
quote_kline_hs300
get_sector_component
feature_tech
download_history_bond_tick
download_history_kline
get_local_tick_data
get_local_kline_data
store_history_bond_tick
sync_bond_tick
sync_stock_kline

# Sanic server config attributes
RESPONSE_TIMEOUT
REQUEST_TIMEOUT
KEEP_ALIVE_TIMEOUT

# ============================================================
# 4. FastAPI route handlers (ashare-quantd, brokerd)
#    Registered via @app.get / @app.post decorators.
# ============================================================
# ashare-quantd routes
provider_error_handler
market_quote
market_bars
market_provider_status
market_decision_status
indicators_calc
intel_report
intel_events
intel_ingest
intel_scheduler_status
intel_scheduler_run
intel_scheduler_target
intel_scheduler_target_delete
watchlist_item_upsert
watchlist_item_delete
watchlist_alerts
watchlist_scan
broker_status
broker_kill_switch
broker_order
broker_cancel
broker_orders
broker_positions
broker_account
advice_generate
risk_check
paper_order
paper_performance
backtest_run

# brokerd routes
session_health
session_connect
session_login
session_disconnect

# ============================================================
# 5. BaseHTTPRequestHandler overrides
#    Called by the HTTP server framework.
# ============================================================
do_POST
log_message

# ============================================================
# 6. XtQuant / QMT SDK data-class attributes
#    Set for interop with the C++ xtquant SDK.
# ============================================================
m_nAccountType
m_strStockCode
m_nOrderType
m_nOrderVolume
m_nPriceType
m_dPrice
m_nOrderStatus
m_nMarket

# ============================================================
# 7. XtQuant SDK enum constants (xtconstant.py)
#    Exported for downstream consumers; used by broker integrations.
# ============================================================
CREDIT_BUY
CREDIT_SELL
CREDIT_FIN_BUY
CREDIT_SLO_SELL
CREDIT_BUY_SECU_REPAY
CREDIT_DIRECT_SECU_REPAY
CREDIT_SELL_SECU_REPAY
CREDIT_DIRECT_CASH_REPAY
CREDIT_FIN_BUY_SPECIAL
CREDIT_SLO_SELL_SPECIAL
CREDIT_BUY_SECU_REPAY_SPECIAL
CREDIT_DIRECT_SECU_REPAY_SPECIAL
CREDIT_SELL_SECU_REPAY_SPECIAL
CREDIT_DIRECT_CASH_REPAY_SPECIAL
ORDER_UNREPORTED
ORDER_WAIT_REPORTING
ORDER_REPORTED
ORDER_REPORTED_CANCEL
ORDER_PARTSUCC_CANCEL
ORDER_PART_CANCEL
ORDER_CANCELED
ORDER_PART_SUCC
ORDER_SUCCEEDED
ORDER_JUNK
ORDER_UNKNOWN

# ============================================================
# 8. XtQuant type classes (xttype.py)
#    Public SDK types consumed by broker integration code.
# ============================================================
XtAsset
XtTrade
XtPosition
XtOrderError
XtCancelError
XtCreditOrder
XtCreditDeal

# ============================================================
# 9. Pydantic model_config & model fields
#    Used by Pydantic v2 for serialization / validation.
#    Fields are accessed via API request/response serialization.
# ============================================================
model_config  # Pydantic v2 model configuration

# ashare-quantd/app/models.py -- Pydantic fields accessed via JSON serialization
REDUCE
LIMIT_UP
LIMIT_DOWN
HALTED
PRIMARY_MEDIA
RUMOR
BULLISH

# ============================================================
# 10. psycopg2 / database connection attributes
# ============================================================
autocommit  # set on psycopg2 connection objects

# ============================================================
# 11. PyTorch / CUDA config attributes
# ============================================================
benchmark    # torch.backends.cudnn.benchmark
allow_tf32   # torch.backends.cuda.matmul.allow_tf32 / cudnn.allow_tf32

# ============================================================
# 12. Event-driven callback attributes
#     Assigned as callable hooks, invoked by event dispatch.
# ============================================================
on_order  # gateway / live_engine order callback

# ============================================================
# 13. Strategy / portfolio state flags
#     Read by monitoring / logging subsystems.
# ============================================================
drawdown_control_triggered  # MasterPortfolio risk flag
_initialized                # BaseStrategy initialization guard
buy_dates                   # LowVolStrategy tracking
last_selected               # LowVolStrategy stock selection cache
_slippage                   # PaperGateway config

# ============================================================
# 14. XtQuant internal attributes
# ============================================================
_base           # xtdata internal
trade_function_template  # xttrader template method

# ============================================================
# 15. QMT broker notification methods
#     Dispatched dynamically based on channel config.
# ============================================================
_send_webhook
_send_wecom
_send_telegram
_send_feishu

# ============================================================
# 16. QMT broker misc
# ============================================================
serve_http         # top-level entry point, called from __main__
topic_label        # used in message formatting
window_args        # provider window configuration
on_account_status  # XtQuant trader callback
_tail_size         # AuditLog internal config

# ============================================================
# 17. Test helper methods
#     Called by test frameworks or used as mock interface stubs.
# ============================================================
describe_bars  # test utility for bar data inspection
