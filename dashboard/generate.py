#!/usr/bin/env python3
"""
Positioning dashboard generator.

Pulls real-time prices (Twelve Data) and options put/call ratios (Alpha Vantage),
computes trend/volatility/Fibonacci metrics, writes a static dashboard to docs/,
and optionally emails a mobile-safe summary.

Designed to run unattended in GitHub Actions twice a weekday.

Env vars:
  TWELVEDATA_KEY   required  price data          (free tier: 800/day, 8/min)
  ALPHAVANTAGE_KEY optional  put/call ratios     (free tier: 25/day)
  SMTP_USER        optional  gmail address       — email skipped if unset
  SMTP_PASS        optional  gmail app password
  MAIL_TO          optional  recipient (defaults to SMTP_USER)
  TICKERS          optional  comma list, default SPY,QQQ,NVDA,TSLA,BE,MU,ACN
  SLOT             optional  "preopen" | "close" — changes framing only
"""
from __future__ import annotations
import os, sys, json, time, math, smtplib, datetime, statistics as st
import urllib.request, urllib.parse, urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS   = os.path.join(ROOT, "docs")
TD_KEY = os.environ.get("TWELVEDATA_KEY", "").strip()
AV_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()
TICKERS = [t.strip().upper() for t in
           os.environ.get("TICKERS", "SPY,QQQ,NVDA,TSLA,BE,MU,ACN").split(",") if t.strip()]
SLOT   = os.environ.get("SLOT", "close").lower()
INDEXES = {"SPY", "QQQ", "DIA", "IWM", "VTI"}

COLORS = ["#c98500", "#9085e9", "#199e70", "#d03b3b", "#3987e5", "#d95926", "#0ca30c",
          "#e66767", "#256abf", "#fab219"]
GOLD, GREEN, RED, AMBER = "#c98500", "#0ca30c", "#d03b3b", "#fab219"


# ───────────────────────────── http ─────────────────────────────

