"""Build the visual Pattern Guide page (drawings + plain-English explanations + live backtest stats)."""
from __future__ import annotations

import json
import re

import pandas as pd

from .guide_content import G


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build(stats: pd.DataFrame, generated: str, verdicts=None) -> str:
    st = {}
    if stats is not None and len(stats):
        pooled = stats[stats.ticker == "ALL"]
        for r in pooled.itertuples():
            st.setdefault(r.pattern, {})[r.tf] = dict(n=int(r.n), win=float(r.target_pct), R=float(r.expectancy_R),
                                                       g=r.grade, bars=None if pd.isna(r.bars_to_target_med)
                                                       else float(r.bars_to_target_med))
    vd = {}
    if verdicts is not None and len(verdicts):
        for r in verdicts.itertuples():
            vd.setdefault(r.pattern, {})[r.tf] = r.verdict
    for g in G:
        g["anchors"] = [slug(n) for n in g["bull"] + g["bear"]]
    payload = dict(guide=G, stats=st, generated=generated, verdicts=vd)
    return TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pattern Guide</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0a0b;--panel:#121214;--panel2:#18181b;--line:#26262b;--text:#fff;--sub:#d4d4d8;--accent:#8b5cf6;--g:#22c55e;--r:#ef4444;--y:#facc15}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 Inter,system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}a{color:#fff}
