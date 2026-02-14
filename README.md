# SPY Elliott Wave Scanner

Automated Elliott Wave detection and alert system for SPY (and extensible to other tickers). The scanner identifies swing pivots, maps Fibonacci levels, detects wave patterns, and pushes real-time alerts when price approaches key wave targets.

**Tech Stack:** Python 3.11+ | Polygon.io API | GitHub Actions | Slack/Email Alerts

## Goal

Provide a fully automated, rules-based Elliott Wave scanning system that:

1. **Detects** 5-wave impulse and ABC corrective patterns on SPY intraday (5-min, 15-min) and daily timeframes
2. **Maps** Fibonacci retracement and extension levels from detected swing pivots, with automatic confluence zone identification
3. **Alerts** in real time when price approaches key wave targets, invalidation levels, or confluence zones
4. **Validates** every wave count against the three cardinal Elliott Wave rules (Wave 2 retrace, Wave 3 length, Wave 4 overlap)
5. **Visualizes** everything in a dark-themed Streamlit dashboard matching professional trading-platform style (candlesticks, wave labels, fib lines, RSI/MACD panels)

The scanner replaces manual chart analysis with an automated pipeline that runs every 5 minutes during market hours via GitHub Actions, sending Slack/email alerts for actionable setups.

## Pairing with the Options Flow Scanner

This wave scanner is designed to work alongside the **Options Flow Scanner** to create a powerful combined signal system:

- **Wave targets inform options entries.** When the wave scanner identifies a Wave 5 target at $680, the options flow scanner can watch for unusual put activity clustering at that strike — confirming the directional bias.
- **Options flow confirms wave counts.** Large block trades or sweeps at Fibonacci levels (e.g., aggressive call buying at the 38.2% retracement zone during Wave 4) provide institutional-level confirmation that the wave count is valid.
- **Invalidation levels become options triggers.** When price approaches an invalidation level (e.g., $689 must hold to keep the Wave 5 drop valid), the options scanner can flag any sudden shift in put/call ratio as an early signal of count invalidation.
- **Shared Polygon.io data feed.** Both scanners use the same Polygon.io API key and can share the data fetch layer to reduce API calls.
- **Unified Slack alerts.** Both scanners push to the same Slack channel, so you see wave structure + options flow in one stream. A combined alert like "Wave 5 target $680 + 10,000 SPY 680P sweeps detected" is a high-conviction setup.

### Integration Pattern

```
Options Flow Scanner                 Wave Scanner
       │                                  │
       │  unusual put sweep at $680       │  Wave 5 target = $680.63
       │                                  │  RSI bullish divergence
       ▼                                  ▼
  ┌──────────────────────────────────────────┐
  │         COMBINED SIGNAL ENGINE           │
  │                                          │
  │  Wave target + options flow = HIGH       │
  │  conviction setup → ALERT                │
  └──────────────────────────────────────────┘
```

## What This Accomplishes

