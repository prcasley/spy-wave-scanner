"""Single-ticker deep-dive email. iOS Gmail safe: bgcolor attributes only,
no CSS background on any element, never an empty cell."""
import re
exec(open('/tmp/spy/deeppage.py').read().split('html=f"""<title>')[0])

W="#ffffff"; S="#c9c9c4"; MU_="#8a8a84"
GOOD="#3ecf6d"; BAD="#ff6b6b"; WARN="#e0a44a"
CARD='bgcolor="#121212" style="border-radius:12px;padding:15px 16px"'
GAP=f'<tr><td height=12 {T}>{NB}</td></tr>'

def head(t):
    return (f'<div style="font-size:10px;letter-spacing:.07em;text-transform:uppercase;'
            f'color:#8a8a84;font-weight:700;padding-bottom:8px">{t}</div>')

def m3(l,v,c,sub=None):
    s2=f'<div style="font-size:9.5px;color:#8a8a84;line-height:1.3">{sub}</div>' if sub else ''
    return (f'<td width="33%" valign=top bgcolor="#121212" style="padding:0 5px 11px 0">'
            f'<div style="font-size:9px;letter-spacing:.06em;text-transform:uppercase;'
            f'color:#8a8a84;font-weight:700">{l}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{c};line-height:1.3">{v}</div>{s2}</td>')

EC={"PASS":GOOD,"FAIL":BAD,"UNKNOWN":WARN}
gate_rows="".join(
  f'<tr><td bgcolor="#121212" valign=top style="padding:8px 0;border-bottom:1px solid #1e1e1e">'
  f'<div style="font-size:13px;font-weight:700;color:{W}">{x["name"]}'
  f' <span style="font-size:9.5px;font-weight:800;color:{EC[x["status"]]};'
  f'border:1px solid {EC[x["status"]]};border-radius:20px;padding:1px 6px">{x["status"]}</span></div>'
  f'<div style="font-size:12px;color:#c9c9c4;padding-top:3px">{x["line"]}</div></td></tr>'
  for x in GATES)

hist_rows_e="".join(
  f'<tr><td bgcolor="#121212" style="font-size:12.5px;color:#c9c9c4;padding:4px 8px 4px 0;'
  f'white-space:nowrap">{d}</td>'
  f'<td bgcolor="#121212" align=right style="font-size:13px;font-weight:700;'
  f'color:{WARN if i==len(hist)-1 else W};padding:4px 8px 4px 0">{x:.2f}</td>'
  f'<td bgcolor="#121212" style="font-family:Menlo,Courier,monospace;font-size:12px;'
  f'color:{WARN if i==len(hist)-1 else ACC};white-space:nowrap">{pcr_bar(x)}</td></tr>'
  for i,(d,x) in enumerate(PCR_HISTORY[SYM]))

need_rows_e="".join(
  f'<tr><td bgcolor="#121212" valign=top style="padding:7px 0;border-bottom:1px solid #1e1e1e">'
  f'<div style="font-size:12.5px;font-weight:700;color:{W}">{n[0]}</div>'
  f'<div style="font-size:11.5px;color:#8a8a84;line-height:1.5;padding-top:2px">{n[2]}</div></td></tr>'
  for n in NEED)

chart_e,clo_e,chi_e=cols(v,ACC,h=90,n=18)