def _get(url: str, tries: int = 2, pause: float = 1.5):
    """GET returning parsed JSON, or None. Never raises."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "positioning-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt == tries - 1:
                print(f"  ! request failed: {type(e).__name__}: {e}", file=sys.stderr)
                return None
            time.sleep(pause)
    return None


# ─────────────────────────── providers ──────────────────────────

class TwelveData:
    """Real-time US equity/ETF prices. Free tier: 800 calls/day, 8 calls/min."""
    BASE = "https://api.twelvedata.com"

    def __init__(self, key: str):
        self.key = key
        self._calls = 0
        self._minute_start = time.time()

    def _throttle(self):
        # hard-respect the 8/min ceiling; sleep out the window rather than burn errors
        if self._calls >= 7:
            elapsed = time.time() - self._minute_start
            if elapsed < 61:
                nap = 61 - elapsed
                print(f"  … twelvedata minute cap, sleeping {nap:.0f}s")
                time.sleep(nap)
            self._calls = 0
            self._minute_start = time.time()
        self._calls += 1

    def quote(self, symbol: str) -> dict | None:
        self._throttle()
        q = urllib.parse.urlencode({"symbol": symbol, "apikey": self.key,
                                    "prepost": "true", "format": "JSON"})
        d = _get(f"{self.BASE}/quote?{q}")
        if not d or "close" not in d:
            print(f"  ! {symbol}: quote unavailable ({(d or {}).get('message', 'no data')})")
            return None
        return d

    def series(self, symbol: str, outputsize: int = 100) -> list[dict] | None:
        self._throttle()
        q = urllib.parse.urlencode({"symbol": symbol, "interval": "1day",
                                    "outputsize": outputsize, "apikey": self.key,
                                    "format": "JSON"})
        d = _get(f"{self.BASE}/time_series?{q}")
        vals = (d or {}).get("values")
        if not vals:
            print(f"  ! {symbol}: series unavailable ({(d or {}).get('message', 'no data')})")
            return None
        return vals  # newest first


class AlphaVantage:
    """Options put/call ratios. Free tier: 25 calls/day — spend them carefully."""
    BASE = "https://www.alphavantage.co/query"

    def __init__(self, key: str, budget: int = 25):
        self.key = key
        self.remaining = budget

    def put_call(self, symbol: str) -> tuple[float | None, list, str | None]:
        """Returns (full_chain_ratio, by_expiry, error)."""
        if not self.key:
            return None, [], "no ALPHAVANTAGE_KEY set"
        if self.remaining <= 0:
            return None, [], "daily 25-call budget exhausted"
        self.remaining -= 1
        q = urllib.parse.urlencode({"function": "REALTIME_PUT_CALL_RATIO",
                                    "symbol": symbol, "apikey": self.key})
        d = _get(f"{self.BASE}?{q}")
        if not d:
            return None, [], "request failed"
        if "Information" in d or "Note" in d:
            self.remaining = 0
            return None, [], "rate limit reached"
        if isinstance(d.get("error"), dict):
            self.remaining = 0
            return None, [], d["error"].get("message", "error")[:80]
        try:
            ratio = float(d["put_call_ratio_full_chain"])
        except (KeyError, TypeError, ValueError):
            return None, [], "unexpected payload shape"
        expiries = [(e.get("date"), float(e.get("value", 0)))
                    for e in d.get("put_call_ratio_by_expiration", [])]
        return ratio, expiries, None


# ─────────────────────────── metrics ────────────────────────────

def annualized_vol(closes: list[float], window: int = 20) -> float | None:
    if len(closes) < window + 1:
        return None
    rets = [100 * (closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    return st.stdev(rets[-window:]) * math.sqrt(252)


def classify_trend(price: float, ma20: float | None, ma50: float | None):
    """Above both = uptrend, below both = broken, straddling = consolidating.

    Deliberately simple and objective. This disagrees with raw return often —
    a name up 50% over the window can still be below both averages, and that
    disagreement is usually the most informative thing on the card.
    """
    if ma20 is None or ma50 is None:
        return "Unknown", "#8a8a84"
    a, b = price > ma20, price > ma50
    if a and b:
        return "Uptrend", GREEN
    if not a and not b:
        return "Broken", RED
    return "Consolidating", AMBER


def fib_levels(high: float, low: float) -> list[tuple[float, float]]:
    """Retracement levels of the high→low swing. Arithmetic, not prediction."""
    return [(f, low + f * (high - low)) for f in (0.236, 0.382, 0.5, 0.618, 0.786)]


def compute(symbol: str, quote: dict, series: list[dict], pcr, pcr_err) -> dict:
    closes = [float(r["close"]) for r in reversed(series)]      # chronological
    close  = float(quote["close"])
    prev   = float(quote.get("previous_close") or close)
    ext    = quote.get("extended_price")
    ext    = float(ext) if ext not in (None, "", "0") else None
    ma20 = st.mean(closes[-20:]) if len(closes) >= 20 else None
    ma50 = st.mean(closes[-50:]) if len(closes) >= 50 else None
    peak, trough = max(closes), min(closes)
    trend, tcolor = classify_trend(close, ma20, ma50)
    return {
        "symbol": symbol,
        "name": quote.get("name", symbol),
        "close": close,
        "prev": prev,
        "day_pct": 100 * (close / prev - 1) if prev else 0.0,
        "ext": ext,
        "ext_pct": (100 * (ext / close - 1)) if ext else None,
        "day_low": float(quote.get("low") or close),
        "day_high": float(quote.get("high") or close),
        "volume": int(float(quote.get("volume") or 0)),
        "w52_low": float(quote.get("fifty_two_week_low") or trough),
        "w52_high": float(quote.get("fifty_two_week_high") or peak),
        "ma20": ma20, "ma50": ma50,
        "vs20": (100 * (close / ma20 - 1)) if ma20 else None,
        "vs50": (100 * (close / ma50 - 1)) if ma50 else None,
        "vol": annualized_vol(closes),
        "peak": peak, "trough": trough,
        "off_peak": 100 * (close / peak - 1),
        "off_low": 100 * (close / trough - 1),
        "trend": trend, "tcolor": tcolor,
        "pcr": pcr, "pcr_err": pcr_err,
        "fib": fib_levels(peak, trough),
        "closes": closes,
        "is_index": symbol in INDEXES,
    }


# ──────────────────────── chart primitives ──────────────────────
# Rules learned the hard way against iOS Gmail:
#   - size bars with height= and bgcolor= ATTRIBUTES, never CSS on a div
#   - never leave a cell empty; always &nbsp;
#   - nested tables only, no divs for structure
#   - CSS `background` on a div gets stripped while white text survives,
#     which renders the chart invisible. bgcolor on <td> survives.

NBSP = "&nbsp;"
TINY = 'style="font-size:1px;line-height:1px"'
BLOCKS = "▁▂▃▄▅▆▇█"


def downsample(values: list[float], n: int):
    """Bucket into n bars. Each bar is its bucket's last value EXCEPT the buckets
    holding the true max and min, which show the real extreme — so the axis
    labels can never disagree with the peak quoted in the text."""
    L = len(values)
    if L <= n:
        return list(values), values.index(max(values))
    gmax, gmin = values.index(max(values)), values.index(min(values))
    out, hit = [], None
    for i in range(n):
        a = round(i * L / n)
        b = max(a + 1, round((i + 1) * L / n))
        seg = list(range(a, min(b, L))) or [min(a, L - 1)]
        if gmax in seg:
            out.append(values[gmax]); hit = i
        elif gmin in seg:
            out.append(values[gmin])
        else:
            out.append(values[seg[-1]])
    return out, hit


def column_chart(values: list[float], color: str, height: int = 104, bars: int = 20) -> str:
    s, mark = downsample(values, bars)
    lo, hi = min(s), max(s)
    rng = (hi - lo) or 1
    cells = []
    for i, v in enumerate(s):
        h = max(3, int((v - lo) / rng * height))
        pad = height - h
        c = GOLD if i == mark else color
        inner = (f'<tr><td height="{pad}" {TINY}>{NBSP}</td></tr>' if pad else "") + \
                f'<tr><td height="{h}" bgcolor="{c}" {TINY}>{NBSP}</td></tr>'
        cells.append(f'<td valign="bottom" style="padding:0 1px">'
                     f'<table width="100%" border="0" cellpadding="0" cellspacing="0">{inner}</table></td>')
    return ('<table width="100%" border="0" cellpadding="0" cellspacing="0"><tr>'
            + "".join(cells) + "</tr></table>")


def sparkline(values: list[float], n: int = 26) -> str:
    """Pure text. Survives every client, including plain-text fallback."""
    s, _ = downsample(values, n)
    lo, hi = min(s), max(s)
    rng = (hi - lo) or 1
    return "".join(BLOCKS[min(7, int((v - lo) / rng * 7.999))] for v in s)


def text_bar(pct_of_max: float, width: int = 18) -> str:
    f = max(0, min(width, round(pct_of_max / 100 * width)))
    return "█" * f + "░" * (width - f)


# ───────────────────────────── render ───────────────────────────

def render_dashboard(rows: list[dict], stamp: str, notes: list[str]) -> str:
    color_of = {r["symbol"]: COLORS[i % len(COLORS)] for i, r in enumerate(rows)}
    idx = [r["pcr"] for r in rows if r["is_index"] and r["pcr"]]
    sng = [r["pcr"] for r in rows if not r["is_index"] and r["pcr"]]

    movers = sorted(rows, key=lambda r: abs(r["day_pct"]), reverse=True)
    lead = ", ".join(f'{r["symbol"]} {r["day_pct"]:+.1f}%' for r in movers[:4])
    read = f"<b>{lead}.</b> "
    if idx and sng:
        read += (f"Index put/call averages <b>{st.mean(idx):.2f}</b> against "
                 f"<b>{st.mean(sng):.2f}</b> for the single names. "
                 f"{'Hedging is concentrated at index level.' if st.mean(idx) > 1 > st.mean(sng) else ''}")

    def fib_rows(r):
        out = []
        for f, p in r["fib"]:
            if p < r["close"]:
                col, txt = GREEN, "cleared"
            else:
                col, txt = "#8a8a84", "%+.1f%%" % (100 * (p / r["close"] - 1))
            out.append(f'<tr><td>{f*100:.1f}%</td><td class="n">{p:,.2f}</td>'
                       f'<td class="n" style="color:{col}">{txt}</td></tr>')
        return "".join(out)

    def card(r):
        c = color_of[r["symbol"]]
        s, _ = downsample(r["closes"], 20)
        chart = column_chart(r["closes"], c)
        ext = (f'<div class="ah">After hours <b>{r["ext"]:,.2f}</b> '
               f'<span style="color:{GREEN if r["ext_pct"]>=0 else RED}">{r["ext_pct"]:+.2f}%</span></div>'
               ) if r["ext"] else ""
        pcr = f'{r["pcr"]:.2f}' if r["pcr"] else "n/a"
        psub = "parity = 1.00" if r["pcr"] else (r["pcr_err"] or "unavailable")
        rng = 100 * (r["day_high"] / r["day_low"] - 1) if r["day_low"] else 0
        return f"""<div class="tc">
