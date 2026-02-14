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

### 1. AVOID MONOLITHIC FILES
- **Guideline: keep source files under ~300 lines.** When a file starts growing large, look for natural seams to split it. Use your judgment — a 320-line file with tightly coupled logic is fine; a 400-line file with 3 distinct responsibilities should be split.
- Before adding significant code to a file, check its line count. If it's already large and your change will push it further, split first, then add.
- `wave_counter.py` (497L) and `dashboard.py` (633L) are currently oversized and should be split on the next change to either file.
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

## Improvement Roadmap

Agents should tackle these when working in the relevant area. Mark items DONE here when completed and update the file tree above.

### HIGH — Split oversized files

- [ ] **Split `wave_counter.py` (497L)** into a `src/wave_counter/` package:
  - `__init__.py` — re-export `WaveCounter` for backwards compatibility
  - `impulse.py` — impulse wave pattern matching (`_find_impulse_waves`, `_score_impulse`)
  - `corrective.py` — corrective pattern matching (zigzag, flat, triangle)
  - `validation.py` — cardinal rule enforcement (W2 retrace, W3 length, W4 overlap)
  - `projection.py` — wave target projections and confidence scoring
  - Update imports in `run_scanner.py`, `dashboard.py`, `backtest.py`, and tests
  - Split `tests/test_wave_rules.py` to mirror the new sub-modules

- [ ] **Split `dashboard.py` (633L)** into a `src/dashboard/` package:
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

- [ ] **Create `tests/test_integration.py`** — end-to-end pipeline test:
  - Load a saved SPY OHLCV fixture (not live Polygon data)
  - Run: data_feed → pivot_detector → wave_counter → fib_mapper → divergence → alert_engine
  - Assert the pipeline produces expected wave counts and alerts for the fixture
  - Add to CI in `scanner.yml`

### MEDIUM — Data caching for backtests

- [ ] **Add local caching to `data_feed.py`**:
  - Cache fetched OHLCV data to `~/.cache/spy-wave-scanner/` or a configurable path in `settings.yaml`
  - Use file-based cache keyed on ticker + timeframe + date range
  - `backtest.py` and `calibrate.py` should hit cache instead of re-fetching
  - Add a `--no-cache` flag to `run_scanner.py` for live scans

### MEDIUM — Polygon API rate limiting

- [ ] **Add rate limiting to `data_feed.py`**:
  - Respect Polygon's rate limits (5 req/min on free tier, higher on paid)
  - Add a configurable `rate_limit_rpm` setting in `settings.yaml`
  - Use a simple token-bucket or sleep-based throttle
  - Especially important for `calibrate.py` which runs many sequential scans

### MEDIUM — Replace demo random data with real fixture

- [ ] **Create `tests/fixtures/spy_sample.csv`** with real SPY OHLCV data:
  - Pick a date range with clear Elliott Wave patterns (e.g., a 5-wave impulse + correction)
  - Dashboard demo mode should load this fixture instead of generating random data
  - Integration tests should also use this fixture

### MEDIUM — Combined Signal Engine (Options Scanner integration)

- [ ] **Create `src/signal_engine.py`**:
  - Accept wave count outputs (this scanner) and unusual options flow (options scanner)
  - Score combined signals: options activity at Fibonacci levels boosts wave confidence
  - Emit combined alerts with both wave context and options flow context
  - Define a shared data contract (JSON schema or dataclass) for cross-scanner communication

### LOW — Add type checking

- [ ] **Add `mypy` to CI**:
  - Add `mypy` to `requirements.txt` (dev section or separate `requirements-dev.txt`)
  - Add a `mypy` step to `.github/workflows/scanner.yml`
  - Fix any type errors that surface
  - Add `py.typed` marker to `src/`

### LOW — Add linting

- [ ] **Add `ruff` to CI**:
  - Add `ruff` to dev dependencies
  - Create a `ruff.toml` or `[tool.ruff]` section in `pyproject.toml`
  - Add a lint step to `.github/workflows/scanner.yml`
  - Run `ruff check --fix` to auto-fix existing issues

## Current Known Issues / Tech Debt

1. **`wave_counter.py` is 497 lines** — see Improvement Roadmap above
2. **`dashboard.py` is 633 lines** — see Improvement Roadmap above
3. **`alert_engine.py` is 321 lines** — borderline; split if it grows
4. **No integration tests** — only unit tests exist; see Improvement Roadmap
5. **No data caching** — every scan re-fetches from Polygon; see Improvement Roadmap
6. **No rate limiting** — Polygon API calls are not throttled; see Improvement Roadmap
7. **Dashboard demo mode uses random data** — should use a saved fixture; see Improvement Roadmap
8. **No type checking** — should add `mypy` to CI; see Improvement Roadmap
9. **No linting** — should add `ruff` to CI; see Improvement Roadmap
10. **No combined signal engine yet** — options scanner integration not implemented; see Improvement Roadmap
