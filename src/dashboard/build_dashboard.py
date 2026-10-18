"""
Stage 11: static website (docs/index.html).

Single self-contained HTML file (no external libraries, fonts or CDNs). Deployable as-is to
Vercel, Netlify, Cloudflare Pages or GitHub Pages; works with a custom domain.
All numbers are read from pipeline outputs at build time.
"""
import hashlib
import html as html_lib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config
from src.common import get_logger
from src.dashboard import site_assets

log = get_logger("build_dashboard")
OUT_DIR = config.ROOT / "docs"
OUT = OUT_DIR / "index.html"


def clean(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 1)
    return v


def build_payload() -> dict:
    master = pd.read_csv(config.COMPANIES_MASTER, low_memory=False)
    idx = pd.read_csv(config.TECH_INDEX, low_memory=False)
    startup = pd.read_csv(config.COMPANY_STARTUP_SCORES)
    coverage = pd.read_csv(config.COVERAGE_REPORT)
    results = pd.read_csv(config.REGRESSION_RESULTS)
    n_startups = len(pd.read_csv(config.STARTUPS_CLEAN, usecols=["startup_id"]))

    latest = idx[idx["year"] == max(config.INDEX_YEARS)].merge(
        master[["company_id", "sic_description", "country", "exchange", "universe_source"]],
        on="company_id", how="left"
    ).merge(startup[["company_id", "technology_categories"]], on="company_id", how="left")
    series = idx.pivot(index="company_id", columns="year", values="technology_disruption_index")

    fin = pd.read_csv(config.FINANCIALS, usecols=["company_id", "year", "revenue", "assets", "rd",
                                                  "public_float", "cash"])
    fin = fin[fin["year"].isin(config.INDEX_YEARS)]
    money = ["revenue", "assets", "rd", "public_float", "cash"]
    fin[money] = (fin[money] / 1e6).round(1)
    rev_hist = fin.pivot(index="company_id", columns="year", values="revenue").reindex(
        columns=config.INDEX_YEARS)
    last_fin = (fin.dropna(subset=["revenue", "assets"], how="all")
                .sort_values("year").groupby("company_id").tail(1).set_index("company_id"))

    rows = []
    for r in latest.itertuples(index=False):
        hist = series.loc[r.company_id].tolist() if r.company_id in series.index else []
        f = last_fin.loc[r.company_id] if r.company_id in last_fin.index else None
        fvals = None if f is None else [int(f["year"])] + [clean(f[k]) for k in money]
        rh = (None if r.company_id not in rev_hist.index
              else [clean(v) for v in rev_hist.loc[r.company_id].tolist()])
        rows.append([
            int(r.company_id), r.company_name if isinstance(r.company_name, str) else f"CIK {r.company_id}",
            clean(r.ticker), clean(r.industry), clean(r.sic_description), clean(r.country),
            clean(r.exchange), clean(r.technology_disruption_index), clean(r.startup_score),
            clean(r.patent_score), int(r.components_available), clean(r.startup_coverage_flag),
            clean(r.technology_categories), [clean(v) for v in hist],
            1 if r.universe_source == "sec_ticker_list" else 0,
            None if fvals is None else fvals[1], fvals, rh,
        ])

    by_industry = (latest.dropna(subset=["industry", "technology_disruption_index"])
                   .groupby("industry")["technology_disruption_index"]
                   .agg(avg="mean", n="count").reset_index().sort_values("avg", ascending=False))
    yearly = idx.groupby("year")["technology_disruption_index"].mean().round(1)
    main = results[results["spec"].isin(["main_year", "main_year_sic2", "main_sic2xyear",
                                         "main_firm_year"])]
    cov = coverage[coverage["scope"] == "any_year"].iloc[0].to_dict()

    return {
        "fields": ["id", "name", "ticker", "industry", "sic", "country", "exchange", "tdi",
                   "startup", "patent", "components", "flag", "categories", "history", "listed",
                   "revenue", "fin", "rev"],
        "years": config.INDEX_YEARS,
        "companies": rows,
        "industries": [[r.industry, round(float(r.avg), 1), int(r.n)]
                       for r in by_industry.itertuples(index=False)],
        "yearly": [[int(y), float(v)] for y, v in yearly.items()],
        "coverage": {k: clean(v) for k, v in cov.items()},
        "results": [{k: (None if pd.isna(v) else (float(v) if k in ("coef", "std_err", "p_value")
                                                     else clean(v)))
                     for k, v in r.items()} for r in main[
            ["model", "spec", "coef", "std_err", "p_value", "n_obs", "n_firms"]].to_dict("records")],
        "weights": config.INDEX_WEIGHTS,
        "n_startups": n_startups,
        "n_fin": int(len(last_fin)),
        "n_patent": int(latest["patent_score"].notna().sum()),
        "n_listed": int((master["universe_source"] == "sec_ticker_list").sum()),
        "n_regressions": int(results["coef"].notna().sum()),
    }


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Technology Disruption Index — tech exposure scores for __NCOMP__ public companies</title>
<meta name="description" content="An open, reproducible index of technology-disruption exposure for __NCOMP__ SEC-registered companies, built from patents, startup-ecosystem activity and SEC fundamentals.">
<link rel="canonical" href="__SITE__/">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="theme-color" content="#0f172a">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Technology Disruption Index">
<meta property="og:url" content="__SITE__/">
<meta property="og:title" content="Technology Disruption Index — which companies are most exposed to tech disruption?">
<meta property="og:description" content="Tech-exposure scores for __NCOMP__ public companies, __Y0__–__Y1__, from 1.6M patents, 19,820 startups and SEC filings. Open data and research.">
<meta property="og:image" content="__SITE__/og-image.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="__SITE__/og-image.png">
<script type="application/ld+json">__LDJSON__</script>
<style>
__CSS__
</style></head><body>
<nav><div class="nav"><a class="logo" href="#"><img src="/favicon.svg" alt="" width="28" height="28">Technology Disruption Index</a>
<div class="links"><a href="#explore">Explore</a><a href="#research">Research</a><a href="#method">Methodology</a><a href="#about">Data</a><a class="gh" href="https://github.com/UmarovMirjalol/quantify" target="_blank" rel="noopener">GitHub</a></div></div></nav>

