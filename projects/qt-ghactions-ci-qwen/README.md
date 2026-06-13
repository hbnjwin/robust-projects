[![CI](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

# Quantitative Trading Platform

Chinese A-share quantitative trading platform with backtesting, live trading, and ML-based signal generation.

## Quick Start

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run linting
make lint

# Run tests (skips PostgreSQL integration tests)
make test

# Run type checking
make typecheck
```

## CI Pipeline

The project uses GitHub Actions with a three-stage pipeline:

| Stage | Tool | Behavior |
|-------|------|----------|
| **Lint** | `ruff check` + `ruff format --check` | Blocking |
| **Test** | `pytest` with coverage | Blocking (integration tests skipped without PG) |
| **Type Check** | `mypy core/ analytics/` | Non-blocking (warnings only) |

## Project Structure

```
core/           # Infrastructure — OMS, risk, matching, events
analytics/      # Performance metrics — Sharpe, Sortino, drawdown
alpha/          # Alpha factor generation
data/           # Market data importers (Tushare, AkShare, DuckDB)
execution/      # Broker simulator, position manager
live/           # Live/paper trading engines
ml/             # ML models (Lasso, LightGBM)
strategies/     # Strategy implementations
services/       # Operational services (signals, backtest, monitoring)
```
