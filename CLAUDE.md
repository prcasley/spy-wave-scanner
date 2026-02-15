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
├── docs/
│   ├── index.html             [477L]  # GitHub Pages dashboard — TradingView Lightweight Charts, dark theme
│   └── data/
│       └── latest_scan.json           # Scan results JSON consumed by dashboard (auto-committed by CI)
│
├── src/
│   ├── __init__.py
│   ├── models.py              [216L]  # Data classes: Pivot, Wave, WaveCount, FibLevel, Alert, Divergence, etc.
│   ├── data_feed.py           [229L]  # Polygon.io OHLCV fetching + RSI/MACD/Volume SMA + caching + rate limiting
│   ├── pivot_detector.py      [192L]  # Swing high/low detection, alternation, sequence classification
│   ├── fib_mapper.py          [203L]  # Fibonacci retracement + extension calc, confluence zones
│   ├── wave_counter.py        [491L]  # Elliott Wave impulse/corrective pattern matching + validation
│   ├── divergence.py          [183L]  # RSI and MACD histogram divergence detection at pivots
│   ├── alert_engine.py        [318L]  # Alert generation, formatting, Slack/email/SMS dispatch
│   ├── json_output.py         [143L]  # JSON serialization for scan results (used by CLI --output-json and CI)
│   └── dashboard.py           [637L]  # Streamlit UI — dark-themed chart, wave labels, fib lines, RSI/MACD
│
├── scripts/
│   ├── run_scanner.py         [459L]  # Main entry point / CLI (--dry-run, --no-cache, --multi-tf, --output-json)
│   ├── backtest.py            [164L]  # Sliding-window historical validation
│   └── calibrate.py           [100L]  # Grid-search parameter tuning
│
├── tests/
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── spy_5min_sample.csv        # 200 bars of SPY 5-min OHLCV with clear wave patterns
│   │   └── generate_fixture.py        # Script to regenerate the fixture
│   ├── test_integration.py    [193L]  # End-to-end pipeline test using fixture data
│   ├── test_pivots.py         [137L]  # Pivot detection + filtering + sequence classification
│   ├── test_fibs.py           [102L]  # Retracement, extension, confluence zone tests
│   ├── test_wave_rules.py     [189L]  # Cardinal rule validation, projection, corrective patterns
│   └── test_alerts.py         [199L]  # Proximity alerts, cooldown, formatting, divergence alerts
│
└── .github/
    └── workflows/
        └── scanner.yml                # GitHub Actions: scan, test, lint (ruff), typecheck (mypy), auto-commit JSON
```

## Code Architecture Rules

### 1. AVOID MONOLITHIC FILES
- **Guideline: keep source files under ~300 lines.** When a file starts growing large, look for natural seams to split it. Use your judgment — a 320-line file with tightly coupled logic is fine; a 400-line file with 3 distinct responsibilities should be split.
- Before adding significant code to a file, check its line count. If it's already large and your change will push it further, split first, then add.
- `wave_counter.py` (491L) and `dashboard.py` (641L) are currently oversized and should be split on the next change to either file.
- `run_scanner.py` (459L) is oversized — consider extracting the summary formatter, multi-TF logic, and JSON output into separate modules.
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
- **Data caching.** `DataFeed.get_bars()` caches to `~/.cache/spy-wave-scanner/` by default (parquet files keyed on ticker+timeframe+lookback+date). Use `--no-cache` flag for live scans.
- **Rate limiting.** `DataFeed` throttles API calls (default 5 req/min for free tier). Configurable via `rate_limit_rpm` constructor param.

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

# CLI scan (dry-run, no alerts sent)
POLYGON_API_KEY=xxx python scripts/run_scanner.py --dry-run

# CLI scan (skip cache, force live fetch)
POLYGON_API_KEY=xxx python scripts/run_scanner.py --no-cache

# CLI scan (multi-timeframe confirmation)
POLYGON_API_KEY=xxx python scripts/run_scanner.py --multi-tf

# CLI scan (output JSON for GitHub Pages dashboard)
POLYGON_API_KEY=xxx python scripts/run_scanner.py --dry-run --output-json docs/data/latest_scan.json

# Streamlit dashboard (local)
POLYGON_API_KEY=xxx streamlit run src/dashboard.py

# GitHub Pages dashboard: served from docs/ — reads docs/data/latest_scan.json
# Enable GitHub Pages in repo settings → Source: Deploy from branch → /docs folder

# Backtest
POLYGON_API_KEY=xxx python scripts/backtest.py --ticker SPY --days 30
```