<header class="hero"><div>
<div class="eyebrow">Open research · __Y0__–__Y1__ · SEC filings, patents, startups</div>
<h1>Which companies are most exposed to <em>technological disruption?</em></h1>
<p class="lead">A transparent, reproducible index scoring __NCOMP__ SEC-registered companies on patent activity and startup-ecosystem activity in their technology domains — and a test of whether markets price it before fundamentals.</p>
<a class="btn p" href="#explore">Explore companies</a><a class="btn s" href="#research">See the research</a></div>
<aside class="finding"><div class="eyebrow">Key finding</div><div class="fig">+__FPCT__%</div>
<p>higher market valuation the following year for a company scoring 10 index points above its industry peers in the same year.</p>
<hr><p>But when a company’s own score rises over time, its valuation does not follow (p = __FIRMP__). Markets appear to price <i>which</i> firms are exposed, not changes in exposure.</p>
<p class="src">Lagged panel regressions, __NOBS__ firm-years, industry×year fixed effects, clustered SEs. Predictive, not causal.</p></aside>
</header>

<div class="wrap"><div class="stats" id="stats"></div>
<section id="explore"><div class="kicker">Explore</div><h2>Highest-scoring companies</h2>
<p class="sub">Index on a 0–100 scale for __Y1__. Cards show listed companies scored on both patents and startup activity; the table below covers all __NCOMP__. Click any company for its score history and fundamentals.</p>
<div class="top" id="top">__TOPHTML__</div>

