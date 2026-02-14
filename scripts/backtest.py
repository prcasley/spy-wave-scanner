#!/usr/bin/env python3
"""Backtest — validate wave detection accuracy on historical data.

Usage:
    python scripts/backtest.py --ticker SPY --days 30 --timeframe 5min
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_feed import DataFeed
from src.pivot_detector import PivotDetector
from src.fib_mapper import FibMapper
from src.wave_counter import WaveCounter
from src.divergence import DivergenceDetector
from src.models import WaveDirection, WaveLabel

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("backtest")


def backtest(
    ticker: str = "SPY",
    timeframe: str = "5min",
    total_days: int = 30,
    window_days: int = 5,
    sensitivity: int = 5,
    min_swing_pct: float = 0.3,
) -> dict:
    """Slide a window over historical data and evaluate wave count quality.

    Returns a summary dict with stats on detected patterns and hit-rate on
    projected targets.
    """
    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        logger.error("POLYGON_API_KEY not set")
        sys.exit(1)

    feed = DataFeed(api_key=api_key, ticker=ticker)
    detector = PivotDetector(sensitivity=sensitivity)
    wc_engine = WaveCounter()
    fm = FibMapper()
    div_det = DivergenceDetector()

    end = datetime.now()
    start = end - timedelta(days=total_days)

    logger.info("Fetching %d days of %s data for %s", total_days, timeframe, ticker)
    df_full = feed.get_bars(timeframe=timeframe, lookback_days=total_days, end_date=end)
    if df_full.empty:
        logger.warning("No data returned")
        return {}
    df_full = feed.compute_indicators(df_full)

    total_windows = 0
    impulse_found = 0
    corrective_found = 0
    no_count = 0
    target_hits = 0
    target_checks = 0
    confidence_sum = 0.0

    # Slide window
    bars_per_window = max(1, int(len(df_full) * (window_days / total_days)))
    step = max(1, bars_per_window // 2)  # 50% overlap

    for i in range(0, len(df_full) - bars_per_window, step):
        window = df_full.iloc[i : i + bars_per_window]
        total_windows += 1

        pivots = detector.find_pivots(window)
        pivots = detector.filter_significant_pivots(pivots, min_swing_pct=min_swing_pct)

        wave_count = wc_engine.count_impulse_best(pivots, direction=WaveDirection.DOWN)
        if wave_count is None:
            wave_count = wc_engine.count_impulse_best(pivots, direction=WaveDirection.UP)
        if wave_count is None:
            wave_count = wc_engine.count_corrective(pivots)

        if wave_count is None:
            no_count += 1
            continue

        if wave_count.pattern_type == "impulse":
            impulse_found += 1
        else:
            corrective_found += 1

        confidence_sum += wave_count.confidence

        # Check if projected target was hit in the bars after this window
        projection = wc_engine.project_targets(wave_count)
        if projection and i + bars_per_window < len(df_full):
            lookahead = df_full.iloc[i + bars_per_window : i + bars_per_window + step]
            if not lookahead.empty:
                target_checks += 1
                target = projection.primary_target
                hit = (
                    lookahead["low"].min() <= target <= lookahead["high"].max()
                )
                if hit:
                    target_hits += 1

    # Summary
    patterns_found = impulse_found + corrective_found
    avg_conf = confidence_sum / patterns_found if patterns_found else 0.0
    hit_rate = target_hits / target_checks * 100 if target_checks else 0.0

    results = {
        "ticker": ticker,
        "timeframe": timeframe,
        "total_bars": len(df_full),
        "windows_scanned": total_windows,
        "impulse_patterns": impulse_found,
        "corrective_patterns": corrective_found,
        "no_pattern": no_count,
        "avg_confidence": round(avg_conf, 3),
        "target_checks": target_checks,
        "target_hits": target_hits,
        "hit_rate_pct": round(hit_rate, 1),
    }

    logger.info("=== Backtest Results ===")
    for k, v in results.items():
        logger.info("  %-25s %s", k, v)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Elliott Wave Scanner")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--timeframe", default="5min")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--sensitivity", type=int, default=5)
    parser.add_argument("--min-swing", type=float, default=0.3)
    args = parser.parse_args()

    backtest(
        ticker=args.ticker,
        timeframe=args.timeframe,
        total_days=args.days,
        window_days=args.window,
        sensitivity=args.sensitivity,
        min_swing_pct=args.min_swing,
    )


if __name__ == "__main__":
    main()
