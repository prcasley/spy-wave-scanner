"""Renders the single-ticker deep dive to HTML (Matte tokens) + a mobile email."""
import statistics as st, re
exec(open('/tmp/spy/deepdive.py').read())

# ── shared chart helpers (iOS Gmail safe: bgcolor attrs, never CSS background) ──
NB='&nbsp;'; T='style="font:1px/1px arial"'
SPK='▁▂▃▄▅▆▇█'
def buckets(vals,n):
    L=len(vals);gx=vals.index(max(vals));gn=vals.index(min(vals));o=[];hit=None
    for i in range(n):
        a=round(i*L/n);b=max(a+1,round((i+1)*L/n));seg=list(range(a,min(b,L))) or [min(a,L-1)]
        if gx in seg:o.append(vals[gx]);hit=i
        elif gn in seg:o.append(vals[gn])
        else:o.append(vals[seg[-1]])
    return o,hit
def spark(vals,n=30):
    s,_=buckets(vals,n);lo,hi=min(s),max(s);rg=(hi-lo) or 1
    return ''.join(SPK[min(7,int((x-lo)/rg*7.999))] for x in s)
def cols(vals,color,h=104,n=22,gold="#c98500"):
    s,mk=buckets(vals,n);lo,hi=min(s),max(s);rg=(hi-lo) or 1;td=[]
    for i,x in enumerate(s):
        bh=max(3,int((x-lo)/rg*h));pad=h-bh
        cc=gold if i==mk else color
        inner=(f'<tr><td height={pad} {T}>{NB}</td></tr>' if pad else '')+\
              f'<tr><td height={bh} bgcolor="{cc}" {T}>{NB}</td></tr>'
        td.append(f'<td valign=bottom><table width="100%" cellspacing=0 cellpadding=0 border=0>{inner}</table></td>')
    return f'<table width="100%" cellspacing=1 cellpadding=0 border=0><tr>{"".join(td)}</tr></table>',lo,hi
def tbar(p,w=18):
    f=max(0,min(w,round(p/100*w)));return '█'*f+'░'*(w-f)

SC={"PASS":"#0ca30c","FAIL":"#d03b3b","UNKNOWN":"#fab219"}
ACC=COL[SYM]

# put/call history bar chart (value vs band)
pmin,pmax=min(hist)*0.92,max(hist)*1.04
def pcr_bar(x):
    frac=(x-pmin)/(pmax-pmin)
    return tbar(frac*100)

hist_rows="".join(
  '<tr><td class="d">%s</td><td class="n">%.2f</td>'
  '<td class="bar" style="color:%s">%s</td><td class="n s">%s</td></tr>'
  % (d, x, ACC if i<len(hist)-1 else "#fab219", pcr_bar(x),
     "today" if i==len(hist)-1 else "")
  for i,(d,x) in enumerate(PCR_HISTORY[SYM]))

exp_rows="".join(
  '<tr><td class="d">%s</td><td class="n">%.2f</td>'
  '<td class="bar" style="color:%s">%s</td></tr>'
  % (d, x, "#d03b3b" if x>=1.5 else ("#0ca30c" if x<0.9 else "#c9c9c4"),
     tbar(min(x,3.0)/3.0*100))
  for d,x in PCR_EXPIRY[SYM])

gate_cards="".join(
  '<div class="gate %s"><div class="gh"><span class="gn">%s</span>'
  '<span class="gb" style="color:%s;border-color:%s">%s</span></div>'
  '<div class="gl">%s</div><div class="gd">%s</div></div>'
  % (x["status"].lower(), x["name"], SC[x["status"]], SC[x["status"]],
     x["status"], x["line"], x["detail"])
  for x in GATES)

chart,clo,chi=cols(v,ACC)

