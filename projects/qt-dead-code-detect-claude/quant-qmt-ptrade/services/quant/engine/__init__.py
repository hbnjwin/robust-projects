"""
engine -- DEPRECATED legacy backtest primitives.

This package (DataFeed, Broker, Portfolio, Backtest) has been superseded by:
  - core/         -- event-driven infrastructure (EventEngine, OMS, RiskGate)
  - live/         -- replay_engine_v5.ReplayEngineV5 (event-driven backtest)
  - execution/    -- ExecutionEngineV3, BrokerSimulator

Use unified_backtest.py as the single entry point for all backtests.

Importing from this package will emit a DeprecationWarning.
Do NOT add new code here.
"""

__all__ = []
