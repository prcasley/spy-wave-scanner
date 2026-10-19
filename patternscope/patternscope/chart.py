"""Chart patterns built on confirmed swing pivots.

Every pattern fires on the *breakout / confirmation bar* — never before the last
pivot it uses is knowable (pivot index + k). Bearish 'top' forms are written once
and run on a price-mirrored context to get the bullish 'bottom' form.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .core import Ctx, Signal, unmirror


def _breakout(ctx: Ctx, t0: int, t1: int, up: Callable[[int], Optional[float]],
              dn: Callable[[int], Optional[float]]) -> Tuple[Optional[int], int]:
    for t in range(max(t0, 1), min(t1, ctx.n)):
        u, d = up(t), dn(t)
        if u is not None and ctx.c[t] > u:
            return t, 1
        if d is not None and ctx.c[t] < d:
            return t, -1
    return None, 0


# ============================================================ top forms (mirrored for bottoms)
def double_top(ctx: Ctx) -> List[Signal]:
    pv, A, out = ctx.pivots, ctx.atr, []
    for j in range(len(pv) - 3):
        L0, H1, L2, H3 = pv[j:j + 4]
        if L0.kind != "L":
            continue
        a = A[H3.idx]
        top, neck = max(H1.price, H3.price), L2.price
        depth = top - neck
        if abs(H1.price - H3.price) > a or H3.idx - H1.idx < 5 or depth < 2 * a or H1.price - L0.price < 2 * a:
            continue
        t0 = H3.idx + ctx.k
        t, s = _breakout(ctx, t0, t0 + ctx.wait, lambda t: top + 0.25 * a, lambda t: neck)
        if s == -1:
            out.append(Signal("Double Top", "chart", -1, H1.idx, t, top, neck - depth))
    return out


def triple_top(ctx: Ctx) -> List[Signal]:
    pv, A, out = ctx.pivots, ctx.atr, []
    for j in range(len(pv) - 4):
        H1, L2, H3, L4, H5 = pv[j:j + 5]
        if H1.kind != "H":
            continue
        a = A[H5.idx]
        hs = [H1.price, H3.price, H5.price]
        if max(hs) - min(hs) > 1.2 * a:
            continue
        top, neck = max(hs), min(L2.price, L4.price)
        depth = top - neck
        if depth < 2 * a:
            continue
        t0 = H5.idx + ctx.k
        t, s = _breakout(ctx, t0, t0 + ctx.wait, lambda t: top + 0.25 * a, lambda t: neck)
        if s == -1:
            out.append(Signal("Triple Top", "chart", -1, H1.idx, t, top, neck - depth))
    return out


def head_shoulders(ctx: Ctx) -> List[Signal]:
    pv, A, out = ctx.pivots, ctx.atr, []
    for j in range(len(pv) - 5):
        L0, H1, L2, H3, L4, H5 = pv[j:j + 6]
        if L0.kind != "L":
            continue
        a = A[H5.idx]
        if not (H3.price > max(H1.price, H5.price) + 0.5 * a):
            continue
        m = (L4.price - L2.price) / (L4.idx - L2.idx)
        neck = lambda t, m=m, L2=L2: L2.price + m * (t - L2.idx)  # noqa: E731
        head_h = H3.price - neck(H3.idx)
        if abs(H1.price - H5.price) > max(1.5 * a, 0.35 * head_h):
            continue
        r = (H3.idx - H1.idx) / max(1, H5.idx - H3.idx)
        if not (0.4 <= r <= 2.5):
            continue
        if H1.price < neck(H1.idx) + a or H5.price < neck(H5.idx) + a or L0.price > neck(L0.idx):
            continue
        t0 = H5.idx + ctx.k
        t, s = _breakout(ctx, t0, t0 + ctx.wait, lambda t: H5.price + 0.25 * a, neck)
        if s == -1:
            out.append(Signal("Head & Shoulders", "chart", -1, H1.idx, t, H5.price, neck(t) - head_h))
    return out


def inverse_cup(ctx: Ctx) -> List[Signal]:
    """Top form = Inverse Cup & Handle / Rounding Top (mirror -> Cup & Handle / Rounding Bottom)."""
    pv, A, h, c, out = ctx.pivots, ctx.atr, ctx.h, ctx.c, []
    for j in range(len(pv) - 2):
        L0, H1, L2 = pv[j:j + 3]
        if L0.kind != "L":
            continue
        a = A[L2.idx]
        rim = min(L0.price, L2.price)
        depth = H1.price - max(L0.price, L2.price)
        width = L2.idx - L0.idx
        if depth < 3 * a or depth > 0.4 * abs(L0.price) or width < 20:
            continue
        if abs(L0.price - L2.price) > max(1.5 * a, 0.15 * depth):
            continue
        near_top = (h[L0.idx:L2.idx + 1] >= H1.price - depth / 3).sum()
        if near_top < 0.25 * width:          # V-shapes don't count, must be rounded
            continue
        t0 = L2.idx + ctx.k
        for t in range(t0, min(t0 + 2 * ctx.wait, ctx.n)):
            mx = h[L2.idx + 1:t].max() if t > L2.idx + 1 else L2.price
            if mx > L2.price + 0.5 * depth or c[t] > H1.price:
                break
            if c[t] < rim:
                handle = mx - L2.price >= 0.75 * a
                name = "Inverse Cup & Handle" if handle else "Rounding Top"
                stop = mx if handle else rim + 0.5 * depth
                out.append(Signal(name, "chart", -1, L0.idx, t, float(stop), rim - depth))
                break
    return out


def bear_flag(ctx: Ctx) -> List[Signal]:
    """Pole down then a tight counter-trend drift; breaks below the drift."""
    pv, A, h, l, c, out = ctx.pivots, ctx.atr, ctx.h, ctx.l, ctx.c, []
    for j in range(len(pv) - 1):
        H0, L1 = pv[j], pv[j + 1]
        if H0.kind != "H":
            continue
        a = A[L1.idx]
        pole = H0.price - L1.price
        if pole < 3.5 * a or L1.idx - H0.idx > 15:
            continue
        t0 = L1.idx + max(4, ctx.k)
        for t in range(t0, min(L1.idx + 22, ctx.n)):
            seg = slice(L1.idx + 1, t)
            lo, hi = l[seg].min(), h[seg].max()
            if lo < L1.price - 0.1 * a or hi > L1.price + 0.5 * pole:
                break
            if c[t] < lo:
                xs = np.arange(L1.idx + 1, t)
                sh = np.polyfit(xs, h[seg], 1)[0]
                sl = np.polyfit(xs, l[seg], 1)[0]
                name = "Bear Pennant" if (sh < 0 < sl) else "Bear Flag"
                out.append(Signal(name, "chart", -1, H0.idx, t, float(hi), float(c[t] - pole)))
                break
    return out


def abcd_bear(ctx: Ctx) -> List[Signal]:
    """AB=CD: two equal up legs; reversal short at D."""
    pv, A, c, out = ctx.pivots, ctx.atr, ctx.c, []
    for j in range(len(pv) - 3):
        Ap, B, C, D = pv[j:j + 4]
        if Ap.kind != "L":
            continue
        ab, bc, cd = B.price - Ap.price, B.price - C.price, D.price - C.price
        if ab <= 0 or cd <= 0:
            continue
        if not (0.382 <= bc / ab <= 0.886 and 0.8 <= cd / ab <= 1.25 and D.price > B.price):
            continue
        t = D.idx + ctx.k
        if t >= ctx.n or c[t] >= D.price:
            continue
        out.append(Signal("Bearish AB=CD", "chart", -1, Ap.idx, t, D.price + 0.5 * A[D.idx],
                          D.price - 0.618 * cd))
    return out


def fib_rally_short(ctx: Ctx) -> List[Signal]:
    """Impulse down, retrace into the 50-61.8% zone, bearish reversal bar -> short."""
    pv, A, h, l, c, out = ctx.pivots, ctx.atr, ctx.h, ctx.l, ctx.c, []
    for j in range(len(pv) - 1):
        H0, L1 = pv[j], pv[j + 1]
        if H0.kind != "H":
            continue
        a = A[L1.idx]
        leg = H0.price - L1.price
        if leg < 3 * a:
            continue
        f50, f786 = L1.price + 0.5 * leg, L1.price + 0.786 * leg
        for t in range(L1.idx + ctx.k, min(L1.idx + 30, ctx.n)):
            mx = h[L1.idx + 1:t + 1].max()
            if mx > f786 or c[t] < L1.price:
                break
            if mx >= f50 and c[t] < l[t - 1]:
                out.append(Signal("Fib 50-61.8 Rejection", "chart", -1, H0.idx, t, f786 + 0.25 * a, L1.price))
                break
    return out


def rsi_div_bear(ctx: Ctx) -> List[Signal]:
    pv, A, c, R, out = ctx.pivots, ctx.atr, ctx.c, ctx.rsi, []
    highs = [p for p in pv if p.kind == "H"]
    for p1, p2 in zip(highs, highs[1:]):
        if p2.idx - p1.idx > 60 or not np.isfinite(R[p1.idx]) or not np.isfinite(R[p2.idx]):
            continue
        if p2.price > p1.price and R[p1.idx] > 60 and R[p2.idx] < R[p1.idx] - 3:
            t = p2.idx + ctx.k
            if t >= ctx.n:
                continue
            stop = p2.price + 0.25 * A[p2.idx]
            out.append(Signal("Bearish RSI Divergence", "chart", -1, p1.idx, t, stop,
                              float(c[t] - 2 * (stop - c[t]))))
    return out


TOP_FORMS = [
    (double_top, {"Double Top": "Double Bottom"}),
    (triple_top, {"Triple Top": "Triple Bottom"}),
    (head_shoulders, {"Head & Shoulders": "Inverse Head & Shoulders"}),
    (inverse_cup, {"Inverse Cup & Handle": "Cup & Handle", "Rounding Top": "Rounding Bottom"}),
    (bear_flag, {"Bear Flag": "Bull Flag", "Bear Pennant": "Bull Pennant"}),
    (abcd_bear, {"Bearish AB=CD": "Bullish AB=CD"}),
    (fib_rally_short, {"Fib 50-61.8 Rejection": "Fib 50-61.8 Bounce"}),
    (rsi_div_bear, {"Bearish RSI Divergence": "Bullish RSI Divergence"}),
]


# ============================================================ geometry (triangles, wedges, channels)
def geometry(ctx: Ctx) -> List[Signal]:
    pv, A, h, l, c = ctx.pivots, ctx.atr, ctx.h, ctx.l, ctx.c
    best: Dict[Tuple[int, int], Signal] = {}
    for j in range(len(pv) - 4):
        w = pv[j:j + 5]
        hs = [p for p in w if p.kind == "H"]
        ls = [p for p in w if p.kind == "L"]
        x0, x1 = w[0].idx, w[-1].idx
        span = x1 - x0
        if span < 12:
            continue
        a = float(np.nanmean(A[x0:x1 + 1]))
        mh, bh = np.polyfit([p.idx for p in hs], [p.price for p in hs], 1)
        ml, bl = np.polyfit([p.idx for p in ls], [p.price for p in ls], 1)
        up = lambda t, mh=mh, bh=bh: mh * t + bh  # noqa: E731
        lo = lambda t, ml=ml, bl=bl: ml * t + bl  # noqa: E731
        # pivots must sit on their lines, all bars inside the lines
        if max(abs(p.price - up(p.idx)) for p in hs) > 0.6 * a or max(abs(p.price - lo(p.idx)) for p in ls) > 0.6 * a:
            continue
        tt = np.arange(x0, x1 + 1)
        if (h[x0:x1 + 1] > up(tt) + 0.6 * a).any() or (l[x0:x1 + 1] < lo(tt) - 0.6 * a).any():
            continue
        height = up(x0) - lo(x0)
        if height < 2 * a:
            continue
        dh, dl = mh * span / a, ml * span / a
        flat = 0.75
        converging = (up(x1) - lo(x1)) < 0.85 * height
        name = None
        if abs(dh) < flat and abs(dl) < flat:
            name = "Rectangle"
        elif abs(dh) < flat and dl > flat and converging:
            name = "Ascending Triangle"
        elif abs(dl) < flat and dh < -flat and converging:
            name = "Descending Triangle"
        elif dh < -flat and dl > flat:
            name = "Symmetrical Triangle"
        elif dh > flat and dl > flat:
            if converging and dl > 1.15 * dh:
                name = "Rising Wedge"
            elif 0.8 <= dl / dh <= 1.25:
                name = "Ascending Channel"
        elif dh < -flat and dl < -flat:
            if converging and dh < 1.15 * dl:
                name = "Falling Wedge"
            elif 0.8 <= dl / dh <= 1.25:
                name = "Descending Channel"
        elif dh > flat and dl < -flat:
            name = "Broadening Formation"
        if name is None:
            continue
        t0 = x1 + ctx.k
        apex_guard = lambda t: up(t) - lo(t) < 0.3 * a  # noqa: E731
        t, s = None, 0
        for tt_ in range(t0, min(t0 + ctx.wait, ctx.n)):
            if apex_guard(tt_):
                break
            if c[tt_] > up(tt_):
                t, s = tt_, 1
                break
            if c[tt_] < lo(tt_):
                t, s = tt_, -1
                break
        if not s:
            continue
        last_l = max(p.price for p in ls if p.idx == max(q.idx for q in ls))
        last_h = max(p.price for p in hs if p.idx == max(q.idx for q in hs))
        if s == 1:
            sig = Signal(f"{name} (break ↑)", "chart", 1, x0, t, float(max(lo(t), last_l)), float(c[t] + height))
        else:
            sig = Signal(f"{name} (break ↓)", "chart", -1, x0, t, float(min(up(t), last_h)), float(c[t] - height))
        best[(t, s)] = sig  # latest window wins for a given breakout bar
    return list(best.values())


def detect(ctx: Ctx) -> List[Signal]:
    out: List[Signal] = []
    mctx = ctx.mirror()
    for fn, names in TOP_FORMS:
        out += fn(ctx)
        out += [unmirror(s, names[s.pattern]) for s in fn(mctx)]
    out += geometry(ctx)
    # if a triple top/bottom fires on a bar, drop the double on the same bar
    triples = {(s.end, s.direction) for s in out if s.pattern.startswith("Triple")}
    out = [s for s in out if not (s.pattern.startswith("Double") and (s.end, s.direction) in triples)]
    seen, uniq = set(), []
    for s in out:
        key = (s.pattern, s.end)
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    return uniq


GEOMETRY = ["Rectangle", "Ascending Triangle", "Descending Triangle", "Symmetrical Triangle", "Rising Wedge",
            "Falling Wedge", "Ascending Channel", "Descending Channel", "Broadening Formation"]
NAMES = [n for _, m in TOP_FORMS for kv in m.items() for n in kv] + \
        [f"{g} (break {d})" for g in GEOMETRY for d in ("↑", "↓")]
