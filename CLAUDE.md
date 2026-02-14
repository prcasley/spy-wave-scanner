# CLAUDE.md — Agent Instructions for SPY Wave Scanner

## Project Overview

SPY Elliott Wave Scanner: automated wave detection, Fibonacci mapping, divergence detection, and real-time alerts. Designed to pair with the **Options Flow Scanner** for combined wave-target + unusual-options-activity signals.

## File Tree (KEEP UPDATED)

**Every agent that adds, removes, or renames a file MUST update this tree.**

```
spy-wave-scanner/
├── CLAUDE.md                          # THIS FILE — agent instructions
├── README.md                          # Project docs, goals, integration guide
├── requirements.txt                   # Python dependencies (no ta library — RSI/MACD computed in-house)
├── .gitignore
│
├── config/
│   ├── settings.yaml                  # Timeframes, pivot sensitivity, fib levels, indicator params
│   └── alert_config.yaml             # Slack webhooks, email, SMS delivery config
│
├── src/
│   ├── __init__.py
│   ├── models.py              [216L]  # Data classes: Pivot, Wave, WaveCount, FibLevel, Alert, Divergence, etc.
│   ├── data_feed.py           [171L]  # Polygon.io OHLCV fetching + RSI/MACD/Volume SMA computation
│   ├── pivot_detector.py      [192L]  # Swing high/low detection, alternation, sequence classification
│   ├── fib_mapper.py          [203L]  # Fibonacci retracement + extension calc, confluence zones
│   ├── wave_counter.py        [497L]  # Elliott Wave impulse/corrective pattern matching + validation
│   ├── divergence.py          [183L]  # RSI and MACD histogram divergence detection at pivots
│   ├── alert_engine.py        [321L]  # Alert generation, formatting, Slack/email/SMS dispatch
│   └── dashboard.py           [633L]  # Streamlit UI — dark-themed chart, wave labels, fib lines, RSI/MACD
│
├── scripts/
│   ├── run_scanner.py         [223L]  # Main entry point / CLI orchestrator
│   ├── backtest.py            [164L]  # Sliding-window historical validation
│   └── calibrate.py           [100L]  # Grid-search parameter tuning
│
├── tests/
│   ├── __init__.py
│   ├── test_pivots.py         [137L]  # Pivot detection + filtering + sequence classification
│   ├── test_fibs.py           [102L]  # Retracement, extension, confluence zone tests
│   ├── test_wave_rules.py     [189L]  # Cardinal rule validation, projection, corrective patterns
│   └── test_alerts.py         [199L]  # Proximity alerts, cooldown, formatting, divergence alerts
│
└── .github/
    └── workflows/
        └── scanner.yml                # GitHub Actions: every 5 min during market hours
```

## Code Architecture Rules

### 1. NO MONOLITHIC FILES
- **Hard limit: 300 lines per source file.** If a file exceeds 300 lines, split it.
- `wave_counter.py` (497L) and `dashboard.py` (633L) are currently over-limit and should be split on the next major change to either file.
- Suggested splits:
  - `wave_counter.py` → `wave_counter/impulse.py`, `wave_counter/corrective.py`, `wave_counter/validation.py`, `wave_counter/projection.py`
  - `dashboard.py` → `dashboard/chart.py` (build_chart), `dashboard/app.py` (Streamlit page), `dashboard/styles.py` (CSS/colors)

### 2. ONE CLASS PER FILE (for non-trivial classes)
- Each major class (DataFeed, PivotDetector, FibMapper, WaveCounter, DivergenceDetector, AlertEngine) gets its own file.
- `models.py` is the exception — dataclasses and enums are fine grouped together since they're small.
- If a models group grows (e.g., alert-related models), split into `models/wave.py`, `models/alert.py`, etc.

### 3. IMPORT STYLE
- Always import from `src.models`, not relative imports.
- Keep imports at the top of the file, sorted: stdlib → third-party → local.

### 4. TESTS MIRROR SOURCE
- `src/foo.py` → `tests/test_foo.py`
- If source splits into `src/foo/bar.py`, tests become `tests/test_foo_bar.py`
- Every new public method gets at least one test.
- Run `pytest tests/ -v` before every commit.

### 5. CONFIG OVER HARDCODING
- Numeric thresholds go in `config/settings.yaml`, not in source code.
- API keys and secrets go in environment variables, referenced in `config/alert_config.yaml`.
- Never commit `.env` files.

## Key Technical Decisions

- **No `ta` library.** RSI and MACD are computed in `data_feed.py` using pure pandas EWM to avoid build issues. Do NOT re-add the `ta` dependency.
- **Polygon.io is the sole data source.** All OHLCV data comes from the Polygon REST client. Do not add yfinance, Alpha Vantage, etc. without explicit user approval.
- **Indicators are computed in `data_feed.py`.** RSI, MACD, and Volume SMA are added as DataFrame columns. Other modules consume these columns; they do not recompute them.
- **Elliott Wave rules are enforced in `wave_counter.py`.** The three cardinal rules (W2 retrace, W3 length, W4 overlap) are never relaxed. A count that violates any rule gets confidence=0 and is rejected.
- **Dashboard uses Plotly + Streamlit.** The dark theme and chart style match a professional trading platform (black bg, colored wave labels, fib lines with price annotations, RSI/MACD sub-panels). Do not change the visual style without user approval.

## Companion Project: Options Flow Scanner

This scanner is designed to pair with the Options Flow Scanner. Key integration points:

- Both use **Polygon.io** for data
- Both push to **Slack** for alerts
- Wave targets (from this scanner) should inform options strike monitoring (in the options scanner)
- Unusual options activity at Fibonacci levels confirms wave counts
- A future **Combined Signal Engine** would merge outputs from both scanners

When making changes, consider whether they affect the integration surface (alert format, shared config keys, data structures).

## Running the Project

```bash
# Install deps
pip install -r requirements.txt

# Run tests (DO THIS BEFORE EVERY COMMIT)
pytest tests/ -v

# CLI scan
POLYGON_API_KEY=xxx python scripts/run_scanner.py

# Dashboard
POLYGON_API_KEY=xxx streamlit run src/dashboard.py

# Backtest
POLYGON_API_KEY=xxx python scripts/backtest.py --ticker SPY --days 30
```

## Commit Conventions

- One logical change per commit
- Prefix: `Add`, `Fix`, `Update`, `Refactor`, `Split`, `Test`
- Always run tests before committing
- Never commit secrets or `.env` files

## Current Known Issues / Tech Debt

1. **`wave_counter.py` is 497 lines** — should be split into sub-modules on next change
2. **`dashboard.py` is 633 lines** — should be split into chart builder, app layout, and styles
3. **No integration tests** — only unit tests exist; need end-to-end pipeline test
4. **No data caching** — every scan re-fetches from Polygon; should add local caching for backtests
5. **No rate limiting** — Polygon API calls are not throttled; could hit limits during calibration
6. **Dashboard demo mode uses random data** — should use a saved fixture of real SPY data instead
7. **No type checking** — should add `mypy` to CI
8. **No combined signal engine yet** — the options scanner integration is documented but not implemented