<div class="th"><span class="ts" style="color:{c}">{r['symbol']}</span><span class="tn">{r['name']}</span>
<span class="pill" style="background:{r['tcolor']}26;color:{r['tcolor']};border-color:{r['tcolor']}66">{r['trend']}</span></div>
<div class="px">{r['close']:,.2f} <span class="chg" style="color:{GREEN if r['day_pct']>0 else RED}">{r['day_pct']:+.2f}%</span></div>
{ext}
<div class="rng">Session {r['day_low']:,.2f}&ndash;{r['day_high']:,.2f} <span class="rp">range {rng:.1f}% &middot; vol {r['volume']:,}</span></div>
<div class="lbl">Close &middot; last {len(r['closes'])} sessions &nbsp;<span style="color:{GOLD}">gold = peak</span></div>
{chart}
<div class="ax"><span>{min(s):,.0f}</span><span>{max(s):,.0f}</span></div>
<div class="sp" style="color:{c}">{sparkline(r['closes'])}</div>
<div class="g">
<div><div class="l">vs 20-day</div><div class="v" style="color:{GREEN if (r['vs20'] or 0)>0 else RED}">{('%+.1f%%'%r['vs20']) if r['vs20'] is not None else '&mdash;'}</div></div>
<div><div class="l">vs 50-day</div><div class="v" style="color:{GREEN if (r['vs50'] or 0)>0 else RED}">{('%+.1f%%'%r['vs50']) if r['vs50'] is not None else '&mdash;'}</div></div>
<div><div class="l">Realized vol</div><div class="v">{('%.0f%%'%r['vol']) if r['vol'] else '&mdash;'}</div><div class="s">20d annualized</div></div>
<div><div class="l">Off peak</div><div class="v" style="color:{RED}">{r['off_peak']:+.1f}%</div><div class="s">peak {r['peak']:,.0f}</div></div>
<div><div class="l">Put/call</div><div class="v" style="color:{c}">{pcr}</div><div class="s">{psub}</div></div>
<div><div class="l">52-week</div><div class="v s2">{r['w52_low']:,.0f}&ndash;{r['w52_high']:,.0f}</div></div>
</div>
<div class="fibwrap"><div class="lbl2">Fibonacci retracement of the window swing</div>
<table class="fib"><tr><th>Level</th><th class="n">Price</th><th class="n">vs now</th></tr>{fib_rows(r)}</table></div>
</div>"""

    table = "".join(
        f'<tr><td><b style="color:{color_of[r["symbol"]]}">{r["symbol"]}</b><div class="nm">{r["name"]}</div></td>'
        f'<td class="n">{r["close"]:,.2f}</td>'
        f'<td class="n" style="color:{GREEN if r["day_pct"]>0 else RED}">{r["day_pct"]:+.2f}%</td>'
        f'<td class="n">{("%+.2f%%"%r["ext_pct"]) if r["ext"] else "&mdash;"}</td>'
        f'<td class="n">{("%.0f%%"%r["vol"]) if r["vol"] else "&mdash;"}</td>'
        f'<td class="n">{r["off_peak"]:+.1f}%</td>'
        f'<td class="n">{("%.2f"%r["pcr"]) if r["pcr"] else "n/a"}</td>'
        f'<td><span class="pill" style="background:{r["tcolor"]}26;color:{r["tcolor"]};border-color:{r["tcolor"]}66">{r["trend"]}</span></td></tr>'
        for r in rows)

    note_html = ("<br>".join(notes)) if notes else "All feeds returned complete data."
    return f"""<title>Positioning Dashboard</title>
