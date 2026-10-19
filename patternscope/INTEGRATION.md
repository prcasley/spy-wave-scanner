# Agent brief: connect the local paper-trading simulator to PatternScope

You are working on Prat's **local paper-trading simulator** (on his Windows PC). Your job is to make it take
trade signals from **PatternScope** reliably, price them with fresh data, and paper-trade them using the same rules
PatternScope used in its backtests, so live results can be compared with the backtest.

Read this whole brief before changing anything. Work in small commits and report back after each phase.

---

## 1. What already exists (don't rebuild it)

| Piece | Where | Notes |
|---|---|---|
| PatternScope engine | GitHub `prcasley/spy-wave-scanner`, folder `patternscope/` | ~110 candle / chart / indicator patterns, backtested and graded |
| Signal feed (JSON) | `https://prcasley.github.io/spy-wave-scanner/patterns/latest.json` | Rebuilt once per weekday after the US close (~5:40pm ET) plus on code pushes. CORS is open. |
| Visual front page | `https://prcasley.github.io/spy-wave-scanner/patterns/` | For humans, not for parsing |
| Excel of everything | `https://github.com/prcasley/spy-wave-scanner/releases/download/patternscope-latest/PatternScope.xlsx` | For humans |
| Python package | `pip install "patternscope[data] @ git+https://github.com/prcasley/spy-wave-scanner#subdirectory=patternscope"` | Lets the simulator run the detectors itself on live candles |

Watchlist: SPY, QQQ, NVDA, TSLA, MU, GOOGL, NBIS, DELL, BE, CLSK, TSLW + crypto BTC-USD, ETH-USD, SOL-USD, XRP-USD, DOGE-USD.
Timeframes: `1h` (day trades), `1d` (swing), `1wk` (buy-and-hold).

---

## 2. Feed schema (`latest.json`, `schema_version` = 1)

```jsonc
{
  "schema_version": 1,                 // refuse to run if this is > the version you were built for
  "generated_utc": "2026-10-19T07:51:49+00:00",
  "source": "PatternScope",
  "signals": [{
    "id": "39b69b5f5d9d5476",          // stable: hash(ticker|tf|pattern|signal_time) — DE-DUPLICATE ON THIS
    "ticker": "DELL", "market": "stocks|crypto", "tf": "1h|1d|1wk",
    "pattern": "Bullish RSI Divergence", "category": "chart|candle|setup",
    "direction": "long|short",
    "signal_time": "2026-10-16T13:30:00-04:00",   // bar at which the pattern confirmed. Hourly: New York time with offset; daily/weekly: date only, no offset
    "signal_close": 456.73,
    "entry_rule": "next bar open",
    "stop": 448.03, "target": 474.13,
    "risk_per_share": 8.70, "reward_risk": 2.0,
    "grade": "A|B|C|F|low-n",          // how this pattern did on the watchlist historically
    "hist_trades": 154, "hist_win_pct": 22.1, "hist_expectancy_R": 0.263, "hist_bars_to_target": 4.0,
    "verdict": "Confirmed|Promising|Watchlist only|Faded out-of-sample|Costs kill it|No edge|Too few trades|null",
    "guide_url": "https://.../guide.html#bullish-rsi-divergence"
  }],
  "snapshots": [{ "ticker", "market", "close", "r1w", "r1m", "r3m", "r1y", "off_high", "rsi", "atr_pct", "trend", "vs50", "vs200" }],
  "verdicts":  [{ "tf", "pattern", "direction", "verdict", "uni_R_net", "oos_R_net" }]
}
```

