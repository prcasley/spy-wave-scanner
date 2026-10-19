"""PatternScope 'Glass Cockpit' front page — the same data as the report, flown like an instrument panel."""
from __future__ import annotations

import json

from .report import payload


def build(res: dict, tf_cfg: dict, demo: bool = False, verdicts=None) -> str:
    return TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload(res, tf_cfg, demo, verdicts), default=str))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>PatternScope Cockpit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=B612:wght@400;700&family=B612+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--glare:#16191d;--glare2:#1c2025;--bezel:#25292f;--bezel-hi:#343941;--screen:#020507;--ink:#f5f7fa;--dim:#aab2bd;
--grn:#39e27a;--amb:#ffb627;--red:#ff4b4b;--cyn:#3fd0ff;--mag:#f062ff;--sky:#2a6db3;--gnd:#8a5a2b}
*{box-sizing:border-box}
html,body{margin:0;background:var(--glare);color:var(--ink);font:15px/1.5 B612,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
body{background:radial-gradient(1200px 500px at 50% -120px,#232830 0%,var(--glare) 70%) fixed}
.mono{font-family:'B612 Mono',ui-monospace,monospace}
.deck{max-width:1240px;margin:0 auto;padding:18px 16px 70px}
a{color:var(--ink)}
/* ---- glareshield header */
.glare{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 18px;padding:4px 2px 14px}
.glare h1{margin:0;font-size:24px;font-weight:700;letter-spacing:.01em}
.glare .meta{color:var(--dim);font-size:13px}
.glare nav{display:flex;flex-wrap:wrap;gap:8px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:8px 13px;border-radius:7px;background:linear-gradient(#2c3138,#22262c);border:1px solid #3a4048;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 2px 0 #0c0e10;color:var(--ink);text-decoration:none;font-size:13.5px;cursor:pointer;font-family:inherit}
.btn:hover{border-color:#56606c}.btn:focus-visible,button:focus-visible,select:focus-visible{outline:2px solid var(--cyn);outline-offset:2px}
.btn i{width:8px;height:8px;border-radius:50%;background:var(--grn);box-shadow:0 0 8px var(--grn)}
/* ---- annunciator panel */
.annun{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;padding:10px;background:#0d0f12;border:1px solid #2a2f36;border-radius:10px;
 box-shadow:inset 0 2px 8px rgba(0,0,0,.6)}
.lamp{position:relative;min-height:58px;padding:7px 9px;border-radius:5px;background:linear-gradient(#1b1e22,#141619);border:1px solid #2e333a;
 display:flex;flex-direction:column;justify-content:center;text-align:center;color:#6f7782;transition:background .2s}
.lamp b{font-size:20px;line-height:1.1;font-family:'B612 Mono',monospace}.lamp span{font-size:11.5px;line-height:1.25;text-transform:uppercase;letter-spacing:.04em}
.lamp.on{color:#fff}.lamp.on.g{background:linear-gradient(#1f5e3a,#174a2d);border-color:#2f8f57;box-shadow:0 0 14px rgba(57,226,122,.25)}
.lamp.on.a{background:linear-gradient(#7a5410,#5f400b);border-color:#b07a17;box-shadow:0 0 14px rgba(255,182,39,.25)}
.lamp.on.r{background:linear-gradient(#7b1f1f,#5d1616);border-color:#b23434;box-shadow:0 0 14px rgba(255,75,75,.28)}
.lamp.on.c{background:linear-gradient(#155873,#0f4358);border-color:#2382a8;box-shadow:0 0 14px rgba(63,208,255,.22)}
.lamptest .lamp{background:linear-gradient(#e8e4d0,#c9c4ab)!important;color:#1a1a1a!important}
/* ---- bezels */
.row{display:grid;gap:14px;margin-top:14px}
.r-pfd{grid-template-columns:minmax(0,1.45fr) minmax(0,1fr)}
.r-two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.bezel{position:relative;background:linear-gradient(160deg,var(--bezel-hi),var(--bezel) 38%,#1e2227);border-radius:14px;padding:14px;
 box-shadow:0 1px 0 rgba(255,255,255,.06) inset,0 12px 26px rgba(0,0,0,.45),0 0 0 1px #0d0f12}
.bezel::before,.bezel::after{content:"";position:absolute;width:7px;height:7px;border-radius:50%;
 background:radial-gradient(circle at 35% 35%,#6b737d,#2a2e33);top:6px;left:6px;box-shadow:calc(100% * 0) 0 0 0 #000}
.bezel::after{left:auto;right:6px}
.bezel .screws-b::before,.bezel .screws-b::after{content:"";position:absolute;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#6b737d,#2a2e33);bottom:6px;left:6px}
.bezel .screws-b::after{left:auto;right:6px}
.screen{position:relative;background:var(--screen);border-radius:8px;overflow:hidden;box-shadow:inset 0 0 0 1px #000,inset 0 0 40px rgba(0,0,0,.9)}
.screen::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:8px;
 background:linear-gradient(155deg,rgba(255,255,255,.07) 0%,rgba(255,255,255,.015) 28%,rgba(255,255,255,0) 45%)}
.plate{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 2px 10px;padding-left:14px}
.plate h2{margin:0;font-size:15.5px;font-weight:700}
.plate .hint{color:var(--dim);font-size:12.5px}
.seg{display:inline-flex;background:#0e1013;border:1px solid #30353c;border-radius:7px;padding:2px}
.seg button{background:none;border:0;color:var(--dim);font:inherit;font-size:12.5px;padding:5px 10px;border-radius:5px;cursor:pointer}
.seg button.on{background:#2c323a;color:#fff;box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
select{background:#0e1013;color:#fff;border:1px solid #30353c;border-radius:7px;padding:6px 8px;font:inherit;font-size:12.5px}
/* ---- PFD */
.pfd{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2.4fr) minmax(0,1.25fr);gap:0;align-items:stretch;padding:10px 6px 8px}
.pfd svg{width:100%;height:auto;display:block;min-width:0}
.bezel,.row>*{min-width:0}
.pfd-foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;padding:8px 12px 10px;border-top:1px solid #11161c;color:var(--dim);font-size:12.5px}
.pfd-foot b{color:#fff;font-weight:400}
.picker{display:flex;gap:6px;overflow-x:auto;padding:2px 2px 10px 14px;scrollbar-width:thin}
.picker button{flex:0 0 auto;background:#0e1013;border:1px solid #30353c;color:var(--dim);font:inherit;font-size:13px;padding:5px 10px;border-radius:6px;cursor:pointer}
.picker button.on{color:#fff;border-color:var(--cyn);box-shadow:0 0 0 1px var(--cyn) inset}
.picker button .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--amb);margin-left:6px;vertical-align:middle}
/* ---- ND */
.nd svg{width:100%;height:auto;display:block}
.sweep{transform-origin:150px 150px;animation:sweep 9s linear infinite}
@keyframes sweep{to{transform:rotate(360deg)}}
.wps{display:flex;flex-direction:column;gap:6px;padding:10px 0 0}
.wp{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:8px 10px;border-radius:8px;background:#0b0e12;border:1px solid #1d232a;cursor:pointer;text-align:left;color:#fff;font:inherit}
.wp:hover{border-color:#3a4450}.wp small{color:var(--dim);display:block;font-size:12px}
.wp .gl{font-size:12px;color:#d8c5ff;text-decoration:underline;text-underline-offset:2px}
/* ---- chart */
#chart{height:400px}
/* ---- gauges */
.gauges{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.gauge{background:#0b0e12;border:1px solid #1d232a;border-radius:12px;padding:6px 6px 8px;cursor:pointer;text-align:center;color:#fff;font:inherit}
.gauge.on{border-color:var(--cyn);box-shadow:0 0 0 1px var(--cyn) inset}
.gauge svg{width:100%;height:auto;display:block}
.gauge .rd{display:flex;justify-content:center;gap:12px;font-size:12px;color:var(--dim)}.gauge .rd b{color:#fff;font-weight:400}
/* ---- ECAM */
.ecam{padding:12px 14px 14px}
.sys{display:grid;grid-template-columns:minmax(0,1.6fr) 44px minmax(0,1fr) 62px;gap:6px 10px;align-items:center;font-size:13px}
.sys .nm a{color:#fff;text-decoration:none}.sys .nm a:hover{text-decoration:underline}
.sys .bar{height:9px;background:#11161c;border-radius:2px;position:relative;overflow:hidden}
.sys .bar i{position:absolute;left:0;top:0;bottom:0;background:var(--grn);border-radius:2px}
.sys .gr{display:inline-block;width:30px;text-align:center;border-radius:4px;font-weight:700;font-size:12px;padding:1px 0;color:#fff}
.gA{background:#16a34a}.gB{background:#2563eb}.gC{background:#a16207}.gF{background:#7f1d1d}.glow-n{background:#3f3f46}
.ecam h3{margin:14px 0 6px;font-size:13px;font-weight:700;color:var(--amb)}
.ecam h3.ok{color:var(--grn)}.ecam h3.cy{color:var(--cyn)}
.chk{display:grid;grid-template-columns:1fr auto;gap:4px 12px;font-size:13px}
.chk .dots{border-bottom:1px dotted #39414b;margin-bottom:5px}
.chk div{display:flex;gap:6px;align-items:flex-end}
.empty{color:var(--dim);font-size:13.5px;padding:10px 2px}
/* ---- fuel & payout */
.fuel{display:grid;grid-template-columns:62px 1fr 48px;gap:6px 10px;align-items:center;font-size:13px;padding:12px 14px}
.fuel .tank{height:12px;background:#11161c;border-radius:3px;position:relative;overflow:hidden;box-shadow:inset 0 0 0 1px #1f262e}
.fuel .tank i{position:absolute;left:0;top:0;bottom:0;border-radius:3px}
.fuel .tank u{position:absolute;top:-2px;bottom:-2px;width:2px;background:#fff;text-decoration:none}
.payout{padding:12px 14px}
.payout .big{font-size:30px;line-height:1.1}
.payout .sub{color:var(--dim);font-size:12.5px}
.foot{margin-top:22px;color:var(--dim);font-size:12.5px;line-height:1.6}
@media (max-width:900px){.r-pfd,.r-two{grid-template-columns:1fr}#chart{height:330px}}
@media (max-width:520px){.deck{padding:12px 10px 60px}.glare h1{font-size:20px}.gauges{grid-template-columns:repeat(2,1fr)}.pfd{grid-template-columns:minmax(0,1fr) minmax(0,2.2fr) minmax(0,1.2fr);padding:6px 2px}}
@media (prefers-reduced-motion:reduce){.sweep{animation:none}*{transition:none!important}}
</style></head><body><div class="deck">

<header class="glare">
 <div><h1>PatternScope</h1><div class="meta" id="meta"></div></div>
 <nav><a class="btn" href="guide.html">Pattern guide</a><a class="btn" href="https://github.com/prcasley/spy-wave-scanner/releases/download/patternscope-latest/PatternScope.xlsx"><i></i>Download Excel</a><a class="btn" href="classic.html">Classic view</a></nav>
</header>

<section class="annun" id="annun" aria-label="Status lights"></section>

<div class="row r-pfd">
 <section class="bezel"><span class="screws-b"></span>
  <div class="plate"><h2 id="pfdTitle">Flight display</h2><span class="hint">daily chart</span></div>
  <div class="picker" id="picker" role="tablist" aria-label="Choose a stock"></div>
  <div class="screen"><div class="pfd" id="pfd"></div><div class="pfd-foot" id="pfdFoot"></div></div>
 </section>
 <section class="bezel nd"><span class="screws-b"></span>
  <div class="plate"><h2>Signal radar</h2><span class="hint">closer to the center = better track record</span></div>
  <div class="screen"><svg viewBox="0 0 300 300" id="radar" role="img" aria-label="Live signals radar"></svg></div>
  <div class="wps" id="wps"></div>
 </section>
</div>

<section class="bezel row"><span class="screws-b"></span>
 <div class="plate"><h2 id="chTitle">Chart</h2>
  <span style="display:flex;gap:8px;flex-wrap:wrap"><span class="seg" id="tfSeg"></span>
  <select id="cCat" aria-label="Which patterns to show"><option value="chart,setup">Chart + setups</option><option value="chart">Chart shapes</option><option value="setup">Setups</option><option value="candle">Candles</option><option value="chart,setup,candle">Everything</option></select>
  <select id="cGr" aria-label="Minimum grade"><option value="AB">Grade A/B</option><option value="ABC">A/B/C</option><option value="">All grades</option></select></span></div>
 <div class="screen"><div id="chart"></div></div>
 <div class="wps" id="cList" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr))"></div>
</section>

<section class="bezel row"><span class="screws-b"></span>
 <div class="plate"><h2>Engine gauges</h2><span class="seg" id="mkSeg"><button class="on" data-m="">All</button><button data-m="stocks">Stocks</button><button data-m="crypto">Crypto</button></span></div>
 <div class="gauges" id="gauges"></div>
</section>

<div class="row r-two">
 <section class="bezel"><span class="screws-b"></span>
  <div class="plate"><h2>Pattern systems</h2><span class="seg" id="sysSeg"></span></div>
  <div class="screen"><div class="ecam" id="sys"></div></div>
 </section>
 <section class="bezel"><span class="screws-b"></span>
  <div class="plate"><h2>Validation checklist</h2><span class="hint">tested on the S&amp;P 500</span></div>
  <div class="screen"><div class="ecam" id="chk"></div></div>
 </section>
</div>

<div class="row r-two">
 <section class="bezel"><span class="screws-b"></span>
  <div class="plate"><h2>Pullback fuel</h2><span class="hint">how deep today's dip is vs. past dips</span></div>
  <div class="screen"><div class="fuel" id="fuel"></div></div>
 </section>
 <section class="bezel"><span class="screws-b"></span>
  <div class="plate"><h2>Payouts</h2><span class="hint">latest distributions</span></div>
  <div class="screen"><div class="payout" id="pay"></div></div>
 </section>
</div>

<p class="foot" id="foot"></p>
</div>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<script>
const D=/*__DATA__*/null;
const $=s=>document.querySelector(s);
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const C={grn:'#39e27a',amb:'#ffb627',red:'#ff4b4b',cyn:'#3fd0ff',mag:'#f062ff',w:'#f5f7fa',dim:'#7d8794'};
const fmt=(v,d=2)=>v==null||Number.isNaN(+v)?'–':(+v).toFixed(d);
const pct=(v,d=1)=>v==null?'–':((v>0?'+':'')+(+v).toFixed(d)+'%');
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const gl=n=>`guide.html#${n.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}`;
const ORD={A:0,B:1,C:2,'low-n':3,F:4};
const SM={};D.stats.forEach(r=>SM[r.ticker+'|'+r.tf+'|'+r.pattern]=r);
const pooled=(tf,p)=>SM['ALL|'+tf+'|'+p];
const SNAP={};D.snapshots.forEach(s=>SNAP[s.ticker]=s);
const PROF={};D.profiles.forEach(p=>PROF[p.ticker+'|'+p.tf]=p);
const tickers=D.snapshots.map(s=>s.ticker);
const fresh=D.fresh.map(f=>({...f,st:pooled(f.tf,f.pattern),own:SM[f.ticker+'|'+f.tf+'|'+f.pattern]}))
 .sort((a,b)=>(ORD[(a.st||{}).grade]??5)-(ORD[(b.st||{}).grade]??5)||((b.st||{}).expectancy_R||-9)-((a.st||{}).expectancy_R||-9));
const liveBy={};fresh.forEach(f=>(liveBy[f.ticker]=liveBy[f.ticker]||[]).push(f));
let sel=(fresh.find(f=>f.st&&ORD[f.st.grade]<=1)||{}).ticker||tickers[0];
let tf='1d',sysTf='1d';
$('#meta').textContent=`Updated ${D.generated} from Yahoo Finance · ${D.n_trades.toLocaleString()} past pattern trades scored`;

/* ---------------- annunciators */
function annun(){const ab=fresh.filter(f=>f.st&&ORD[f.st.grade]<=1);const L=ab.filter(f=>f.direction===1).length,S=ab.filter(f=>f.direction===-1).length;
 const spy=SNAP.SPY||{};const up=/Uptrend|Above/.test(spy.trend||'');
 const over=D.snapshots.filter(s=>s.rsi<30).length;const deep=D.profiles.filter(p=>p.tf==='1d'&&(p.now||{}).deeper_than_pct_of_history>=85).length;
 const conf=D.verdicts.filter(v=>v.verdict==='Confirmed').length;
 const L_=[[fresh.length,'Live signals (all)',fresh.length?'a':''],[L,'A/B longs',L?'g':''],[S,'A/B shorts',S?'r':''],
  [up?'UP':'DOWN','SPY trend',up?'g':'r'],...(SNAP['BTC-USD']?[[/Uptrend|Above/.test(SNAP['BTC-USD'].trend)?'UP':'DOWN','BTC trend',/Uptrend|Above/.test(SNAP['BTC-USD'].trend)?'g':'r']]:[]),[over,'Oversold (RSI<30)',over?'a':''],[deep,'Deep pullbacks',deep?'a':''],
  [D.verdicts.length?conf:'…','Confirmed patterns',conf?'c':'']];
 $('#annun').innerHTML=L_.map(([b,s,c])=>`<div class="lamp ${c?'on '+c:''}" role="status"><b>${b}</b><span>${s}</span></div>`).join('')}
annun();
if(!RM){$('#annun').classList.add('lamptest');setTimeout(()=>$('#annun').classList.remove('lamptest'),650)}

/* ---------------- PFD */
function bugsFor(t){const fs=(liveBy[t]||[]).filter(f=>f.st&&ORD[f.st.grade]<=2);return fs[0]||null}
function pfd(){const s=SNAP[sel]||{};const pr=PROF[sel+'|1d']||{};const b=bugsFor(sel);
 $('#pfdTitle').textContent=`Flight display · ${sel}`;
 document.querySelectorAll('#picker button').forEach(x=>x.classList.toggle('on',x.dataset.t===sel));
 // RSI speed tape
 const rsi=s.rsi??50;const H=300,cy=150,sc=4.2;let tape=`<rect x="6" y="6" width="58" height="${H-12}" rx="4" fill="#0a0f15"/>`;
 [[0,30,C.amb],[30,70,C.grn],[70,100,C.amb]].forEach(([a,z,c])=>{const y1=cy-(z-rsi)*sc,y2=cy-(a-rsi)*sc;tape+=`<rect x="56" y="${clamp(y1,6,H-6)}" width="6" height="${Math.max(0,clamp(y2,6,H-6)-clamp(y1,6,H-6))}" fill="${c}" opacity=".85"/>`});
 for(let v=0;v<=100;v+=5){const y=cy-(v-rsi)*sc;if(y<12||y>H-12)continue;tape+=`<line x1="${v%10?44:38}" x2="54" y1="${y}" y2="${y}" stroke="${C.w}" stroke-width="1.2"/>`;if(v%10===0)tape+=`<text x="34" y="${y+4}" fill="${C.w}" font-size="11" text-anchor="end" font-family="B612 Mono">${v}</text>`}
 tape+=`<path d="M4 ${cy-13} H50 L60 ${cy} L50 ${cy+13} H4 Z" fill="#000" stroke="${C.w}" stroke-width="1.4"/><text x="30" y="${cy+5}" fill="#fff" font-size="15" text-anchor="middle" font-family="B612 Mono" font-weight="700">${fmt(rsi,0)}</text>`;
 tape+=`<text x="35" y="22" fill="${C.cyn}" font-size="11" text-anchor="middle">RSI</text>`;
 // attitude indicator: pitch = % vs 50-day, roll = 1-week change
 const pitch=clamp(s.vs50??0,-20,20),roll=clamp(-(s.r1w??0)*2.4,-40,40);const R=128,ppx=5.2;
 let ladder='';for(let p=-20;p<=20;p+=5){if(!p)continue;const y=-p*ppx,w=p%10?22:40;ladder+=`<line x1="${-w}" x2="${w}" y1="${y}" y2="${y}" stroke="#fff" stroke-width="1.6"/>`;if(!(p%10))ladder+=`<text x="${w+6}" y="${y+4}" fill="#fff" font-size="11" font-family="B612 Mono">${p>0?'+':''}${p}%</text>`}
 let rollTicks='';[-45,-30,-20,-10,0,10,20,30,45].forEach(a=>{const r1=R-4,r2=a%30===0||a===0?R-18:R-12;const t=(a-90)*Math.PI/180;rollTicks+=`<line x1="${r1*Math.cos(t)}" y1="${r1*Math.sin(t)}" x2="${r2*Math.cos(t)}" y2="${r2*Math.sin(t)}" stroke="#fff" stroke-width="2"/>`});
 const att=`<svg viewBox="-150 -150 300 300" role="img" aria-label="Trend horizon for ${sel}"><defs><clipPath id="adi"><circle r="${R}"/></clipPath>
  <radialGradient id="glass" cx="35%" cy="25%" r="80%"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>
  <g clip-path="url(#adi)"><g id="horizon" style="transform:rotate(${roll}deg) translateY(${pitch*ppx}px);transition:transform 1.1s cubic-bezier(.2,.8,.2,1)">
   <rect x="-400" y="-400" width="800" height="400" fill="var(--sky)"/><rect x="-400" y="0" width="800" height="400" fill="var(--gnd)"/>
   <line x1="-400" x2="400" y1="0" y2="0" stroke="#fff" stroke-width="2"/>${ladder}</g></g>
  <circle r="${R}" fill="url(#glass)" stroke="#000" stroke-width="3"/>${rollTicks}
  <path d="M0 ${-R+6} l-7 -12 h14z" fill="${C.amb}" transform="rotate(${roll})"/>
  <path d="M-78 0 h40 l10 14 M78 0 h-40 l-10 14" fill="none" stroke="${C.amb}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="-5" y="-5" width="10" height="10" fill="#000" stroke="${C.amb}" stroke-width="3"/>
  <text x="0" y="${R+18}" fill="#fff" font-size="12" text-anchor="middle">${s.trend||''}</text></svg>`;
 // price altitude tape
 const px=s.close||0,atr=(s.atr_pct||2)/100*px,span=atr*4;const pt=v=>cy-(v-px)/span*(cy-14);
 let alt=`<rect x="6" y="6" width="${108}" height="${H-12}" rx="4" fill="#0a0f15"/>`;
 const step=niceStep(span/4);const busy=[cy];if(b)busy.push(clamp(pt(b.target),14,H-14),clamp(pt(b.stop),14,H-14));
 const hiY=s.off_high!=null?pt(px/(1+s.off_high/100)):-99;busy.push(hiY);
 for(let v=Math.ceil((px-span)/step)*step;v<=px+span;v+=step){const y=pt(v);if(y<12||y>H-12||busy.some(z=>Math.abs(z-y)<(z===cy?20:12)))continue;alt+=`<line x1="12" x2="24" y1="${y}" y2="${y}" stroke="#fff" stroke-width="1.2"/><text x="28" y="${y+4}" fill="#fff" font-size="11" font-family="B612 Mono">${fmtPx(v)}</text>`}
 const hi52=s.off_high!=null?px/(1+s.off_high/100):null;if(hi52){const y=pt(hi52);if(y>=30)alt+=`<line x1="8" x2="112" y1="${y}" y2="${y}" stroke="${C.cyn}" stroke-dasharray="4 3"/><text x="110" y="${y-4}" fill="${C.cyn}" font-size="10" text-anchor="end">52w high</text>`;else alt+=`<text x="60" y="${H-14}" fill="${C.cyn}" font-size="10" text-anchor="middle">52w high ${fmtPx(hi52)} ▲</text>`}
 if(b){[[b.target,C.mag,'target'],[b.stop,C.red,'stop']].forEach(([v,c,l])=>{const y=clamp(pt(v),14,H-14);const yy=Math.abs(y-cy)<22?(y<cy?cy-24:cy+24):y;alt+=`<path d="M6 ${y-7} h10 l6 7 l-6 7 h-10 z" fill="${c}"/><rect x="24" y="${yy-8}" width="90" height="16" rx="3" fill="#0a0f15"/><text x="27" y="${yy+4}" fill="${c}" font-size="10.5" font-family="B612 Mono" font-weight="700">${l} ${fmtPx(v)}</text>`})}
 alt+=`<path d="M118 ${cy-14} H34 L24 ${cy} L34 ${cy+14} H118 Z" fill="#000" stroke="#fff" stroke-width="1.4"/><text x="74" y="${cy+5}" fill="#fff" font-size="14" text-anchor="middle" font-family="B612 Mono" font-weight="700">${fmtPx(px)}</text>`;
 alt+=`<text x="60" y="22" fill="${C.cyn}" font-size="11" text-anchor="middle">price</text>`;
 $('#pfd').innerHTML=`<svg viewBox="0 0 70 ${H}">${tape}</svg>${att}<svg viewBox="0 0 120 ${H}">${alt}</svg>`;
 const now=(pr.now||{});
 $('#pfdFoot').innerHTML=[`1W <b>${pct(s.r1w)}</b>`,`1M <b>${pct(s.r1m)}</b>`,`1Y <b>${pct(s.r1y,0)}</b>`,`vs 50-day <b>${pct(s.vs50)}</b>`,
  `off 52w high <b>${pct(s.off_high)}</b>`,now.deeper_than_pct_of_history!=null?`dip deeper than <b>${fmt(now.deeper_than_pct_of_history,0)}%</b> of past dips`:'',
  b?`active: <b>${b.pattern}</b> (${b.tf})`:'no active A/B/C signal'].filter(Boolean).map(x=>`<span>${x}</span>`).join('');
 drawChart();}
function niceStep(x){const p=Math.pow(10,Math.floor(Math.log10(x)));const m=x/p;return(m<1.5?1:m<3?2:m<7?5:10)*p}
function fmtPx(v){return v>=1000?v.toFixed(0):v>=100?v.toFixed(1):v.toFixed(2)}
$('#picker').innerHTML=tickers.map(t=>`<button role="tab" data-t="${t}">${t.replace('-USD','')}${liveBy[t]?'<span class="dot" title="live signal"></span>':''}</button>`).join('');
$('#picker').onclick=e=>{const b=e.target.closest('button');if(b){sel=b.dataset.t;pfd();gauges()}};

/* ---------------- radar */
function radar(){const n=tickers.length,cx=150,cy=150;const ringR={A:38,B:70,C:100,'low-n':124,F:124};let s='';
 s+=`<defs><radialGradient id="rg"><stop offset="0" stop-color="#0d2a1a"/><stop offset="1" stop-color="#020507"/></radialGradient>
  <linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${C.grn}" stop-opacity="0"/><stop offset="1" stop-color="${C.grn}" stop-opacity=".22"/></linearGradient></defs>
  <circle cx="${cx}" cy="${cy}" r="140" fill="url(#rg)"/>`;
 [[38,'A'],[70,'B'],[100,'C'],[124,'other']].forEach(([r,l])=>{s+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${C.grn}" stroke-opacity=".28" stroke-dasharray="${r===124?'3 4':''}"/><text x="${cx+3}" y="${cy-r+11}" fill="${C.grn}" fill-opacity=".8" font-size="9.5">${l}</text>`});
 for(let a=0;a<360;a+=10){const t=a*Math.PI/180,r1=140,r2=a%30?134:128;s+=`<line x1="${cx+r1*Math.sin(t)}" y1="${cy-r1*Math.cos(t)}" x2="${cx+r2*Math.sin(t)}" y2="${cy-r2*Math.cos(t)}" stroke="#fff" stroke-opacity=".5"/>`}
 if(!RM)s+=`<g class="sweep"><path d="M150 150 L150 10 A140 140 0 0 1 249 51 Z" fill="url(#sw)"/></g>`;
 tickers.forEach((t,i)=>{const a=i/n*2*Math.PI;s+=`<text x="${cx+147*Math.sin(a)}" y="${cy-147*Math.cos(a)+4}" fill="#fff" font-size="9.5" text-anchor="middle" opacity=".85">${t}</text>`});
 fresh.forEach((f,k)=>{const i=tickers.indexOf(f.ticker);if(i<0||!f.st||ORD[f.st.grade]>2)return;const grp=liveBy[f.ticker].filter(x=>x.st&&ORD[x.st.grade]<=2);const same=grp.indexOf(f);const a=(i/n+(same-(grp.length-1)/2)*0.03)*2*Math.PI;
  const r=ringR[(f.st||{}).grade]||124;const x=cx+r*Math.sin(a),y=cy-r*Math.cos(a);const c=f.direction>0?C.grn:C.red;
  s+=`<g style="cursor:pointer" data-k="${k}"><path d="${f.direction>0?`M${x} ${y-6} l5 9 h-10z`:`M${x} ${y+6} l5 -9 h-10z`}" fill="${c}" stroke="#000" stroke-width=".8"/></g>`});
 s+=`<circle cx="${cx}" cy="${cy}" r="3" fill="${C.amb}"/>`;
 $('#radar').innerHTML=s;
 $('#radar').onclick=e=>{const g=e.target.closest('g[data-k]');if(g){sel=fresh[+g.dataset.k].ticker;tf=fresh[+g.dataset.k].tf;segs();pfd();gauges()}};
 $('#wps').innerHTML=fresh.length?fresh.slice(0,6).map((f,k)=>{const st=f.st||{};return `<button class="wp" data-k="${k}">
  ${dial(st.target_pct,st.expectancy_R,f.direction)}
  <span><b>${f.ticker}</b> · <a class="gl" href="${gl(f.pattern)}" onclick="event.stopPropagation()">${f.pattern}</a><small>${f.tf} · ${f.direction>0?'long':'short'} from ${fmtPx(f.signal_close)} · stop ${fmtPx(f.stop)} · target ${fmtPx(f.target)}</small></span>
  <span class="gr ${'g'+(st.grade||'low-n')}" style="width:auto;padding:1px 7px;border-radius:4px;font-weight:700;font-size:12px">${st.grade||'–'}</span></button>`}).join(''):'<div class="empty">No patterns confirmed on the latest bars. Radar is clear.</div>';
 document.querySelectorAll('.wp').forEach(w=>w.onclick=()=>{const f=fresh[+w.dataset.k];sel=f.ticker;tf=f.tf;segs();pfd();gauges();$('#chart').scrollIntoView({behavior:RM?'auto':'smooth',block:'center'})})}
function dial(win,R,d){const w=clamp(win||0,0,100),a=-120+w*2.4,t=(a-90)*Math.PI/180;return `<svg viewBox="-24 -24 48 40" width="54" aria-label="${fmt(win,0)}% win"><path d="M-17 10 A20 20 0 1 1 17 10" fill="none" stroke="#1f2730" stroke-width="5"/>
 <path d="M-17 10 A20 20 0 ${w>50?1:0} 1 ${20*Math.cos(t)} ${20*Math.sin(t)}" fill="none" stroke="${(R||0)>0?C.grn:C.red}" stroke-width="5"/><text x="0" y="5" fill="#fff" font-size="10" text-anchor="middle" font-family="B612 Mono">${fmt(win,0)}%</text></svg>`}

/* ---------------- chart */
const CH={};D.charts.forEach(c=>CH[c.ticker+'|'+c.tf]=c);
let chart=null;
function segs(){$('#tfSeg').innerHTML=['1h','1d','1wk'].map(t=>`<button class="${t===tf?'on':''}" data-t="${t}">${{'1h':'Hourly','1d':'Daily','1wk':'Weekly'}[t]}</button>`).join('');
 $('#sysSeg').innerHTML=['1h','1d','1wk'].map(t=>`<button class="${t===sysTf?'on':''}" data-t="${t}">${{'1h':'Hourly','1d':'Daily','1wk':'Weekly'}[t]}</button>`).join('')}
$('#tfSeg').onclick=e=>{const b=e.target.closest('button');if(b){tf=b.dataset.t;segs();drawChart()}};
$('#sysSeg').onclick=e=>{const b=e.target.closest('button');if(b){sysTf=b.dataset.t;segs();systems()}};
['#cCat','#cGr'].forEach(s=>$(s).onchange=drawChart);
function drawChart(){const c=CH[sel+'|'+tf];const el=$('#chart');el.innerHTML='';$('#chTitle').textContent=`Chart · ${sel} · ${{'1h':'hourly','1d':'daily','1wk':'weekly'}[tf]}`;
 if(!c||!window.LightweightCharts){el.innerHTML='<div class="empty" style="padding:20px">No chart for this timeframe yet.</div>';return}
 chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{color:'#020507'},textColor:'#e8edf3',fontFamily:'B612 Mono'},
  grid:{vertLines:{color:'#0c1a12'},horzLines:{color:'#0c1a12'}},rightPriceScale:{borderColor:'#1d262f'},timeScale:{borderColor:'#1d262f',timeVisible:tf==='1h'},
  crosshair:{mode:0,vertLine:{color:'#3fd0ff55'},horzLine:{color:'#3fd0ff55'}},localization:{locale:'en-US'}});
 const cs=chart.addCandlestickSeries({upColor:'#39e27a',downColor:'#ff4b4b',borderVisible:false,wickUpColor:'#39e27a',wickDownColor:'#ff4b4b'});
 cs.setData(c.candles.map(([t,o,h,l,cl])=>({time:t,open:o,high:h,low:l,close:cl})));
 const zz=chart.addLineSeries({color:'#f062ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
 const seen=new Set();zz.setData(c.pivots.filter(p=>!seen.has(p[0])&&seen.add(p[0])).map(p=>({time:p[0],value:p[1]})));
 const cats=$('#cCat').value.split(','),gr=$('#cGr').value;
 const ms=c.marks.filter(m=>cats.includes(m.c)).map(m=>({...m,st:pooled(tf,m.p)})).filter(m=>!gr||gr.includes((m.st||{}).grade));
 cs.setMarkers(ms.slice().sort((a,b)=>a.t-b.t).map(m=>({time:m.t,position:m.d>0?'belowBar':'aboveBar',color:m.d>0?'#39e27a':'#ff4b4b',shape:m.d>0?'arrowUp':'arrowDown',text:m.fresh?'● '+m.p:''})));
 const live=ms.filter(m=>m.fresh).pop();if(live){cs.createPriceLine({price:live.tgt,color:'#f062ff',lineWidth:1,lineStyle:2,title:'target'});cs.createPriceLine({price:live.stop,color:'#ff4b4b',lineWidth:1,lineStyle:2,title:'stop'})}
 chart.timeScale().fitContent();
 const T=c.candles.map(x=>x[0]);const recent=ms.slice().sort((a,b)=>b.t-a.t).slice(0,8);
 $('#cList').innerHTML=recent.map(m=>`<button class="wp" data-t="${m.t}" data-s="${m.ts}"><span class="gr g${(m.st||{}).grade||'low-n'}" style="padding:1px 7px;border-radius:4px;font-weight:700;font-size:12px">${(m.st||{}).grade||'–'}</span><span><b>${m.p}</b><small>${new Date(m.t*1000).toISOString().slice(0,tf==='1h'?16:10).replace('T',' ')} · ${m.d>0?'long':'short'}</small></span><a class="gl" href="${gl(m.p)}" onclick="event.stopPropagation()">what is it?</a></button>`).join('');
 document.querySelectorAll('#cList .wp').forEach(w=>w.onclick=()=>{const ie=T.indexOf(+w.dataset.t),is=T.indexOf(+w.dataset.s);chart.timeScale().setVisibleLogicalRange({from:Math.min(is<0?ie:is,ie)-40,to:ie+25})})}

/* ---------------- gauges */
let mk='';
$('#mkSeg').onclick=e=>{const b=e.target.closest('button');if(b){mk=b.dataset.m;document.querySelectorAll('#mkSeg button').forEach(x=>x.classList.toggle('on',x===b));gauges()}};
function gauges(){$('#gauges').innerHTML=D.snapshots.filter(s=>!mk||(s.market||'stocks')===mk).map(s=>{const v=clamp(s.rsi??50,0,100);const ang=-135+v*2.7;
 const arc=(a0,a1,c)=>{const p=a=>{const t=(a-90)*Math.PI/180;return[50+40*Math.cos(t),52+40*Math.sin(t)]};const[x0,y0]=p(-135+a0*2.7),[x1,y1]=p(-135+a1*2.7);return `<path d="M${x0} ${y0} A40 40 0 ${(a1-a0)*2.7>180?1:0} 1 ${x1} ${y1}" fill="none" stroke="${c}" stroke-width="6"/>`};
 let ticks='';for(let k=0;k<=10;k++){const t=(-135+k*27-90)*Math.PI/180;ticks+=`<line x1="${50+33*Math.cos(t)}" y1="${52+33*Math.sin(t)}" x2="${50+(k%5?30:27)*Math.cos(t)}" y2="${52+(k%5?30:27)*Math.sin(t)}" stroke="#fff" stroke-opacity=".7"/>`}
 const lv=liveBy[s.ticker]?`<circle cx="88" cy="12" r="4" fill="${C.amb}"><title>live signal</title></circle>`:'';
 return `<button class="gauge ${s.ticker===sel?'on':''}" data-t="${s.ticker}" aria-label="${s.ticker} RSI ${fmt(s.rsi,0)}">
 <svg viewBox="0 0 100 90"><circle cx="50" cy="52" r="46" fill="#05080b" stroke="#232a32" stroke-width="2"/>${arc(0,20,C.red)}${arc(20,30,C.amb)}${arc(30,70,C.grn)}${arc(70,80,C.amb)}${arc(80,100,C.red)}${ticks}
 <g class="needle" style="transform-origin:50px 52px;transform:rotate(${RM?ang:-135}deg);transition:transform 1.2s cubic-bezier(.2,.9,.25,1.05)" data-a="${ang}"><path d="M50 52 L48.6 50 L50 17 L51.4 50Z" fill="#fff"/></g>
 <circle cx="50" cy="52" r="4.5" fill="#2a3038" stroke="#fff" stroke-width="1"/>${lv}
 <text x="50" y="74" fill="#fff" font-size="10" text-anchor="middle" font-family="B612 Mono">${fmt(s.rsi,0)}</text>
 <text x="50" y="87" fill="#fff" font-size="11" text-anchor="middle" font-weight="700">${s.ticker.replace('-USD','')}</text>${s.market==='crypto'?'<text x="12" y="14" fill="#3fd0ff" font-size="8.5">24/7</text>':''}</svg>
 <div class="rd"><span>1M <b>${pct(s.r1m)}</b></span><span>hi <b>${pct(s.off_high,0)}</b></span></div></button>`}).join('');
 document.querySelectorAll('.gauge').forEach(g=>g.onclick=()=>{sel=g.dataset.t;pfd();gauges()});
 if(!RM)requestAnimationFrame(()=>requestAnimationFrame(()=>document.querySelectorAll('.needle').forEach(n=>n.style.transform=`rotate(${n.dataset.a}deg)`)))}

/* ---------------- systems (pattern leaderboard as ECAM) */
function systems(){const rows=D.stats.filter(r=>r.ticker==='ALL'&&r.tf===sysTf);
 const good=rows.filter(r=>ORD[r.grade]<=1).sort((a,b)=>b.expectancy_R-a.expectancy_R).slice(0,12);
 const bad=rows.filter(r=>r.grade==='F'&&r.n>=50).sort((a,b)=>a.expectancy_R-b.expectancy_R).slice(0,6);
 const mx=Math.max(.01,...good.map(r=>r.expectancy_R));
 const line=r=>`<span class="nm"><a href="${gl(r.pattern)}">${r.pattern}</a></span><span><span class="gr g${r.grade}">${r.grade}</span></span>
  <span class="bar"><i style="width:${clamp(r.expectancy_R/mx*100,2,100)}%;background:${r.direction==='LONG'?C.grn:C.red}"></i></span><span class="mono" style="text-align:right">${r.expectancy_R>0?'+':''}${fmt(r.expectancy_R)}R</span>`;
 $('#sys').innerHTML=`<h3 class="ok">Normal — best performers</h3><div class="sys">${good.map(line).join('')||'<span class="empty">None yet</span>'}</div>
 <h3>Caution — losing patterns, don't trade</h3><div class="sys">${bad.map(r=>`<span class="nm"><a href="${gl(r.pattern)}">${r.pattern}</a></span><span><span class="gr gF">F</span></span><span class="mono" style="color:var(--dim);font-size:12px">${r.direction.toLowerCase()} · n=${r.n}</span><span class="mono" style="text-align:right">${fmt(r.expectancy_R)}R</span>`).join('')||'<span class="empty">None</span>'}</div>`}

/* ---------------- checklist (validation) */
function checklist(){if(!D.verdicts.length){$('#chk').innerHTML='<div class="empty">The S&amp;P 500 validation hasn\'t finished yet. This checklist fills in automatically after the Sunday run.</div>';return}
 const grp=v=>D.verdicts.filter(x=>x.verdict===v);
 const item=(x,mark,c)=>`<div><span style="color:${c};width:14px;display:inline-block">${mark}</span><a href="${gl(x.pattern)}" style="color:#fff;text-decoration:none">${x.pattern}</a> <span style="color:var(--dim);font-size:12px">${x.tf} ${x.direction.toLowerCase()}</span><span class="dots" style="flex:1"></span></div><span class="mono">${x.uni_R_net>0?'+':''}${fmt(x.uni_R_net)}R</span>`;
 const conf=grp('Confirmed'),prom=grp('Promising');
 const cnt={};D.verdicts.forEach(v=>cnt[v.verdict]=(cnt[v.verdict]||0)+1);
 $('#chk').innerHTML=`<h3 class="ok">Confirmed — works on ~500 stocks, after costs, in recent years</h3><div class="chk">${conf.slice(0,10).map(x=>item(x,'✓',C.grn)).join('')||'<span class="empty">None passed every test yet.</span>'}</div>
 <h3 class="cy">Promising — not yet statistically proven</h3><div class="chk">${prom.slice(0,8).map(x=>item(x,'○',C.cyn)).join('')||'<span class="empty">None</span>'}</div>
 <h3>Rejected</h3><div class="chk">${['Watchlist only','Faded out-of-sample','Costs kill it','No edge'].map(k=>`<div>${k}<span class="dots" style="flex:1"></span></div><span class="mono">${cnt[k]||0}</span>`).join('')}</div>`}

/* ---------------- fuel + payouts */
function fuel(){const rows=D.profiles.filter(p=>p.tf==='1d'&&p.now&&p.now.state);
 $('#fuel').innerHTML=rows.map(p=>{const n=p.now,pull=/pull/.test(n.state);const v=pull?clamp(n.deeper_than_pct_of_history||0,0,100):0;
  const c=v>=90?C.red:v>=75?C.amb:C.grn;return `<span>${p.ticker}</span><span class="tank" title="${n.state}"><i style="width:${pull?v:100}%;background:${pull?c:'#1d3a2a'}"></i>${pull?'':`<u style="left:0"></u>`}</span>
  <span class="mono" style="text-align:right">${pull?fmt(v,0)+'%':'rising'}</span>`}).join('')}
function payouts(){const ds=D.snapshots.filter(s=>s.dividends&&s.dividends.last_amount!=null).sort((a,b)=>(b.dividends.frequency==='weekly')-(a.dividends.frequency==='weekly'));
 if(!ds.length){$('#pay').innerHTML='<div class="empty">No distributions on record.</div>';return}
 const top=ds[0],d=top.dividends,mult={weekly:52,monthly:12,quarterly:4}[d.frequency]||0,y=mult?mult*d.last_amount/top.close*100:null;
 const rec=(d.recent||[]).slice(0,8).reverse(),mx=Math.max(...rec.map(r=>r.amount));
 const bars=rec.map((r,i)=>`<rect x="${i*30+4}" y="${60-r.amount/mx*52}" width="22" height="${r.amount/mx*52}" rx="2" fill="${C.cyn}" opacity="${i===rec.length-1?1:.55}"><title>${r.date} $${r.amount}</title></rect>`).join('');
 $('#pay').innerHTML=`<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><div><div class="sub">${top.ticker} · ${d.name||''}</div>
  <div class="big mono">$${fmt(d.last_amount,3)}</div><div class="sub">latest ${d.frequency} payout · ex-date ${d.last_date}</div></div>
  <div style="text-align:right"><div class="big mono">${y?fmt(y,1)+'%':'–'}</div><div class="sub">run-rate yield at $${fmt(top.close)}</div></div></div>
  <svg viewBox="0 0 ${rec.length*30+8} 64" style="width:100%;height:84px;margin-top:10px" role="img" aria-label="Recent payouts">${bars}</svg>
  <div class="sub" style="margin-top:6px">${ds.slice(1).map(s=>`${s.ticker} $${fmt(s.dividends.last_amount,2)} ${s.dividends.frequency}`).join(' · ')}</div>`}

$('#foot').innerHTML=`Patterns are tendencies from history, not promises. Win = target hit before stop. R = profit measured in risk units (+0.30R ≈ +$30 per $100 risked). Data: ${D.coverage.length} ticker/timeframe series from Yahoo Finance.`;
segs();pfd();radar();gauges();systems();checklist();fuel();payouts();
</script></body></html>"""
