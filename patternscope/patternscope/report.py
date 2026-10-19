"""Self-contained HTML report (dark matte, white text, works on a phone)."""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd


def _records(df: pd.DataFrame, cols=None):
    if df is None or not len(df):
        return []
    d = df if cols is None else df[[c for c in cols if c in df.columns]]
    d = d.replace([np.inf, -np.inf], np.nan).astype(object).where(d.notna(), None)
    out = d.to_dict("records")
    for r in out:
        for k, v in r.items():
            if isinstance(v, (pd.Timestamp, datetime)):
                r[k] = str(v)[:16]
            elif isinstance(v, (np.floating,)):
                r[k] = float(v)
            elif isinstance(v, (np.integer,)):
                r[k] = int(v)
    return out


def build(res: dict, tf_cfg: dict, demo: bool = False, verdicts=None) -> str:
    return TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload(res, tf_cfg, demo, verdicts), default=str))


def payload(res: dict, tf_cfg: dict, demo: bool = False, verdicts=None) -> dict:
    stats = res["stats"]
    fresh = res["fresh"]
    payload = dict(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        demo=demo,
        horizons={tf: c["horizons"] for tf, c in tf_cfg.items()},
        stats=_records(stats),
        fresh=_records(fresh, ["ticker", "tf", "pattern", "category", "direction", "signal_time", "signal_close",
                               "entry", "stop", "target", "formation_bars", "outcome"]),
        profiles=json.loads(json.dumps(res["profiles"], default=float)),
        coverage=res["coverage"],
        charts=res.get("charts", []),
        snapshots=json.loads(json.dumps(res.get("snapshots", []), default=float)),
        verdicts=_records(verdicts, ["tf", "pattern", "direction", "verdict", "watch_grade", "watch_R_net", "uni_n",
                                     "uni_win", "uni_R_net", "is_R_net", "oos_n", "oos_R_net", "uni_p", "uni_sig"])
        if verdicts is not None else [],
        n_trades=int(len(res["trades"])),
        n_patterns=int(res["trades"].pattern.nunique()) if len(res["trades"]) else 0,
    )
    return payload


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PatternScope</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0a0b;--panel:#121214;--panel2:#18181b;--line:#26262b;--text:#ffffff;--sub:#c9c9cf;--accent:#8b5cf6;
--long:#16a34a;--short:#dc2626;--A:#16a34a;--B:#2563eb;--C:#a16207;--F:#7f1d1d;--low:#3f3f46}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 Inter,system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:26px;margin:0;font-weight:700;letter-spacing:-.01em}h1 span{color:var(--accent)}
h2{font-size:18px;margin:34px 0 4px;font-weight:600}.sub{color:var(--sub);font-size:13.5px}
.banner{background:#3b0764;border:1px solid var(--accent);border-radius:10px;padding:10px 14px;margin:14px 0;font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:22px;font-family:'JetBrains Mono',monospace}.kpi span{color:var(--sub);font-size:12.5px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
.card .top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.card .name{font-weight:600;font-size:16px}.mono{font-family:'JetBrains Mono',monospace}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;color:#fff}
.L{background:var(--long)}.S{background:var(--short)}
.g{display:inline-block;min-width:34px;text-align:center;padding:2px 6px;border-radius:6px;font-weight:700;font-size:12px;color:#fff}
.gA{background:var(--A)}.gB{background:var(--B)}.gC{background:var(--C)}.gF{background:var(--F)}.glow-n{background:var(--low)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;margin-top:10px;font-size:13.5px}
.grid2 span{color:var(--sub)}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
select,input{background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font:inherit;font-size:14px}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:900px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{position:sticky;top:0;background:var(--panel2);cursor:pointer;font-weight:600;user-select:none}
th:first-child,td:first-child{text-align:left}td:first-child{font-weight:500}
tr:hover td{background:#1b1b1f}.pos{color:#86efac}.neg{color:#fca5a5}
.meter{position:relative;height:10px;background:var(--panel2);border-radius:999px;margin:10px 0 4px;border:1px solid var(--line)}
.meter i{position:absolute;top:-1px;bottom:-1px;background:#3f3f46;border-radius:999px}
.meter u{position:absolute;top:-5px;width:4px;height:18px;background:#fff;border-radius:2px;text-decoration:none}
.empty{color:var(--sub);padding:16px;background:var(--panel);border:1px dashed var(--line);border-radius:12px}
details{margin-top:30px;color:var(--sub)}summary{cursor:pointer;color:var(--text);font-weight:600}
@media(max-width:560px){h1{font-size:22px}.grid2{font-size:13px}}
</style></head><body><div class="wrap">
<h1>Pattern<span>Scope</span></h1>
<div class="sub" id="meta"></div>
<a href="guide.html" style="display:inline-block;margin-top:10px;background:#8b5cf6;color:#fff;padding:8px 14px;border-radius:999px;font-weight:600;text-decoration:none">📘 Pattern Guide — what every pattern means</a>
<a href="https://github.com/prcasley/spy-wave-scanner/releases/download/patternscope-latest/PatternScope.xlsx" style="display:inline-block;margin:10px 0 0 6px;background:#16a34a;color:#fff;padding:8px 14px;border-radius:999px;font-weight:600;text-decoration:none">⬇ Excel — all the data</a>
<div id="demo"></div>
<div class="kpis" id="kpis"></div>

<h2>Live now</h2>
<div class="sub">Patterns that confirmed on the latest bars, with how that exact pattern has played out on that ticker &amp; timeframe (and across the whole watchlist).</div>
<div class="cards" id="fresh"></div>

<h2>Watchlist compare</h2>
<div class="sub">Daily chart state. Tap a header to sort.</div>
<div class="tbl"><table id="cmp" style="min-width:820px"><thead></thead><tbody></tbody></table></div>
<div id="divs"></div>

<h2>Charts with pattern overlay</h2>
<div class="sub">Candles with the swing structure (thin line) and every pattern that confirmed in view. Tap a pattern in the list to draw its stop &amp; target.</div>
<div class="controls"><select id="cTk"></select><select id="cTf"></select>
<select id="cCat"><option value="chart,setup">Chart + setups</option><option value="chart">Chart patterns</option><option value="setup">Setups</option><option value="candle">Candles</option><option value="chart,setup,candle">Everything</option></select>
<select id="cGr"><option value="AB">Grade A/B only</option><option value="ABC">A/B/C</option><option value="">All grades</option></select></div>
<div id="chart" style="height:440px;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--panel)"></div>
<div class="cards" id="cList" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))"></div>

<div id="valwrap"></div>

<h2>Pattern leaderboard</h2>
<div class="sub">Win = target hit before stop. Expectancy in R (1R = the planned risk). Edge = how much more often price moved the pattern's way than from a random bar.</div>
<div class="controls">
<select id="fTk"></select><select id="fTf"></select>
<select id="fCat"><option value="">All types</option><option>chart</option><option>candle</option><option>setup</option></select>
<select id="fDir"><option value="">Long &amp; short</option><option>LONG</option><option>SHORT</option></select>
<select id="fN"><option value="20">n ≥ 20</option><option value="10">n ≥ 10</option><option value="50">n ≥ 50</option><option value="0">any n</option></select>
<input id="fQ" placeholder="search pattern" size="14">
</div>
<div class="tbl"><table id="lb"><thead></thead><tbody></tbody></table></div>

<h2>Pullback map</h2>
<div class="sub">From the swing structure: how far pullbacks usually retrace the prior up-leg, how long they last, and where price sits right now. White tick = now; gray band = typical (25th–75th pct) range.</div>
<div class="cards" id="pb"></div>

<details><summary>How to read this</summary>
<p>Entries are next-bar open; if stop and target are touched in the same bar it counts as a stop. No hit inside the hold window = timeout at the close. Hourly day-trade setups (ORB, VWAP, intraday gaps) are closed at the end of the session. <b>Grade A</b> needs n ≥ 30, expectancy ≥ 0.25R, edge ≥ 5pp and positive results in both halves of history. <b>low-n</b> means fewer than 20 occurrences — treat as anecdote. Past behaviour is a tendency, not a promise.</p>
</details>
<div class="sub" id="cov" style="margin-top:14px"></div>
</div>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<script>
const D=/*__DATA__*/null;
const $=s=>document.querySelector(s);
const fmt=(v,d=2)=>v==null||Number.isNaN(v)?'–':(+v).toFixed(d);
const sgn=v=>v==null?'':(v>0?'pos':(v<0?'neg':''));
const gl=n=>`guide.html#${n.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}`;
const mid=tf=>{const h=D.horizons[tf]||[];return h[Math.floor(h.length/2)]};
$('#meta').textContent=`Generated ${D.generated} · ${D.n_trades.toLocaleString()} historical detections · ${D.n_patterns} pattern types`;
if(D.demo)$('#demo').innerHTML='<div class="banner">DEMO DATA — synthetic prices used to test the engine. These numbers say nothing about real markets.</div>';
const tks=[...new Set(D.stats.map(r=>r.ticker))];const tfs=[...new Set(D.stats.map(r=>r.tf))];
$('#fTk').innerHTML=tks.map(t=>`<option ${t==='ALL'?'selected':''}>${t}</option>`).join('');
$('#fTf').innerHTML=tfs.map(t=>`<option>${t}</option>`).join('');
const S=D.stats;const key=(t,f,p)=>t+'|'+f+'|'+p;const SM={};S.forEach(r=>SM[key(r.ticker,r.tf,r.pattern)]=r);
const good=S.filter(r=>r.ticker==='ALL'&&(r.grade==='A'||r.grade==='B'));
$('#kpis').innerHTML=[
 [D.fresh.length,'live signals'],[good.length,'grade A/B patterns (pooled)'],
 [tks.filter(t=>t!=='ALL').length,'tickers'],[tfs.join(' · '),'timeframes']]
 .map(([b,s])=>`<div class="kpi"><b>${b}</b><span>${s}</span></div>`).join('');
function gradeBadge(g){return `<span class="g g${g}">${g||'–'}</span>`}
function statLine(r,label){if(!r)return `<div><span>${label}</span></div><div>no history</div>`;const m=mid(r.tf);
 return `<span>${label}</span><div>${gradeBadge(r.grade)} n=${r.n} · win ${fmt(r.target_pct,0)}% · <span class="${sgn(r.expectancy_R)}">${fmt(r.expectancy_R)}R</span> · edge ${fmt(r['edge'+m+'_pp'],1)}pp</div>`}
const order={A:0,B:1,C:2,'low-n':3,F:4};
const fr=D.fresh.map(f=>({...f,own:SM[key(f.ticker,f.tf,f.pattern)],all:SM[key('ALL',f.tf,f.pattern)]}))
 .sort((a,b)=>(order[(a.all||{}).grade]??5)-(order[(b.all||{}).grade]??5)||((b.all||{}).expectancy_R||-9)-((a.all||{}).expectancy_R||-9));
$('#fresh').innerHTML=fr.length?fr.map(f=>{const L=f.direction===1;const a=f.all||{};return `<div class="card">
 <div class="top"><div class="name">${f.ticker} · <a href="${gl(f.pattern)}" style="color:#fff">${f.pattern}</a></div><span class="badge ${L?'L':'S'}">${L?'LONG':'SHORT'}</span></div>
 <div class="sub">${f.tf} · confirmed ${f.signal_time} · ${f.outcome==='pending'?'entry next open':'in progress: '+f.outcome}</div>
 <div class="grid2 mono"><span>close</span><div>${fmt(f.signal_close)}</div><span>stop</span><div>${fmt(f.stop)}</div><span>target</span><div>${fmt(f.target)}</div>
 <span>usually takes</span><div>${a.bars_to_target_med!=null?fmt(a.bars_to_target_med,0)+' bars to target':'–'}</div></div>
 <div class="grid2">${statLine(f.own,'this ticker')}${statLine(f.all,'watchlist')}</div></div>`}).join(''):'<div class="empty">Nothing confirmed on the latest bars.</div>';
const cols=[['pattern','Pattern'],['direction','Dir'],['grade','Grade'],['n','n'],['per_1000_bars','/1k bars'],['target_pct','Win %'],['stop_pct','Stop %'],
 ['timeout_pct','Timeout %'],['expectancy_R','Exp R'],['profit_factor','PF'],['EDGE','Edge pp'],['HIT','Dir hit %'],['formation_bars_med','Forms in'],
 ['bars_to_target_med','Bars→tgt'],['mae_R_med','Heat R'],['exp_R_first_half','1st half R'],['exp_R_second_half','2nd half R']];
let sortK='expectancy_R',sortD=-1;
function val(r,k){const m=mid(r.tf);if(k==='EDGE')return r['edge'+m+'_pp'];if(k==='HIT')return r['hit'+m+'_pct'];return r[k]}
function renderLB(){const tk=$('#fTk').value,tf=$('#fTf').value,cat=$('#fCat').value,dir=$('#fDir').value,nmin=+$('#fN').value,q=$('#fQ').value.toLowerCase();
 const m=mid(tf);$('#lb thead').innerHTML='<tr>'+cols.map(([k,l])=>`<th data-k="${k}">${k==='EDGE'?`Edge ${m}b`:k==='HIT'?`Hit ${m}b %`:l}${sortK===k?(sortD<0?' ↓':' ↑'):''}</th>`).join('')+'</tr>';
 let rows=S.filter(r=>r.ticker===tk&&r.tf===tf&&(!cat||r.category===cat)&&(!dir||r.direction===dir)&&r.n>=nmin&&r.pattern.toLowerCase().includes(q));
 rows.sort((a,b)=>{let x=val(a,sortK),y=val(b,sortK);if(sortK==='grade'){x=order[x];y=order[y]}if(x==null)return 1;if(y==null)return -1;return(typeof x==='string'?x.localeCompare(y):x-y)*sortD});
 $('#lb tbody').innerHTML=rows.length?rows.map(r=>'<tr>'+cols.map(([k])=>{const v=val(r,k);
  if(k==='pattern')return`<td><a href="${gl(v)}" style="color:#fff">${v}</a></td>`;if(k==='grade')return`<td>${gradeBadge(v)}</td>`;
  if(k==='direction')return`<td><span class="badge ${v==='LONG'?'L':'S'}">${v}</span></td>`;
  const dec=['n','formation_bars_med','bars_to_target_med'].includes(k)?0:(k.endsWith('pct')||k==='EDGE'||k==='HIT'?1:2);
  const cl=['expectancy_R','EDGE','exp_R_first_half','exp_R_second_half'].includes(k)?sgn(v):'';
  return`<td class="mono ${cl}">${fmt(v,dec)}</td>`}).join('')+'</tr>').join(''):`<tr><td colspan="${cols.length}" style="text-align:left;color:var(--sub)">No patterns match these filters.</td></tr>`;
 document.querySelectorAll('#lb th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortK===k)sortD*=-1;else{sortK=k;sortD=-1}renderLB()})}
['#fTk','#fTf','#fCat','#fDir','#fN'].forEach(s=>$(s).onchange=renderLB);$('#fQ').oninput=renderLB;renderLB();
$('#pb').innerHTML=D.profiles.map(p=>{const pd=p.pullback_depth||{},pb=p.pullback_bars||{},bd=p.bounce_depth||{},n=p.now||{};
 const isPull=(n.state||'').startsWith('pull');const dist=isPull?pd:bd;const cap=Math.max(1.2,(dist[90]||1)*1.1,(n.retraced||0)*1.05);
 const band=dist[25]!=null?`<i style="left:${100*dist[25]/cap}%;width:${100*(dist[75]-dist[25])/cap}%"></i>`:'';
 const tick=n.retraced!=null?`<u style="left:calc(${Math.min(100,Math.max(0,100*n.retraced/cap))}% - 2px)"></u>`:'';
 return `<div class="card"><div class="top"><div class="name">${p.ticker} · ${p.tf}</div><span class="mono sub">${fmt(p.last_close)}</span></div>
 <div class="sub">${n.state||'no swings yet'}${n.bars_since!=null?' · '+n.bars_since+' bars':''}</div>
 <div class="meter">${band}${tick}</div>
 <div class="sub">now ${fmt(100*(n.retraced??NaN),0)}% of the leg · deeper than ${fmt(n.deeper_than_pct_of_history,0)}% of past ${isPull?'pullbacks':'bounces'}</div>
 <div class="grid2"><span>typical pullback</span><div class="mono">${fmt(100*pd[50],0)}% (75th ${fmt(100*pd[75],0)}%, 90th ${fmt(100*pd[90],0)}%)</div>
 <span>pullback lasts</span><div class="mono">${fmt(pb[50],0)} bars (75th ${fmt(pb[75],0)})</div>
 <span>typical bounce</span><div class="mono">${fmt(100*bd[50],0)}% (75th ${fmt(100*bd[75],0)}%)</div>
 <span>sample</span><div class="mono">${p.n_pullbacks} pullbacks · ${p.n_bounces} bounces</div></div></div>`}).join('');
// ---------- watchlist compare
const cc=[['ticker','Ticker'],['close','Close'],['r1w','1W %'],['r1m','1M %'],['r3m','3M %'],['r1y','1Y %'],['off_high','vs 52W hi %'],
 ['vs50','vs 50D %'],['vs200','vs 200D %'],['rsi','RSI'],['atr_pct','ATR %'],['trend','Trend'],['live','Live sigs']];
let cK='r1m',cD=-1;const liveBy={};D.fresh.forEach(f=>liveBy[f.ticker]=(liveBy[f.ticker]||0)+1);
function renderCmp(){const rows=D.snapshots.map(r=>({...r,live:liveBy[r.ticker]||0}));
 rows.sort((a,b)=>{const x=a[cK],y=b[cK];if(x==null)return 1;if(y==null)return -1;return(typeof x==='string'?x.localeCompare(y):x-y)*cD});
 $('#cmp thead').innerHTML='<tr>'+cc.map(([k,l])=>`<th data-k="${k}">${l}${cK===k?(cD<0?' ↓':' ↑'):''}</th>`).join('')+'</tr>';
 $('#cmp tbody').innerHTML=rows.map(r=>'<tr>'+cc.map(([k])=>{const v=r[k];if(k==='ticker')return`<td>${v}</td>`;
  if(k==='trend')return`<td>${v}</td>`;if(k==='live')return`<td class="mono">${v}</td>`;
  return`<td class="mono ${k.startsWith('r')||k.startsWith('vs')||k==='off_high'?sgn(v):''}">${fmt(v,k==='rsi'?1:2)}</td>`}).join('')+'</tr>').join('');
 document.querySelectorAll('#cmp th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(cK===k)cD*=-1;else{cK=k;cD=-1}renderCmp()})}
renderCmp();
const dv=D.snapshots.filter(s=>s.dividends&&(s.dividends.last_amount!=null||s.dividends.name));
$('#divs').innerHTML=dv.length?'<h2>Distributions</h2><div class="cards">'+dv.map(s=>{const d=s.dividends;
 const y=d.last_amount&&s.close?(d.frequency==='weekly'?52:d.frequency==='monthly'?12:d.frequency==='quarterly'?4:0)*d.last_amount/s.close*100:null;
 return`<div class="card"><div class="top"><div class="name">${s.ticker}</div><span class="mono">${fmt(s.close)}</span></div>
 <div class="sub">${d.name||''}</div>${d.last_amount!=null?`<div class="grid2 mono"><span>latest</span><div>$${fmt(d.last_amount,4)} · ${d.last_date}</div>
 <span>pays</span><div>${d.frequency}</div><span>run-rate yield</span><div>${y?fmt(y,1)+'%':'–'}</div>
 <span>recent</span><div>${(d.recent||[]).slice(0,4).map(r=>'$'+fmt(r.amount,3)).join(' · ')}</div></div>`:'<div class="sub">no distributions on record</div>'}</div>`}).join('')+'</div>':'';
// ---------- charts
const CH={};D.charts.forEach(c=>CH[c.ticker+'|'+c.tf]=c);
const ctk=[...new Set(D.charts.map(c=>c.ticker))];
$('#cTk').innerHTML=ctk.map(t=>`<option>${t}</option>`).join('');$('#cTf').innerHTML=[...new Set(D.charts.map(c=>c.tf))].map(t=>`<option ${t==='1d'?'selected':''}>${t}</option>`).join('');
let chart=null,cs=null,lines=[];
function drawChart(){const c=CH[$('#cTk').value+'|'+$('#cTf').value];const el=$('#chart');el.innerHTML='';$('#cList').innerHTML='';
 if(!c||!window.LightweightCharts){el.innerHTML='<div class="empty">No chart data.</div>';return}
 chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{color:'#121214'},textColor:'#ffffff',fontFamily:'Inter'},
  grid:{vertLines:{color:'#1d1d21'},horzLines:{color:'#1d1d21'}},rightPriceScale:{borderColor:'#26262b'},
  timeScale:{borderColor:'#26262b',timeVisible:c.tf==='1h'},crosshair:{mode:0},localization:{locale:'en-US'}});
 cs=chart.addCandlestickSeries({upColor:'#16a34a',downColor:'#dc2626',borderVisible:false,wickUpColor:'#16a34a',wickDownColor:'#dc2626'});
 cs.setData(c.candles.map(([t,o,h,l,cl])=>({time:t,open:o,high:h,low:l,close:cl})));
 const zz=chart.addLineSeries({color:'#8b5cf6',lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
 const seen=new Set();zz.setData(c.pivots.filter(p=>!seen.has(p[0])&&seen.add(p[0])).map(p=>({time:p[0],value:p[1]})));
 const cats=$('#cCat').value.split(','),gr=$('#cGr').value;
 const ms=c.marks.filter(m=>cats.includes(m.c)).map(m=>({...m,st:SM[key('ALL',c.tf,m.p)]})).filter(m=>!gr||gr.includes((m.st||{}).grade));
 cs.setMarkers(ms.slice().sort((a,b)=>a.t-b.t).map(m=>({time:m.t,position:m.d>0?'belowBar':'aboveBar',color:m.d>0?'#22c55e':'#ef4444',
  shape:m.d>0?'arrowUp':'arrowDown',text:m.fresh?'● '+m.p:m.p})));
 chart.timeScale().fitContent();
 $('#cList').innerHTML=ms.slice().reverse().slice(0,40).map((m,i)=>`<div class="card" data-i="${i}" style="cursor:pointer;padding:10px">
  <div class="top"><div style="font-weight:600">${m.fresh?'● ':''}${m.p}</div><span class="badge ${m.d>0?'L':'S'}">${m.d>0?'LONG':'SHORT'}</span></div>
  <a href="${gl(m.p)}" onclick="event.stopPropagation()" class="sub" style="color:#c4b5fd">what is this? →</a><div class="sub">${new Date(m.t*1000).toISOString().slice(0,c.tf==='1h'?16:10).replace('T',' ')} · ${m.st?gradeBadge(m.st.grade)+' '+fmt(m.st.expectancy_R)+'R':'no stats'}</div></div>`).join('')||'<div class="empty">No patterns of this kind in view.</div>';
 const rev=ms.slice().reverse().slice(0,40);
 document.querySelectorAll('#cList .card').forEach(card=>card.onclick=()=>{const m=rev[+card.dataset.i];lines.forEach(l=>cs.removePriceLine(l));
  lines=[cs.createPriceLine({price:m.stop,color:'#ef4444',lineWidth:1,lineStyle:2,title:'stop'}),cs.createPriceLine({price:m.tgt,color:'#22c55e',lineWidth:1,lineStyle:2,title:'target'})];
  const T=c.candles.map(x=>x[0]);const ie=T.indexOf(m.t),is=T.indexOf(m.ts);chart.timeScale().setVisibleLogicalRange({from:Math.min(is<0?ie:is,ie)-40,to:ie+25});el.scrollIntoView({behavior:'smooth',block:'center'})})}
['#cTk','#cTf','#cCat','#cGr'].forEach(s=>$(s).onchange=drawChart);drawChart();

// ---------- validation
const VH={"Confirmed":"Works on ~500 stocks, after costs, in recent years, and passed the luck test","Promising":"Works on ~500 stocks after costs and in recent years, not yet statistically proven",
"Watchlist only":"Only looked good on your 11 picks — probably hindsight","Faded out-of-sample":"Worked in older data, stopped working lately","Costs kill it":"Profit disappears after trading costs","No edge":"No better than random on the broad market","Too few trades":"Not enough examples"};
const VC={"Confirmed":"#16a34a","Promising":"#2563eb","Watchlist only":"#a16207","Faded out-of-sample":"#9a3412","Costs kill it":"#7f1d1d","No edge":"#3f3f46","Too few trades":"#27272a"};
if(D.verdicts.length){const cnt={};D.verdicts.forEach(v=>cnt[v.verdict]=(cnt[v.verdict]||0)+1);
 const top=D.verdicts.filter(v=>v.verdict==='Confirmed'||v.verdict==='Promising');
 $('#valwrap').innerHTML=`<h2>Validation — is the edge real?</h2><div class="sub">Every pattern re-tested on the S&P 500 (not just your picks), split into older vs. recent years, after trading costs, with a luck test.</div>
 <div class="kpis">${Object.keys(VH).filter(k=>cnt[k]).map(k=>`<div class="kpi" style="border-left:4px solid ${VC[k]}"><b>${cnt[k]}</b><span>${k}<br>${VH[k]}</span></div>`).join('')}</div>
 <div class="tbl" style="margin-top:12px"><table style="min-width:760px"><thead><tr><th>Pattern</th><th>TF</th><th>Dir</th><th>Verdict</th><th>S&P trades</th><th>S&P win %</th><th>Net R (all)</th><th>Net R (older)</th><th>Net R (recent)</th><th>Your grade</th></tr></thead><tbody>
 ${(top.length?top:D.verdicts.slice(0,25)).map(v=>`<tr><td><a href="${gl(v.pattern)}" style="color:#fff">${v.pattern}</a></td><td>${v.tf}</td><td><span class="badge ${v.direction==='LONG'?'L':'S'}">${v.direction}</span></td>
 <td><span class="g" style="background:${VC[v.verdict]}">${v.verdict}</span></td><td class="mono">${(v.uni_n||0).toLocaleString()}</td><td class="mono">${fmt(v.uni_win,1)}</td>
 <td class="mono ${sgn(v.uni_R_net)}">${fmt(v.uni_R_net)}</td><td class="mono ${sgn(v.is_R_net)}">${fmt(v.is_R_net)}</td><td class="mono ${sgn(v.oos_R_net)}">${fmt(v.oos_R_net)}</td><td>${gradeBadge(v.watch_grade)}</td></tr>`).join('')}</tbody></table></div>
 <div class="sub" style="margin-top:6px">Showing ${top.length?'Confirmed + Promising':'top 25'} of ${D.verdicts.length}. Full table in the Excel file.</div>`}
$('#cov').textContent='Data: '+D.coverage.map(c=>`${c.ticker} ${c.tf} ${c.first.slice(0,10)}→${c.last.slice(0,10)} (${c.bars} bars)`).join(' · ');
</script></body></html>"""
