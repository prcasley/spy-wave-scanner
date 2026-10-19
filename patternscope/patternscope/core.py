"""Core types: Signal, Pivot, Ctx (price arrays + indicators), pivot detection."""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import List, Optional

import numpy as np
import pandas as pd

INTRADAY = {"1m", "5m", "15m", "30m", "1h"}


# ----------------------------------------------------------------------------- types
@dataclass
class Signal:
    pattern: str            # display name, e.g. "Bull Flag"
    category: str           # candle | chart | setup
    direction: int          # +1 long / -1 short
    start: int              # first bar of the pattern
    end: int                # confirmation bar (pattern is known at this bar's close)
    stop: float             # invalidation price
    target: float           # objective price
    entry_idx: Optional[int] = None   # default: end + 1 (next bar open)
    entry_px: Optional[float] = None  # default: open[entry_idx]
    expire_idx: Optional[int] = None  # hard time stop (e.g. end of session for day trades)


@dataclass
class Pivot:
    idx: int
    price: float
    kind: str  # 'H' or 'L'


def unmirror(sig: Signal, name: str) -> Signal:
    """Convert a signal found on the price-mirrored context back to real prices."""
    return replace(
        sig, pattern=name, direction=-sig.direction, stop=-sig.stop, target=-sig.target,
        entry_px=None if sig.entry_px is None else -sig.entry_px,
    )


# ----------------------------------------------------------------------------- indicators
def sma(x, n):
    return pd.Series(x).rolling(n, min_periods=n).mean().values


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def wilder(x, n):
    return pd.Series(x).ewm(alpha=1.0 / n, adjust=False).mean().values


def atr(h, l, c, n=14):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return wilder(tr, n)


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = wilder(np.where(d > 0, d, 0.0), n)
    dn = wilder(np.where(d < 0, -d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + up / dn)
    r[dn == 0] = 100.0
    r[:n] = np.nan
    return r


def rolling_std(x, n):
    return pd.Series(x).rolling(n, min_periods=n).std(ddof=0).values


def linreg_end(x, n):
    """Value of a rolling least-squares line at its last point (TTM momentum style)."""
    s = pd.Series(x)
    t = np.arange(n, dtype=float)
    tm = t.mean()
    denom = ((t - tm) ** 2).sum()

    def f(w):
        if np.isnan(w).any():
            return np.nan
        slope = ((t - tm) * (w - w.mean())).sum() / denom
        return w.mean() + slope * (n - 1 - tm)

    return s.rolling(n, min_periods=n).apply(f, raw=True).values


# ----------------------------------------------------------------------------- pivots
def find_pivots(h, l, atr_arr, k, min_swing_atr) -> List[Pivot]:
    """Fractal swing points (k bars each side), forced to alternate H/L, with
    swings smaller than `min_swing_atr` x ATR filtered out (zig-zag style).
    A pivot at index i is only *known* at bar i + k — detectors respect this."""
    n = len(h)
    raw: List[Pivot] = []
    for i in range(k, n - k):
        if h[i] > h[i - k:i].max() and h[i] >= h[i + 1:i + k + 1].max():
            raw.append(Pivot(i, float(h[i]), "H"))
        if l[i] < l[i - k:i].min() and l[i] <= l[i + 1:i + k + 1].min():
            raw.append(Pivot(i, float(l[i]), "L"))
    out: List[Pivot] = []
    for p in raw:
        if not out:
            out.append(p)
            continue
        q = out[-1]
        if p.kind == q.kind:
            if (p.kind == "H" and p.price > q.price) or (p.kind == "L" and p.price < q.price):
                out[-1] = p
        elif p.idx != q.idx and abs(p.price - q.price) >= min_swing_atr * atr_arr[p.idx]:
            out.append(p)
    return out


def mirror_pivots(pv: List[Pivot]) -> List[Pivot]:
    return [Pivot(p.idx, -p.price, "L" if p.kind == "H" else "H") for p in pv]


# ----------------------------------------------------------------------------- context
class Ctx:
    """Everything a detector needs for one ticker on one timeframe."""

    def __init__(self, df: pd.DataFrame, tf: str, cfg: dict, ticker: str = ""):
        self.df = df
        self.ticker = ticker
        self.tf = tf
        self.cfg = cfg
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float) if "volume" in df else np.zeros(len(df))
        self.n = len(df)
        self.k = cfg["k"]
        self.wait = cfg["wait"]
        self.atr = atr(self.h, self.l, self.c, 14)
        self.rsi = rsi(self.c, 14)
        self.intraday = tf in INTRADAY
        self.pivots = find_pivots(self.h, self.l, self.atr, self.k, cfg["min_swing_atr"])
        self.mirrored = False
        # sessions (intraday): id per bar + last bar index of that session
        if self.intraday:
            idx = pd.DatetimeIndex(df.index)
            dates = pd.Series(idx.date)
            self.session = pd.factorize(dates)[0]
            last = pd.Series(np.arange(self.n)).groupby(self.session).transform("max").values
            self.sess_end = last.astype(int)
            self.sess_start = pd.Series(np.arange(self.n)).groupby(self.session).transform("min").values.astype(int)
        else:
            self.session = None
            self.sess_end = None
            self.sess_start = None

    def mirror(self) -> "Ctx":
        """Price-negated copy: a 'top' detector run on it finds the matching 'bottom'."""
        m = copy.copy(self)
        m.o, m.c = -self.o, -self.c
        m.h, m.l = -self.l, -self.h
        m.rsi = 100.0 - self.rsi
        m.pivots = mirror_pivots(self.pivots)
        m.mirrored = True
        return m
