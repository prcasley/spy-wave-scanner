# Wave Options Scanner

Multi-ticker Elliott Wave + options confluence scanner. Pulls free OHLCV and
options data from Yahoo Finance, runs the wave engine, picks an options
structure, and emits a structured trade signal that other systems can consume.

Backed by a FastAPI service, in-process scheduler, JSONL + SQLite persistence,
and a Discord webhook for high-confluence alerts.

## Features

- Multi-ticker via `SCAN_TICKERS` env var (default `SPY,QQQ,IWM,DIA`)
- Yahoo Finance v8 chart endpoint for OHLCV (free, no API key)
- Yahoo Finance v7 options endpoint for chains (free, no API key)
- Elliott Wave detection: 5-wave impulse + ABC corrective with cardinal-rule
  validation, confidence scoring, target projection
- Fibonacci retracement / extension / confluence-zone mapping
- RSI + MACD-histogram divergence detection
- Black-Scholes Greeks (delta, probability-of-profit) where Yahoo doesn't
  provide them
- Strategy selector picks `long_call`, `bull_call_spread`, `long_put`, or
  `bear_put_spread` based on direction + IV regime
- Canonical signal JSON validated against a Draft 2020-12 schema
- JSONL (`signals/YYYY-MM-DD.jsonl`) and SQLite (`signals.db`) persistence
- Discord webhook with rich embeds (only fires when confluence >= 70)
- REST endpoint: `GET /api/signals?ticker=SPY&since=2026-05-08T00:00:00Z`
- APScheduler cron during US market hours (Mon-Fri 13:30-20:00 UTC)

No mock data, no fallbacks: if Yahoo refuses, every layer raises a typed
exception (`DataFeedError`, `OptionsFeedError`, `StrategySelectorError`) so a
broken scan never silently emits stale signals.

## Architecture

```
SCAN_TICKERS=SPY,QQQ,NVDA
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │  scanner.scan_universe()                                │
   │     │                                                   │
   │     ▼                                                   │
   │  DataFeed (Yahoo v8) → indicators (RSI, MACD, VolSMA)   │
   │     ▼                                                   │
   │  PivotDetector → WaveCounter → FibMapper → Divergences  │
   │     ▼                                                   │
   │  OptionsFeed (Yahoo v7) → StrategySelector + Greeks     │
   │     ▼                                                   │
   │  signal_builder.build_signal()  ← schema-validated      │
   │     ▼                                                   │
   │  SignalStore (JSONL + SQLite)  + DiscordWebhook         │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   GET /api/signals  (FastAPI, polled by your trader app)
```

## Quick start

```bash
pip install -r requirements.txt

# One-off scan
export SCAN_TICKERS="SPY,QQQ,NVDA"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."  # optional
python scripts/run_scanner.py --print-signals

# Long-running API + scheduler
export SCAN_INTERVAL_MIN=15
uvicorn src.api:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/api/signals
curl http://localhost:8000/api/signals/latest
curl -X POST "http://localhost:8000/api/scan?tickers=AAPL,SPY"
```

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `SCAN_TICKERS` | `SPY,QQQ,IWM,DIA` | Comma-separated universe |
| `SCAN_INTERVAL_MIN` | `15` | Minutes between scheduled scans |
| `DISCORD_WEBHOOK_URL` | unset | Channel for high-confluence alerts |
| `DISABLE_SCHEDULER` | unset | Set to `1` to run API without the cron |

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

## CLI reference

```bash
# Scan a custom set
python scripts/run_scanner.py --tickers AAPL,SPY,NVDA --print-signals

# Pick a different bar interval / DTE
python scripts/run_scanner.py --timeframe 15min --target-dte 14

# Skip Discord and SQLite for ad-hoc analysis
python scripts/run_scanner.py --no-discord --no-persist --print-signals

# Fixture-backed end-to-end demo (no network)
python scripts/demo_pipeline.py
```

## Sample signal payload