- **Eliminates manual chart work** — wave counting, fib drawing, and level-watching happen automatically every 5 minutes
- **Enforces discipline** — every count is validated against Elliott Wave rules; invalid counts are rejected, not traded
- **Reduces noise** — pivot sensitivity filters and minimum swing thresholds suppress insignificant price action
- **Provides clear trade parameters** — every alert includes entry level, target, and invalidation price
- **Scales to multiple tickers** — change `--ticker AVGO` and the same engine runs on any Polygon-supported symbol
- **Backtestable** — the `backtest.py` script validates detection accuracy on historical data before going live
- **Calibratable** — `calibrate.py` grid-searches parameter combinations to optimize hit rate for your preferred ticker/timeframe

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SPY WAVE SCANNER                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │   DATA FEED  │──▶│  WAVE ENGINE │──▶│  ALERT ENGINE  │  │
│  │  (Polygon)   │   │              │   │                │  │
│  └──────────────┘   └──────────────┘   └────────────────┘  │
│         │                  │                    │           │
│         ▼                  ▼                    ▼           │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  OHLCV Data  │   │ Wave Count   │   │  Slack/Email   │  │
│  │  RSI / MACD  │   │ Fib Levels   │   │  SMS (Twilio)  │  │
│  │  Volume Prof │   │ Invalidation │   │  Dashboard     │  │
│  └──────────────┘   └──────────────┘   └────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
spy-wave-scanner/
├── config/
│   ├── settings.yaml          # Timeframes, pivot sensitivity, fib levels
│   └── alert_config.yaml      # Slack webhooks, email, SMS settings
├── src/
│   ├── models.py              # Data classes: Pivot, WaveCount, Alert, etc.
│   ├── data_feed.py           # Polygon.io OHLCV fetching + RSI/MACD
│   ├── pivot_detector.py      # Swing high/low identification
│   ├── fib_mapper.py          # Fibonacci retracement & extension calc
│   ├── wave_counter.py        # Elliott Wave 5-wave/ABC pattern matching
│   ├── divergence.py          # RSI/MACD divergence detection
│   ├── alert_engine.py        # Notification dispatch (Slack/Email/SMS)
│   └── dashboard.py           # Streamlit real-time dashboard
├── scripts/
│   ├── run_scanner.py         # Main entry point / orchestrator
│   ├── backtest.py            # Historical wave detection validation
│   └── calibrate.py           # Grid-search parameter tuning
├── tests/
│   ├── test_pivots.py
│   ├── test_fibs.py
│   ├── test_wave_rules.py
│   └── test_alerts.py
└── .github/workflows/
    └── scanner.yml            # Runs every 5 min during market hours
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export POLYGON_API_KEY="your_polygon_api_key"
export SLACK_WEBHOOK="https://hooks.slack.com/services/..."  # optional
```

### 3. Run the scanner (CLI)

```bash
python scripts/run_scanner.py
python scripts/run_scanner.py --ticker AVGO --timeframe 15min
python scripts/run_scanner.py --lookback 10 --sensitivity 3
```

### 4. Launch the dashboard

```bash
python scripts/run_scanner.py --dashboard
# or directly:
streamlit run src/dashboard.py
```

### 5. Run tests

```bash
pip install pytest
pytest tests/ -v
```

## Modules

### Data Feed (`data_feed.py`)
Fetches OHLCV bars from Polygon.io and computes RSI(7,14), MACD(5,13,8), and Volume SMA(20).

### Pivot Detector (`pivot_detector.py`)
Identifies swing highs and lows using a configurable sensitivity window. Filters noise by enforcing minimum swing percentages and alternation.

### Fibonacci Mapper (`fib_mapper.py`)
Calculates retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%) and extension levels (100%, 127.2%, 138.2%, 161.8%, 200%, 261.8%). Detects confluence zones where multiple fib levels cluster.

### Wave Counter (`wave_counter.py`)
Applies the three cardinal Elliott Wave rules:
1. Wave 2 cannot retrace more than 100% of Wave 1
2. Wave 3 cannot be the shortest impulse wave
3. Wave 4 cannot overlap Wave 1 territory

Supports both 5-wave impulse and ABC corrective patterns. Assigns confidence scores and projects next-wave targets.

### Divergence Detector (`divergence.py`)
Detects bullish and bearish divergences on RSI and MACD histogram at swing pivot points — key confirmations for wave completions.

### Alert Engine (`alert_engine.py`)
Monitors price proximity to key levels and dispatches alerts via Slack, email, or SMS. Implements cooldown to prevent duplicate alerts.

**Alert types:**
| Signal | Priority | Action |
|--------|----------|--------|
| Wave 5 completing + RSI divergence | HIGH | Immediate alert |
| Invalidation level breached | HIGH | Count invalidated |
| Price at fib confluence zone | MEDIUM | Watch for confirmation |
| Wave 4 approaching resistance | MEDIUM | Prepare for entry |
| Wave count unclear | LOW | Log only |

### Dashboard (`dashboard.py`)
Streamlit-based real-time UI with:
- Dark-themed candlestick chart with wave labels
- Fibonacci horizontal lines with price annotations
- Wave connector lines between pivots
- RSI and MACD sub-panels
- Live price badge and bid/ask bar
- Alert history and projection panel

## GitHub Actions

The scanner runs every 5 minutes during US market hours (Mon-Fri 9:30 AM - 4:00 PM ET) via GitHub Actions. Store credentials in repository secrets:

- `POLYGON_API_KEY` - Polygon.io API key
- `SLACK_WEBHOOK` - Slack incoming webhook URL
- `ALERT_EMAIL` - Email address for alerts
- `SMTP_PASSWORD` - SMTP password for email delivery

## Configuration

Edit `config/settings.yaml` to adjust:

```yaml
ticker: SPY
timeframes:
  primary: "5min"
  confirmation: "15min"
pivot_detection:
  sensitivity: 5        # 3=aggressive, 5=balanced, 8=conservative
  min_swing_pct: 0.3    # ~$2 move on SPY at $685
fibonacci:
  confluence_tolerance: 0.50
alerts:
  proximity_threshold_pct: 0.15
  cooldown_minutes: 15
indicators:
  rsi_periods: [7, 14]
  macd_fast: 5
  macd_slow: 13
  macd_signal: 8
```

## Backtesting & Calibration

```bash
# Backtest over 30 days of 5-min data
python scripts/backtest.py --ticker SPY --days 30

# Auto-calibrate pivot sensitivity and swing thresholds
python scripts/calibrate.py --ticker SPY --days 30
```

## Extension Points

- **Multi-ticker support** - add AVGO, QQQ, or any Polygon-supported ticker
- **Multi-timeframe confluence** - run wave counts on 5min, 15min, hourly simultaneously
- **Options flow integration** - cross-reference wave targets with unusual options activity
- **ML confidence layer** - train a classifier on historical wave patterns
