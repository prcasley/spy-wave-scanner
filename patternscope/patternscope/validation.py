"""Research validation: is a pattern's edge real, or luck / hindsight / costs?

Tests
  1. Survivorship  — re-run every pattern on the S&P 500 (not a hand-picked watchlist).
                     Signals before a stock joined the index are dropped, so a stock isn't
                     credited for the run-up that got it into the index.
  2. Out-of-sample — split history at a fixed date. Grade on the early part only, then check
                     whether the same patterns still worked afterwards, untouched.
  3. Costs         — subtract commissions + slippage (bps per side, in config) from every trade.
  4. Significance  — t-test of each pattern's mean R, with Benjamini-Hochberg correction for
                     testing ~300 pattern/timeframe combos at once.
"""
from __future__ import annotations

import math
import os
import time
from typing import Dict, List

import numpy as np
import pandas as pd

from .config import COST_BPS, OOS_SPLIT, TIMEFRAMES, YF
from .pipeline import analyze

KEEP = ["ticker", "tf", "pattern", "category", "direction", "signal_time", "outcome", "entry", "stop", "R",
        "bars_held"]


def load_universe(path: str) -> pd.DataFrame:
    u = pd.read_csv(path)
    u["Symbol"] = u["Symbol"].str.replace(".", "-", regex=False)  # BRK.B -> BRK-B for Yahoo
    u["added"] = pd.to_datetime(u["Date added"], errors="coerce")
    return u


def _download_chunk(tickers: List[str], tf: str) -> Dict[str, pd.DataFrame]:
    import yfinance as yf

    from .data import _clean
    spec = YF[tf]
    for attempt in range(3):
        try:
            raw = yf.download(tickers, interval=spec["interval"], period=spec["period"], auto_adjust=True,
                              progress=False, prepost=False, group_by="ticker", threads=True)
            out = {}
            for t in tickers:
                try:
                    df = _clean(raw[t].copy()) if isinstance(raw.columns, pd.MultiIndex) else _clean(raw.copy())
                except KeyError:
                    continue
                if len(df):
                    if tf == "1h" and df.index.tz is not None:
                        df.index = df.index.tz_convert("America/New_York")
                    out[t] = df
            return out
        except Exception as e:  # rate limit / network
            print(f"    chunk retry {attempt + 1}: {e}")
            time.sleep(10 * (attempt + 1))
    return {}


def run_universe(universe: pd.DataFrame, tfs: List[str], hourly_sample: int = 80, seed: int = 11,
                 chunk: int = 40) -> pd.DataFrame:
    frames = []
    added = dict(zip(universe.Symbol, universe.added))
    for tf in tfs:
        syms = list(universe.Symbol)
        if tf == "1h":  # hourly is heavy: a fixed random sample keeps it neutral but fast
            rng = np.random.default_rng(seed)
            syms = list(rng.choice(syms, size=min(hourly_sample, len(syms)), replace=False))
        t0, done = time.time(), 0
        for i in range(0, len(syms), chunk):
            data = _download_chunk(syms[i:i + chunk], tf)
            for tk, df in data.items():
                if len(df) < 120:
                    continue
                try:
                    tr = analyze(df, tk, tf, TIMEFRAMES[tf])["trades"]
                except Exception as e:
                    print(f"    {tk} {tf} failed: {e}")
                    continue
                if not len(tr):
                    continue
                tr = tr[[c for c in KEEP if c in tr.columns]]
                a = added.get(tk)
                if a is not None and not pd.isna(a):
                    st = pd.to_datetime(tr.signal_time, utc=True).dt.tz_localize(None)
                    tr = tr[st >= a]
                frames.append(tr)
                done += 1
            print(f"  {tf}: {done}/{len(syms)} tickers, {time.time() - t0:.0f}s")
    if not frames:
        return pd.DataFrame(columns=KEEP)
    out = pd.concat(frames, ignore_index=True)
    out["direction"] = out["direction"].astype("int8")
    return out


