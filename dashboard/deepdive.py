"""Single-ticker deep dive: gate score + full stats + a put/call explainer that is
honest about what the ratio can and cannot tell you about direction.

Usage: python3 deepdive.py SPY
Reusable for any symbol in d10.py; SPY is the reference implementation.
"""
import statistics as st, sys, json, re
exec(open('/tmp/spy/d10.py').read())

SYM = (sys.argv[1] if len(sys.argv) > 1 else "SPY").upper()
STAMP = "Tuesday 25 August 2026, 2:21pm ET"

# ── live overrides captured after the ten-ticker run ────────────────────────
LIVE = {
    "SPY": dict(price=765.645, prev=763.47, dlo=763.09, dhi=766.75,
                rsi=53.97, atr=6.48, w52lo=629.28, w52hi=779.37,
                avgvol=33604236),
}
# SPY full-chain put/call, 13:15 ET, with the by-expiry breakdown.
PCR_EXPIRY = {"SPY": [("2026-08-25",0.98),("2026-08-26",1.05),("2026-08-27",0.87),
                      ("2026-08-28",0.99),("2026-08-31",2.45),("2026-09-01",1.37),
                      ("2026-09-02",1.03),("2026-09-03",0.71),("2026-09-04",1.42),
                      ("2026-09-08",1.43),("2026-09-11",0.82),("2026-09-18",2.50),
                      ("2026-09-25",0.74),("2026-09-30",4.69),("2026-10-02",4.02),
                      ("2026-10-16",4.54),("2026-10-30",0.96),("2026-11-20",5.92)]}
# Every SPY full-chain reading I have actually captured. n is small and the page says so.
PCR_HISTORY = {"SPY": [("2026-07-29",1.37),("2026-08-10",1.11),("2026-08-17",1.33),
                       ("2026-08-24",1.28),("2026-08-25",1.05)]}

L = LIVE[SYM]
v = list(reversed(SERIES[SYM]))
v[-1] = L["price"]                       # refresh the live bar
rets = [100*(v[i]/v[i-1]-1) for i in range(1, len(v))]
ma20, ma50 = st.mean(v[-20:]), st.mean(v[-50:])
price, prev = L["price"], L["prev"]
day = 100*(price/prev-1)
vs20, vs50 = 100*(price/ma20-1), 100*(price/ma50-1)
rvol = st.stdev(rets[-20:])*(252**0.5)
peak, trough = max(v), min(v)
hist = [x for _, x in PCR_HISTORY[SYM]]
pcr = hist[-1]
base = hist[:-1]
pcr_lo, pcr_hi = min(hist), max(hist)
pcr_med = st.median(base)
front = [x for d, x in PCR_EXPIRY[SYM][:4]]        # this week's expiries
front_avg = st.mean(front)

# ── GATES ───────────────────────────────────────────────────────────────────
# Positioning gates, not fundamentals. Each one states what it can see and,
# where relevant, what it cannot. UNKNOWN is a first-class outcome: a gate we
# cannot evaluate is never quietly passed.
def g(name, status, line, detail):
    return dict(name=name, status=status, line=line, detail=detail)

GATES = [
 g("Gate 1: Above 20-day", "PASS" if vs20 > 0 else "FAIL",
   "%+.2f%% vs its 20-day average." % vs20,
   "Short-term trend. Above = buyers in control on a three-week view."),
 g("Gate 2: Above 50-day", "PASS" if vs50 > 0 else "FAIL",
   "%+.2f%% vs its 50-day average." % vs50,
   "Intermediate trend. Both gates green is the definition of an intact uptrend."),
 g("Gate 3: RSI not extreme", "PASS" if 30 < L["rsi"] < 70 else "FAIL",
   "RSI(14) is %.1f." % L["rsi"],
   "Outside 30-70 the move is stretched and mean-reversion risk rises. 54 is dead centre."),
 g("Gate 4: Volatility contained", "PASS" if rvol < 25 else "FAIL",
   "Realized vol %.0f%% annualized; ATR %.2f is %.2f%% of price." % (rvol, L["atr"], 100*L["atr"]/price),
   "SPY's own long-run realized vol sits mid-teens. 13%% is calm, not stressed."),
 g("Gate 5: Near the highs", "PASS" if 100*(price/L["w52hi"]-1) > -10 else "FAIL",
   "%.2f%% below the 52-week high, %+.1f%% above the low." % (100*(price/L["w52hi"]-1), 100*(price/L["w52lo"]-1)),
   "Within 10%% of the high keeps the structural bid intact."),
 g("Gate 6: Put/call inside its own band",
   "FAIL" if pcr <= min(base) else "PASS",
   "%.2f, against a captured range of %.2f-%.2f." % (pcr, pcr_lo, pcr_hi),
   "This is the lowest reading in the sample — hedges are coming off. "
   "Read as mild complacency, NOT as a sell signal. See the explainer below."),
 g("Gate 7: Front-week not one-sided",
   "PASS" if 0.7 < front_avg < 1.4 else "FAIL",
   "This week's four expiries average %.2f vs %.2f for the full chain." % (front_avg, pcr),
   "Near-dated flow is where short-term direction gets expressed. "
   "Near parity means no crowded one-way bet into this week."),
 g("Gate 8: Baseline is statistically usable", "FAIL",
   "Only %d captured observations. A percentile needs ~250." % len(hist),
   "This is the single biggest gap. Without a real distribution, "
   "'high' and 'low' are guesses. Fix costs one API call per day."),
 g("Gate 9: Directional inference supported", "FAIL",
   "No open interest, no greeks, no trade side.",
   "The put/call ratio alone cannot tell you which way price goes. "
   "The mechanism that actually moves price is dealer hedging, and computing it "
   "needs data this feed does not carry. Full requirement list below."),
]
passed = sum(1 for x in GATES if x["status"] == "PASS")
score = "%d/%d" % (passed, len(GATES))

print("%s  %.2f  %+.2f%%   gates %s" % (SYM, price, day, score))
for x in GATES:
    print("  %-42s %s  %s" % (x["name"], x["status"], x["line"]))

json.dump(dict(symbol=SYM, price=price, day=day, score=score,
               vs20=vs20, vs50=vs50, rvol=rvol, rsi=L["rsi"], atr=L["atr"],
               pcr=pcr, pcr_range=[pcr_lo, pcr_hi], front_avg=front_avg,
               gates=[{k: x[k] for k in ("name","status","line")} for x in GATES]),
          open('/tmp/spy/deep_%s.json' % SYM, 'w'), indent=1)