<style>
:root{{--pl:#080808;--s1:#121212;--tp:#fff;--ts:#c9c9c4;--tm:#8a8a84;--bd:rgba(255,255,255,.10);
--f:system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--pl);color:var(--tp);font:400 17px/1.65 var(--f);-webkit-font-smoothing:antialiased}}
.w{{max-width:1140px;margin:0 auto;padding:40px 22px 70px}}
.k{{font-size:12.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--tm);font-weight:600}}
h1{{font-size:2.1rem;font-weight:620;letter-spacing:-.025em;margin:10px 0 4px;text-wrap:balance}}
.sub{{color:var(--ts);font-size:15px}}
.card{{background:var(--s1);border:1px solid var(--bd);border-radius:14px;padding:22px;margin:22px 0}}
h2{{font-size:1.3rem;font-weight:600;margin:38px 0 10px}}
.scroll{{overflow-x:auto;border-radius:12px}}
table.t{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;min-width:720px}}
.t th{{text-align:right;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--tm);font-weight:650;padding:10px 8px;border-bottom:1px solid var(--bd)}}
.t th:first-child,.t td:first-child{{text-align:left}}
.t td{{padding:12px 8px;border-bottom:1px solid rgba(255,255,255,.05);font-size:15px;white-space:nowrap}}
.t tr:last-child td{{border-bottom:0}}
.n{{text-align:right;font-weight:650}}
.nm{{font-size:12px;color:var(--tm);font-weight:400}}
.pill{{font-size:11.5px;padding:3px 10px;border-radius:20px;border:1px solid;font-weight:650;white-space:nowrap}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin-top:14px}}
.tc{{background:var(--s1);border:1px solid var(--bd);border-radius:14px;padding:18px 20px}}
.th{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.ts{{font-size:1.5rem;font-weight:750}}
.tn{{font-size:13px;color:var(--ts)}}
.th .pill{{margin-left:auto}}
.px{{font-size:1.9rem;font-weight:700;letter-spacing:-.02em;margin-top:10px;font-variant-numeric:tabular-nums}}
.chg{{font-size:1rem;font-weight:650;margin-left:6px}}
.ah{{font-size:12.5px;color:var(--tm);margin-top:2px}}
.rng{{font-size:12px;color:var(--ts);margin-top:6px}}
.rp{{color:var(--tm)}}
.lbl{{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--tm);font-weight:700;margin:16px 0 6px}}
.lbl2{{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--tm);font-weight:700;margin:0 0 6px}}
.ax{{display:flex;justify-content:space-between;font-size:11px;color:var(--tm);padding-top:4px}}
.sp{{font-family:ui-monospace,Menlo,monospace;font-size:15px;letter-spacing:-.5px;line-height:1;margin:10px 0 0;overflow:hidden}}
.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px 14px;margin:16px 0 0;border-top:1px solid var(--bd);padding-top:14px}}
.l{{font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--tm);font-weight:650}}
.v{{font-size:1.12rem;font-weight:650;font-variant-numeric:tabular-nums}}
.v.s2{{font-size:.92rem}}
.s{{font-size:10px;color:var(--tm)}}
.fibwrap{{margin-top:14px;border-top:1px solid var(--bd);padding-top:12px}}
table.fib{{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}}
.fib th{{text-align:left;font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--tm);font-weight:650;padding:3px 0}}
.fib th.n,.fib td.n{{text-align:right}}
.fib td{{padding:3px 0;color:var(--ts)}}
.fn{{margin-top:34px;padding-top:18px;border-top:1px solid var(--bd);font-size:13px;line-height:1.65;color:var(--tm)}}
@media(max-width:520px){{.g{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:1.7rem}}}}
</style>
<div class="w">
<div class="k">{len(rows)} tickers &middot; {SLOT} &middot; {stamp}</div>
<h1>Positioning dashboard</h1>
<div class="sub">Prices live via Twelve Data &middot; put/call via Alpha Vantage</div>
<div class="card"><div class="k" style="margin-bottom:8px">The read</div>
<div style="font-size:18px;line-height:1.55">{read}</div></div>
<h2>All {len(rows)}</h2>
<div class="card" style="padding:8px 20px"><div class="scroll">
<table class="t"><thead><tr><th>Ticker</th><th>Close</th><th>Day</th><th>After hrs</th><th>Vol 20d</th><th>Off peak</th><th>Put/call</th><th style="text-align:left">Trend</th></tr></thead>
<tbody>{table}</tbody></table></div></div>
<h2>Ticker detail</h2>
<div class="grid">{"".join(card(r) for r in rows)}</div>
<div class="fn"><b>Data health.</b> {note_html}<br>
Fibonacci levels are arithmetic on the window's high and low &mdash; reference levels, not forecasts.
Realized volatility is the annualized standard deviation of the last 20 daily returns; it describes
what has already happened, not what will.<br>
Positioning and trend context only &mdash; not investment advice, and nothing here is a
recommendation to buy, hold or sell.</div>
</div>"""


def render_email(rows: list[dict], stamp: str, notes: list[str], url: str | None) -> tuple[str, str]:
    """Mobile-safe HTML + a plain-text twin carrying the same charts."""
    color_of = {r["symbol"]: COLORS[i % len(COLORS)] for i, r in enumerate(rows)}
    mx = max(abs(r["day_pct"]) for r in rows) or 1
    movers = sorted(rows, key=lambda r: r["day_pct"], reverse=True)

    move_html, move_txt = [], []
    for r in movers:
        bar = text_bar(abs(r["day_pct"]) / mx * 100)
        move_html.append(f'<span style="color:{color_of[r["symbol"]]}">{r["symbol"]:<4} '
                         f'{r["day_pct"]:+6.2f}%</span> {bar}<br>')
        move_txt.append(f'  {r["symbol"]:<5}{r["day_pct"]:+7.2f}%  {bar}')

    pcr_rows = sorted([r for r in rows if r["pcr"]], key=lambda r: -r["pcr"])
    pmax = max((r["pcr"] for r in pcr_rows), default=1.4)
    pcr_html, pcr_txt = [], []
    for r in pcr_rows:
        bar = text_bar(r["pcr"] / (pmax * 1.1) * 100)
        pcr_html.append(f'<span style="color:{color_of[r["symbol"]]}">{r["symbol"]:<4} '
                        f'{r["pcr"]:.2f}</span> {bar}<br>')
        pcr_txt.append(f'  {r["symbol"]:<5}{r["pcr"]:.2f}  {bar}')

    link = (f'<tr><td bgcolor="#121212" style="border-radius:12px;padding:16px;text-align:center">'
            f'<a href="{url}" style="display:inline-block;padding:13px 28px;background:#3987e5;'
            f'color:#fff;text-decoration:none;border-radius:9px;font-weight:600;font-size:16px">'
            f'Open the full dashboard &rarr;</a></td></tr>'
            f'<tr><td height="14" style="font-size:1px;line-height:1px">&nbsp;</td></tr>') if url else ""

    note_line = " ".join(notes) if notes else ""
    html = f"""<table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#080808"><tr>