`verdict` comes from a test on ~500 S&P 500 stocks (survivorship, out-of-sample split, trading costs, false-discovery
correction). It is `null` for crypto (crypto wasn't in that test).

---

## 3. Phases

### Phase 0 — Understand the simulator (no code changes)
1. Map how it currently gets data from the spy-wave-scanner repo (which files/URLs, how often, what it parses).
2. Map how it decides to open a position, how it fills, sizes, closes, and where it stores trades.
3. Write a short summary for Prat: current data flow, fill logic, storage, and anything that conflicts with Section 4.

### Phase 1 — Signals from the feed
1. Replace any scraping of repo HTML/CSV with a poller for `latest.json` (every 15 min is plenty; it changes ~daily).
2. Validate `schema_version`. If `generated_utc` is older than 30 hours on a weekday, flag the feed as stale in the UI and don't open new trades from it.
3. De-duplicate on `id`. Never open the same signal twice, even across restarts (persist seen IDs).
4. Default filter (make it configurable):
   - stocks: `grade in {A,B}` **and** `verdict in {Confirmed, Promising}`
   - crypto: `grade in {A,B}`
   - skip `low-n` and `F` always.

### Phase 2 — Live prices
- **Crypto:** CCXT public endpoints, **exchange = coinbase (or kraken)**. Do **not** use Binance, which blocks US IPs.
  `ccxt.coinbase({"enableRateLimit": True}).fetch_ohlcv("BTC/USD", "1h")` for bars; `fetch_ticker` for last price.
- **Stocks:** `yfinance` is acceptable for delayed quotes and bars. It is NOT accurate enough for real-time or 0DTE fills.
- **Options / SPY 0DTE (later, optional):** `schwab-py`. It needs Prat's Schwab account plus an approved Schwab developer app.
  Schwab's API has no historical options prices and no paper account, so fills stay simulated in our app.
- Every quote must carry a timestamp. **Never fill on a quote older than 60 s (crypto) or 15 min (delayed stocks)**; mark the trade "waiting for fresh price" instead.
- No verified free overnight stock feed exists, so don't simulate overnight stock fills.

### Phase 3 — Fill & exit rules (must match the backtest)
| Rule | Value |
|---|---|
| Entry | Open of the first bar **after** `signal_time` on the signal's timeframe |
| Stop / target | From the feed. If the entry open gaps past the stop or past the target, **skip** the trade (backtest marks these invalid) |
| Stop closer than 0.2 × ATR to entry | **Skip** (too tight to be meaningful; backtest drops these) |
| Same bar hits stop and target | Count as **stop** |
| Gap through stop | Fill at that bar's open, not the stop |
| Time stop (max bars held) | 1h: 14 bars, 1d: 20 bars, 1wk: 26 bars → exit at that bar's close |
| Day-trade setups on 1h (`Opening Range…`, `VWAP…`, `Gap…`) | Close by end of that session |
| Costs per side | 1h: 5 bps, 1d: 3 bps, 1wk: 3 bps (configurable) |
| Crypto | Trades 24/7. A year is 365 daily bars and a week is 7 bars. |

Position sizing default: risk **0.5% of simulated equity** per trade = equity × 0.005 ÷ `risk_per_share`.
Configurable max open positions (default 8) and max one open trade per ticker per timeframe.

### Phase 4 — Optional: real-time detection
The feed is daily. For intraday freshness, run the detectors locally on live candles:
```python
from patternscope.config import TIMEFRAMES
from patternscope.data import load_ccxt
from patternscope.pipeline import analyze
df = load_ccxt("BTC-USD", "1h", exchange="coinbase", days=120)
fresh = analyze(df, "BTC-USD", "1h", TIMEFRAMES["1h"])["fresh"]   # stop/target/pattern/signal_time
```
Build the same `id` (sha1 of `ticker|tf|pattern|signal_time` ISO string, first 16 hex chars) so local and feed signals
de-duplicate against each other. Use the feed's `grade` and `verdict` for filtering.

### Phase 5 — Forward-test log (the real proof)
Store every simulated trade with: `signal_id, ticker, tf, pattern, direction, grade, verdict, signal_time, entry_time,
entry, stop, target, exit_time, exit, exit_reason (target|stop|timeout|session_end), R, R_net, quote_source, quote_age_s`.
Export as CSV daily. Add a view comparing **live average R per pattern vs `hist_expectancy_R`**: that's how Prat will
know whether the edges are real.

### Phase 6 — Tests
1. **Replay test:** feed the simulator historical bars plus historical signals and check it reproduces PatternScope's
   outcomes (`patternscope/output/all_detections.csv` or the Excel "All Detections" sheet) within rounding.
2. Stale-feed test, duplicate-signal test, gap-through-stop test, same-bar stop/target test, crypto weekend test.

---

## 4. Rules for you (the agent)
- **Never delete Prat's files, data, or trade history without asking him first and getting a yes.**
- Don't modify `prcasley/spy-wave-scanner` directly. If the feed needs a change, describe it and Prat will route it
  (that repo has its own agent rules in `CLAUDE.md`).
- Never commit API keys or account tokens; use environment variables / a local `.env` that is git-ignored.
- Paper trading only. No live order placement, ever, unless Prat explicitly asks in writing.
- UI changes: keep the simulator's existing look unless Prat asks; if asked, confirm the theme with him first.
- After each phase, report: what changed, what you tested, what's next. Keep it short.

## 5. Done means
- [ ] Signals come only from `latest.json` (+ optional local detection), de-duplicated by `id`
- [ ] Stale feed or stale quote blocks new entries, and the UI shows that clearly
- [ ] Fills / exits follow Section 3 exactly; replay test passes
- [ ] Crypto priced via CCXT (coinbase); stocks via yfinance with quote age shown
- [ ] Forward-test log exports daily and compares live R to historical R per pattern