<div class="card" style="margin-top:20px">
<div class="controls"><input id="q" placeholder="Search by company name or ticker…">
<select id="ind"><option value="">All industries</option></select>
<select id="cat"><option value="">All technologies</option></select>
<select id="lst"><option value="">All companies</option><option value="1">Currently listed</option><option value="0">Historical filers</option></select></div>
<div class="tw"><table><thead><tr><th data-k="name">Company</th><th data-k="ticker">Ticker</th><th data-k="industry">Industry</th>
<th data-k="tdi" class="r">Index</th><th data-k="startup" class="r">Startup</th><th data-k="patent" class="r">Patent</th><th data-k="revenue" class="r">Revenue</th></tr></thead><tbody id="tb">__ROWSHTML__</tbody></table></div>
<div class="pager"><span id="pg"></span>
<select id="per"><option value="25">25 per page</option><option value="50" selected>50 per page</option><option value="100">100 per page</option><option value="500">500 per page</option><option value="0">Show all</option></select>
<button id="first" title="First page">«</button><button id="prev" title="Previous page">←</button>
<span>Page <input id="pno" type="number" min="1" value="1"> of <b id="pmax">1</b></span>
<button id="next" title="Next page">→</button><button id="last" title="Last page">»</button></div></div>

<div class="g2" style="margin-top:20px"><div class="card" id="detail"><h3 style="margin:0">Company profile</h3><p class="muted">Select a company to see details.</p></div>
<div class="card"><h3 style="margin:0 0 6px">Score distribution</h3><div id="hist"></div><p class="small muted">Amber bar: industries not linked to any tracked technology category (score 0).</p></div></div>
</section>

<section id="research"><div class="kicker">Research</div><h2>Do markets price technology exposure before fundamentals?</h2>
<p class="sub">Lagged panel regressions: index in year t, outcomes in year t+1, standard errors clustered by company. Coefficients per 10 index points. These are predictive associations, not causal effects.</p>
<div class="g2"><div class="card"><div class="tw" id="res"></div><p class="small muted">Green = p &lt; 0.05. __NREG__ specifications in total incl. robustness checks; full results in the repository.</p></div>
<div class="card"><h3 style="margin:0 0 6px">Average index by industry</h3><div id="inds"></div></div></div>
<div class="note" style="margin-top:20px"><b>Read with care.</b> Patent data cover __NPAT__ companies — those whose patents could be linked to an SEC registrant. For the remaining firms the index reflects industry-level exposure to startup activity only; a blank patent score means “not linked”, not “zero patents”.</div>
</section>

<section id="method" class="method"><div class="kicker">Methodology</div><h2>How the index is built</h2>
<p class="sub">Every parameter lives in one configuration file; every company in the universe is kept, and missing data are never treated as zero.</p>
<div class="g3">
<div class="card"><div class="num">1</div><h3>Company universe</h3><p>__NCOMP__ SEC registrants: __NLISTED__ currently listed companies plus historical XBRL filers (reducing survivorship bias). Funds and SPAC shells are flagged.</p></div>
<div class="card"><div class="num">2</div><h3>Startup ecosystem</h3><p>__NSTART__ accelerator startups (YC, Techstars, Plug and Play, 500 Global, Antler, Alchemist, EF) tagged into 9 technology categories; activity is mapped to companies via documented SIC rules.</p></div>
<div class="card"><div class="num">3</div><h3>Patents</h3><p>US patent grants (USPTO PatentsView, linked to public firms by Ma, 2025, and to SEC CIKs) for __NPAT__ companies: log-scaled volume and 3-year momentum, so the largest patent holders do not dominate.</p></div>
<div class="card"><div class="num">4</div><h3>Normalization</h3><p>Within-year percentiles for startup exposure, fixed log anchors for patents, all on 0–100 and rounded to one decimal.</p></div>
<div class="card"><div class="num">5</div><h3>Index</h3><p>Weighted average of available components (default __WP__/__WS__). Each company-year reports components available and a coverage score.</p></div>
<div class="card"><div class="num">6</div><h3>Fundamentals</h3><p>Revenue, assets, R&D, CAPEX, cash, debt and public float from SEC XBRL, used to test predictive relationships with year, industry and firm fixed effects.</p></div>
</div></section>