h1{font-size:28px;margin:0;font-weight:700}h1 span{color:var(--accent)}
.sub{color:var(--sub);font-size:14.5px}
.intro{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin:18px 0}
.box{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
.box h3{margin:0 0 6px;font-size:17px}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 6px;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:2}
.pill{background:var(--panel2);border:1px solid var(--line);color:#fff;border-radius:999px;padding:8px 14px;font:inherit;font-size:14px;cursor:pointer}
.pill.on{background:var(--accent);border-color:var(--accent)}
input{background:var(--panel2);color:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 14px;font:inherit;font-size:14px;flex:1;min-width:160px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;margin-top:8px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px;scroll-margin-top:80px}
.card:target{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent)}
.card h2{font-size:19px;margin:0 0 2px}
.tag{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:#27272a;border-radius:6px;padding:2px 8px}
svg{width:100%;height:auto;display:block;margin:10px 0 6px;background:#0d0d0f;border-radius:12px;border:1px solid var(--line)}
.q{font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:#fff;margin-top:12px;opacity:.75}
p{margin:2px 0 0}
.flip{font-size:14px;color:var(--sub);margin-top:10px;font-style:italic}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:13.5px}
th,td{padding:6px 6px;border-top:1px solid var(--line);text-align:center}th{font-weight:600;color:#fff}
td:first-child,th:first-child{text-align:left}
.g{display:inline-block;min-width:30px;padding:1px 6px;border-radius:6px;font-weight:700;font-size:12px;color:#fff}
.gA{background:#16a34a}.gB{background:#2563eb}.gC{background:#a16207}.gF{background:#7f1d1d}.glow-n{background:#3f3f46}
.mono{font-family:'JetBrains Mono',monospace}.dim{color:var(--sub)}
.verdict{margin-top:10px;font-weight:600;font-size:14.5px}
@media(max-width:700px){.intro{grid-template-columns:1fr}.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<a href="./" class="sub">← back to the report</a>
<h1 style="margin-top:6px">Pattern <span>Guide</span></h1>
<div class="sub" id="meta"></div>
<div class="intro">
 <div class="box"><h3>How to read a candle</h3>
 <p>Each candle is one period of time (an hour, a day, or a week). <b>Green</b> = price ended higher than it started. <b>Red</b> = it ended lower. The thick part (body) is from where it started to where it ended. The thin lines (wicks) show the highest and lowest prices during that time.</p>
 <svg viewBox="0 0 320 130" id="candleIntro"></svg></div>
 <div class="box"><h3>How to read the scores</h3>
 <p><b>Grade</b> = how well this pattern actually worked on your 11 stocks over many years. <span class="g gA">A</span> works well and consistently. <span class="g gB">B</span> decent. <span class="g gC">C</span> barely. <span class="g gF">F</span> loses money. <span class="g glow-n">low-n</span> not enough examples yet.</p>
 <p style="margin-top:8px"><b>Win %</b> = how often price reached the goal before hitting the stop. <b>R</b> = average profit per trade measured in "risk units": +0.30R means if you risk $100 each time, you average about +$30.</p></div>
</div>
<div class="controls">
 <button class="pill on" data-f="">All</button><button class="pill" data-f="chart">Chart shapes</button>
 <button class="pill" data-f="candle">Candles</button><button class="pill" data-f="setup">Indicator setups</button>
 <button class="pill" id="works">Only ones that work</button><input id="q" placeholder="Search a pattern">
</div>
<div class="grid" id="grid"></div>
</div>
<script>
const D=/*__DATA__*/null;
document.getElementById('meta').textContent=`${D.guide.length} pattern families · scores updated ${D.generated} from your watchlist`;
const COL={w:'#ffffff',g:'#22c55e',r:'#ef4444',p:'#a78bfa',y:'#facc15'};
const W=320,H=170,PAD=14;
const X=x=>PAD+x/100*(W-2*PAD), Y=(y,h=H,top=PAD,bot=PAD)=>top+(1-y/100)*(h-top-bot);
function txt(x,y,s,c='#fff',a='start'){return `<text x="${x}" y="${y}" fill="${c}" font-size="11" font-family="Inter" text-anchor="${a}" font-weight="600">${s}</text>`}
function poly(pts,c,w=2.5,dash=''){return `<polyline points="${pts.map(p=>X(p[0])+','+Y(p[1])).join(' ')}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round" ${dash?`stroke-dasharray="${dash}"`:''}/>`}
function draw(d){let s='',hTot=d.panel?240:H;
 (d.lines||[]).forEach(([x1,y1,x2,y2,st,c,l])=>{s+=`<line x1="${X(x1)}" y1="${Y(y1)}" x2="${X(x2)}" y2="${Y(y2)}" stroke="${COL[c]}" stroke-width="1.6" ${st==='dash'?'stroke-dasharray="5 4"':''} opacity=".9"/>`;if(l)s+=txt(X(x1)+2,Y(y1)+(y1<35?14:-6),l,COL[c],'start')});
 (d.ma||[]).forEach(([pts,c,l],i)=>{s+=poly(pts,COL[c],2,'');const e=pts[pts.length-1];s+=txt(X(e[0])-2,Y(e[1])+(i%2?14:-6),l,COL[c],'end')});
 if(d.path)s+=poly(d.path,d.ma?'#71717a':'#e4e4e7',d.ma?2:2.6)+(d.ma?txt(X(d.path[0][0])+2,Y(d.path[0][1])-6,'price','#a1a1aa'):'');
 if(d.candles){const n=d.candles.length,lo=Math.min(...d.candles.map(c=>c[2])),hi=Math.max(...d.candles.map(c=>c[1]));
  const sc=v=>Y((v-lo)/(hi-lo||1)*80+10),bw=Math.min(26,(W-2*PAD)/n*0.55);
  d.candles.forEach(([o,h,l,c,f],i)=>{const cx=PAD+(i+0.5)*(W-2*PAD)/n,up=c>=o,col=up?'#22c55e':'#ef4444',op=f?1:.35;
   s+=`<line x1="${cx}" y1="${sc(h)}" x2="${cx}" y2="${sc(l)}" stroke="${col}" stroke-width="2" opacity="${op}"/>`;
   const t=sc(Math.max(o,c)),b=sc(Math.min(o,c));s+=`<rect x="${cx-bw/2}" y="${t}" width="${bw}" height="${Math.max(2,b-t)}" rx="2" fill="${col}" opacity="${op}"/>`});
  const fi=d.candles.map((c,i)=>c[4]?i:-1).filter(i=>i>=0);if(fi.length){const a=PAD+fi[0]*(W-2*PAD)/n,b=PAD+(fi[fi.length-1]+1)*(W-2*PAD)/n;
   s=`<rect x="${a+2}" y="6" width="${b-a-4}" height="${H-12}" rx="8" fill="#8b5cf6" opacity=".12"/>`+s+txt((a+b)/2,H-2,'the pattern','#c4b5fd','middle')}}
 if(d.arrow){const[x,y,dir]=d.arrow,cx=X(x),cy=Y(y),up=dir==='up',c=up?'#22c55e':'#ef4444',dy=up?-1:1;
  s+=`<path d="M${cx-7} ${cy} L${cx} ${cy+dy*12} L${cx+7} ${cy} Z" fill="${c}"/><circle cx="${cx}" cy="${cy-dy*4}" r="3" fill="${c}"/>`}
 if(d.panel){const top=H+8,bot=8,ph=hTot;const PY=y=>top+(1-y/100)*(ph-top-bot);
  s+=`<rect x="${PAD-6}" y="${top-4}" width="${W-2*PAD+12}" height="${ph-top-bot+8}" rx="8" fill="#141418" stroke="#26262b"/>`;
  (d.panel.levels||[]).forEach(([y,l])=>{s+=`<line x1="${X(0)}" x2="${X(100)}" y1="${PY(y)}" y2="${PY(y)}" stroke="#71717a" stroke-dasharray="4 4"/>`+txt(X(0)+2,PY(y)-3,l,'#a1a1aa')});
  (d.panel.lines||[]).forEach(([pts,c,l],i)=>{s+=`<polyline points="${pts.map(p=>X(p[0])+','+PY(p[1])).join(' ')}" fill="none" stroke="${COL[c]}" stroke-width="2.2"/>`;const e=pts[pts.length-1];s+=txt(X(e[0])-2,PY(e[1])+(i%2?14:-6),l,COL[c],'end')});
  (d.panel.marks||[]).forEach(([x1,y1,x2,y2,c,l])=>{s+=`<line x1="${X(x1)}" y1="${PY(y1)}" x2="${X(x2)}" y2="${PY(y2)}" stroke="${COL[c]}" stroke-width="2"/>`+txt(X(x2)+4,PY(y2)+4,l,COL[c])})}
 return `<svg viewBox="0 0 ${W} ${hTot}" role="img">${s}</svg>`}
document.getElementById('candleIntro').outerHTML=`<svg viewBox="0 0 320 130">
 <line x1="90" y1="12" x2="90" y2="118" stroke="#22c55e" stroke-width="2.5"/><rect x="74" y="34" width="32" height="58" rx="3" fill="#22c55e"/>
 <line x1="230" y1="12" x2="230" y2="118" stroke="#ef4444" stroke-width="2.5"/><rect x="214" y="34" width="32" height="58" rx="3" fill="#ef4444"/>
 ${txt(112,16,'highest price')}${txt(112,38,'close (ended here)')}${txt(112,94,'open (started here)')}${txt(112,120,'lowest price')}
 ${txt(252,38,'open')}${txt(252,94,'close')}</svg>`;
const ORD={A:0,B:1,C:2,'low-n':3,F:4};
function best(names){let b=null;names.forEach(n=>Object.values(D.stats[n]||{}).forEach(s=>{if(s.n>=20&&(!b||ORD[s.g]<ORD[b.g]||(s.g===b.g&&s.R>b.R)))b={...s,name:n}}));return b}
const VS={"Confirmed":"✅ confirmed","Promising":"🔵 promising","Watchlist only":"⚠️ your picks only","Faded out-of-sample":"📉 faded","Costs kill it":"💸 costs","No edge":"✖ no edge","Too few trades":""};
function chip(s,v){if(!s)return'<span class="dim">–</span>';return `<span class="g g${s.g}">${s.g}</span><br><span class="mono">${s.win.toFixed(0)}% · ${s.R>=0?'+':''}${s.R.toFixed(2)}R</span><br><span class="dim" style="font-size:11.5px">n=${s.n}</span>${v&&VS[v]?`<br><span style="font-size:11.5px">${VS[v]}</span>`:''}`}
function card(g){const rows=[...g.bull.map(n=>[n,'▲','#22c55e']),...g.bear.map(n=>[n,'▼','#ef4444'])];
 const b=best([...g.bull,...g.bear]);
 const verdict=b?(ORD[b.g]<=1?`✅ Works best: <b>${b.name}</b> — ${b.win.toFixed(0)}% win, ${b.R>=0?'+':''}${b.R.toFixed(2)}R per trade`:ORD[b.g]===2?'⚠️ Barely profitable on your stocks — not worth trading alone':'❌ Has lost money on your stocks — don\'t trade it'):'<span class="dim">Not enough history yet</span>';
 return `<div class="card" id="${g.id}" data-f="${g.family}" data-w="${b&&ORD[b.g]<=1?1:0}">${g.anchors.map(a=>`<span id="${a}"></span>`).join('')}
 <span class="tag">${g.family==='chart'?'Chart shape':g.family==='candle'?'Candle':'Indicator setup'}</span><h2>${g.title}</h2>
 ${draw(g.draw)}
 <div class="q">What you see</div><p>${g.what}</p>
 <div class="q">What it means</div><p>${g.means}</p>
 <div class="q">How traders use it</div><p>${g.trade}</p>
 ${g.flip?`<div class="flip">${g.flip}</div>`:''}
 <div class="verdict">${verdict}</div>
 <table><tr><th>Your stocks</th><th>Hourly<br><span class="dim" style="font-weight:400">day trade</span></th><th>Daily<br><span class="dim" style="font-weight:400">swing</span></th><th>Weekly<br><span class="dim" style="font-weight:400">hold</span></th></tr>
 ${rows.map(([n,a,c])=>`<tr><td><span style="color:${c}">${a}</span> ${n}</td>${['1h','1d','1wk'].map(tf=>`<td>${chip((D.stats[n]||{})[tf],(D.verdicts[n]||{})[tf])}</td>`).join('')}</tr>`).join('')}</table></div>`}
let F='',onlyW=false;
function render(){const q=document.getElementById('q').value.toLowerCase();
 document.getElementById('grid').innerHTML=D.guide.filter(g=>(!F||g.family===F)&&(!q||(g.title+g.bull.join()+g.bear.join()+g.what).toLowerCase().includes(q))).map(card).join('');
 if(onlyW)document.querySelectorAll('.card[data-w="0"]').forEach(c=>c.style.display='none')}
document.querySelectorAll('.pill[data-f]').forEach(b=>b.onclick=()=>{F=b.dataset.f;document.querySelectorAll('.pill[data-f]').forEach(x=>x.classList.toggle('on',x===b));render()});
document.getElementById('works').onclick=e=>{onlyW=!onlyW;e.target.classList.toggle('on',onlyW);render()};
document.getElementById('q').oninput=render;render();
if(location.hash){const el=document.getElementById(location.hash.slice(1));if(el)setTimeout(()=>el.closest('.card').scrollIntoView({block:'start'}),50)}
</script></body></html>"""
