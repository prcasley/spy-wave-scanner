"""Run every detector on one ticker/timeframe and score the results."""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from . import candles, chart, setups
from .core import Ctx, sma
from .evaluate import baseline, evaluate, pullback_profile, summarize


def normalize_index(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """One time convention for every source: intraday = New York time (tz-aware), daily/weekly = date (naive)."""
    idx = pd.DatetimeIndex(df.index)
    if tf in ("1d", "1wk"):
        if idx.tz is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
    else:
        idx = idx.tz_localize("America/New_York") if idx.tz is None else idx.tz_convert("America/New_York")
    df = df.copy()
    df.index = idx
    return df


def analyze(df: pd.DataFrame, ticker: str, tf: str, cfg: dict) -> dict:
    df = normalize_index(df, tf)
    ctx = Ctx(df, tf, cfg, ticker)
    sigs = candles.detect(ctx) + chart.detect(ctx) + setups.detect(ctx)
    trades = evaluate(ctx, sigs, cfg["max_hold"], cfg["horizons"])
    fresh = trades[trades.end_idx >= ctx.n - cfg["fresh"]].copy() if len(trades) else trades
    if len(fresh):
        fresh["signal_close"] = [float(ctx.c[i]) for i in fresh.end_idx]
    return dict(ticker=ticker, tf=tf, trades=trades, fresh=fresh, base=baseline(ctx, cfg["horizons"]),
                profile=pullback_profile(ctx), bars=ctx.n, first=df.index[0], last=df.index[-1],
                chart=chart_payload(ctx, sigs), snapshot=snapshot(ctx) if tf == "1d" else None)


def _t(ts) -> int:
    """Wall-clock time as epoch seconds so the chart shows exchange time, not UTC."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return int(ts.value // 10**9)


def chart_payload(ctx: Ctx, sigs, bars: int = 260) -> dict:
    lo = max(0, ctx.n - bars)
    idx = ctx.df.index
    candles_ = [[_t(idx[i]), round(ctx.o[i], 4), round(ctx.h[i], 4), round(ctx.l[i], 4), round(ctx.c[i], 4)]
                for i in range(lo, ctx.n)]
    piv = [[_t(idx[p.idx]), round(p.price, 4), p.kind] for p in ctx.pivots if p.idx >= lo]
    marks = []
    for s in sigs:
        if s.end < lo:
            continue
        marks.append(dict(t=_t(idx[s.end]), ts=_t(idx[max(s.start, lo)]), p=s.pattern, c=s.category,
                          d=s.direction, stop=round(s.stop, 4), tgt=round(s.target, 4),
                          fresh=bool(s.end >= ctx.n - ctx.cfg["fresh"])))
    return dict(ticker=ctx.ticker, tf=ctx.tf, candles=candles_, pivots=piv, marks=marks)


def snapshot(ctx: Ctx) -> dict:
    """Daily-chart state for the watchlist comparison table."""
    c, h, n = ctx.c, ctx.h, ctx.n
    s50, s200 = sma(c, 50)[-1], sma(c, 200)[-1]

    w, m, q, y = (7, 30, 91, 365) if ctx.crypto else (5, 21, 63, 252)

    def ret(k):
        return round((c[-1] / c[-1 - k] - 1) * 100, 2) if n > k else None

    hi52 = h[-y:].max()
    trend = ("Uptrend" if c[-1] > s50 > s200 else "Downtrend" if c[-1] < s50 < s200
             else "Above 200" if c[-1] > s200 else "Below 200")
    return dict(ticker=ctx.ticker, market="crypto" if ctx.crypto else "stocks", close=round(float(c[-1]), 4 if c[-1] < 1 else 2),
                r1w=ret(w), r1m=ret(m), r3m=ret(q), r1y=ret(y), off_high=round((c[-1] / hi52 - 1) * 100, 2), rsi=round(float(ctx.rsi[-1]), 1),
                atr_pct=round(float(ctx.atr[-1] / c[-1] * 100), 2), trend=trend,
                vs50=round((c[-1] / s50 - 1) * 100, 2) if np.isfinite(s50) else None,
                vs200=round((c[-1] / s200 - 1) * 100, 2) if np.isfinite(s200) else None)


def combine(results: List[dict], tf_cfg: Dict[str, dict]) -> dict:
    trades = pd.concat([r["trades"] for r in results if len(r["trades"])], ignore_index=True)
    fresh = pd.concat([r["fresh"] for r in results if len(r["fresh"])], ignore_index=True) \
        if any(len(r["fresh"]) for r in results) else pd.DataFrame()
    bases = {(r["ticker"], r["tf"]): r["base"] for r in results}
    bars = {(r["ticker"], r["tf"]): r["bars"] for r in results}
    hz = {tf: c["horizons"] for tf, c in tf_cfg.items()}
    per_ticker = summarize(trades, bases, bars, hz)
    # pooled across the whole watchlist: bigger samples, steadier estimates
    pooled_tr = trades.assign(ticker="ALL")
    pooled_base, pooled_bars = {}, {}
    for tf in trades.tf.unique():
        keys = [k for k in bases if k[1] == tf]
        w = sum(bars[k] for k in keys)
        pooled_bars[("ALL", tf)] = w
        pooled_base[("ALL", tf)] = {h: sum(bases[k][h] * bars[k] for k in keys) / w for h in hz[tf]}
    pooled = summarize(pooled_tr, pooled_base, pooled_bars, hz)
    stats = pd.concat([pooled, per_ticker], ignore_index=True)
    return dict(trades=trades, fresh=fresh, stats=stats, profiles=[r["profile"] for r in results],
                charts=[r["chart"] for r in results], snapshots=[r["snapshot"] for r in results if r["snapshot"]],
                coverage=[dict(ticker=r["ticker"], tf=r["tf"], bars=r["bars"], first=str(r["first"])[:16],
                               last=str(r["last"])[:16]) for r in results])
