# PatternScope

Detects ~110 trading patterns, backtests every past occurrence, and grades which ones actually play out — per ticker and per timeframe.

| Lens | Timeframe | Hold window | Use |
|---|---|---|---|
| Day trade | 1h (last ~2 yrs from Yahoo) | ~2 sessions; ORB/VWAP/gaps close at end of day | morning scalps |
| Swing | 1d | 20 bars | multi-day |
| Buy & hold | 1wk | 26 bars | entries, and knowing when pullbacks come |

## Run it
```bash
pip install -r requirements.txt
python scan.py                       # watchlist in patternscope/config.py, 1h + 1d + 1wk
python scan.py --tickers SPY NVDA --tf 1h
python scan.py --demo                # offline test with fake prices
```
Open `output/report.html`. CSVs: `pattern_stats.csv`, `live_signals.csv`, `all_detections.csv`.

## What's in the library
- **40 candlesticks** — hammer, engulfing, stars, harami, three soldiers/crows, tweezers, kicker, abandoned baby, three methods, tasuki, belt hold, counterattack… (reversals require trend context)
- **36 chart patterns** — double/triple tops & bottoms, head & shoulders (+inverse), cup & handle, rounding top/bottom, bull/bear flags & pennants, AB=CD, fib 50–61.8 bounce/rejection, RSI divergence, and triangles / wedges / rectangles / channels / broadening formations, each scored by which way it broke
- **35 setups** — golden/death cross, EMA 9/21, MACD crosses, RSI 30/70, Bollinger & TTM squeeze fires, NR7, inside bars, 52-week breakouts, 50-SMA & 20-EMA trend pullbacks, lost-50-SMA, gap fill vs gap-and-go, opening range breakout, VWAP reclaim/rejection

## How it scores
- Entry next bar's open. Stop/target checked bar by bar; both in one bar = stop. No hit = timeout at close.
- **Win %**, **expectancy (R)**, profit factor, **how long it takes to form**, **bars to target**, heat (MAE).
- **Edge** = how often price moved the pattern's way minus how often it does from any random bar. A 55% "win" on a stock that rises 55% of days is no edge.
- **Grade A** needs n ≥ 30, ≥ 0.25R, ≥ 5pp edge, and positive in both halves of history. `low-n` = under 20 samples.
- **Pullback map**: typical retracement depth/duration from swing structure, and where price sits now.

## Notes
- Detectors were tested for lookahead: >99.5% of signals reproduce identically on truncated history. Remaining differences come from rare swing-pivot revisions.
- Yahoo limits 1h history to ~730 days, so hourly samples are smaller than daily.
- Tune pivot sensitivity, hold windows and horizons in `patternscope/config.py`.

## Automation
`.github/workflows/scan.yml` runs once after the close on weekdays (manual run button too) and uploads the report as an artifact. No intraday or hourly runs.
