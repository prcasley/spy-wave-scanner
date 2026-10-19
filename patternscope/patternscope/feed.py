"""Machine-readable signal feed for other apps (e.g. the local paper-trading simulator).

Published at  https://prcasley.github.io/spy-wave-scanner/patterns/latest.json
Schema v1 (additive changes only; breaking changes bump schema_version):
{
  "schema_version": 1, "generated_utc": "...", "source": "PatternScope",
  "signals": [ {
     "id": "stable hash of ticker|tf|pattern|signal_time — use it to de-duplicate",
     "ticker", "market": "stocks|crypto", "tf": "1h|1d|1wk", "pattern", "category", "direction": "long|short",
     "signal_time": ISO-8601, "signal_close", "entry_rule": "next bar open",
     "stop", "target", "risk_per_share", "reward_risk",
     "grade", "hist_trades", "hist_win_pct", "hist_expectancy_R", "hist_bars_to_target",   # pooled watchlist history
     "verdict",                                                                            # S&P 500 validation (stocks)
     "guide_url"
  } ],
  "snapshots": [ {ticker, market, close, r1w, r1m, r3m, r1y, off_high, rsi, atr_pct, trend, vs50, vs200} ],
  "verdicts": [ {tf, pattern, direction, verdict, uni_R_net, oos_R_net} ]
}
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import is_crypto

GUIDE = "https://prcasley.github.io/spy-wave-scanner/patterns/guide.html#"


def _num(x, d=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else round(x, d)


def build(res: dict, verdicts: pd.DataFrame | None = None) -> dict:
    stats = res["stats"]
    pooled = {(r.tf, r.pattern): r for r in stats[stats.ticker == "ALL"].itertuples()} if len(stats) else {}
    vmap = {}
    if verdicts is not None and len(verdicts):
        for r in verdicts.itertuples():
            vmap[(r.tf, r.pattern)] = r.verdict
    sigs = []
    fr = res.get("fresh")
    if fr is not None and len(fr):
        for r in fr.itertuples():
            ts = pd.Timestamp(r.signal_time)
            iso = ts.isoformat()
            key = f"{r.ticker}|{r.tf}|{r.pattern}|{iso}"
            st = pooled.get((r.tf, r.pattern))
            risk = abs(r.signal_close - r.stop)
            sigs.append(dict(
                id=hashlib.sha1(key.encode()).hexdigest()[:16], ticker=r.ticker,
                market="crypto" if is_crypto(r.ticker) else "stocks", tf=r.tf, pattern=r.pattern, category=r.category,
                direction="long" if r.direction == 1 else "short", signal_time=iso,
                signal_close=_num(r.signal_close), entry_rule="next bar open", stop=_num(r.stop), target=_num(r.target),
                risk_per_share=_num(risk), reward_risk=_num(abs(r.target - r.signal_close) / risk if risk else None, 2),
                grade=getattr(st, "grade", None), hist_trades=int(st.n) if st is not None else None,
                hist_win_pct=_num(getattr(st, "target_pct", None), 1),
                hist_expectancy_R=_num(getattr(st, "expectancy_R", None), 3),
                hist_bars_to_target=_num(getattr(st, "bars_to_target_med", None), 1),
                verdict=vmap.get((r.tf, r.pattern)),
                guide_url=GUIDE + re.sub(r"[^a-z0-9]+", "-", r.pattern.lower()).strip("-"),
            ))
    order = {"A": 0, "B": 1, "C": 2, "low-n": 3, "F": 4, None: 5}
    sigs.sort(key=lambda s: (order.get(s["grade"], 5), -(s["hist_expectancy_R"] or -9)))
    snaps = [{k: v for k, v in s.items() if k != "dividends"} for s in res.get("snapshots", [])]
    vt = []
    if verdicts is not None and len(verdicts):
        vt = [dict(tf=r.tf, pattern=r.pattern, direction=r.direction, verdict=r.verdict,
                   uni_R_net=_num(r.uni_R_net, 3), oos_R_net=_num(r.oos_R_net, 3)) for r in verdicts.itertuples()]
    return dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source="PatternScope", signals=sigs, snapshots=snaps, verdicts=vt)


def write(path: str, res: dict, verdicts=None):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(build(res, verdicts), f, default=str, separators=(",", ":"))