<section id="about"><div class="kicker">Data</div><h2>Open and reproducible</h2>
<p class="sub">The full pipeline — data collection, scoring, validation and regressions — runs with one command. The index is a measurable proxy for technology exposure, not an objective measure of “true” disruption.</p>
<div class="card" style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between"><div><h3 style="margin:0">Download the data</h3><p class="muted small" style="margin:4px 0 0">Latest scores for all __NCOMP__ companies and the full regression results (CSV).</p></div>
<div><a class="btn p" href="data/company_technology_index_latest.csv" download>Index scores (CSV)</a><a class="btn s" href="data/regression_results.csv" download>Regression results</a></div></div></section>
</div>
<footer><div class="foot">
<div><a class="logo" href="#"><img src="/favicon.svg" alt="" width="28" height="28">Technology Disruption Index</a>
<p>An open, reproducible measure of technology exposure for __NCOMP__ public companies. Research project; not investment advice.</p></div>
<div><b>Explore</b><a href="#explore">Companies</a><a href="#research">Research results</a><a href="#method">Methodology</a><a href="data/company_technology_index_latest.csv">Download data (CSV)</a></div>
<div><b>Sources</b><a href="https://www.sec.gov/edgar" target="_blank" rel="noopener">SEC EDGAR</a><a href="https://www.uspto.gov/ip-policy/economic-research/patentsview" target="_blank" rel="noopener">USPTO PatentsView</a><a href="https://github.com/songma/patent-firm-link-share" target="_blank" rel="noopener">Patent–firm linkage (Ma, 2025)</a><a href="https://github.com/UmarovMirjalol/quantify" target="_blank" rel="noopener">Source code on GitHub</a></div>
</div></footer>