NEED=[("Open interest by strike and expiry",
       "Shows where dealer exposure actually sits. Volume tells you what traded today; "
       "open interest tells you what is still held.",
       "Alpha Vantage REALTIME_OPTIONS (premium tier), Polygon options, CBOE DataShop"),
      ("Gamma per strike, or the full greeks",
       "Lets you compute net dealer gamma (GEX) — the real feedback loop between "
       "option hedging and spot price.",
       "Alpha Vantage REALTIME_OPTIONS with greeks (premium), ORATS, Unusual Whales"),
      ("Trade side — executed at bid or at ask",
       "Separates put BUYING (hedging, bearish) from put SELLING (premium collection, "
       "bullish). Same ratio, opposite meaning. This is the single biggest blind spot.",
       "Polygon options trades with NBBO, Unusual Whales flow"),
      ("Implied-vol skew, 25-delta put vs 25-delta call",
       "The price of fear rather than the quantity of it. Moves before volume does.",
       "ORATS, CBOE, or any options feed carrying IV per contract"),
      ("A year of daily put/call history",
       "Turns 1.05 from a number into a percentile. Without it, 'high' and 'low' "
       "are opinions.",
       "Alpha Vantage HISTORICAL_PUT_CALL_RATIO — free, but one call per date"),
      ("The gamma flip level",
       "The spot price where net dealer gamma crosses zero. Above it, hedging damps "
       "moves; below it, hedging amplifies them.",
       "Derived once you have open interest plus gamma")]
need_rows="".join(
  '<tr><td><b>%s</b><div class="s">%s</div></td><td class="src">%s</td></tr>' % n
  for n in NEED)

