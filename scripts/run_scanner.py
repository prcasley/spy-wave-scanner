#!/usr/bin/env python3
"""Wave Options Scanner — one-off CLI entry point.

Usage:
    python scripts/run_scanner.py
    python scripts/run_scanner.py --tickers SPY,QQQ,NVDA
    python scripts/run_scanner.py --timeframe 15m --target-dte 7 --no-discord
    python scripts/run_scanner.py --dashboard
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.scanner import _env_tickers, scan_universe  # noqa: E402

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scanner.cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wave Options Scanner")
    parser.add_argument("--tickers", default=None, help="Comma-separated override of SCAN_TICKERS")
    parser.add_argument(
        "--timeframe",
        default="1h",
        choices=["5min", "15min", "1h", "1day"],
        help="Bar interval (default 1h — Yahoo lookback supports up to 730d)",
    )
    parser.add_argument("--lookback-days", type=int, default=60)
    parser.add_argument("--sensitivity", type=int, default=5)
    parser.add_argument("--min-swing", type=float, default=0.5)
    parser.add_argument("--target-dte", type=int, default=7)
    parser.add_argument("--use-cache", action="store_true", help="Allow on-disk cache hits")
    parser.add_argument("--no-discord", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard")
    parser.add_argument(
        "--print-signals", action="store_true",
        help="Pretty-print resulting signal JSON to stdout",
    )
    args = parser.parse_args()

    if args.dashboard:
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "src" / "dashboard.py")],
            check=True,
        )
        return

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else _env_tickers()
    )

    signals = scan_universe(
        tickers,
        timeframe=args.timeframe,
        lookback_days=args.lookback_days,
        sensitivity=args.sensitivity,
        min_swing_pct=args.min_swing,
        target_dte=args.target_dte,
        use_cache=args.use_cache,
        persist=not args.no_persist,
        post_to_discord=not args.no_discord,
    )

    print(f"\nScanned {len(tickers)} tickers, emitted {len(signals)} signals.")
    if args.print_signals:
        for sig in signals:
            print(json.dumps(sig, indent=2))


if __name__ == "__main__":
    main()
