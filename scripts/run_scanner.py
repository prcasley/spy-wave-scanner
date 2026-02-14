#!/usr/bin/env python3
"""Main entry point — orchestrates the full SPY Wave Scanner pipeline.

Usage:
    python scripts/run_scanner.py                # defaults: SPY, 5min, 5-day lookback
    python scripts/run_scanner.py --ticker AVGO --timeframe 15min
    python scripts/run_scanner.py --dashboard    # launch Streamlit UI
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_feed import DataFeed
from src.pivot_detector import PivotDetector
from src.fib_mapper import FibMapper
from src.wave_counter import WaveCounter
from src.divergence import DivergenceDetector
from src.alert_engine import AlertEngine
from src.models import WaveDirection, WaveLabel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scanner")


# ──────────────────────────────────────────────────────────────────────────
# Configuration loader
# ──────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load settings.yaml and merge with environment overrides."""
    config_path = ROOT / "config" / "settings.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    # Allow env-var overrides
    cfg.setdefault("ticker", os.environ.get("TICKER", "SPY"))
    return cfg


# ──────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────

def run_pipeline(
    ticker: str = "SPY",
    timeframe: str = "5min",
    lookback_days: int = 5,
    sensitivity: int = 5,
    min_swing_pct: float = 0.3,
) -> None:
    """Execute the full scan pipeline and dispatch alerts."""

    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        logger.error("POLYGON_API_KEY not set — aborting")
        sys.exit(1)

    # 1. Fetch data
    logger.info("=== SPY Wave Scanner — %s %s ===", ticker, timeframe)
    feed = DataFeed(api_key=api_key, ticker=ticker)
    df = feed.get_bars(timeframe=timeframe, lookback_days=lookback_days)
    if df.empty:
        logger.warning("No data returned — market may be closed")
        return
    df = feed.compute_indicators(df)
    last_close = df["close"].iloc[-1]
    logger.info("Latest close: $%.2f (%d bars)", last_close, len(df))

    # 2. Detect pivots
    detector = PivotDetector(sensitivity=sensitivity)
    pivots = detector.find_pivots(df)
    pivots = detector.filter_significant_pivots(pivots, min_swing_pct=min_swing_pct)
    seq = detector.classify_pivot_sequence(pivots)
    logger.info("Pivots: %d significant, sequence = %s", len(pivots), seq.value)

    # 3. Wave counting — try down impulse first, then up, then corrective
    wc = WaveCounter()
    wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.DOWN)
    if wave_count is None:
        wave_count = wc.count_impulse_best(pivots, direction=WaveDirection.UP)
    if wave_count is None:
        wave_count = wc.count_corrective(pivots)

    if wave_count:
        logger.info(
            "Wave count: %s %s — %d waves, confidence %.0f%%",
            wave_count.pattern_type,
            wave_count.direction.value,
            len(wave_count.waves),
            wave_count.confidence * 100,
        )
        if wave_count.violations:
            logger.warning("Violations: %s", wave_count.violations)
    else:
        logger.info("No clear wave count detected")

    # 4. Fibonacci levels
    fm = FibMapper()
    fib_levels = []
    confluence_zones = []
    if wave_count and wave_count.waves:
        w1 = wave_count.wave_by_label(WaveLabel.W1)
        if w1:
            fib_levels = fm.calculate_retracements(
                swing_high=max(w1.start.price, w1.end.price),
                swing_low=min(w1.start.price, w1.end.price),
                direction="down" if wave_count.direction == WaveDirection.DOWN else "up",
            )
        w2 = wave_count.wave_by_label(WaveLabel.W2)
        if w1 and w2:
            ext_levels = fm.calculate_extensions(w1.start.price, w1.end.price, w2.end.price)
            fib_levels.extend(ext_levels)
            confluence_zones = fm.find_fib_confluence([fib_levels])
            logger.info("Fib levels: %d, confluence zones: %d", len(fib_levels), len(confluence_zones))

    # 5. Divergence detection
    div_det = DivergenceDetector()
    divergences = div_det.detect_rsi_divergence(df, pivots)
    divergences += div_det.detect_macd_divergence(df, pivots)
    if divergences:
        logger.info("Divergences: %d detected", len(divergences))

    # 6. Projections
    projection = None
    if wave_count:
        projection = wc.project_targets(wave_count)
        if projection:
            logger.info(
                "Projection: %s target $%.2f (invalidation $%.2f)",
                projection.next_wave, projection.primary_target, projection.invalidation,
            )

    # 7. Alerts
    alert_engine = AlertEngine(ticker=ticker)
    alerts = alert_engine.check_proximity_alerts(
        current_price=last_close,
        wave_count=wave_count,
        fib_levels=fib_levels,
        confluence_zones=confluence_zones,
        divergences=divergences,
        projection=projection,
    )

    if alerts:
        logger.info("Alerts generated: %d", len(alerts))
        for alert in alerts:
            logger.info("  [%s] %s", alert.priority.value.upper(), alert.message)
            alert_engine.dispatch_alert(alert)
    else:
        logger.info("No alerts triggered at current price $%.2f", last_close)

    logger.info("=== Scan complete ===")


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="SPY Elliott Wave Scanner")
    parser.add_argument("--ticker", default=cfg.get("ticker", "SPY"))
    parser.add_argument(
        "--timeframe",
        default=cfg.get("timeframes", {}).get("primary", "5min"),
        choices=["1min", "5min", "15min", "1h", "1day"],
    )
    parser.add_argument("--lookback", type=int, default=5, help="Lookback days")
    parser.add_argument(
        "--sensitivity",
        type=int,
        default=cfg.get("pivot_detection", {}).get("sensitivity", 5),
    )
    parser.add_argument(
        "--min-swing",
        type=float,
        default=cfg.get("pivot_detection", {}).get("min_swing_pct", 0.3),
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the Streamlit dashboard instead of CLI scan",
    )
    args = parser.parse_args()

    if args.dashboard:
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "src" / "dashboard.py")],
            check=True,
        )
    else:
        run_pipeline(
            ticker=args.ticker,
            timeframe=args.timeframe,
            lookback_days=args.lookback,
            sensitivity=args.sensitivity,
            min_swing_pct=args.min_swing,
        )


if __name__ == "__main__":
    main()