html=f"""<title>{SYM} Deep Dive</title>
<style>
:root{{
--plane:#080808;--surface-1:#121212;--surface-2:#1a1a1a;--surface-3:#222;
--text-primary:#fff;--text-secondary:#c9c9c4;--text-muted:#8a8a84;
--grid:#232323;--axis:#383835;--border:rgba(255,255,255,.10);
--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;
--accent:{ACC};
--font:system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--plane);color:var(--text-primary);
font:400 17px/1.65 var(--font);-webkit-font-smoothing:antialiased}}
.w{{max-width:1120px;margin:0 auto;padding:40px 22px 72px}}
.k{{font-size:13px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted);font-weight:560}}
h1{{font-size:1.9rem;font-weight:620;letter-spacing:-.015em;margin:10px 0 4px}}
h2{{font-size:1.35rem;font-weight:600;margin:44px 0 12px}}
h3{{font-size:1.05rem;font-weight:600;margin:24px 0 6px}}
p{{max-width:72ch}}
.sub{{color:var(--text-secondary);font-size:15px}}
.card{{background:var(--surface-1);border:1px solid var(--border);border-radius:14px;padding:24px;margin:24px 0}}
.hero{{display:flex;gap:32px;align-items:center;flex-wrap:wrap}}
.ring{{width:132px;height:132px;border-radius:50%;flex:none;
background:conic-gradient(var(--good) 0 {passed/len(GATES)*360:.0f}deg, var(--surface-3) {passed/len(GATES)*360:.0f}deg 360deg);
display:flex;align-items:center;justify-content:center}}
.ring i{{width:104px;height:104px;border-radius:50%;background:var(--surface-1);
display:flex;flex-direction:column;align-items:center;justify-content:center;font-style:normal}}
.ring b{{font-size:1.7rem;font-weight:600;letter-spacing:-.02em}}
.ring s{{font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted);text-decoration:none;font-weight:560}}
.px{{font-size:clamp(2.75rem,7vw,4rem);font-weight:600;letter-spacing:-.03em;line-height:1.05}}
.chg{{font-size:1.15rem;font-weight:600;margin-left:10px;letter-spacing:0}}
.mg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:16px}}
.m{{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:13px 15px}}
.m .l{{font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted);font-weight:560}}
.m .v{{font-size:1.15rem;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}}
.m .s2{{font-size:11px;color:var(--text-muted)}}
.gates{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}
.gate{{background:var(--surface-1);border:1px solid var(--border);border-left:3px solid var(--good);
border-radius:10px;padding:15px 17px}}
.gate.fail{{border-left-color:var(--critical)}}
.gate.unknown{{border-left-color:var(--warning)}}
.gh{{display:flex;align-items:center;gap:10px}}
.gn{{font-size:14.5px;font-weight:600}}
.gb{{margin-left:auto;font-size:10px;font-weight:700;letter-spacing:.08em;
border:1px solid;border-radius:20px;padding:2px 9px;white-space:nowrap}}
.gl{{font-size:13.5px;color:var(--text-secondary);margin-top:5px;font-variant-numeric:tabular-nums}}
.gd{{font-size:12.5px;color:var(--text-muted);margin-top:5px;line-height:1.55}}
table.t{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
.t td,.t th{{padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.05);font-size:14px;vertical-align:top}}
.t th{{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted);
font-weight:560;text-align:left;border-bottom:1px solid var(--border)}}
.t .n{{text-align:right;font-weight:600;width:64px}}
.t .d{{color:var(--text-secondary);white-space:nowrap;width:104px}}
.t .bar{{font-family:ui-monospace,Menlo,monospace;font-size:13px;letter-spacing:-.5px;white-space:nowrap}}
.t .s{{color:var(--text-muted);font-weight:400;font-size:12px}}
.t .src{{color:var(--text-muted);font-size:12.5px;width:38%}}
.s{{font-size:12.5px;color:var(--text-muted);line-height:1.5;font-weight:400}}
.ax{{display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);padding-top:5px}}
.sp{{font-family:ui-monospace,Menlo,monospace;font-size:15px;letter-spacing:-.5px;
line-height:1;margin-top:10px;overflow:hidden;color:var(--accent)}}
.callout{{background:var(--surface-2);border:1px solid var(--border);border-left:3px solid var(--warning);
border-radius:10px;padding:16px 19px;margin:18px 0}}
.callout .k{{color:var(--warning);margin-bottom:6px}}
.verdict{{background:var(--surface-2);border:1px solid var(--border);border-left:3px solid var(--accent);
border-radius:10px;padding:18px 21px;margin:18px 0;font-size:17px;line-height:1.6}}
.fn{{margin-top:44px;padding-top:20px;border-top:1px solid var(--border);
font-size:13px;line-height:1.65;color:var(--text-muted);max-width:74ch}}
ol.why{{max-width:72ch;padding-left:20px}}
ol.why li{{margin-bottom:14px}}
@media(max-width:560px){{.hero{{gap:20px}}h1{{font-size:1.6rem}}}}
</style>
<div class="w">
<div class="k">Single-ticker deep dive &middot; {STAMP}</div>
<h1>{SYM} &mdash; {NAMES[SYM]}</h1>
<div class="sub">Prices via Twelve Data &middot; options via Alpha Vantage &middot; market open at capture</div>

<div class="card hero">
  <div class="ring"><i><b>{score}</b><s>Gates</s></i></div>
  <div style="flex:1;min-width:240px">
    <div class="px">{price:,.2f}<span class="chg" style="color:{'var(--good)' if day>=0 else 'var(--critical)'}">{day:+.2f}%</span></div>
    <div class="sub" style="margin-top:6px">Session {L['dlo']:,.2f}&ndash;{L['dhi']:,.2f}
    &middot; <span style="color:var(--text-muted)">prev close {prev:,.2f}</span></div>
    <div class="verdict" style="margin-bottom:0">
      Trend is intact and orderly. The three failing gates are all about
      <b>options positioning and what this data cannot see</b> &mdash; not about price.
    </div>
  </div>
</div>

<div class="card">
<div class="k">Metrics</div>
<div class="mg">
<div class="m"><div class="l">Last</div><div class="v">{price:,.2f}</div><div class="s2">live, market open</div></div>
<div class="m"><div class="l">Day change</div><div class="v" style="color:{'var(--good)' if day>=0 else 'var(--critical)'}">{day:+.2f}%</div><div class="s2">vs {prev:,.2f}</div></div>
<div class="m"><div class="l">Put/call</div><div class="v" style="color:var(--warning)">{pcr:.2f}</div><div class="s2">full chain, 13:15 ET</div></div>
<div class="m"><div class="l">RSI (14)</div><div class="v">{L['rsi']:.1f}</div><div class="s2">30&ndash;70 is neutral</div></div>
<div class="m"><div class="l">vs 20-day</div><div class="v" style="color:{'var(--good)' if vs20>0 else 'var(--critical)'}">{vs20:+.2f}%</div><div class="s2">MA {ma20:,.2f}</div></div>
<div class="m"><div class="l">vs 50-day</div><div class="v" style="color:{'var(--good)' if vs50>0 else 'var(--critical)'}">{vs50:+.2f}%</div><div class="s2">MA {ma50:,.2f}</div></div>
<div class="m"><div class="l">Realized vol</div><div class="v">{rvol:.0f}%</div><div class="s2">20d annualized</div></div>
<div class="m"><div class="l">ATR (14)</div><div class="v">{L['atr']:.2f}</div><div class="s2">{100*L['atr']/price:.2f}% of price</div></div>
<div class="m"><div class="l">52-week high</div><div class="v">{L['w52hi']:,.2f}</div><div class="s2">{100*(price/L['w52hi']-1):+.2f}% away</div></div>
<div class="m"><div class="l">52-week low</div><div class="v">{L['w52lo']:,.2f}</div><div class="s2">{100*(price/L['w52lo']-1):+.1f}% above</div></div>
<div class="m"><div class="l">Avg volume</div><div class="v">{L['avgvol']/1e6:.1f}M</div><div class="s2">daily, trailing</div></div>
<div class="m"><div class="l">55-session peak</div><div class="v">{peak:,.2f}</div><div class="s2">{100*(price/peak-1):+.2f}% off</div></div>
</div>
</div>

<div class="card">
<div class="k">Close &middot; last {len(v)} sessions &nbsp;<span style="color:#c98500">gold = peak</span></div>
<div style="margin-top:12px">{chart}</div>
<div class="ax"><span>{clo:,.0f}</span><span>{chi:,.0f}</span></div>
</div>

<h2>Gates</h2>
<div class="gates">{gate_cards}</div>

<h2>What the put/call ratio actually is</h2>
<p>It is one division: <b>every put contract traded, divided by every call contract traded</b>,
across the whole {SYM} option chain. Alpha Vantage computes it on volume, for the full chain and
again for each expiry. Nothing more sophisticated is happening.</p>
<p>The conventional reading is that above 1.00 means more puts than calls, so traders are
defensive; below 0.60 means calls dominate, so traders are bullish. <b>For {SYM} that rule is
actively misleading</b>, and here is why.</p>

<div class="callout">
<div class="k">The threshold everyone quotes does not apply to SPY</div>
SPY is the market's default hedging instrument. Pension funds, RIAs and desks buy SPY puts to
protect portfolios they hold <i>somewhere else entirely</i>. That is permanent, price-insensitive
put demand with no directional opinion in it. It pushes SPY's baseline ratio structurally above
1.00 and keeps it there. Judging SPY against a generic "1.00 = bearish" line means calling it
bearish essentially always.
</div>

<h3>{SYM} measured against itself</h3>
<div class="card" style="margin-top:10px">
<table class="t"><tr><th>Date</th><th class="n">Ratio</th><th>Relative</th><th></th></tr>
{hist_rows}</table>
<div class="s" style="margin-top:12px">Every full-chain reading I have actually captured for {SYM}.
Today's <b style="color:var(--warning)">{pcr:.2f}</b> is the lowest of the five &mdash; against the
textbook line it still reads "bearish", but against {SYM}'s own behaviour it is the most
call-leaning print on file.</div>
</div>

<h3>Term structure &mdash; the same ratio, expiry by expiry</h3>
<div class="card" style="margin-top:10px">
<table class="t"><tr><th>Expiry</th><th class="n">Ratio</th><th>Relative (capped at 3.0)</th></tr>
{exp_rows}</table>
<div class="s" style="margin-top:12px">This week's four expiries average <b>{front_avg:.2f}</b> against
<b>{pcr:.2f}</b> for the full chain &mdash; near-dated flow is slightly more call-leaning than the
chain as a whole, so there is no crowded one-way bet into this week.
The far-dated rows (30 Sep, 2 Oct, 16 Oct, 20 Nov) run 4&ndash;6&times; and are mostly structural
portfolio hedging rather than a view; they inflate the full-chain number every single day.
<b>That is the clearest argument for reading the front of the curve separately from the whole chain.</b></div>
</div>

<h2>Will this push the price up or down?</h2>
<div class="verdict">
<b>On this data alone: I cannot tell you, and neither can anyone else.</b> The put/call ratio is a
coincident sentiment gauge, not a forecast. Below is exactly why, and exactly what would change
the answer.
</div>

<ol class="why">
<li><b>It cannot see whether the puts were bought or sold.</b> A ratio of 1.50 might be frightened
investors buying protection &mdash; bearish. Or it might be income desks writing puts to collect
premium &mdash; bullish, since a put seller wants the price to rise. Identical number, opposite
meaning. Separating them needs each trade tagged as executed at the bid or the ask. This feed has
no such tag. <b>This is the largest single blind spot.</b></li>

<li><b>It counts volume, not open interest.</b> Volume includes contracts opened and closed inside
the same session, and a single institutional roll can move the ratio without changing anyone's net
exposure by a dollar. Open interest &mdash; positions still held overnight &mdash; is the number
that describes real exposure, and it is not in this figure.</li>

<li><b>The thing that actually moves price is dealer hedging, and the ratio does not measure it.</b>
Market makers who sell you options hedge in the underlying. When they are net <i>short gamma</i>
they must sell as price falls and buy as it rises, amplifying the move. When they are net
<i>long gamma</i> they do the reverse and damp it. Which regime the market is in depends on open
interest by strike and the gamma at those strikes. That is the causal mechanism; the put/call ratio
is a shadow of it at best.</li>

<li><b>Five observations is not a distribution.</b> The one genuine, well-documented edge in this
indicator is contrarian and only appears at extremes &mdash; heavy hedging near a bottom,
complacency near a top. "Extreme" means the far tail of a ticker's own history. With n=5 I can tell
you today is the lowest I have seen; I cannot tell you whether that is the 40th percentile or the
2nd.</li>
</ol>

<h3>So what can be said today, honestly</h3>
<div class="verdict">
{SYM} is <b>{price:,.2f}</b>, up <b>{day:+.2f}%</b>, {abs(100*(price/L['w52hi']-1)):.1f}% below its
52-week high, with RSI at {L['rsi']:.0f} and realized vol at {rvol:.0f}% &mdash; a calm, intact uptrend.
Put/call at <b>{pcr:.2f}</b> is the lowest of my five captures, down from {base[-1]:.2f} on Monday.
<div style="margin-top:12px">The defensible statement is narrow: <b>hedges are being removed while price
sits near the highs.</b> In the contrarian frame that is mild complacency, which historically raises the
cost of a surprise rather than predicting one. It is not a sell signal, it is not a buy signal, and
anyone quoting this number as a directional call is overreading it.</div>
</div>

<h2>What we would need to answer it properly</h2>
<div class="card" style="margin-top:10px">
<table class="t"><tr><th>Data</th><th>Where it comes from</th></tr>{need_rows}</table>
</div>

<div class="callout">
<div class="k">The free path</div>
Item five &mdash; the year of history that turns this number into a percentile &mdash; costs nothing
but patience. <code>HISTORICAL_PUT_CALL_RATIO</code> is on the free tier at one call per date, and the
scheduled pipeline already runs twice every weekday. Logging the ratio on each run builds a real
distribution in roughly three months at zero extra cost. Everything else on that list requires a paid
options feed carrying open interest and greeks.
</div>

<div class="fn">
Price, session range, RSI and ATR: Twelve Data, real-time, captured {STAMP} with the market open
&mdash; the last price is a live quote, not a close, and will move. Put/call: Alpha Vantage
<code>REALTIME_PUT_CALL_RATIO</code>, full chain, 13:15 ET; history via
<code>HISTORICAL_PUT_CALL_RATIO</code>. Moving averages, realized volatility and the peak are computed
from the trailing {len(v)} daily closes shown in the chart. Realized volatility is the annualized
standard deviation of the last 20 daily returns and describes what has already happened, not what will.
<br><br>
Gate outcomes are mechanical rules applied to that data, not judgements about the security. A FAIL on
gates 8 and 9 describes a limitation in the data available, not a defect in {SYM}.
<br><br>
Positioning and trend context only &mdash; not investment advice, and nothing here is a recommendation
to buy, hold or sell.
</div>
</div>"""

open('/tmp/spy/deep_%s.html'%SYM,'w').write(html)
print("page: %s bytes -> deep_%s.html"%(len(html),SYM))
