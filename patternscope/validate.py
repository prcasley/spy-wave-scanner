#!/usr/bin/env python3
"""PatternScope research validation (heavy — run weekly or on demand).

  python validate.py                      # watchlist + S&P 500 universe, all timeframes
  python validate.py --limit 60           # quick run on 60 random S&P names
Writes  output/validation/verdicts.csv, output/PatternScope.xlsx, output/report.html, output/guide.html
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

from patternscope import cockpit, excel, guide, report
from patternscope.config import CRYPTO, TIMEFRAMES, WATCHLIST, is_crypto
from patternscope.data import load_dividends, load_yahoo
from patternscope.pipeline import analyze, combine
from patternscope.validation import load_universe, run_universe, verdicts, write_tables

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="output")
    ap.add_argument("--tf", nargs="+", default=["1h", "1d", "1wk"])
    ap.add_argument("--limit", type=int, default=0, help="random subset of the universe for a quick run")
    ap.add_argument("--hourly-sample", type=int, default=80)
    a = ap.parse_args(argv)
    t0 = time.time()

    print("Watchlist…")
    results = []
    for tk in WATCHLIST + CRYPTO:
        for tf in a.tf:
            try:
                df = load_yahoo(tk, tf)
                if len(df) < 120:
                    continue
                r = analyze(df, tk, tf, TIMEFRAMES[tf])
                if r["snapshot"] is not None and not is_crypto(tk):
                    r["snapshot"]["dividends"] = load_dividends(tk)
                results.append(r)
            except Exception as e:
                print(f"  ERROR {tk} {tf}: {e}", file=sys.stderr)
    res = combine(results, TIMEFRAMES)

    print("Universe…")
    uni = load_universe(os.path.join(HERE, "universe_sp500.csv"))
    if a.limit:
        uni = uni.sample(n=min(a.limit, len(uni)), random_state=7)
    ut = run_universe(uni, a.tf, hourly_sample=a.hourly_sample)
    print(f"  universe detections: {len(ut):,}")

    tbl = verdicts(res["trades"], ut, res["stats"])
    meta = dict(universe_tickers=len(uni), universe_trades=len(ut), timeframes="/".join(a.tf),
                hourly_sample=a.hourly_sample, minutes=round((time.time() - t0) / 60, 1))
    write_tables(os.path.join(a.out, "validation"), tbl, meta)
    excel.build(os.path.join(a.out, "PatternScope.xlsx"), res, tbl, meta, uni)
    with open(os.path.join(a.out, "report.html"), "w", encoding="utf-8") as f:
        f.write(report.build(res, TIMEFRAMES, verdicts=tbl))
    with open(os.path.join(a.out, "cockpit.html"), "w", encoding="utf-8") as f:
        f.write(cockpit.build(res, TIMEFRAMES, verdicts=tbl))
    with open(os.path.join(a.out, "guide.html"), "w", encoding="utf-8") as f:
        f.write(guide.build(res["stats"], time.strftime("%Y-%m-%d"), verdicts=tbl))
    print(tbl.verdict.value_counts().to_string())
    print(f"Done in {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
