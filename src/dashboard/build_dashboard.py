"""
Stage 11: self-contained interactive dashboard (docs/index.html).

Single HTML file, no external libraries or CDNs: works offline and on GitHub Pages.
All numbers are read from pipeline outputs at build time.
"""
import json

import numpy as np
import pandas as pd

import config
from src.common import get_logger

log = get_logger("build_dashboard")
OUT = config.ROOT / "docs" / "index.html"


def clean(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 1)
    return v


def build_payload() -> dict:
    master = pd.read_csv(config.COMPANIES_MASTER)
    idx = pd.read_csv(config.TECH_INDEX, low_memory=False)
    startup = pd.read_csv(config.COMPANY_STARTUP_SCORES)
    coverage = pd.read_csv(config.COVERAGE_REPORT)
    results = pd.read_csv(config.REGRESSION_RESULTS)

    latest = idx[idx["year"] == max(config.INDEX_YEARS)].merge(
        master[["company_id", "sic_description", "country", "exchange"]], on="company_id", how="left"
    ).merge(startup[["company_id", "technology_categories"]], on="company_id", how="left")
    series = idx.pivot(index="company_id", columns="year", values="technology_disruption_index")

    rows = []
    for r in latest.itertuples(index=False):
        hist = series.loc[r.company_id].tolist() if r.company_id in series.index else []
        rows.append([
            int(r.company_id), r.company_name, clean(r.ticker), clean(r.industry),
            clean(r.sic_description), clean(r.country), clean(r.exchange),
            clean(r.technology_disruption_index), clean(r.startup_score), clean(r.patent_score),
            int(r.components_available), clean(r.startup_coverage_flag),
            clean(r.technology_categories), [clean(v) for v in hist],
        ])

    by_industry = (latest.dropna(subset=["industry", "technology_disruption_index"])
                   .groupby("industry")["technology_disruption_index"]
                   .agg(avg="mean", n="count").reset_index().sort_values("avg", ascending=False))
    main = results[results["spec"].str.startswith("main_") | results["spec"].str.startswith("horizon")]
    cov = coverage[coverage["scope"] == "any_year"].iloc[0].to_dict()

    return {
        "fields": ["id", "name", "ticker", "industry", "sic", "country", "exchange", "tdi",
                   "startup", "patent", "components", "flag", "categories", "history"],
        "years": config.INDEX_YEARS,
        "companies": rows,
        "industries": [[r.industry, round(float(r.avg), 1), int(r.n)]
                       for r in by_industry.itertuples(index=False)],
        "coverage": {k: clean(v) for k, v in cov.items()},
        "results": [{k: clean(v) for k, v in r.items()} for r in main[
            ["model", "outcome", "spec", "horizon", "coef", "std_err", "p_value", "n_obs",
             "n_firms"]].to_dict("records")],
        "weights": config.INDEX_WEIGHTS,
    }


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Technology Disruption Index</title>
<style>
:root{--bg:#0f1420;--panel:#171e2e;--line:#273047;--text:#e6e9f0;--muted:#8d97ad;--acc:#5b9cff;--acc2:#3ddc97;--warn:#ffb454}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{padding:28px 32px 8px}h1{margin:0;font-size:26px}h2{font-size:16px;margin:0 0 12px}
.sub{color:var(--muted);max-width:900px}.wrap{padding:16px 32px 48px;display:grid;gap:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.card .v{font-size:24px;font-weight:600}.card .l{color:var(--muted);font-size:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
input,select{background:#0c111b;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:7px 10px;font:inherit}
input{flex:1;min-width:200px}table{width:100%;border-collapse:collapse}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:500;cursor:pointer;user-select:none}tbody tr{cursor:pointer}tbody tr:hover{background:#1d2539}
td.num,th.num{text-align:right}.bar{display:inline-block;height:8px;border-radius:4px;background:var(--acc);vertical-align:middle;margin-left:6px}
.muted{color:var(--muted)}.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;background:#222b40;margin:2px 4px 2px 0}
.pager{display:flex;gap:8px;align-items:center;margin-top:10px}button{background:#222b40;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:5px 12px;cursor:pointer}
.tablewrap{overflow-x:auto}.note{color:var(--muted);font-size:12px}.sig{color:var(--acc2)}.na{color:var(--warn)}
svg text{fill:var(--muted);font-size:11px}
</style></head><body>
<header><h1>Technology Disruption Index</h1>
<p class="sub">A reproducible proxy signal of technology-disruption exposure for SEC-registered public companies,
combining patent activity and startup-ecosystem activity in each company's technology domains.
It is a measurable signal, not a measurement of "true" disruption. Scores are 0-100.</p></header>
<div class="wrap">
<div class="cards" id="cards"></div>
<div class="panel"><h2>Companies</h2>
<div class="controls"><input id="q" placeholder="Search company or ticker...">
<select id="ind"><option value="">All industries</option></select>
<select id="cov"><option value="">All coverage</option><option value="2">Both components</option><option value="1">One component</option><option value="0">No data</option></select></div>
<div class="tablewrap"><table><thead><tr>
<th data-k="name">Company</th><th data-k="ticker">Ticker</th><th data-k="industry">Industry</th>
<th data-k="tdi" class="num">Index</th><th data-k="startup" class="num">Startup</th><th data-k="patent" class="num">Patent</th><th data-k="flag">Coverage</th>
</tr></thead><tbody id="tb"></tbody></table></div>
<div class="pager"><button id="prev">&larr;</button><span id="pg" class="muted"></span><button id="next">&rarr;</button></div></div>
<div class="grid2">
<div class="panel" id="detail"><h2>Company detail</h2><p class="muted">Click a company in the table.</p></div>
<div class="panel"><h2>Distribution of the index (latest year)</h2><div id="hist"></div>
<p class="note">Spike at 0 = industries the documented SIC mapping does not link to any tracked technology category.</p></div>
</div>
<div class="grid2">
<div class="panel"><h2>Average index by industry</h2><div id="inds"></div></div>
<div class="panel"><h2>Does the index predict outcomes? (year FE, t &rarr; t+1)</h2><div class="tablewrap" id="res"></div>
<p class="note">Coefficients per 10 index points, SEs clustered by company. Predictive associations, not causal effects.
<span class="sig">Green</span> = p &lt; 0.05.</p></div>
</div>
<div class="panel note"><b>Limitations.</b> Patent data currently cover very few firms, so for most companies the index equals the
startup-ecosystem component, which is an industry-level exposure measure. Universe = today's listed companies (survivorship bias).
"Coverage" flags show where data are missing; missing is never treated as zero. Full methodology in the project README.</div>
</div>
<script>
const D = __DATA__;
const F = D.fields, C = D.companies.map(r => Object.fromEntries(F.map((f,i)=>[f,r[i]])));
const fmt = v => v===null||v===undefined ? '<span class="muted">-</span>' : v.toFixed(1);
const pct = (a,b) => (100*a/b).toFixed(1)+'%';
const cv = D.coverage;
const cards = [["Companies", cv.total_companies.toLocaleString()],["Index available", pct(cv.index_coverage, cv.total_companies)],
 ["Startup component", pct(cv.startup_coverage, cv.total_companies)],["Patent component", pct(cv.patent_coverage, cv.total_companies)],
 ["Years", D.years[0]+"-"+D.years[D.years.length-1]],["Weights (patent/startup)", D.weights.patent_score+" / "+D.weights.startup_score]];
document.getElementById('cards').innerHTML = cards.map(c=>`<div class="card"><div class="v">${c[1]}</div><div class="l">${c[0]}</div></div>`).join('');

const ind = document.getElementById('ind');
[...new Set(C.map(c=>c.industry).filter(Boolean))].sort().forEach(i=>ind.insertAdjacentHTML('beforeend',`<option>${i}</option>`));
let sortK='tdi', sortDir=-1, page=0; const PER=25;
function filtered(){
  const q=document.getElementById('q').value.trim().toLowerCase(), iv=ind.value, cov=document.getElementById('cov').value;
  let r=C.filter(c=>(!q||c.name.toLowerCase().includes(q)||(c.ticker||'').toLowerCase().includes(q))&&(!iv||c.industry===iv)&&(cov===''||c.components==+cov));
  return r.sort((a,b)=>{const x=a[sortK],y=b[sortK]; if(x===null||x===undefined)return 1; if(y===null||y===undefined)return -1; return (x>y?1:x<y?-1:0)*sortDir;});
}
function esc(s){return String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
function render(){
  const r=filtered(), pages=Math.max(1,Math.ceil(r.length/PER)); page=Math.min(page,pages-1);
  document.getElementById('tb').innerHTML=r.slice(page*PER,(page+1)*PER).map(c=>`<tr data-id="${c.id}">
   <td>${esc(c.name)}</td><td>${esc(c.ticker)}</td><td class="muted">${esc(c.industry)}</td>
   <td class="num">${fmt(c.tdi)}${c.tdi!==null?`<span class="bar" style="width:${c.tdi*0.6}px"></span>`:''}</td>
   <td class="num">${fmt(c.startup)}</td><td class="num">${fmt(c.patent)}</td><td class="muted">${esc(c.flag)}</td></tr>`).join('');
  document.getElementById('pg').textContent=`${r.length.toLocaleString()} companies - page ${page+1}/${pages}`;
}
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k; sortDir = sortK===k ? -sortDir : (['name','ticker','industry','flag'].includes(k)?1:-1); sortK=k; render();});
['q','ind','cov'].forEach(id=>document.getElementById(id).oninput=()=>{page=0;render();});
document.getElementById('prev').onclick=()=>{page=Math.max(0,page-1);render();};
document.getElementById('next').onclick=()=>{page++;render();};
document.getElementById('tb').onclick=e=>{const tr=e.target.closest('tr'); if(tr) detail(C.find(c=>c.id==tr.dataset.id));};

function line(values){
  const W=640,H=200,P=30, ys=D.years, pts=values.map((v,i)=>v===null?null:[P+i*(W-2*P)/(ys.length-1), H-P-(v/100)*(H-2*P)]);
  let path='', open=false; pts.forEach(p=>{ if(!p){open=false;return;} path+=(open?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1); open=true; });
  const grid=[0,50,100].map(g=>{const y=H-P-(g/100)*(H-2*P); return `<line x1="${P}" x2="${W-P}" y1="${y}" y2="${y}" stroke="#273047"/><text x="4" y="${y+4}">${g}</text>`}).join('');
  const xl=ys.map((y,i)=>i%3===0?`<text x="${P+i*(W-2*P)/(ys.length-1)-12}" y="${H-8}">${y}</text>`:'').join('');
  const dots=pts.filter(Boolean).map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="2.5" fill="#5b9cff"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%">${grid}${xl}<path d="${path}" fill="none" stroke="#5b9cff" stroke-width="2"/>${dots}</svg>`;
}
function detail(c){
  const cats=(c.categories||'').split(';').map(s=>s.trim()).filter(Boolean).map(s=>`<span class="pill">${esc(s)}</span>`).join('') || '<span class="muted">none linked</span>';
  document.getElementById('detail').innerHTML=`<h2>${esc(c.name)} <span class="muted">${esc(c.ticker)}</span></h2>
   <p class="muted">${esc(c.sic)} &middot; ${esc(c.country)} &middot; ${esc(c.exchange)}</p>
   <div class="cards"><div class="card"><div class="v">${fmt(c.tdi)}</div><div class="l">Index ${D.years[D.years.length-1]}</div></div>
   <div class="card"><div class="v">${fmt(c.startup)}</div><div class="l">Startup score</div></div>
   <div class="card"><div class="v">${fmt(c.patent)}</div><div class="l">Patent score</div></div></div>
   <p>Technology exposure: ${cats}</p><p class="note">Components available: ${c.components} / 2 &middot; coverage flag: ${esc(c.flag)}</p>
   ${line(c.history)}`;
}
(function hist(){
  const b=new Array(10).fill(0); let zero=0; C.forEach(c=>{ if(c.tdi===null)return; if(c.tdi===0){zero++;return;} b[Math.min(9,Math.floor(c.tdi/10))]++; });
  const bins=[['0',zero],...b.map((n,i)=>[`${i*10}-${i*10+10}`,n])], W=640,H=220,P=24, m=Math.max(...bins.map(x=>x[1])), bw=(W-2*P)/bins.length;
  document.getElementById('hist').innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%">`+bins.map((x,i)=>{const h=(x[1]/m)*(H-2*P-10);
   return `<rect x="${P+i*bw+2}" y="${H-P-h}" width="${bw-4}" height="${h}" rx="3" fill="${i===0?'#ffb454':'#5b9cff'}"/><text x="${P+i*bw+2}" y="${H-8}">${x[0]}</text><text x="${P+i*bw+2}" y="${H-P-h-4}">${x[1]}</text>`}).join('')+'</svg>';
})();
document.getElementById('inds').innerHTML='<table>'+D.industries.map(r=>`<tr><td>${esc(r[0])}</td><td class="num">${r[1].toFixed(1)}<span class="bar" style="width:${r[1]*1.2}px"></span></td><td class="num muted">n=${r[2]}</td></tr>`).join('')+'</table>';
(function res(){
  const pick=D.results.filter(r=>r.spec==='main_year'), lab={M1:'ln public float',M1b:'valuation change',M2:'revenue growth',M3:'R&D / assets',M4:'CAPEX / assets'};
  document.getElementById('res').innerHTML='<table><tr><th>Model</th><th>Outcome (t+1)</th><th class="num">Coef</th><th class="num">p</th><th class="num">N</th></tr>'+
   pick.map(r=>`<tr><td>${r.model}</td><td>${lab[r.model]||esc(r.outcome)}</td><td class="num ${r.p_value<0.05?'sig':''}">${r.coef.toFixed(4)}</td><td class="num">${r.p_value<0.001?'<0.001':r.p_value.toFixed(3)}</td><td class="num">${r.n_obs.toLocaleString()}</td></tr>`).join('')+'</table>';
})();
render();
</script></body></html>
"""


def main() -> None:
    payload = build_payload()
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
    log.info("Dashboard: %d companies, %.1f MB -> %s", len(payload["companies"]),
             OUT.stat().st_size / 1e6, OUT)


if __name__ == "__main__":
    main()
