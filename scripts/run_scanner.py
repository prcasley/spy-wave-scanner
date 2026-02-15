#!/usr/bin/env python3
"""Main entry point — orchestrates the full SPY Wave Scanner pipeline.

Usage:
    python scripts/run_scanner.py                # defaults: SPY, 5min, 5-day lookback
    python scripts/run_scanner.py --ticker AVGO --timeframe 15min
    python scripts/run_scanner.py --dashboard    # launch Streamlit UI
    python scripts/run_scanner.py --dry-run      # analyse without sending alerts
    python scripts/run_scanner.py --no-cache     # skip data cache (always fetch live)
    python scripts/run_scanner.py --multi-tf     # confirm with higher timeframe
"""

from __future__ import annotations

import argparse
import json
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

from src.data_feed import DataFeed  # noqa: E402
from src.pivot_detector import PivotDetector  # noqa: E402
from src.fib_mapper import FibMapper  # noqa: E402
from src.wave_counter import WaveCounter  # noqa: E402
from src.divergence import DivergenceDetector  # noqa: E402
from src.alert_engine import AlertEngine  # noqa: E402
from src.models import WaveDirection, WaveLabel  # noqa: E402
from src.json_output import scan_result_to_json  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scanner")


# Width of the summary box
_BOX_W = 52


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
# Summary formatting
# ──────────────────────────────────────────────────────────────────────────

def _box_line(text: str) -> str:
    """Pad *text* to fit inside the summary box."""
    return f"\u2551 {text:<{_BOX_W - 4}} \u2551"


def print_summary(
    ticker: str,
    last_close: float,
    timeframe: str,
    bar_count: int,
    wave_count,
    projection,
    divergences: list,
    alerts: list,
) -> None:
    """Print a formatted summary box to stdout."""
    top = "\u2554" + "\u2550" * (_BOX_W - 2) + "\u2557"
    mid = "\u2560" + "\u2550" * (_BOX_W - 2) + "\u2563"
    bot = "\u255a" + "\u2550" * (_BOX_W - 2) + "\u255d"

    lines = [
        top,
        _box_line(f"{'SPY WAVE SCANNER \u2014 RESULTS':^{_BOX_W - 4}}"),
        mid,
        _box_line(f"Ticker:     {ticker}"),
        _box_line(f"Price:      ${last_close:.2f}"),
        _box_line(f"Timeframe:  {timeframe} ({bar_count} bars)"),
        _box_line(""),
    ]

    if wave_count:
        direction = wave_count.direction.value.upper()
        conf = f"{wave_count.confidence * 100:.0f}%"
        label = wave_count.current_wave_label.value if wave_count.current_wave_label else "?"
        lines.append(_box_line(f"Wave Count: {wave_count.pattern_type.title()} {direction} ({conf} confidence)"))
        lines.append(_box_line(f"Current:    Wave {label} completing"))
        if projection:
            lines.append(_box_line(f"Target:     ${projection.primary_target:.2f} ({projection.next_wave})"))
        if wave_count.invalidation_price:
            lines.append(_box_line(f"Invalidation: ${wave_count.invalidation_price:.2f}"))
    else:
        lines.append(_box_line("Wave Count: No clear pattern detected"))

    lines.append(_box_line(""))

    div_count = len(divergences)
    if div_count:
        div_types = set(d.type.value for d in divergences)
        div_str = ", ".join(f"{t} {divergences[0].indicator}" for t in div_types)
        lines.append(_box_line(f"Divergences: {div_count} ({div_str})"))
    else:
        lines.append(_box_line("Divergences: None"))

    lines.append(_box_line(f"Alerts:     {len(alerts)} triggered"))
    lines.append(bot)

    print("\n".join(lines))


# ──────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────

