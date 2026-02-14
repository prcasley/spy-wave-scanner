#!/usr/bin/env python3
"""Calibrate — grid-search over pivot sensitivity and Fibonacci tolerance
to find parameters that maximise wave-detection hit rate.

Usage:
    python scripts/calibrate.py --ticker SPY --days 30
"""

from __future__ import annotations

import argparse
import itertools
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.backtest import backtest

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("calibrate")


def calibrate(
    ticker: str = "SPY",
    timeframe: str = "5min",
    total_days: int = 30,
) -> dict:
    """Run a grid search over key parameters and return the best combo."""

    sensitivities = [3, 5, 8]
    min_swings = [0.2, 0.3, 0.5]

    best_score = -1.0
    best_params: dict = {}
    all_results: list[dict] = []

    combos = list(itertools.product(sensitivities, min_swings))
    logger.info(
        "Calibrating %d parameter combos on %s %s (%d days)",
        len(combos), ticker, timeframe, total_days,
    )

    for sensitivity, min_swing in combos:
        logger.info("--- sensitivity=%d  min_swing=%.2f ---", sensitivity, min_swing)
        result = backtest(
            ticker=ticker,
            timeframe=timeframe,
            total_days=total_days,
            sensitivity=sensitivity,
            min_swing_pct=min_swing,
        )
        if not result:
            continue

        # Score: weighted combination of hit rate and pattern-find rate
        patterns_found = result["impulse_patterns"] + result["corrective_patterns"]
        total = result["windows_scanned"] or 1
        find_rate = patterns_found / total
        hit_rate = result["hit_rate_pct"] / 100
        score = hit_rate * 0.6 + find_rate * 0.2 + result["avg_confidence"] * 0.2

        entry = {
            "sensitivity": sensitivity,
            "min_swing_pct": min_swing,
            "score": round(score, 4),
            **result,
        }
        all_results.append(entry)

        if score > best_score:
            best_score = score
            best_params = entry

    logger.info("=== Calibration Complete ===")
    logger.info("Best parameters:")
    for k, v in best_params.items():
        logger.info("  %-25s %s", k, v)

    return best_params


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Wave Scanner Parameters")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--timeframe", default="5min")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    calibrate(ticker=args.ticker, timeframe=args.timeframe, total_days=args.days)


if __name__ == "__main__":
    main()
