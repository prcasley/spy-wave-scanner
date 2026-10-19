"""Turn detections into outcomes, outcomes into statistics.

Outcome rules (conservative on purpose):
  * entry = next bar's open (gaps use the gap bar's open)
  * stop and target checked bar by bar; if both are touched in the same bar -> stop
  * no resolution by `max_hold` bars (or end of session for day trades) -> timeout at close
  * still unresolved at the end of the data -> 'open' (excluded from stats)
Every pattern is compared with the ticker's *baseline*: how often price moves the
same direction over the same horizon from any random bar. Edge = hit rate - baseline.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .core import Ctx, Pivot, Signal


def evaluate(ctx: Ctx, sigs: List[Signal], max_hold: int, horizons: List[int]) -> pd.DataFrame:
    o, h, l, c, n = ctx.o, ctx.h, ctx.l, ctx.c, ctx.n
    idx = ctx.df.index
    rows = []
    for s in sigs:
        e = s.end + 1 if s.entry_idx is None else s.entry_idx
        d = s.direction
        row = dict(ticker=ctx.ticker, tf=ctx.tf, pattern=s.pattern, category=s.category, direction=d,
                   start_time=idx[s.start], signal_time=idx[s.end], start_idx=s.start, end_idx=s.end,
                   formation_bars=s.end - s.start + 1, stop=s.stop, target=s.target)
        if e >= n:
            row.update(outcome="pending", entry=np.nan)
            rows.append(row)
            continue
        entry = o[e] if s.entry_px is None else s.entry_px
        risk = (entry - s.stop) * d
        reward = (s.target - entry) * d
        row["entry"] = entry
        a_ref = ctx.atr[min(s.end, n - 1)]
        # a stop tighter than 0.2 ATR is noise-level; its R multiple would be meaningless
        if not np.isfinite(risk) or risk < 0.2 * a_ref or reward <= 0:
            row["outcome"] = "invalid"
            rows.append(row)
            continue
        last = e + max_hold - 1
        if s.expire_idx is not None:
            last = min(last, s.expire_idx)
        truncated = last > n - 1
        last = min(last, n - 1)
        outcome, exit_px, t_exit = None, None, last
        mfe = mae = 0.0
        for t in range(e, last + 1):
            fav = (h[t] - entry) if d == 1 else (entry - l[t])
            adv = (entry - l[t]) if d == 1 else (h[t] - entry)
            mfe, mae = max(mfe, fav), max(mae, adv)
            hit_stop = l[t] <= s.stop if d == 1 else h[t] >= s.stop
            hit_tgt = h[t] >= s.target if d == 1 else l[t] <= s.target
            if hit_stop:
                outcome, exit_px, t_exit = "stop", s.stop, t
                # gap through stop: fill at the open, not the stop
                if (d == 1 and o[t] < s.stop) or (d == -1 and o[t] > s.stop):
                    exit_px = o[t] if t > e else exit_px
                break
            if hit_tgt:
                outcome, exit_px, t_exit = "target", s.target, t
                break
        if outcome is None:
            if truncated:
                outcome, exit_px = "open", c[last]
            else:
                outcome, exit_px = "timeout", c[last]
        R = (exit_px - entry) * d / risk
        row.update(outcome=outcome, exit=exit_px, R=R, rr_planned=reward / risk,
                   bars_held=t_exit - e + 1, mfe_R=mfe / risk, mae_R=mae / risk,
                   ret_pct=(exit_px / entry - 1) * d * 100 if entry > 0 else np.nan)
        for hz in horizons:
            j = e + hz - 1
            row[f"fwd{hz}"] = ((c[j] / entry - 1) * d * 100) if j < n and entry > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def baseline(ctx: Ctx, horizons: List[int]) -> Dict[int, float]:
    """P(close h bars ahead > next open) from any bar — the coin-flip to beat."""
    o, c, n = ctx.o, ctx.c, ctx.n
    out = {}
    for hz in horizons:
        e = np.arange(1, n - hz + 1)
        j = e + hz - 1
        ok = o[e] > 0
        out[hz] = float(((c[j] > o[e]) & ok).sum() / max(1, ok.sum()))
    return out


def summarize(trades: pd.DataFrame, bases: Dict[tuple, Dict[int, float]], bars: Dict[tuple, int],
              horizons_by_tf: Dict[str, List[int]]) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    done = trades[trades["outcome"].isin(["target", "stop", "timeout"])].copy()
    rows = []
    for (tk, tf, pat, cat, d), g in done.groupby(["ticker", "tf", "pattern", "category", "direction"]):
        n = len(g)
        hz = horizons_by_tf[tf]
        g = g.sort_values("signal_time")
        half = n // 2
        wins = g[g.R > 0].R.sum()
        losses = -g[g.R < 0].R.sum()
        row = dict(
            ticker=tk, tf=tf, pattern=pat, category=cat, direction="LONG" if d == 1 else "SHORT", n=n,
            per_1000_bars=round(1000 * n / max(1, bars[(tk, tf)]), 2),
            target_pct=round(100 * (g.outcome == "target").mean(), 1),
            stop_pct=round(100 * (g.outcome == "stop").mean(), 1),
            timeout_pct=round(100 * (g.outcome == "timeout").mean(), 1),
            expectancy_R=round(g.R.mean(), 3),
            profit_factor=round(wins / losses, 2) if losses > 0 else np.nan,
            avg_rr_planned=round(g.rr_planned.mean(), 2),
            formation_bars_med=int(g.formation_bars.median()),
            bars_to_target_med=float(g[g.outcome == "target"].bars_held.median()) if (g.outcome == "target").any() else np.nan,
            bars_held_med=float(g.bars_held.median()),
            mfe_R_med=round(g.mfe_R.median(), 2), mae_R_med=round(g.mae_R.median(), 2),
            exp_R_first_half=round(g.R.iloc[:half].mean(), 3) if half else np.nan,
            exp_R_second_half=round(g.R.iloc[half:].mean(), 3) if half else np.nan,
            last_seen=g.signal_time.iloc[-1],
        )
        base = bases[(tk, tf)]
        for h in hz:
            col = f"fwd{h}"
            vals = g[col].dropna()
            if len(vals):
                b = base[h] if d == 1 else 1 - base[h]
                hit = (vals > 0).mean()
                row[f"hit{h}_pct"] = round(100 * hit, 1)
                row[f"edge{h}_pp"] = round(100 * (hit - b), 1)
                row[f"avgret{h}_pct"] = round(vals.mean(), 3)
        rows.append(row)
    st = pd.DataFrame(rows)
    st["grade"] = st.apply(_grade, axis=1, horizons_by_tf=horizons_by_tf)
    return st.sort_values(["tf", "expectancy_R"], ascending=[True, False]).reset_index(drop=True)


def _grade(r, horizons_by_tf):
    if r.n < 20:
        return "low-n"
    hz = horizons_by_tf[r.tf]
    mid = hz[len(hz) // 2]
    edge = r.get(f"edge{mid}_pp", np.nan)
    stable = (np.sign(r.exp_R_first_half) == np.sign(r.exp_R_second_half)) and r.exp_R_first_half > 0
    if r.expectancy_R >= 0.25 and edge >= 5 and stable and r.n >= 30:
        return "A"
    if r.expectancy_R >= 0.10 and (edge >= 2 or stable):
        return "B"
    if r.expectancy_R > 0:
        return "C"
    return "F"


def pullback_profile(ctx: Ctx) -> dict:
    """How deep and how long pullbacks (and bounces) usually run, plus where price is now."""
    pv: List[Pivot] = ctx.pivots
    c = ctx.c
    pulls, pull_bars, bounces, bounce_bars = [], [], [], []
    for a, b, d in zip(pv, pv[1:], pv[2:]):
        leg = abs(b.price - a.price)
        if leg <= 0:
            continue
        if a.kind == "L" and b.kind == "H":
            pulls.append((b.price - d.price) / leg)
            pull_bars.append(d.idx - b.idx)
        elif a.kind == "H" and b.kind == "L":
            bounces.append((d.price - b.price) / leg)
            bounce_bars.append(d.idx - b.idx)

    def pct(x):
        if not x:
            return {}
        x = np.asarray(x, float)
        return {p: round(float(np.percentile(x, p)), 3) for p in (25, 50, 75, 90)}

    now = {}
    if len(pv) >= 2:
        last = pv[-1]
        prev = pv[-2]
        hi = max(last.price, ctx.h[last.idx:].max()) if last.kind == "H" else last.price
        if last.kind == "H":
            leg = hi - prev.price
            depth = (hi - c[-1]) / leg if leg > 0 else np.nan
            ranks = float((np.asarray(pulls) <= depth).mean() * 100) if pulls else np.nan
            now = dict(state="pullback from swing high", swing_high=round(hi, 2), leg_start=round(prev.price, 2),
                       retraced=round(depth, 3), bars_since=int(ctx.n - 1 - last.idx),
                       deeper_than_pct_of_history=round(ranks, 1))
        else:
            leg = prev.price - last.price
            hgt = (c[-1] - last.price) / leg if leg > 0 else np.nan
            ranks = float((np.asarray(bounces) <= hgt).mean() * 100) if bounces else np.nan
            now = dict(state="bounce from swing low", swing_low=round(last.price, 2), leg_start=round(prev.price, 2),
                       retraced=round(hgt, 3), bars_since=int(ctx.n - 1 - last.idx),
                       deeper_than_pct_of_history=round(ranks, 1))
    return dict(ticker=ctx.ticker, tf=ctx.tf, pullback_depth=pct(pulls), pullback_bars=pct(pull_bars),
                bounce_depth=pct(bounces), bounce_bars=pct(bounce_bars), n_pullbacks=len(pulls),
                n_bounces=len(bounces), now=now, last_close=round(float(c[-1]), 2))