html=f"""<table width="100%" cellpadding=0 cellspacing=0 border=0 bgcolor="#080808"><tr>
<td align=center bgcolor="#080808" style="padding:18px 10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding=0 cellspacing=0 border=0 style="max-width:430px">

<tr><td bgcolor="#080808" style="padding:0 4px 13px">
<div style="font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:#8a8a84;font-weight:700">Single-ticker deep dive &middot; TEST</div>
<div style="font-size:23px;font-weight:800;color:{W};padding-top:5px;line-height:1.3">{SYM} &mdash; {score} gates</div>
<div style="font-size:12.5px;color:#8a8a84;padding-top:3px">{STAMP}</div></td></tr>

<tr><td {CARD}>
<table width="100%" cellspacing=0 cellpadding=0 border=0>
<tr><td bgcolor="#121212">
<span style="font-size:34px;font-weight:800;color:{W}">{price:,.2f}</span>
<span style="font-size:15px;font-weight:700;color:{GOOD if day>=0 else BAD}">{NB}{day:+.2f}%</span></td></tr>
<tr><td bgcolor="#121212" style="font-size:11.5px;color:#c9c9c4;padding-top:3px">
Session {L['dlo']:,.2f}&ndash;{L['dhi']:,.2f} &middot; <span style="color:#8a8a84">prev close {prev:,.2f}</span></td></tr>
<tr><td bgcolor="#121212" style="font-size:13px;color:{W};line-height:1.55;padding-top:10px">
Trend is intact and orderly. <b>All three failing gates are about options positioning
and what this data cannot see</b> &mdash; not about price.</td></tr>
</table></td></tr>
{GAP}

<tr><td {CARD}>{head("Metrics")}
<table width="100%" cellspacing=0 cellpadding=0 border=0>
<tr>{m3("Put/call","%.2f"%pcr,WARN,"full chain")}{m3("RSI (14)","%.1f"%L['rsi'],W,"30-70 neutral")}{m3("Realized vol","%.0f%%"%rvol,W,"20d annualized")}</tr>
<tr>{m3("vs 20-day","%+.2f%%"%vs20,GOOD if vs20>0 else BAD,"MA %s"%format(ma20,",.2f"))}{m3("vs 50-day","%+.2f%%"%vs50,GOOD if vs50>0 else BAD,"MA %s"%format(ma50,",.2f"))}{m3("ATR (14)","%.2f"%L['atr'],W,"%.2f%% of price"%(100*L['atr']/price))}</tr>
<tr>{m3("52w high","%s"%format(L['w52hi'],",.0f"),W,"%+.2f%% away"%(100*(price/L['w52hi']-1)))}{m3("52w low","%s"%format(L['w52lo'],",.0f"),W,"%+.1f%% above"%(100*(price/L['w52lo']-1)))}{m3("Avg volume","%.1fM"%(L['avgvol']/1e6),W,"daily")}</tr>
</table></td></tr>
{GAP}

<tr><td {CARD}>{head("Close &middot; last %d sessions &nbsp;<span style='color:#c98500'>gold = peak</span>"%len(v))}
{chart_e}
<table width="100%" cellspacing=0 cellpadding=0 border=0><tr>
<td bgcolor="#121212" style="font-size:10px;color:#8a8a84;padding-top:4px">{clo_e:,.0f}</td>
<td bgcolor="#121212" align=right style="font-size:10px;color:#8a8a84;padding-top:4px">{chi_e:,.0f}</td></tr></table>
</td></tr>
{GAP}

<tr><td {CARD}>{head("Gates &nbsp;&middot;&nbsp; %s"%score)}
<table width="100%" cellspacing=0 cellpadding=0 border=0>{gate_rows}</table></td></tr>
{GAP}

<tr><td {CARD}>{head("What put/call means")}
<div style="font-size:13.5px;line-height:1.6;color:{W}">
It is one division: <b>every put contract traded divided by every call contract traded</b>,
across the whole chain. Above 1.00 = more puts. Below 0.60 = calls dominate.
<div style="padding-top:11px"><b style="color:{WARN}">That textbook line does not apply to SPY.</b>
SPY is the market's default hedging instrument &mdash; funds buy SPY puts to protect portfolios they
hold somewhere else entirely. That is permanent put demand with no directional opinion in it, and it
holds SPY's baseline structurally above 1.00. Judge SPY by the generic rule and it reads bearish
essentially always.</div>
</div></td></tr>
{GAP}

<tr><td {CARD}>{head("SPY measured against itself")}
<table width="100%" cellspacing=0 cellpadding=0 border=0>{hist_rows_e}</table>
<div style="font-size:11.5px;color:#8a8a84;line-height:1.5;padding-top:10px">
Every full-chain reading captured so far. Today's <b style="color:{WARN}">{pcr:.2f}</b> is the lowest
of the five &mdash; by the textbook it still reads bearish; against SPY's own behaviour it is the
most call-leaning print on file.</div></td></tr>
{GAP}

<tr><td bgcolor="#2a1a0a" style="border-radius:12px;padding:15px 16px">
<div style="font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:#e0a44a;font-weight:700;padding-bottom:8px">Will it push price up or down?</div>
<div style="font-size:13.5px;line-height:1.6;color:#e8dcc8">
<b style="color:{W}">On this data alone I cannot tell you, and neither can anyone else.</b> Four reasons:
<div style="padding-top:10px"><b style="color:{W}">1. It cannot see buying from selling.</b> A ratio of 1.50 could be
frightened investors buying protection (bearish) or income desks writing puts (bullish &mdash; a put
seller wants price to rise). Same number, opposite meaning. Telling them apart needs each trade tagged
at bid or ask. This feed has no such tag. <b style="color:{W}">Biggest blind spot.</b></div>
<div style="padding-top:10px"><b style="color:{W}">2. It is volume, not open interest.</b> Volume counts contracts
opened and closed the same session; one institutional roll moves it without changing net exposure at all.</div>
<div style="padding-top:10px"><b style="color:{W}">3. Dealer hedging is what actually moves price.</b> Market makers
short gamma must sell into falls and buy into rallies, amplifying moves; long gamma they damp them.
That depends on open interest by strike and gamma at those strikes &mdash; neither is in this number.</div>
<div style="padding-top:10px"><b style="color:{W}">4. Five observations is not a distribution.</b> The one real edge here
is contrarian and only shows at extremes of a ticker's <i>own</i> history. With n=5 I can say today is the
lowest I have seen; I cannot say whether that is the 40th percentile or the 2nd.</div>
</div></td></tr>
{GAP}

<tr><td {CARD}>{head("What can honestly be said today")}
<div style="font-size:13.5px;line-height:1.6;color:{W}">
{SYM} at <b>{price:,.2f}</b>, {abs(100*(price/L['w52hi']-1)):.1f}% under its 52-week high, RSI {L['rsi']:.0f},
realized vol {rvol:.0f}% &mdash; calm, intact uptrend. Put/call <b>{pcr:.2f}</b>, down from {base[-1]:.2f} Monday.
<div style="padding-top:11px">The defensible statement is narrow: <b style="color:{WARN}">hedges are coming off
while price sits near the highs.</b> In the contrarian frame that is mild complacency, which raises the cost
of a surprise rather than predicting one. Not a buy signal. Not a sell signal.</div>
</div></td></tr>
{GAP}

<tr><td {CARD}>{head("What we would need to answer it properly")}
<table width="100%" cellspacing=0 cellpadding=0 border=0>{need_rows_e}</table>
<div style="font-size:12px;color:#c9c9c4;line-height:1.55;padding-top:11px">
<b style="color:{GOOD}">The free one:</b> the year of history that turns 1.05 into a percentile costs nothing
but time. <b>HISTORICAL_PUT_CALL_RATIO</b> is free at one call per date, and the pipeline already runs twice
a weekday &mdash; logging each run builds a real distribution in about three months. Everything else on that
list needs a paid options feed with open interest and greeks.</div></td></tr>
{GAP}

<tr><td bgcolor="#080808" style="padding:8px 4px 0;font-size:11.5px;line-height:1.65;color:#8a8a84">
Price, RSI and ATR: Twelve Data, real-time, captured with the market open &mdash; the last price is a live
quote, not a close. Put/call: Alpha Vantage full chain, 13:15 ET. Gate outcomes are mechanical rules applied
to that data; a FAIL on gates 8 and 9 describes a limit in the data available, not a defect in {SYM}.<br><br>
Not investment advice, and nothing here is a recommendation to buy, hold or sell.</td></tr>
</table></td></tr></table>"""

