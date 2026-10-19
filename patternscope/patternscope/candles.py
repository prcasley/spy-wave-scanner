"""Candlestick patterns (vectorised). Each fires at the close of its last bar.

Reversal patterns require trend context (a 5-bar decline/advance and price on the
right side of the 20 SMA) so a hammer in the middle of nowhere doesn't count.
Stop = beyond the pattern's extreme; target = 2R from the signal close.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .core import Ctx, Signal, sma


def _sh(a, k):
    """Shift right by k (value from k bars ago)."""
    out = np.full_like(a, np.nan, dtype=float)
    if k < len(a):
        out[k:] = a[:-k] if k else a
    return out


def detect(ctx: Ctx) -> List[Signal]:
    o, h, l, c, A = ctx.o, ctx.h, ctx.l, ctx.c, ctx.atr
    n = ctx.n
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = np.where(h - l > 0, h - l, np.nan)
        body = np.abs(c - o)
        top = np.maximum(o, c)
        bot = np.minimum(o, c)
        upw = h - top
        low = bot - l
        bull = c > o
        bear = c < o
        avgb = sma(body, 14)
        long_ = body >= 1.0 * avgb
        small = body <= 0.35 * avgb
        doji = body <= 0.1 * rng
        s20 = sma(c, 20)
        down = (_sh(c, 1) < _sh(c, 6)) & (_sh(c, 1) < _sh(s20, 1))
        up = (_sh(c, 1) > _sh(c, 6)) & (_sh(c, 1) > _sh(s20, 1))

        S = lambda a, k: _sh(a, k)  # noqa: E731
        o1, h1, l1, c1 = S(o, 1), S(h, 1), S(l, 1), S(c, 1)
        o2, h2, l2, c2 = S(o, 2), S(h, 2), S(l, 2), S(c, 2)
        b1, b2 = S(body, 1), S(body, 2)
        bull1, bear1 = S(bull.astype(float), 1) == 1, S(bear.astype(float), 1) == 1
        bull2, bear2 = S(bull.astype(float), 2) == 1, S(bear.astype(float), 2) == 1
        long1, long2 = S(long_.astype(float), 1) == 1, S(long_.astype(float), 2) == 1
        small1 = S(small.astype(float), 1) == 1
        doji1 = S(doji.astype(float), 1) == 1
        mid1 = (o1 + c1) / 2
        mid2 = (o2 + c2) / 2
        down1, up1 = S(down.astype(float), 1) == 1, S(up.astype(float), 1) == 1
        down2, up2 = S(down.astype(float), 2) == 1, S(up.astype(float), 2) == 1

        hammer_shape = (low >= 2 * body) & (upw <= 0.15 * rng) & (body >= 0.03 * rng)
        inv_shape = (upw >= 2 * body) & (low <= 0.15 * rng) & (body >= 0.03 * rng)

        bull_engulf = down & bear1 & bull & (o <= c1) & (c >= o1) & (body > b1)
        bear_engulf = up & bull1 & bear & (o >= c1) & (c <= o1) & (body > b1)
        bull_harami = down & bear1 & long1 & (top <= o1) & (bot >= c1) & (body < 0.6 * b1)
        bear_harami = up & bull1 & long1 & (top <= c1) & (bot >= o1) & (body < 0.6 * b1)

        P = {}  # name -> (mask, direction, n_bars)
        P["Hammer"] = (down & hammer_shape, 1, 1)
        P["Hanging Man"] = (up & hammer_shape, -1, 1)
        P["Inverted Hammer"] = (down & inv_shape, 1, 1)
        P["Shooting Star"] = (up & inv_shape, -1, 1)
        P["Bullish Engulfing"] = (bull_engulf, 1, 2)
        P["Bearish Engulfing"] = (bear_engulf, -1, 2)
        P["Piercing Line"] = (down & bear1 & long1 & bull & (o < c1) & (c > mid1) & (c < o1), 1, 2)
        P["Dark Cloud Cover"] = (up & bull1 & long1 & bear & (o > c1) & (c < mid1) & (c > o1), -1, 2)
        P["Morning Star"] = (down2 & bear2 & long2 & small1 & ~doji1 & (np.maximum(o1, c1) <= c2 + 0.1 * b2)
                             & bull & (c > mid2), 1, 3)
        P["Evening Star"] = (up2 & bull2 & long2 & small1 & ~doji1 & (np.minimum(o1, c1) >= c2 - 0.1 * b2)
                             & bear & (c < mid2), -1, 3)
        P["Morning Doji Star"] = (down2 & bear2 & long2 & doji1 & (np.maximum(o1, c1) <= c2 + 0.1 * b2)
                                  & bull & (c > mid2), 1, 3)
        P["Evening Doji Star"] = (up2 & bull2 & long2 & doji1 & (np.minimum(o1, c1) >= c2 - 0.1 * b2)
                                  & bear & (c < mid2), -1, 3)
        soldier = bull & long_ & (upw <= 0.3 * body)
        crow = bear & long_ & (low <= 0.3 * body)
        sol1, sol2 = S(soldier.astype(float), 1) == 1, S(soldier.astype(float), 2) == 1
        cro1, cro2 = S(crow.astype(float), 1) == 1, S(crow.astype(float), 2) == 1
        P["Three White Soldiers"] = (soldier & sol1 & sol2 & (c > c1) & (c1 > c2)
                                     & (o > o1) & (o < c1) & (o1 > o2) & (o1 < c2), 1, 3)
        P["Three Black Crows"] = (crow & cro1 & cro2 & (c < c1) & (c1 < c2)
                                  & (o < o1) & (o > c1) & (o1 < o2) & (o1 > c2), -1, 3)
        P["Bullish Harami"] = (bull_harami & ~doji, 1, 2)
        P["Bearish Harami"] = (bear_harami & ~doji, -1, 2)
        P["Bullish Harami Cross"] = (bull_harami & doji, 1, 2)
        P["Bearish Harami Cross"] = (bear_harami & doji, -1, 2)
        tw = 0.1 * A
        P["Tweezer Bottom"] = (down & bear1 & bull & (np.abs(l - l1) <= tw), 1, 2)
        P["Tweezer Top"] = (up & bull1 & bear & (np.abs(h - h1) <= tw), -1, 2)
        P["Bullish Marubozu"] = (bull & long_ & (body >= 0.95 * rng), 1, 1)
        P["Bearish Marubozu"] = (bear & long_ & (body >= 0.95 * rng), -1, 1)
        P["Dragonfly Doji"] = (down & doji & (upw <= 0.1 * rng) & (low >= 0.6 * rng), 1, 1)
        P["Gravestone Doji"] = (up & doji & (low <= 0.1 * rng) & (upw >= 0.6 * rng), -1, 1)
        bh1 = S(bull_harami.astype(float), 1) == 1
        brh1 = S(bear_harami.astype(float), 1) == 1
        P["Three Inside Up"] = (bh1 & bull & (c > o2), 1, 3)
        P["Three Inside Down"] = (brh1 & bear & (c < o2), -1, 3)
        be1 = S(bull_engulf.astype(float), 1) == 1
        bre1 = S(bear_engulf.astype(float), 1) == 1
        P["Three Outside Up"] = (be1 & bull & (c > c1), 1, 3)
        P["Three Outside Down"] = (bre1 & bear & (c < c1), -1, 3)
        # rising / falling three methods (5 bars)
        o4, h4, l4, c4 = S(o, 4), S(h, 4), S(l, 4), S(c, 4)
        long4 = S(long_.astype(float), 4) == 1
        bull4 = S(bull.astype(float), 4) == 1
        bear4 = S(bear.astype(float), 4) == 1
        inner_hi = np.fmax(np.fmax(h1, h2), S(h, 3))
        inner_lo = np.fmin(np.fmin(l1, l2), S(l, 3))
        inner_small = (np.fmax(np.fmax(b1, b2), S(body, 3)) < S(body, 4) * 0.6)
        P["Rising Three Methods"] = (long4 & bull4 & inner_small & (inner_hi <= h4) & (inner_lo >= l4)
                                     & bull & long_ & (c > c4), 1, 5)
        P["Falling Three Methods"] = (long4 & bear4 & inner_small & (inner_hi <= h4) & (inner_lo >= l4)
                                      & bear & long_ & (c < c4), -1, 5)
        P["Bullish Kicker"] = (bear1 & long1 & bull & long_ & (o >= o1) & (l > c1), 1, 2)
        P["Bearish Kicker"] = (bull1 & long1 & bear & long_ & (o <= o1) & (h < c1), -1, 2)
        P["Bullish Abandoned Baby"] = (down2 & bear2 & long2 & doji1 & (h1 < l2) & bull & (l > h1), 1, 3)
        P["Bearish Abandoned Baby"] = (up2 & bull2 & long2 & doji1 & (l1 > h2) & bear & (h < l1), -1, 3)
        P["Bullish Belt Hold"] = (down & bull & long_ & (low <= 0.03 * rng), 1, 1)
        P["Bearish Belt Hold"] = (up & bear & long_ & (upw <= 0.03 * rng), -1, 1)
        P["Upside Tasuki Gap"] = (bull2 & bull1 & (l1 > h2) & bear & (o < c1) & (o > o1)
                                  & (c > h2) & (c < l1), 1, 3)
        P["Downside Tasuki Gap"] = (bear2 & bear1 & (h1 < l2) & bull & (o > c1) & (o < o1)
                                    & (c < l2) & (c > h1), -1, 3)
        P["Bullish Counterattack"] = (down & bear1 & long1 & bull & long_ & (np.abs(c - c1) <= 0.1 * A), 1, 2)
        P["Bearish Counterattack"] = (up & bull1 & long1 & bear & long_ & (np.abs(c - c1) <= 0.1 * A), -1, 2)

    out: List[Signal] = []
    for name, (mask, d, nb) in P.items():
        mask = np.asarray(mask, dtype=bool)
        mask[: 25] = False
        for i in np.flatnonzero(mask):
            s = i - nb + 1
            if d == 1:
                stop = float(l[s:i + 1].min() - 0.1 * A[i])
                tgt = float(c[i] + 2 * (c[i] - stop))
            else:
                stop = float(h[s:i + 1].max() + 0.1 * A[i])
                tgt = float(c[i] - 2 * (stop - c[i]))
            out.append(Signal(name, "candle", d, s, int(i), stop, tgt))
    return out


NAMES = [
    "Hammer", "Hanging Man", "Inverted Hammer", "Shooting Star", "Bullish Engulfing", "Bearish Engulfing",
    "Piercing Line", "Dark Cloud Cover", "Morning Star", "Evening Star", "Morning Doji Star",
    "Evening Doji Star", "Three White Soldiers", "Three Black Crows", "Bullish Harami", "Bearish Harami",
    "Bullish Harami Cross", "Bearish Harami Cross", "Tweezer Bottom", "Tweezer Top", "Bullish Marubozu",
    "Bearish Marubozu", "Dragonfly Doji", "Gravestone Doji", "Three Inside Up", "Three Inside Down",
    "Three Outside Up", "Three Outside Down", "Rising Three Methods", "Falling Three Methods",
    "Bullish Kicker", "Bearish Kicker", "Bullish Abandoned Baby", "Bearish Abandoned Baby",
    "Bullish Belt Hold", "Bearish Belt Hold", "Upside Tasuki Gap", "Downside Tasuki Gap",
    "Bullish Counterattack", "Bearish Counterattack",
]