<script>
fetch('/data/site.json?v=__VER__').then(r=>r.json()).then(D=>{
const F=D.fields,C=D.companies.map(r=>Object.fromEntries(F.map((f,i)=>[f,r[i]])));
const $=id=>document.getElementById(id),fmt=v=>v==null?'<span class="muted">–</span>':v.toFixed(1);
const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const cv=D.coverage,pct=(a,b)=>Math.round(100*a/b)+'%';
const usd=v=>{if(v==null)return '<span class="muted">–</span>';const a=Math.abs(v),s=v<0?'−$':'$';return a>=1e6?s+(a/1e6).toFixed(2)+'T':a>=1e3?s+(a/1e3).toFixed(1)+'B':a>=1?s+a.toFixed(0)+'M':s+(a*1000).toFixed(0)+'K'};
$('stats').innerHTML=[[cv.total_companies.toLocaleString(),'companies in the universe'],[pct(cv.index_coverage,cv.total_companies),'with an index score'],[D.n_fin.toLocaleString(),'with SEC financials'],[D.n_startups.toLocaleString(),'startups analysed']]
 .map(s=>`<div class="stat"><b>${s[0]}</b><span>${s[1]}</span></div>`).join('');
const FL={sic_linked:'Industry linked to technology',"sic_linked+name":'Industry + company name',name_only:'Company name only',industry_unlinked:'Industry not linked (score 0)',missing_sic:'No industry data',uninformative_sic:'Industry code too broad'};
const cats=['AI','Fintech','Cloud','Robotics','Cybersecurity','Biotech','Semiconductors','Energy','Quantum'];
cats.forEach(c=>$('cat').insertAdjacentHTML('beforeend',`<option>${c}</option>`));
[...new Set(C.map(c=>c.industry).filter(Boolean))].sort().forEach(i=>$('ind').insertAdjacentHTML('beforeend',`<option>${esc(i)}</option>`));
$('top').innerHTML=C.filter(c=>c.tdi!=null&&c.listed&&c.components==2).sort((a,b)=>b.tdi-a.tdi||a.name.localeCompare(b.name)).slice(0,10)
 .map((c,i)=>`<div class="tc" data-id="${c.id}"><span class="rk">#${i+1}</span><div class="s">${c.tdi.toFixed(1)}</div><div class="bar"><i style="width:${c.tdi}%"></i></div><div class="n">${esc(c.name)}</div><div class="t">${esc(c.ticker)} · ${esc(c.industry)}</div></div>`).join('');
$('top').onclick=e=>{const t=e.target.closest('.tc');if(t){detail(C.find(c=>c.id==t.dataset.id));$('detail').scrollIntoView({behavior:'smooth',block:'center'})}};
let sortK='tdi',dir=-1,page=0;
function rows(){const q=$('q').value.trim().toLowerCase(),i=$('ind').value,c=$('cat').value,l=$('lst').value;
 return C.filter(x=>(!q||x.name.toLowerCase().includes(q)||(x.ticker||'').toLowerCase().includes(q))&&(!i||x.industry===i)&&(!c||(x.categories||'').includes(c+'='))&&(l===''||x.listed==+l))
 .sort((a,b)=>{const x=a[sortK],y=b[sortK];if(x==null)return 1;if(y==null)return -1;return(x>y?1:x<y?-1:0)*dir})}
function render(){const r=rows(),PER=+$('per').value||r.length||1,P=Math.max(1,Math.ceil(r.length/PER));page=Math.max(0,Math.min(page,P-1));
 $('tb').innerHTML=r.slice(page*PER,page*PER+PER).map(c=>`<tr data-id="${c.id}"><td>${esc(c.name)} ${c.listed?'':'<span class="badge">historical</span>'}</td><td>${esc(c.ticker)}</td><td class="muted">${esc(c.industry)}</td>
 <td class="r"><b>${fmt(c.tdi)}</b>${c.tdi!=null?`<span class="meter"><i style="width:${c.tdi}%"></i></span>`:''}</td><td class="r">${fmt(c.startup)}</td><td class="r">${fmt(c.patent)}</td><td class="r">${usd(c.revenue)}</td></tr>`).join('');
 const a=r.length?page*PER+1:0,b=Math.min(r.length,page*PER+PER);
 $('pg').textContent=`Showing ${a.toLocaleString()}–${b.toLocaleString()} of ${r.length.toLocaleString()} companies`;
 $('pno').value=page+1;$('pno').max=P;$('pmax').textContent=P.toLocaleString();
 $('first').disabled=$('prev').disabled=page===0;$('next').disabled=$('last').disabled=page>=P-1;
 document.querySelector('.tw').classList.toggle('scroll',PER>100)}
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;dir=sortK===k?-dir:(['name','ticker','industry'].includes(k)?1:-1);sortK=k;render()});
['q','ind','cat','lst','per'].forEach(id=>$(id).oninput=()=>{page=0;render()});
$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};
$('first').onclick=()=>{page=0;render()};$('last').onclick=()=>{page=1e9;render()};
$('pno').onchange=()=>{page=(+$('pno').value||1)-1;render()};
$('tb').onclick=e=>{const t=e.target.closest('tr');if(t){detail(C.find(c=>c.id==t.dataset.id));$('detail').scrollIntoView({behavior:'smooth',block:'center'})}};
function line(v){const W=640,H=210,P=32,ys=D.years,X=i=>P+i*(W-2*P)/(ys.length-1),Y=s=>H-P-(s/100)*(H-2*P);
 let d='',o=false,area='';v.forEach((s,i)=>{if(s==null){o=false;return}d+=(o?'L':'M')+X(i)+','+Y(s);o=true});
 const pts=v.map((s,i)=>s==null?null:[X(i),Y(s)]).filter(Boolean);if(pts.length>1)area=`<path d="M${pts[0][0]},${H-P} L${pts.map(p=>p.join(',')).join(' L')} L${pts[pts.length-1][0]},${H-P}Z" fill="url(#g)"/>`;
 return `<svg viewBox="0 0 ${W} ${H}" width="100%"><defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#d97706" stop-opacity=".22"/><stop offset="1" stop-color="#d97706" stop-opacity="0"/></linearGradient></defs>
 ${[0,50,100].map(g=>`<line x1="${P}" x2="${W-P}" y1="${Y(g)}" y2="${Y(g)}" stroke="#e6e0d4"/><text x="4" y="${Y(g)+4}">${g}</text>`).join('')}
 ${ys.map((y,i)=>i%3==0||i==ys.length-1?`<text x="${X(i)-14}" y="${H-10}">${y}</text>`:'').join('')}${area}<path d="${d}" fill="none" stroke="#0f172a" stroke-width="2.5"/>
 ${pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#fff" stroke="#0f172a" stroke-width="2"/>`).join('')}</svg>`}
const WHY={missing_sic:'SEC filings list no industry code for this company, so its technology exposure cannot be measured. The index is left blank rather than set to zero.',uninformative_sic:'The company’s SEC industry code is a catch-all category (e.g. “business services, not elsewhere classified”) that says nothing about its technology domain. The index is left blank rather than set to zero.',industry_unlinked:'The company’s industry is not linked to any of the nine tracked technology categories, so its startup-ecosystem exposure is 0.'};
function bars(v){if(!v||v.every(x=>x==null))return '';const W=640,H=170,P=32,ys=D.years,bw=(W-2*P)/ys.length,m=Math.max(...v.map(x=>Math.abs(x||0)))||1;
 return `<svg viewBox="0 0 ${W} ${H}" width="100%">`+v.map((x,i)=>{if(x==null)return '';const h=Math.abs(x)/m*(H-2*P-10);return `<rect x="${P+i*bw+4}" y="${H-P-h}" width="${bw-8}" height="${h}" rx="3" fill="${x<0?'#b91c1c':'#334155'}"><title>${ys[i]}: ${usd(x).replace(/<[^>]+>/g,'')}</title></rect>`}).join('')
 +ys.map((y,i)=>i%3==0||i==ys.length-1?`<text x="${P+i*bw+bw/2-14}" y="${H-10}">${y}</text>`:'').join('')+`<text x="4" y="14">max ${usd(m).replace(/<[^>]+>/g,'')}</text></svg>`}
function kpi(v,l){return `<div class="kpi"><b>${v}</b><span>${l}</span></div>`}
function detail(c){const tags=(c.categories||'').split(';').map(s=>s.trim()).filter(Boolean).map(s=>`<span class="pill">${esc(s.replace('=',' · '))}</span>`).join('')||'<span class="muted small">No tracked technology linked</span>';
 const f=c.fin,rdp=f&&f[1]>0&&f[3]!=null?(100*f[3]/f[1]).toFixed(1)+'%':'<span class="muted">–</span>';
 const pat=c.patent!=null?fmt(c.patent):'<span class="muted small" style="font-size:13px">not linked</span>';
 $('detail').innerHTML=`<div class="muted small">${esc(c.ticker||'no ticker')}${c.exchange?' · '+esc(c.exchange):''}${c.listed?'':' · <span class="badge">historical filer</span>'}</div><h3 style="margin:2px 0 4px;font-size:22px">${esc(c.name)}</h3>
 <div class="muted small">${esc(c.sic||'Industry unknown')}${c.country?' · '+esc(c.country):''}</div>
 <div style="display:flex;flex-wrap:wrap;gap:28px;margin:16px 0"><div><div class="big">${fmt(c.tdi)}</div><div class="muted small">Index ${D.years[D.years.length-1]}</div></div>
 <div><div class="big" style="font-size:28px;margin-top:12px">${fmt(c.startup)}</div><div class="muted small">Startup score</div></div>
 <div><div class="big" style="font-size:28px;margin-top:12px">${pat}</div><div class="muted small">Patent score</div></div></div>
 ${WHY[c.flag]?`<div class="note" style="margin-bottom:12px;font-size:13px">${WHY[c.flag]}</div>`:''}
 <div>${tags}</div>${c.history&&c.history.some(x=>x!=null)?'<h4>Index history</h4>'+line(c.history):''}
 <h4>Fundamentals${f?` <span class="muted small">(SEC XBRL, FY${f[0]})</span>`:''}</h4>
 ${f?`<div class="kpis">${kpi(usd(f[1]),'Revenue')}${kpi(usd(f[2]),'Total assets')}${kpi(rdp,'R&amp;D / revenue')}${kpi(usd(f[4]),'Public float')}${kpi(usd(f[5]),'Cash')}</div>${bars(c.rev)?'<div class="muted small" style="margin-top:10px">Revenue by year</div>'+bars(c.rev):''}`:'<p class="muted small">No XBRL financial statements reported to the SEC for 2015–2024.</p>'}
 <div class="muted small" style="margin-top:8px">Components available: ${c.components}/2 · ${esc(FL[c.flag]||'no data')} · <a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${c.id}" target="_blank" rel="noopener">SEC filings ↗</a></div>`}