def run_pipeline(
    ticker: str = "SPY",
    timeframe: str = "5min",
    lookback_days: int = 5,
    sensitivity: int = 5,
    min_swing_pct: float = 0.3,
    dry_run: bool = False,
    use_cache: bool = True,
    multi_tf: bool = False,
    output_json: str | None = None,
) -> None:
    """Execute the full scan pipeline and dispatch alerts."""

    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        logger.error("POLYGON_API_KEY not set — aborting")
        sys.exit(1)

    # 1. Fetch data
    logger.info("=== SPY Wave Scanner — %s %s ===", ticker, timeframe)
    feed = DataFeed(api_key=api_key, ticker=ticker)
    df = feed.get_bars(timeframe=timeframe, lookback_days=lookback_days, use_cache=use_cache)
    market_status = "open"
    if df.empty:
        logger.warning("No live data — attempting to load most recent cache")
        df = _load_latest_cache(feed, ticker, timeframe, lookback_days)
        market_status = "closed"
    if df.empty:
        logger.warning("No data available — market may be closed and no cache exists")
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

    # 3b. Multi-timeframe confirmation
    if multi_tf and wave_count:
        _multi_timeframe_confirm(feed, wave_count, timeframe, lookback_days, sensitivity, min_swing_pct, use_cache)

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
            if not dry_run:
                alert_engine.dispatch_alert(alert)
            else:
                logger.info("  (dry-run — alert not dispatched)")
    else:
        logger.info("No alerts triggered at current price $%.2f", last_close)

    # 8. Print summary box
    print_summary(
        ticker=ticker,
        last_close=last_close,
        timeframe=timeframe,
        bar_count=len(df),
        wave_count=wave_count,
        projection=projection,
        divergences=divergences,
        alerts=alerts,
    )

    # 9. Write JSON output if requested
    if output_json:
        ohlcv_records = []
        for ts, row in df.iterrows():
            ohlcv_records.append({
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            })

        result = scan_result_to_json(
            ticker=ticker,
            timestamp=datetime.now(),
            current_price=float(last_close),
            timeframe=timeframe,
            bar_count=len(df),
            ohlcv_records=ohlcv_records,
            pivots=pivots,
            wave_count=wave_count,
            fib_levels=fib_levels,
            confluence_zones=confluence_zones,
            divergences=divergences,
            alerts=alerts,
            projection=projection,
            market_status=market_status,
        )

        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        logger.info("JSON output written to %s", out_path)

    logger.info("=== Scan complete ===")


# ──────────────────────────────────────────────────────────────────────────
# Cache fallback (weekends / market closed)
# ──────────────────────────────────────────────────────────────────────────

def _load_latest_cache(feed: DataFeed, ticker: str, timeframe: str, lookback_days: int):
    """Try to load the most recent cached parquet file for this ticker/timeframe."""
    import pandas as pd

    cache_dir = feed.cache_dir
    if not cache_dir.exists():
        return pd.DataFrame()
    pattern = f"{ticker}_{timeframe}_{lookback_days}d_*.parquet"
    files = sorted(cache_dir.glob(pattern), reverse=True)
    if files:
        logger.info("Loading cached data from %s", files[0])
        return pd.read_parquet(files[0])
    return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────
# Multi-timeframe confirmation
# ──────────────────────────────────────────────────────────────────────────

# Map primary timeframe to confirmation timeframe
_CONFIRM_TF = {
    "1min": "5min",
    "5min": "15min",
    "15min": "1h",
    "1h": "1day",
    "1day": "1day",
}


def _multi_timeframe_confirm(
    feed: DataFeed,
    wave_count,
    primary_tf: str,
    lookback_days: int,
    sensitivity: int,
    min_swing_pct: float,
    use_cache: bool,
) -> None:
    """Run a confirmation scan on a higher timeframe and boost confidence if directions agree."""
    confirm_tf = _CONFIRM_TF.get(primary_tf, primary_tf)
    if confirm_tf == primary_tf:
        return

    logger.info("Multi-TF: confirming with %s timeframe", confirm_tf)
    df2 = feed.get_bars(timeframe=confirm_tf, lookback_days=lookback_days, use_cache=use_cache)
    if df2.empty:
        logger.info("Multi-TF: no data for %s — skipping", confirm_tf)
        return
    df2 = feed.compute_indicators(df2)

    detector = PivotDetector(sensitivity=sensitivity)
    pivots2 = detector.find_pivots(df2)
    pivots2 = detector.filter_significant_pivots(pivots2, min_swing_pct=min_swing_pct)

    wc2 = WaveCounter()
    confirm_count = wc2.count_impulse_best(pivots2, direction=wave_count.direction)
    if confirm_count is None:
        confirm_count = wc2.count_corrective(pivots2, direction=wave_count.direction)

    if confirm_count and confirm_count.direction == wave_count.direction:
        boost = 0.10
        old_conf = wave_count.confidence
        wave_count.confidence = min(wave_count.confidence + boost, 1.0)
        logger.info(
            "Multi-TF: %s confirms %s direction — confidence %.0f%% -> %.0f%%",
            confirm_tf, wave_count.direction.value,
            old_conf * 100, wave_count.confidence * 100,
        )
    else:
        logger.info("Multi-TF: %s does not confirm — no boost", confirm_tf)


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without sending alerts",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip data cache — always fetch live from Polygon",
    )
    parser.add_argument(
        "--multi-tf",
        action="store_true",
        help="Confirm wave count with higher timeframe",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Path to write scan results as JSON (for GitHub Pages dashboard)",
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
            dry_run=args.dry_run,
            use_cache=not args.no_cache,
            multi_tf=args.multi_tf,
            output_json=args.output_json,
        )


if __name__ == "__main__":
    main()