```json
{
  "signal_id": "1e709d30-e08c-41a1-8b14-9336784458fd",
  "timestamp": "2026-05-08T14:30:00+00:00",
  "ticker": "SPY",
  "direction": "long",
  "wave": {
    "primary_count": "wave_3_impulse",
    "alternate_count": null,
    "primary_probability": 0.65,
    "degree": "intermediate",
    "current_wave": "3"
  },
  "price": {
    "spot": 612.45,
    "entry_zone": [611.5, 613.0],
    "invalidation": 608.2,
    "targets": [
      {"price": 618.0, "fib_ratio": 1.618, "probability": 0.55},
      {"price": 622.5, "fib_ratio": 2.618, "probability": 0.30}
    ]
  },
  "options": {
    "suggested_structure": "long_call",
    "expiration": "2026-05-16",
    "dte": 8,
    "legs": [
      {"action": "buy", "type": "call", "strike": 614.0,
       "premium": 2.85, "delta": 0.42, "iv": 0.18}
    ],
    "max_loss": 285.0,
    "max_gain": "unlimited",
    "breakeven": 616.85,
    "probability_of_profit": 0.48
  },
  "confluence": {
    "score": 78,
    "factors": ["wave_3_extension", "rsi_or_macd_bullish_divergence",
                "iv_rank_below_30"]
  },
  "risk": {
    "suggested_position_size_pct": 1.5,
    "max_loss_at_account_pct_1": 100.0,
    "stop_loss_method": "invalidation_level"
  }
}
```

## Deployment (Railway)

A `Procfile` is included:

```
web: uvicorn src.api:app --host 0.0.0.0 --port $PORT
```

1. Push the repo to Railway
2. Set `SCAN_TICKERS`, `DISCORD_WEBHOOK_URL`, optional `SCAN_INTERVAL_MIN`
3. Railway boots `uvicorn`; the in-process scheduler kicks off every
   `SCAN_INTERVAL_MIN` minutes during US market hours

## GitHub Actions

`.github/workflows/scanner.yml` runs:

- `scan` job — every 15 min during market hours via cron
- `test` job — pytest on push
- `lint` / `typecheck` — ruff + mypy

Set repo variables `SCAN_TICKERS` and secret `DISCORD_WEBHOOK_URL`.

## File layout

```
spy-wave-scanner/
├── src/
│   ├── data_feed.py          # Yahoo v8 OHLCV fetcher + indicator math
│   ├── options_feed.py       # Yahoo v7 chain fetcher
│   ├── greeks.py             # Black-Scholes delta + probability
│   ├── pivot_detector.py     # Swing pivot detection
│   ├── fib_mapper.py         # Retracements, extensions, confluence
│   ├── wave_counter.py       # Elliott Wave engine + cardinal rules
│   ├── divergence.py         # RSI + MACD divergence
│   ├── strategy_selector.py  # Picks options structure from chain
│   ├── signal_builder.py     # Canonical signal JSON + schema validation
│   ├── persistence.py        # JSONL + SQLite store
│   ├── discord_webhook.py    # Rich-embed alerts
│   ├── scanner.py            # Multi-ticker orchestrator
│   ├── api.py                # FastAPI app + APScheduler
│   ├── models.py             # Dataclasses + enums
│   ├── alert_engine.py       # Legacy proximity-alert engine (kept for tests)
│   └── dashboard.py          # Streamlit visualization
├── scripts/
│   ├── run_scanner.py        # CLI entry point
│   ├── demo_pipeline.py      # Fixture-backed end-to-end demo
│   ├── backtest.py           # Historical wave-detection harness
│   └── calibrate.py          # Parameter grid search
├── tests/                    # 85 tests
├── config/                   # YAML settings
├── Procfile                  # Railway/Heroku-style web entry
└── requirements.txt
```

## Hard rules (read before changing code)

1. No mock data, no fallback fixtures in production paths. Yahoo failure
   raises typed exceptions; the caller decides what to do.
2. No SPY hardcoding. Every fetch takes a `ticker` parameter.
3. No paid APIs. Yahoo Finance only.
4. Reuse before rewrite. The wave engine, pivot detector, fib mapper, and
   divergence detector are unchanged from the original SPY scanner.
5. Signals are structured JSON, not log lines. Every signal validates
   against the Draft 2020-12 schema in `src/signal_builder.py` before
   emission.
