#!/usr/bin/env python3
"""Live-data diagnostic for Wave Options Scanner.

One-shot check that reports pass/fail for every pipeline stage against real
Yahoo Finance, so you can confirm the scanner works in your environment
before turning on the scheduler.

Usage:
    python scripts/check_live.py                # default: SPY
    python scripts/check_live.py AAPL SPY NVDA
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_feed import DataFeed, DataFeedError  # noqa: E402
from src.divergence import DivergenceDetector  # noqa: E402
from src.fib_mapper import FibMapper  # noqa: E402
from src.models import WaveDirection, WaveLabel  # noqa: E402
from src.options_feed import OptionsFeed, OptionsFeedError  # noqa: E402
from src.pivot_detector import PivotDetector  # noqa: E402
from src.signal_builder import build_signal  # noqa: E402
from src.strategy_selector import select_strategy  # noqa: E402
from src.wave_counter import WaveCounter  # noqa: E402


OK = "  PASS"
FAIL = "  FAIL"


def _step(label: str, fn):
    print(f"\n[{label}] ...", end=" ", flush=True)
    try:
        result = fn()
        print(OK)
        return result
    except (DataFeedError, OptionsFeedError) as exc:
        print(FAIL)
        print(f"   -> {type(exc).__name__}: {exc}")
        sys.exit(2)
    except Exception as exc:
        print(FAIL)
        print(f"   -> {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(3)


def check(ticker: str) -> None:
    print("=" * 60)
    print(f"Live-data check: {ticker}")
    print("=" * 60)

    feed = DataFeed()
    options_feed = OptionsFeed()

    df = _step(
        "Yahoo v8 chart fetch (1h, 60d)",
        lambda: feed.get_bars(timeframe="1h", lookback_days=60, use_cache=False, ticker=ticker),
    )
    print(f"   bars={len(df)} last_close=${df['close'].iloc[-1]:.2f}")

    df = _step("Indicator math (RSI, MACD, VolSMA)", lambda: feed.compute_indicators(df))

    pivots = _step(
        "Swing pivot detection",
        lambda: PivotDetector(sensitivity=5).filter_significant_pivots(
            PivotDetector(sensitivity=5).find_pivots(df), min_swing_pct=0.5
        ),
    )
    print(f"   pivots={len(pivots)}")

    def _wave():
        wc = WaveCounter()
        for direction in (WaveDirection.DOWN, WaveDirection.UP):
            cnt = wc.count_impulse_best(pivots, direction=direction)
            if cnt:
                return wc, cnt
        for direction in (WaveDirection.UP, WaveDirection.DOWN):
            cnt = wc.count_corrective(pivots, direction=direction)
            if cnt:
                return wc, cnt
        raise RuntimeError("No wave count could be fitted")

    wc, wave_count = _step("Wave counting", _wave)
    print(
        f"   {wave_count.pattern_type} {wave_count.direction.value} "
        f"confidence={wave_count.confidence:.0%} waves={len(wave_count.waves)}"
    )

    def _fibs():
        fm = FibMapper()
        first = wave_count.wave_by_label(WaveLabel.W1) or wave_count.waves[0]
        levels = fm.calculate_retracements(
            swing_high=max(first.start.price, first.end.price),
            swing_low=min(first.start.price, first.end.price),
            direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
        )
        return levels, fm.find_fib_confluence([levels])

    fibs, zones = _step("Fibonacci levels + confluence zones", _fibs)
    print(f"   levels={len(fibs)} zones={len(zones)}")

    def _div():
        d = DivergenceDetector()
        return d.detect_rsi_divergence(df, pivots) + d.detect_macd_divergence(df, pivots)

    divs = _step("RSI/MACD divergence", _div)
    print(f"   divergences={len(divs)}")

    chain = _step(
        "Yahoo v7 options chain fetch",
        lambda: options_feed.get_chain(ticker, target_dte=7),
    )
    print(
        f"   spot=${chain.spot:.2f} expiration={chain.selected_expiration.date() if chain.selected_expiration else '?'} "
        f"calls={len(chain.calls)} puts={len(chain.puts)}"
    )

    direction = "long" if wave_count.direction == WaveDirection.UP else "short"
    projection = wc.project_targets(wave_count)
    strategy = _step(
        "Strategy selection",
        lambda: select_strategy(
            chain=chain,
            direction=direction,
            invalidation_price=wave_count.invalidation_price,
            target_price=projection.primary_target if projection else None,
        ),
    )
    print(f"   structure={strategy.structure} legs={len(strategy.legs)}")

    signal = _step(
        "Signal JSON build + schema validation",
        lambda: build_signal(
            ticker=ticker,
            spot=float(df["close"].iloc[-1]),
            wave_count=wave_count,
            projection=projection,
            divergences=divs,
            confluence_zones=zones,
            chain=chain,
            strategy=strategy,
        ),
    )
    print(f"   signal_id={signal['signal_id'][:8]} score={signal['confluence']['score']}")

    print("\n--- LIVE SIGNAL ---")
    print(json.dumps(signal, indent=2))


def main() -> None:
    tickers = [t.upper() for t in sys.argv[1:]] or ["SPY"]
    for t in tickers:
        try:
            check(t)
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    main()