(function(){const b=new Array(10).fill(0);let z=0;C.forEach(c=>{if(c.tdi==null)return;if(c.tdi===0){z++;return}b[Math.min(9,Math.floor(c.tdi/10))]++});
 const bins=[['=0',z],...b.map((n,i)=>[i?i*10+'+':'>0',n])],W=640,H=230,P=26,m=Math.max(...bins.map(x=>x[1])),bw=(W-2*P)/bins.length;
 $('hist').innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%">`+bins.map((x,i)=>{const h=x[1]/m*(H-2*P-14);return `<rect x="${P+i*bw+3}" y="${H-P-h}" width="${bw-6}" height="${h}" rx="3" fill="${i?'#1e293b':'#d97706'}"/><text x="${P+i*bw+bw/2-8}" y="${H-8}">${x[0]}</text><text x="${P+i*bw+bw/2-12}" y="${H-P-h-6}">${x[1]>=1000?(x[1]/1000).toFixed(1)+'k':x[1]}</text>`}).join('')+'</svg>'})();
$('inds').innerHTML='<table>'+D.industries.map(r=>`<tr><td>${esc(r[0])}</td><td class="r"><b>${r[1].toFixed(1)}</b><span class="meter"><i style="width:${r[1]}%"></i></span></td><td class="r muted small">${r[2].toLocaleString()}</td></tr>`).join('')+'</table>';
(function(){const L={M1:'Market valuation',M1b:'Valuation change',M2:'Revenue growth',M3:'R&D / assets',M4:'CAPEX / assets'},S={main_year:'Year FE',main_year_sic2:'+ Industry FE',main_sic2xyear:'Industry×year FE',main_firm_year:'Firm FE'};
 const specs=Object.keys(S);let h='<table><tr><th>Outcome (t+1)</th>'+specs.map(s=>`<th class="r">${S[s]}</th>`).join('')+'</tr>';
 Object.keys(L).forEach(m=>{h+=`<tr><td>${L[m]}</td>`+specs.map(s=>{const r=D.results.find(x=>x.model==m&&x.spec==s);return r&&r.coef!=null?`<td class="r ${r.p_value<.05?'sig':''}">${r.coef.toFixed(3)}</td>`:'<td class="r muted">–</td>'}).join('')+'</tr>'});
 $('res').innerHTML=h+'</table>'})();
render();detail(C.find(c=>c.id==$('top').firstElementChild.dataset.id));
});
</script></body></html>
"""


def esc(v) -> str:
    return html_lib.escape("" if v is None else str(v), quote=True)


def static_html(p: dict):
    """Server-rendered top cards and first table page, so crawlers see content without JS
    (the script re-renders the same elements once the data file has loaded)."""
    f = {k: i for i, k in enumerate(p["fields"])}
    comps = [c for c in p["companies"] if c[f["tdi"]] is not None]
    comps.sort(key=lambda c: (-c[f["tdi"]], c[f["name"]]))
    top = [c for c in comps if c[f["listed"]] and c[f["components"]] == 2][:10]
    cards = "".join(
        f'<div class="tc" data-id="{c[f["id"]]}"><span class="rk">#{i}</span>'
        f'<div class="s">{c[f["tdi"]]:.1f}</div><div class="bar"><i style="width:{c[f["tdi"]]}%">'
        f'</i></div><div class="n">{esc(c[f["name"]])}</div><div class="t">'
        f'{esc(c[f["ticker"]])} · {esc(c[f["industry"]])}</div></div>'
        for i, c in enumerate(top, 1))
    num = lambda v: "–" if v is None else f"{v:.1f}"
    rows = "".join(
        f'<tr data-id="{c[f["id"]]}"><td>{esc(c[f["name"]])}</td><td>{esc(c[f["ticker"]])}</td>'
        f'<td class="muted">{esc(c[f["industry"]])}</td><td class="r"><b>{num(c[f["tdi"]])}</b></td>'
        f'<td class="r">{num(c[f["startup"]])}</td><td class="r">{num(c[f["patent"]])}</td>'
        f'<td class="r">–</td></tr>' for c in comps[:50])
    return cards, rows


def main() -> None:
    p = build_payload()
    data = json.dumps(p, separators=(",", ":"), ensure_ascii=False)
    version = hashlib.sha1(data.encode("utf-8")).hexdigest()[:10]
    top_html, rows_html = static_html(p)
    site = config.SITE_URL.rstrip("/")
    ncomp, y0, y1 = f"{p['coverage']['total_companies']:,}", min(p["years"]), max(p["years"])
    ld = json.dumps([
        {"@context": "https://schema.org", "@type": "WebSite", "name": "Technology Disruption Index",
         "alternateName": "TDI", "url": f"{site}/"},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": "Technology Disruption Index — company technology-exposure scores",
         "description": f"Annual technology-exposure scores (0-100) for {ncomp} SEC-registered "
                        f"companies, {y0}-{y1}, built from US patent grants (USPTO PatentsView), "
                        "accelerator startup activity mapped to industries, and SEC XBRL "
                        "fundamentals, with panel regressions testing whether markets price "
                        "technology exposure before fundamentals.",
         "url": f"{site}/", "sameAs": "https://github.com/UmarovMirjalol/quantify",
         "keywords": ["technology disruption", "innovation index", "patents", "startups",
                      "SEC EDGAR", "public companies", "stock market", "panel data"],
         "temporalCoverage": f"{y0}/{y1}", "isAccessibleForFree": True,
         "creator": {"@type": "Person", "name": "Mirjalol Umarov",
                     "url": "https://github.com/UmarovMirjalol"},
         "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv",
                           "contentUrl": f"{site}/data/company_technology_index_latest.csv"}]},
    ], ensure_ascii=False).replace("</", "<\\/")
    res = {(r["model"], r["spec"]): r for r in p["results"]}
    peer, firm = res[("M1", "main_sic2xyear")], res[("M1", "main_firm_year")]
    css = (Path(__file__).with_name("style.css")).read_text(encoding="utf-8")
    html = (TEMPLATE.replace("__CSS__", css).replace("__VER__", version)
            .replace("__FPCT__", f"{100 * (np.exp(peer['coef']) - 1):.1f}")
            .replace("__FIRMP__", f"{firm['p_value']:.2f}")
            .replace("__NOBS__", f"{int(peer['n_obs']):,}")
            .replace("__TOPHTML__", top_html)
            .replace("__ROWSHTML__", rows_html).replace("__LDJSON__", ld).replace("__SITE__", site)
            .replace("__NCOMP__", f"{p['coverage']['total_companies']:,}")
            .replace("__NLISTED__", f"{p['n_listed']:,}")
            .replace("__NSTART__", f"{p['n_startups']:,}")
            .replace("__NPAT__", f"{p['n_patent']:,}")
            .replace("__NREG__", str(p["n_regressions"]))
            .replace("__Y0__", str(min(p["years"]))).replace("__Y1__", str(max(p["years"])))
            .replace("__WP__", f"{int(p['weights']['patent_score'] * 100)}")
            .replace("__WS__", f"{int(p['weights']['startup_score'] * 100)}"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    import shutil
    (OUT_DIR / "data").mkdir(exist_ok=True)
    shutil.copy(config.TECH_INDEX_LATEST, OUT_DIR / "data" / "company_technology_index_latest.csv")
    shutil.copy(config.REGRESSION_RESULTS, OUT_DIR / "data" / "regression_results.csv")
    (OUT_DIR / "data" / "site.json").write_text(data, encoding="utf-8")
    (OUT_DIR / "vercel.json").write_text('{"cleanUrls": true}\n', encoding="utf-8")
    site_assets.write_all(OUT_DIR, ncomp, f"{y0}–{y1}")
    log.info("Website: %d companies | index.html %.0f KB + data/site.json %.1f MB -> %s",
             len(p["companies"]), OUT.stat().st_size / 1e3, len(data) / 1e6, OUT_DIR)


if __name__ == "__main__":
    main()