# ---------------------------------------------------------------- statistics
def add_costs(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    risk = (t.entry - t.stop).abs()
    bps = t.tf.map(COST_BPS).fillna(5) / 10000.0
    with np.errstate(divide="ignore", invalid="ignore"):
        t["cost_R"] = (2 * bps * t.entry / risk).replace([np.inf, -np.inf], np.nan)
    t["R_net"] = t.R - t.cost_R
    return t


def _bh(p: pd.Series, q: float = 0.10) -> pd.Series:
    """Benjamini-Hochberg: True where the result survives a 10% false-discovery rate."""
    p = p.fillna(1.0)
    order = p.sort_values().index
    m = len(p)
    ranked = p.loc[order].values
    thresh = q * (np.arange(1, m + 1) / m)
    passed = ranked <= thresh
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = pd.Series(False, index=p.index)
    out.loc[order[:k]] = True
    return out


def pooled(trades: pd.DataFrame, prefix: str) -> pd.DataFrame:
    done = trades[trades.outcome.isin(["target", "stop", "timeout"])]
    if not len(done):
        return pd.DataFrame(columns=["tf", "pattern", "direction"])
    g = done.groupby(["tf", "pattern", "direction"])
    st = g.agg(n=("R", "size"), win=("outcome", lambda s: (s == "target").mean() * 100),
               R=("R", "mean"), R_net=("R_net", "mean"), sd=("R_net", "std")).reset_index()
    st["t"] = st.R_net / (st.sd / np.sqrt(st.n))
    st["p"] = st.t.apply(lambda t: 0.5 * math.erfc(t / math.sqrt(2)) if np.isfinite(t) else 1.0)  # one-sided
    st = st.drop(columns="sd")
    st.columns = ["tf", "pattern", "direction"] + [f"{prefix}{c}" for c in st.columns[3:]]
    return st


def split_oos(trades: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
    st = pd.to_datetime(trades.signal_time, utc=True)
    cut = trades.tf.map({tf: pd.Timestamp(d, tz="UTC") for tf, d in OOS_SPLIT.items()})
    is_mask = st < cut
    return trades[is_mask], trades[~is_mask]


def verdicts(watch_trades: pd.DataFrame, uni_trades: pd.DataFrame, watch_stats: pd.DataFrame) -> pd.DataFrame:
    w = add_costs(watch_trades)
    u = add_costs(uni_trades)
    u_is, u_oos = split_oos(u)
    tbl = pooled(w, "watch_")
    for part, pre in [(u, "uni_"), (u_is, "is_"), (u_oos, "oos_")]:
        tbl = tbl.merge(pooled(part, pre), on=["tf", "pattern", "direction"], how="outer")
    tbl["uni_sig"] = _bh(tbl["uni_p"]) if "uni_p" in tbl else False
    g = watch_stats[watch_stats.ticker == "ALL"][["tf", "pattern", "grade"]].rename(columns={"grade": "watch_grade"})
    tbl = tbl.merge(g, on=["tf", "pattern"], how="left")
    tbl["direction"] = tbl.direction.map({1: "LONG", -1: "SHORT"})
    tbl["verdict"] = tbl.apply(_verdict, axis=1)
    order = {"Confirmed": 0, "Promising": 1, "Watchlist only": 2, "Faded out-of-sample": 3, "Costs kill it": 4,
             "No edge": 5, "Too few trades": 6}
    tbl["_o"] = tbl.verdict.map(order)
    return tbl.sort_values(["_o", "tf", "uni_R_net"], ascending=[True, True, False]).drop(columns="_o").reset_index(drop=True)


def _verdict(r) -> str:
    def v(k):
        x = r.get(k)
        return None if x is None or pd.isna(x) else x
    un, isn, oosn = v("uni_n") or 0, v("is_n") or 0, v("oos_n") or 0
    if un < 50 or isn < 20 or oosn < 20:
        return "Too few trades"
    gross, net = v("uni_R"), v("uni_R_net")
    is_net, oos_net = v("is_R_net"), v("oos_R_net")
    if gross is not None and gross > 0.05 and net <= 0:
        return "Costs kill it"
    if is_net is not None and is_net > 0.05 and (oos_net is None or oos_net <= 0):
        return "Faded out-of-sample"
    if net > 0.05 and oos_net > 0.05 and bool(r.get("uni_sig")):
        return "Confirmed"
    if net > 0.05 and oos_net > 0:
        return "Promising"
    if r.get("watch_grade") in ("A", "B"):
        return "Watchlist only"
    return "No edge"


def write_tables(out_dir: str, tbl: pd.DataFrame, meta: dict):
    os.makedirs(out_dir, exist_ok=True)
    tbl.round(4).to_csv(os.path.join(out_dir, "verdicts.csv"), index=False)
    pd.DataFrame([meta]).to_csv(os.path.join(out_dir, "meta.csv"), index=False)
