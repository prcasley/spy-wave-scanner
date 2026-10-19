"""Indicator & price-action setups: crosses, squeezes, gaps, ORB, VWAP, trend pullbacks.

Intraday-only setups (ORB, VWAP, gaps on intraday) carry a time stop at the end of
the session — they are day trades and are graded as such.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .core import Ctx, Signal, ema, linreg_end, rolling_std, sma


def _cross_up(a, b):
    out = np.zeros(len(a), bool)
    out[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return out


def _cross_dn(a, b):
    return _cross_up(b, a)


def _risk_sig(ctx, name, d, i, stop, start=None, rr=2.0, expire=None, entry_idx=None, entry_px=None):
    c = ctx.c[i] if entry_px is None else entry_px
    tgt = c + rr * (c - stop) if d == 1 else c - rr * (stop - c)
    return Signal(name, "setup", d, i if start is None else start, int(i), float(stop), float(tgt),
                  entry_idx=entry_idx, entry_px=entry_px, expire_idx=expire)


def detect(ctx: Ctx) -> List[Signal]:
    o, h, l, c, A, n = ctx.o, ctx.h, ctx.l, ctx.c, ctx.atr, ctx.n
    out: List[Signal] = []
    warm = 30

    def emit(mask, name, d, stop_fn, rr=2.0, start_off=0, min_i=warm):
        for i in np.flatnonzero(mask):
            if i < min_i:
                continue
            out.append(_risk_sig(ctx, name, d, int(i), stop_fn(int(i)), start=int(i) - start_off, rr=rr))

    atr_stop_long = lambda i: c[i] - 2 * A[i]   # noqa: E731
    atr_stop_short = lambda i: c[i] + 2 * A[i]  # noqa: E731

    # ---- moving-average crosses
    s50, s200 = sma(c, 50), sma(c, 200)
    emit(_cross_up(s50, s200), "Golden Cross (50/200)", 1, atr_stop_long, min_i=200)
    emit(_cross_dn(s50, s200), "Death Cross (50/200)", -1, atr_stop_short, min_i=200)
    e9, e21 = ema(c, 9), ema(c, 21)
    emit(_cross_up(e9, e21), "EMA 9/21 Bull Cross", 1, lambda i: l[i - 2:i + 1].min() - 0.25 * A[i])
    emit(_cross_dn(e9, e21), "EMA 9/21 Bear Cross", -1, lambda i: h[i - 2:i + 1].max() + 0.25 * A[i])

    # ---- MACD
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    emit(_cross_up(macd, sig) & (macd < 0), "MACD Bull Cross (below 0)", 1, atr_stop_long)
    emit(_cross_dn(macd, sig) & (macd > 0), "MACD Bear Cross (above 0)", -1, atr_stop_short)
    zero = np.zeros(n)
    emit(_cross_up(macd, zero), "MACD Zero-Line Cross ↑", 1, atr_stop_long)
    emit(_cross_dn(macd, zero), "MACD Zero-Line Cross ↓", -1, atr_stop_short)

    # ---- RSI
    R = ctx.rsi
    emit(_cross_up(R, np.full(n, 30.0)), "RSI Oversold Reclaim (30)", 1, lambda i: l[i - 3:i + 1].min() - 0.25 * A[i])
    emit(_cross_dn(R, np.full(n, 70.0)), "RSI Overbought Rejection (70)", -1, lambda i: h[i - 3:i + 1].max() + 0.25 * A[i])

    # ---- Bollinger squeeze breakout & TTM squeeze fire
    mid = sma(c, 20)
    sd = rolling_std(c, 20)
    ub, lb = mid + 2 * sd, mid - 2 * sd
    with np.errstate(invalid="ignore", divide="ignore"):
        bw = (ub - lb) / mid
    bw_rank = pd.Series(bw).rolling(120, min_periods=120).rank(pct=True).values
    was_tight = pd.Series((bw_rank <= 0.10).astype(float)).rolling(5).max().values == 1
    emit(was_tight & _cross_up(c, ub), "Bollinger Squeeze Breakout ↑", 1, lambda i: mid[i])
    emit(was_tight & _cross_dn(c, lb), "Bollinger Squeeze Breakdown ↓", -1, lambda i: mid[i])

    atr20 = pd.Series(A).rolling(20).mean().values
    kc_u, kc_l = mid + 1.5 * atr20, mid - 1.5 * atr20
    sq_on = (lb > kc_l) & (ub < kc_u)
    fired = np.zeros(n, bool)
    fired[1:] = sq_on[:-1] & ~sq_on[1:]
    donch_mid = (pd.Series(h).rolling(20).max().values + pd.Series(l).rolling(20).min().values) / 2
    mom = linreg_end(c - (donch_mid + mid) / 2, 20)
    emit(fired & (mom > 0), "TTM Squeeze Fire ↑", 1, lambda i: l[i - 3:i + 1].min() - 0.25 * A[i])
    emit(fired & (mom < 0), "TTM Squeeze Fire ↓", -1, lambda i: h[i - 3:i + 1].max() + 0.25 * A[i])

    # ---- range contraction: NR7 & inside bar breakouts
    rng = h - l
    nr7 = rng <= pd.Series(rng).rolling(7).min().values
    nr7_prev = np.r_[False, nr7[:-1]]
    hp, lp = np.r_[np.nan, h[:-1]], np.r_[np.nan, l[:-1]]
    with np.errstate(invalid="ignore"):
        emit(nr7_prev & (c > hp), "NR7 Breakout ↑", 1, lambda i: l[i - 1])
        emit(nr7_prev & (c < lp), "NR7 Breakdown ↓", -1, lambda i: h[i - 1])
        inside = np.r_[False, (h[1:] <= h[:-1]) & (l[1:] >= l[:-1])]
        inside_prev = np.r_[False, inside[:-1]]
        emit(inside_prev & (c > hp), "Inside Bar Breakout ↑", 1, lambda i: l[i - 1])
        emit(inside_prev & (c < lp), "Inside Bar Breakdown ↓", -1, lambda i: h[i - 1])

    # ---- N-bar high/low breakouts (52 week on daily/weekly, 20-day on intraday)
    N = {"1d": 365 if ctx.crypto else 252, "1wk": 52}.get(ctx.tf, 140)
    label = "52-Week" if ctx.tf in ("1d", "1wk") else "20-Day"
    prior_hi = pd.Series(h).shift(1).rolling(N, min_periods=N).max().values
    prior_lo = pd.Series(l).shift(1).rolling(N, min_periods=N).min().values
    with np.errstate(invalid="ignore"):
        brk_up = c > prior_hi
        brk_dn = c < prior_lo
    fresh_up = brk_up & (pd.Series(brk_up.astype(float)).shift(1).rolling(10, min_periods=1).max().values == 0)
    fresh_dn = brk_dn & (pd.Series(brk_dn.astype(float)).shift(1).rolling(10, min_periods=1).max().values == 0)
    emit(fresh_up, f"{label} High Breakout", 1, atr_stop_long, min_i=N)
    emit(fresh_dn, f"{label} Low Breakdown", -1, atr_stop_short, min_i=N)

    # ---- trend pullbacks (buy-the-dip / sell-the-rip with structure)
    with np.errstate(invalid="ignore"):
        up_trend = (s50 > s200) & (c > s200)
        dn_trend = (s50 < s200) & (c < s200)
        above50 = pd.Series((c > s50).astype(float)).shift(1).rolling(10).min().values == 1
        below50 = pd.Series((c < s50).astype(float)).shift(1).rolling(10).min().values == 1
        emit(up_trend & above50 & (l <= s50) & (c > s50), "Pullback to 50 SMA (uptrend)", 1,
             lambda i: l[i] - 1.0 * A[i], min_i=200)
        emit(dn_trend & below50 & (h >= s50) & (c < s50), "Rally to 50 SMA (downtrend)", -1,
             lambda i: h[i] + 1.0 * A[i], min_i=200)
        e20, e50 = ema(c, 20), ema(c, 50)
        stack_up = (e9 > e20) & (e20 > e50)
        stack_dn = (e9 < e20) & (e20 < e50)
        emit(stack_up & (l <= e20) & (c > e20) & (c > o), "20 EMA Pullback (trend)", 1,
             lambda i: l[i] - 0.5 * A[i], min_i=60)
        emit(stack_dn & (h >= e20) & (c < e20) & (c < o), "20 EMA Rejection (trend)", -1,
             lambda i: h[i] + 0.5 * A[i], min_i=60)
        lost50 = (c < s50) & (pd.Series((c > s50).astype(float)).shift(1).rolling(20).min().values == 1)
        emit(lost50, "Lost 50 SMA after 20+ bars above", -1, lambda i: max(s50[i], c[i]) + 1.0 * A[i], min_i=60)

    # ---- gaps: fill vs. go (complementary — the stats tell you which side wins)
    pc = np.r_[np.nan, c[:-1]]
    pa = np.r_[np.nan, A[:-1]]
    with np.errstate(invalid="ignore"):
        gap_up = (o - pc) >= 0.5 * pa
        gap_dn = (pc - o) >= 0.5 * pa
    for i in np.flatnonzero(gap_up):
        if i < warm:
            continue
        exp = int(ctx.sess_end[i]) if ctx.intraday else None
        g = o[i] - pc[i]
        out.append(Signal("Gap Up → Fill", "setup", -1, i, i, float(o[i] + g), float(pc[i]),
                          entry_idx=int(i), entry_px=float(o[i]), expire_idx=exp))
        out.append(Signal("Gap Up → Go", "setup", 1, i, i, float(pc[i]), float(o[i] + g),
                          entry_idx=int(i), entry_px=float(o[i]), expire_idx=exp))
    for i in np.flatnonzero(gap_dn):
        if i < warm:
            continue
        exp = int(ctx.sess_end[i]) if ctx.intraday else None
        g = pc[i] - o[i]
        out.append(Signal("Gap Down → Fill", "setup", 1, i, i, float(o[i] - g), float(pc[i]),
                          entry_idx=int(i), entry_px=float(o[i]), expire_idx=exp))
        out.append(Signal("Gap Down → Go", "setup", -1, i, i, float(pc[i]), float(o[i] - g),
                          entry_idx=int(i), entry_px=float(o[i]), expire_idx=exp))

    # ---- intraday only: opening-range breakout & session VWAP
    if ctx.intraday:
        out += _intraday(ctx)
    return out


def _intraday(ctx: Ctx) -> List[Signal]:
    o, h, l, c, v, A = ctx.o, ctx.h, ctx.l, ctx.c, ctx.v, ctx.atr
    out: List[Signal] = []
    ss, se = ctx.sess_start, ctx.sess_end
    # opening range = first bar of the session (first hour on 1h data)
    orb_bars = {"1h": 1, "30m": 2, "15m": 4, "5m": 6}.get(ctx.tf, 1)
    for start in np.unique(ss):
        end = int(se[start])
        or_end = start + orb_bars - 1
        if or_end >= end:
            continue
        orh, orl = h[start:or_end + 1].max(), l[start:or_end + 1].min()
        for t in range(or_end + 1, end + 1):
            if c[t] > orh:
                out.append(Signal("Opening Range Breakout ↑", "setup", 1, start, t, float(orl),
                                  float(c[t] + (orh - orl)), expire_idx=end))
                break
            if c[t] < orl:
                out.append(Signal("Opening Range Breakdown ↓", "setup", -1, start, t, float(orh),
                                  float(c[t] - (orh - orl)), expire_idx=end))
                break
    # session VWAP
    tp = (h + l + c) / 3
    vol = np.where(v > 0, v, 1.0)
    df = pd.DataFrame({"pv": tp * vol, "v": vol, "s": ctx.session})
    vwap = (df.groupby("s")["pv"].cumsum() / df.groupby("s")["v"].cumsum()).values
    below = c < vwap
    for t in range(3, ctx.n):
        if ss[t] > t - 3 or (t >= se[t] and t < ctx.n - 1):
            continue  # need 3 prior bars in the same session, and a bar left to trade
        if c[t] > vwap[t] and below[t - 3:t].all():
            stop = l[t - 3:t + 1].min() - 0.1 * A[t]
            out.append(_risk_sig(ctx, "VWAP Reclaim", 1, t, stop, start=t - 3, expire=int(se[t])))
        elif c[t] < vwap[t] and (~below[t - 3:t]).all():
            stop = h[t - 3:t + 1].max() + 0.1 * A[t]
            out.append(_risk_sig(ctx, "VWAP Rejection", -1, t, stop, start=t - 3, expire=int(se[t])))
    return out
