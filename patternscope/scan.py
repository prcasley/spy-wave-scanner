#!/usr/bin/env python3
"""PatternScope — scan, backtest and grade ~150 trading patterns.

Examples
  python scan.py                                   # watchlist x 1h, 1d, 1wk from Yahoo Finance
  python scan.py --tickers SPY NVDA --tf 1h        # day-trading lens only
  python scan.py --csv mydata/SPY_1d.csv --name SPY --tf 1d   # your own OHLCV file
  python scan.py --demo                            # synthetic data, no internet needed
Outputs land in ./output: report.html, pattern_stats.csv, live_signals.csv, all_detections.csv
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from patternscope import guide, report
from patternscope.config import TIMEFRAMES, WATCHLIST
from patternscope.data import load_csv, load_dividends, load_yahoo, synthetic
from patternscope.pipeline import analyze, combine


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", default=WATCHLIST)
    ap.add_argument("--tf", nargs="+", default=["1h", "1d", "1wk"], choices=list(TIMEFRAMES))
    ap.add_argument("--csv", help="load one OHLCV csv instead of Yahoo (use with --name and one --tf)")
    ap.add_argument("--name", default="CSV")
    ap.add_argument("--demo", action="store_true", help="synthetic prices to test the engine offline")
    ap.add_argument("--refresh", action="store_true", help="ignore the local data cache")
    ap.add_argument("--out", default="output")
    a = ap.parse_args(argv)

    os.makedirs(a.out, exist_ok=True)
    results, t0 = [], time.time()
    jobs = []
    if a.demo:
        jobs = [(f"DEMO{i}", tf, lambda tf=tf, i=i: synthetic(tf, 3000 if tf != "1wk" else 1200, seed=i))
                for i in range(1, 4) for tf in a.tf]
    elif a.csv:
        jobs = [(a.name, a.tf[0], lambda: load_csv(a.csv))]
    else:
        jobs = [(tk, tf, lambda tk=tk, tf=tf: load_yahoo(tk, tf, refresh=a.refresh)) for tk in a.tickers for tf in a.tf]

    for tk, tf, loader in jobs:
        try:
            df = loader()
            if len(df) < 120:
                print(f"  skip {tk} {tf}: only {len(df)} bars")
                continue
            r = analyze(df, tk, tf, TIMEFRAMES[tf])
            if r["snapshot"] is not None and not a.demo and not a.csv:
                r["snapshot"]["dividends"] = load_dividends(tk)
            results.append(r)
            print(f"  {tk:6s} {tf:4s} {len(df):6d} bars  {len(r['trades']):6d} detections  {len(r['fresh'])} live")
        except Exception as e:
            print(f"  ERROR {tk} {tf}: {e}", file=sys.stderr)
    if not results:
        print("No data processed.")
        return 1

    res = combine(results, TIMEFRAMES)
    res["stats"].to_csv(os.path.join(a.out, "pattern_stats.csv"), index=False)
    res["trades"].to_csv(os.path.join(a.out, "all_detections.csv"), index=False)
    if len(res["fresh"]):
        res["fresh"].to_csv(os.path.join(a.out, "live_signals.csv"), index=False)
    html = report.build(res, TIMEFRAMES, demo=a.demo)
    path = os.path.join(a.out, "report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    from datetime import datetime
    with open(os.path.join(a.out, "guide.html"), "w", encoding="utf-8") as f:
        f.write(guide.build(res["stats"], datetime.now().strftime("%Y-%m-%d")))
    print(f"\nDone in {time.time() - t0:.0f}s -> {path}")
    top = res["stats"]
    top = top[(top.ticker == "ALL") & top.grade.isin(["A", "B"])]
    if len(top):
        print("\nBest pooled patterns (grade A/B):")
        print(top[["tf", "pattern", "direction", "n", "target_pct", "expectancy_R", "grade"]].head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
