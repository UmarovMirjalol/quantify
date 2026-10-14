"""
Stage 11: static website (docs/index.html).

Single self-contained HTML file (no external libraries, fonts or CDNs). Deployable as-is to
Vercel, Netlify, Cloudflare Pages or GitHub Pages; works with a custom domain.
All numbers are read from pipeline outputs at build time.
"""
import json

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
<meta name="theme-color" content="#4f46e5">
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
:root{--bg:#f7f8fb;--card:#fff;--ink:#0f172a;--muted:#64748b;--line:#e6e9f0;--acc:#4f46e5;--acc2:#06b6d4;--good:#059669;--warn:#d97706;--r:16px;
--shadow:0 1px 2px rgba(15,23,42,.04),0 8px 24px rgba(15,23,42,.06)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Inter,sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
nav{position:sticky;top:0;z-index:10;backdrop-filter:saturate(180%) blur(12px);background:rgba(247,248,251,.8);border-bottom:1px solid var(--line)}
.nav{max-width:1180px;margin:auto;display:flex;align-items:center;gap:28px;padding:14px 24px}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;color:var(--ink)}.logo i{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:inline-block}
.nav .links{display:flex;gap:22px;margin-left:auto}.nav .links a{color:var(--muted);font-size:14px}.nav .links a:hover{color:var(--ink)}
.hero{position:relative;overflow:hidden;padding:88px 24px 64px;text-align:center}
.hero:before{content:"";position:absolute;inset:-40% -10% auto;height:620px;background:radial-gradient(closest-side,rgba(79,70,229,.18),transparent),radial-gradient(closest-side at 70% 40%,rgba(6,182,212,.16),transparent);z-index:-1}
.tag{display:inline-block;padding:6px 14px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--muted);font-size:13px}
h1{font-size:clamp(34px,5.4vw,62px);line-height:1.05;letter-spacing:-.03em;margin:18px auto 16px;max-width:900px}
h1 span{background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{color:var(--muted);font-size:18px;max-width:720px;margin:0 auto 30px}
.btn{display:inline-block;padding:12px 22px;border-radius:12px;font-weight:600;font-size:15px}.btn.p{background:var(--ink);color:#fff}.btn.s{background:#fff;border:1px solid var(--line);color:var(--ink);margin-left:8px}
.wrap{max-width:1180px;margin:auto;padding:0 24px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:48px auto 0;max-width:1000px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:20px;box-shadow:var(--shadow);text-align:left}
.stat b{display:block;font-size:30px;letter-spacing:-.02em}.stat span{color:var(--muted);font-size:13px}
section{padding:72px 0 8px}.kicker{color:var(--acc);font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.08em}
h2{font-size:clamp(26px,3vw,36px);letter-spacing:-.02em;margin:6px 0 10px}.sub{color:var(--muted);max-width:760px;margin:0 0 28px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:22px;box-shadow:var(--shadow)}
.g2{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.top{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.tc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;cursor:pointer;transition:.15s}.tc:hover{transform:translateY(-2px);box-shadow:var(--shadow)}
.tc .n{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tc .t{color:var(--muted);font-size:12px}.tc .s{font-size:26px;font-weight:700;color:var(--acc)}
.controls{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
input,select{font:inherit;border:1px solid var(--line);background:#fff;border-radius:10px;padding:10px 12px;color:var(--ink)}input{flex:1;min-width:220px}
input:focus,select:focus{outline:2px solid rgba(79,70,229,.25);border-color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;user-select:none}
tbody tr{cursor:pointer}tbody tr:hover{background:#f5f6ff}td.r,th.r{text-align:right}
.meter{display:inline-block;width:70px;height:6px;border-radius:6px;background:#eef0f6;vertical-align:middle;margin-left:8px;overflow:hidden}.meter i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--acc2))}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;background:#eef2ff;color:#3730a3;margin:2px 6px 2px 0}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;background:#f1f5f9;color:var(--muted)}
.pager{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;justify-content:flex-end;margin-top:12px;color:var(--muted);font-size:13px}
.pager #pg{margin-right:auto}.pager select{padding:6px 10px;border-radius:10px}.pager input{flex:0 0 70px;width:70px;min-width:0;padding:6px 8px;border:1px solid var(--line);border-radius:10px;font:inherit;text-align:center}
.pager button:disabled{opacity:.4;cursor:default}
.tw.scroll{max-height:75vh;overflow-y:auto}.tw thead th{position:sticky;top:0;background:#fff;z-index:1}
button{font:inherit;background:#fff;border:1px solid var(--line);border-radius:10px;padding:6px 14px;cursor:pointer}
.tw{overflow-x:auto}.muted{color:var(--muted)}.small{font-size:13px}.sig{color:var(--good);font-weight:600}
.big{font-size:44px;font-weight:700;letter-spacing:-.03em}
.method .card h3{margin:0 0 6px;font-size:17px}.method .card p{margin:0;color:var(--muted);font-size:14px}
.num{display:inline-flex;width:30px;height:30px;border-radius:10px;align-items:center;justify-content:center;background:#eef2ff;color:var(--acc);font-weight:700;margin-bottom:10px}
.note{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:12px;padding:14px 16px;font-size:14px}
footer{margin-top:80px;border-top:1px solid var(--line);padding:32px 24px;color:var(--muted);font-size:13px;text-align:center}
svg text{fill:var(--muted);font-size:11px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}.kpi{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.kpi b{display:block;font-size:18px}.kpi span{color:var(--muted);font-size:12px}#detail h4{margin:18px 0 8px;font-size:14px}
body{overflow-x:hidden}.card,.tc,.stat,.g2>*,.g3>*{min-width:0}.card{overflow-x:auto}
@media(max-width:900px){.stats,.top{grid-template-columns:repeat(2,1fr)}.g2,.g3{grid-template-columns:1fr}.nav .links{display:none}}
</style></head><body>
<nav><div class="nav"><a class="logo" href="#"><i></i>Technology Disruption Index</a>
<div class="links"><a href="#explore">Explore</a><a href="#research">Research</a><a href="#method">Methodology</a><a href="#about">About</a></div></div></nav>

<header class="hero"><span class="tag">Open data · __Y0__–__Y1__ · updated from SEC filings</span>
<h1>Which companies are most exposed to <span>technological disruption?</span></h1>
<p class="lead">A transparent, reproducible index scoring __NCOMP__ SEC-registered companies on patent activity and startup-ecosystem activity in their technology domains — and a test of whether markets price it before fundamentals.</p>
<a class="btn p" href="#explore">Explore companies</a><a class="btn s" href="#research">See the research</a>
<div class="stats" id="stats"></div></header>

<div class="wrap">
<section id="explore"><div class="kicker">Explore</div><h2>Highest-scoring companies</h2>
<p class="sub">Index on a 0–100 scale for __Y1__. Click any company to see its score history and technology exposure.</p>
<div class="top" id="top"></div>

<div class="card" style="margin-top:20px">
<div class="controls"><input id="q" placeholder="Search by company name or ticker…">
<select id="ind"><option value="">All industries</option></select>
<select id="cat"><option value="">All technologies</option></select>
<select id="lst"><option value="">All companies</option><option value="1">Currently listed</option><option value="0">Historical filers</option></select></div>
<div class="tw"><table><thead><tr><th data-k="name">Company</th><th data-k="ticker">Ticker</th><th data-k="industry">Industry</th>
<th data-k="tdi" class="r">Index</th><th data-k="startup" class="r">Startup</th><th data-k="patent" class="r">Patent</th><th data-k="revenue" class="r">Revenue</th></tr></thead><tbody id="tb"></tbody></table></div>
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

<section id="about"><div class="kicker">About</div><h2>Open and reproducible</h2>
<p class="sub">The full pipeline — data collection, scoring, validation and regressions — runs with one command. The index is a measurable proxy for technology exposure, not an objective measure of “true” disruption.</p>
<div class="card" style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between"><div><h3 style="margin:0">Download the data</h3><p class="muted small" style="margin:4px 0 0">Latest scores for all __NCOMP__ companies and the full regression results (CSV).</p></div>
<div><a class="btn p" href="data/company_technology_index_latest.csv" download>Index scores (CSV)</a><a class="btn s" href="data/regression_results.csv" download>Regression results</a></div></div></section>
</div>
<footer>Technology Disruption Index · Data: SEC EDGAR, USPTO PatentsView (firm linkage: Ma, 2025, RFS), accelerator portfolios · Not investment advice</footer>

<script>
const D=__DATA__;const F=D.fields,C=D.companies.map(r=>Object.fromEntries(F.map((f,i)=>[f,r[i]])));
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
$('top').innerHTML=C.filter(c=>c.tdi!=null&&c.listed).sort((a,b)=>b.tdi-a.tdi||a.name.localeCompare(b.name)).slice(0,10)
 .map(c=>`<div class="tc" data-id="${c.id}"><div class="s">${c.tdi.toFixed(1)}</div><div class="n">${esc(c.name)}</div><div class="t">${esc(c.ticker)} · ${esc(c.industry)}</div></div>`).join('');
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
 return `<svg viewBox="0 0 ${W} ${H}" width="100%"><defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#4f46e5" stop-opacity=".25"/><stop offset="1" stop-color="#4f46e5" stop-opacity="0"/></linearGradient></defs>
 ${[0,50,100].map(g=>`<line x1="${P}" x2="${W-P}" y1="${Y(g)}" y2="${Y(g)}" stroke="#e6e9f0"/><text x="4" y="${Y(g)+4}">${g}</text>`).join('')}
 ${ys.map((y,i)=>i%3==0||i==ys.length-1?`<text x="${X(i)-14}" y="${H-10}">${y}</text>`:'').join('')}${area}<path d="${d}" fill="none" stroke="#4f46e5" stroke-width="2.5"/>
 ${pts.map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#fff" stroke="#4f46e5" stroke-width="2"/>`).join('')}</svg>`}
const WHY={missing_sic:'SEC filings list no industry code for this company, so its technology exposure cannot be measured. The index is left blank rather than set to zero.',uninformative_sic:'The company’s SEC industry code is a catch-all category (e.g. “business services, not elsewhere classified”) that says nothing about its technology domain. The index is left blank rather than set to zero.',industry_unlinked:'The company’s industry is not linked to any of the nine tracked technology categories, so its startup-ecosystem exposure is 0.'};
function bars(v){if(!v||v.every(x=>x==null))return '';const W=640,H=170,P=32,ys=D.years,bw=(W-2*P)/ys.length,m=Math.max(...v.map(x=>Math.abs(x||0)))||1;
 return `<svg viewBox="0 0 ${W} ${H}" width="100%">`+v.map((x,i)=>{if(x==null)return '';const h=Math.abs(x)/m*(H-2*P-10);return `<rect x="${P+i*bw+4}" y="${H-P-h}" width="${bw-8}" height="${h}" rx="5" fill="${x<0?'#f43f5e':'#06b6d4'}" opacity=".85"><title>${ys[i]}: ${usd(x).replace(/<[^>]+>/g,'')}</title></rect>`}).join('')
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
 $('hist').innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%">`+bins.map((x,i)=>{const h=x[1]/m*(H-2*P-14);return `<rect x="${P+i*bw+3}" y="${H-P-h}" width="${bw-6}" height="${h}" rx="6" fill="${i?'#6366f1':'#f59e0b'}" opacity="${i?.85:1}"/><text x="${P+i*bw+bw/2-8}" y="${H-8}">${x[0]}</text><text x="${P+i*bw+bw/2-12}" y="${H-P-h-6}">${x[1]>=1000?(x[1]/1000).toFixed(1)+'k':x[1]}</text>`}).join('')+'</svg>'})();
$('inds').innerHTML='<table>'+D.industries.map(r=>`<tr><td>${esc(r[0])}</td><td class="r"><b>${r[1].toFixed(1)}</b><span class="meter"><i style="width:${r[1]}%"></i></span></td><td class="r muted small">${r[2].toLocaleString()}</td></tr>`).join('')+'</table>';
(function(){const L={M1:'Market valuation',M1b:'Valuation change',M2:'Revenue growth',M3:'R&D / assets',M4:'CAPEX / assets'},S={main_year:'Year FE',main_year_sic2:'+ Industry FE',main_sic2xyear:'Industry×year FE',main_firm_year:'Firm FE'};
 const specs=Object.keys(S);let h='<table><tr><th>Outcome (t+1)</th>'+specs.map(s=>`<th class="r">${S[s]}</th>`).join('')+'</tr>';
 Object.keys(L).forEach(m=>{h+=`<tr><td>${L[m]}</td>`+specs.map(s=>{const r=D.results.find(x=>x.model==m&&x.spec==s);return r&&r.coef!=null?`<td class="r ${r.p_value<.05?'sig':''}">${r.coef.toFixed(3)}</td>`:'<td class="r muted">–</td>'}).join('')+'</tr>'});
 $('res').innerHTML=h+'</table>'})();
render();detail(C.find(c=>c.id==$('top').firstElementChild.dataset.id));
</script></body></html>
"""


def main() -> None:
    p = build_payload()
    data = json.dumps(p, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
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
    html = (TEMPLATE.replace("__DATA__", data).replace("__LDJSON__", ld).replace("__SITE__", site)
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
    (OUT_DIR / "vercel.json").write_text('{"cleanUrls": true}\n', encoding="utf-8")
    site_assets.write_all(OUT_DIR, ncomp, f"{y0}–{y1}")
    log.info("Website: %d companies, %.1f MB -> %s", len(p["companies"]), OUT.stat().st_size / 1e6, OUT)


if __name__ == "__main__":
    main()