txt=f"""{SYM} DEEP DIVE (TEST) - {STAMP}

{price:,.2f}  {day:+.2f}%   GATES {score}
Session {L['dlo']:,.2f}-{L['dhi']:,.2f}, prev close {prev:,.2f}

METRICS
  Put/call      {pcr:.2f}   full chain, 13:15 ET
  RSI(14)       {L['rsi']:.1f}
  Realized vol  {rvol:.0f}%   20d annualized
  ATR(14)       {L['atr']:.2f}   {100*L['atr']/price:.2f}% of price
  vs 20-day     {vs20:+.2f}%   MA {ma20:,.2f}
  vs 50-day     {vs50:+.2f}%   MA {ma50:,.2f}
  52w high      {L['w52hi']:,.2f}   {100*(price/L['w52hi']-1):+.2f}% away
  52w low       {L['w52lo']:,.2f}   {100*(price/L['w52lo']-1):+.1f}% above

GATES
""" + "\n".join("  [%-4s] %s\n         %s"%(x["status"],x["name"],x["line"]) for x in GATES) + f"""

WHAT PUT/CALL MEANS
Put contracts traded divided by call contracts traded, whole chain. Above 1.00 = more
puts, below 0.60 = calls dominate. That textbook line does NOT apply to SPY: SPY is the
market's default hedging instrument, so there is permanent put demand with no directional
view in it, holding the baseline structurally above 1.00.

SPY AGAINST ITSELF
""" + "\n".join("  %s  %.2f%s"%(d,x," <- today" if i==len(hist)-1 else "")
                for i,(d,x) in enumerate(PCR_HISTORY[SYM])) + f"""

WILL IT PUSH PRICE UP OR DOWN? On this data alone, I cannot tell you.
  1. It cannot see buying vs selling. 1.50 could be hedgers buying puts (bearish) or
     desks writing puts (bullish). Same number, opposite meaning. Needs bid/ask tagging.
  2. It is volume, not open interest. One roll moves it without changing net exposure.
  3. Dealer hedging is the real mechanism - needs open interest by strike plus gamma.
  4. Five observations is not a distribution.

HONEST READ: hedges are coming off while price sits near the highs. Mild complacency in
the contrarian frame. Not a buy signal, not a sell signal.

WHAT WE WOULD NEED
""" + "\n".join("  - %s\n      %s"%(n[0],n[2]) for n in NEED) + """

The free one: HISTORICAL_PUT_CALL_RATIO is free at one call per date. The pipeline runs
twice a weekday - logging each run builds a real percentile in about three months.

Not investment advice, and nothing here is a recommendation to buy, hold or sell.
"""

open('/tmp/spy/deepmail.html','w').write(html)
open('/tmp/spy/deepmail.txt','w').write(txt)
css=len(re.findall(r'style="[^"]*background:',html))
empty=len(re.findall(r'<td[^>]*>\s*</td>',html))
print("html %d bytes   text %d bytes"%(len(html),len(txt)))
print("  bgcolor= attributes      :",len(re.findall(r'bgcolor=',html)))
print("  css background on element:",css," (must be 0)")
print("  empty <td> with no nbsp  :",empty," (must be 0)")
assert css==0 and empty==0 and len(html)<90000
print("  guardrails PASS")