<td align="center" bgcolor="#080808" style="padding:18px 10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width:420px">
<tr><td bgcolor="#080808" style="padding:0 4px 12px">
<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8a8a84;font-weight:700">{SLOT} &middot; {stamp}</div>
<div style="font-size:22px;font-weight:700;color:#fff;padding-top:5px;line-height:1.3">Positioning &mdash; {len(rows)} tickers</div></td></tr>
<tr><td bgcolor="#121212" style="border-radius:12px;padding:16px">
<div style="font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#8a8a84;font-weight:700;padding-bottom:10px">Day change</div>
<div style="font-family:Menlo,Courier,monospace;font-size:13.5px;line-height:1.95;color:#fff;white-space:nowrap">{"".join(move_html)}</div>
</td></tr>
<tr><td height="14" style="font-size:1px;line-height:1px">&nbsp;</td></tr>
<tr><td bgcolor="#121212" style="border-radius:12px;padding:16px">
<div style="font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#8a8a84;font-weight:700;padding-bottom:10px">Put/call &middot; parity 1.00</div>
<div style="font-family:Menlo,Courier,monospace;font-size:13.5px;line-height:1.95;color:#fff;white-space:nowrap">{"".join(pcr_html)}</div>
</td></tr>
<tr><td height="14" style="font-size:1px;line-height:1px">&nbsp;</td></tr>
{link}
<tr><td bgcolor="#080808" style="padding:12px 4px 0;font-size:12px;line-height:1.6;color:#8a8a84">
{note_line}<br><br>Not investment advice, and nothing here is a recommendation to buy, hold or sell.</td></tr>
</table></td></tr></table>"""

    text = (f"POSITIONING — {len(rows)} tickers — {SLOT} — {stamp}\n\n"
            "DAY CHANGE\n" + "\n".join(move_txt) +
            "\n\nPUT/CALL (parity 1.00)\n" + "\n".join(pcr_txt) +
            (f"\n\nFull dashboard: {url}" if url else "") +
            (f"\n\n{note_line}" if note_line else "") +
            "\n\nNot investment advice, and nothing here is a recommendation to buy, hold or sell.\n")
    return html, text


def send_email(subject: str, html: str, text: str) -> bool:
    user, pwd = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if not (user and pwd):
        print("  · SMTP_USER/SMTP_PASS unset — skipping email")
        return False
    to = os.environ.get("MAIL_TO", user)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pwd)
            s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
        print(f"  · emailed {to}")
        return True
    except Exception as e:
        print(f"  ! email failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


# ───────────────────────────── main ─────────────────────────────

def main() -> int:
    if not TD_KEY:
        print("FATAL: TWELVEDATA_KEY is not set", file=sys.stderr)
        return 1

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    td, av = TwelveData(TD_KEY), AlphaVantage(AV_KEY)
    rows, notes = [], []

    for sym in TICKERS:
        print(f"· {sym}")
        q = td.quote(sym)
        if not q:
            notes.append(f"{sym}: price unavailable, omitted.")
            continue
        s = td.series(sym, 100)
        if not s:
            notes.append(f"{sym}: history unavailable, omitted.")
            continue
        pcr, _exp, err = av.put_call(sym)
        if err:
            notes.append(f"{sym}: put/call missing ({err}).")
        rows.append(compute(sym, q, s, pcr, err))
        print(f"    {rows[-1]['close']:,.2f}  {rows[-1]['day_pct']:+.2f}%  {rows[-1]['trend']}")

    if not rows:
        print("FATAL: no tickers resolved", file=sys.stderr)
        return 1

    os.makedirs(os.path.join(DOCS, "archive"), exist_ok=True)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    html = render_dashboard(rows, stamp, notes)
    open(os.path.join(DOCS, "index.html"), "w").write(html)
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    open(os.path.join(DOCS, "archive", f"{day}-{SLOT}.html"), "w").write(html)
    json.dump([{k: v for k, v in r.items() if k not in ("closes", "fib")} for r in rows],
              open(os.path.join(DOCS, "latest.json"), "w"), indent=1, default=str)
    print(f"· wrote docs/index.html ({len(html):,} bytes) and archive/{day}-{SLOT}.html")

    url = os.environ.get("PAGES_URL")
    e_html, e_text = render_email(rows, stamp, notes, url)
    lead = sorted(rows, key=lambda r: abs(r["day_pct"]), reverse=True)[0]
    send_email(f"Positioning {SLOT} — {lead['symbol']} {lead['day_pct']:+.1f}%", e_html, e_text)

    print(f"· done. twelvedata calls: {td._calls}+, alphavantage budget left: {av.remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