## Commit Conventions

- One logical change per commit
- Prefix: `Add`, `Fix`, `Update`, `Refactor`, `Split`, `Test`
- Always run tests before committing
- Never commit secrets or `.env` files

## Improvement Roadmap

Agents should tackle these when working in the relevant area. Mark items DONE here when completed and update the file tree above.

### HIGH — Split oversized files

- [ ] **Split `wave_counter.py` (491L)** into a `src/wave_counter/` package:
  - `__init__.py` — re-export `WaveCounter` for backwards compatibility
  - `impulse.py` — impulse wave pattern matching (`_find_impulse_waves`, `_score_impulse`)
  - `corrective.py` — corrective pattern matching (zigzag, flat, triangle)
  - `validation.py` — cardinal rule enforcement (W2 retrace, W3 length, W4 overlap)
  - `projection.py` — wave target projections and confidence scoring
  - Update imports in `run_scanner.py`, `dashboard.py`, `backtest.py`, and tests
  - Split `tests/test_wave_rules.py` to mirror the new sub-modules

- [ ] **Split `dashboard.py` (641L)** into a `src/dashboard/` package:
  - `__init__.py` — re-export for `streamlit run src/dashboard`
  - `chart.py` — `build_chart()` and Plotly figure construction
  - `app.py` — Streamlit page layout, sidebar controls, data loading
  - `styles.py` — CSS strings, color palettes, theme constants
  - Update `.github/workflows/scanner.yml` if the entry point changes

- [ ] **Split `alert_engine.py` (321L)** if it grows further:
  - `alert_engine/generator.py` — alert creation and proximity logic
  - `alert_engine/formatter.py` — message formatting (Slack, email, SMS)
  - `alert_engine/dispatcher.py` — delivery via webhooks/SMTP/Twilio

### HIGH — Add integration tests

- [x] **Create `tests/test_integration.py`** — DONE
  - Loads `tests/fixtures/spy_5min_sample.csv` (200 bars with clear wave patterns)
  - Tests full pipeline: indicators → pivots → fibs → wave count → divergences → alerts
  - 8 test cases covering each pipeline stage + end-to-end

### MEDIUM — Data caching for backtests

- [x] **Add local caching to `data_feed.py`** — DONE
  - Cache fetched OHLCV data to `~/.cache/spy-wave-scanner/` as parquet files
  - File-based cache keyed on ticker + timeframe + lookback + date
  - `backtest.py` and `calibrate.py` hit cache automatically via default `use_cache=True`
  - `--no-cache` flag added to `run_scanner.py` for live scans

### MEDIUM — Polygon API rate limiting

- [x] **Add rate limiting to `data_feed.py`** — DONE
  - Default 5 req/min (12s between calls) for free tier
  - Configurable via `rate_limit_rpm` param on `DataFeed` constructor
  - `_throttle()` called before every API request

### MEDIUM — Replace demo random data with real fixture

- [x] **Create `tests/fixtures/spy_5min_sample.csv`** — DONE
  - 200 bars of SPY 5-min OHLCV with 5-wave impulse down + ABC correction
  - Dashboard demo mode loads this fixture (falls back to synthetic if missing)
  - Integration tests use this fixture

### MEDIUM — Combined Signal Engine (Options Scanner integration)

- [ ] **Create `src/signal_engine.py`**:
  - Accept wave count outputs (this scanner) and unusual options flow (options scanner)
  - Score combined signals: options activity at Fibonacci levels boosts wave confidence
  - Emit combined alerts with both wave context and options flow context
  - Define a shared data contract (JSON schema or dataclass) for cross-scanner communication

### LOW — Add type checking

- [x] **Add `mypy` to CI** — DONE
  - `mypy` step added to `.github/workflows/scanner.yml`
  - Runs `mypy src/ --ignore-missing-imports`

### LOW — Add linting

- [x] **Add `ruff` to CI** — DONE
  - `ruff` lint step added to `.github/workflows/scanner.yml`
  - Runs `ruff check src/ scripts/ tests/`

## Current Known Issues / Tech Debt

1. **`wave_counter.py` is 491 lines** — see Improvement Roadmap above
2. **`dashboard.py` is 637 lines** — see Improvement Roadmap above
3. **`run_scanner.py` is 459 lines** — oversized; extract summary formatter, multi-TF logic, JSON output
4. **`alert_engine.py` is 318 lines** — borderline; split if it grows
5. **No combined signal engine yet** — options scanner integration not implemented; see Improvement Roadmap
