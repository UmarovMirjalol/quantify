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
        "extra": (json.loads(config.EXTRA_TESTS_JSON.read_text(encoding="utf-8"))
                  if config.EXTRA_TESTS_JSON.exists() else None),
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
<div class="links"><a href="#explore">Explore</a><a href="#research">Research</a><a href="#lab">Stress test</a><a href="#replicate">Run it yourself</a><a href="#method">Methodology</a><a href="#about">Data</a>
<button type="button" class="kb" id="openK">Search <kbd>⌘K</kbd></button>
<a class="gh" href="https://github.com/UmarovMirjalol/quantify" target="_blank" rel="noopener">GitHub</a></div></div></nav>

<header class="hero"><div>
<div class="eyebrow">Open research · __Y0__–__Y1__ · SEC filings, patents, startups</div>
<h1>Which companies are most exposed to <em>technological disruption?</em></h1>
<p class="lead">A transparent, reproducible index scoring __NCOMP__ SEC-registered companies on patent activity and startup-ecosystem activity in their technology domains — and a test of whether markets price it before fundamentals.</p>
<a class="btn p" href="#explore">Explore companies</a>
<button type="button" class="btn s" id="tourBtn">45-second tour</button>
<p class="askwrap"><input id="ask" placeholder="Try NVDA vs INTC, top AI, 2018, or tour" autocomplete="off"></p></div>
<aside class="finding"><div class="eyebrow">Key finding</div><div class="fig">+__FPCT__%</div>
<p>higher next-year public float for a company scoring 10 index points above its industry peers in the same year.</p>
<div class="cmpfind">
<div><span>vs industry peers, same year</span><b>+__FPCT__%</b><i style="width:100%"></i></div>
<div><span>same company over time (p = __FIRMP__)</span><b>~0%</b><i class="dim"></i></div>
</div>
<p>Markets appear to price <i>which</i> firms are exposed, not changes in exposure.</p>
<p class="src">Lagged panel regressions, __NOBS__ firm-years, industry×year fixed effects, clustered SEs. Predictive, not causal. Public float, not Tobin’s Q.</p></aside>
</header>

<div class="wrap"><div class="stats" id="stats"></div>
<section id="explore"><div class="kicker">Explore</div><h2>Highest-scoring companies</h2>
<p class="sub">Index on a 0–100 scale. Drag the year or hit Play decade — the ranking is the real historical index, not a forecast. Cards are listed companies scored on both patents and startup activity.</p>
<div class="yearbar card" id="yearbar">
<div><b id="yval">__Y1__</b><span class="muted small">Index year · fully scored listed firms</span></div>
<input id="yslider" type="range" min="0" max="9" value="9">
<button type="button" class="btn s" id="yplay">Play decade</button>
</div>
<div class="chips" id="chips"></div>
<div class="top" id="top">__TOPHTML__</div>

<h3 style="margin:32px 0 8px;font-size:20px">Names you know, over the decade</h3>
<p class="sub" style="margin-bottom:12px">Index paths for a handful of well-known listed firms. The dashed line is the year on the slider. Click a name in the legend to open the firm.</p>
<div class="card" id="lanecard"><div id="lanes"></div><div class="chips" id="laneleg"></div></div>

<div class="g2" style="margin-top:20px">
<div class="card"><h3 style="margin:0 0 6px">Who climbed, who slipped</h3>
<p class="muted small" style="margin:0 0 12px">Change in the index from __Y0__ to the year on the slider, among listed firms scored on both patents and startup activity. Firms that only inherit an industry startup score are excluded so the list is not a copy of one industry. History of the index, not a forecast.</p>
<div id="movers"></div></div>
<div class="card"><h3 style="margin:0 0 6px">The two ingredients</h3>
<p class="muted small" style="margin:0 0 12px">Each dot is a listed firm with both scores. Horizontal bands are real: startup exposure is mostly industry-level, so firms in one industry share a y-value; patents spread them on x. The index is their average. Click a dot.</p>
<canvas id="scat" width="640" height="400"></canvas>
<p class="muted small" id="scattip">Hover or click a point.</p></div>
</div>

<h3 style="margin:28px 0 10px;font-size:20px">Companies by technology tag</h3>
<p class="sub" style="margin-bottom:12px">Click a category to filter the table. A firm can belong to more than one tag.</p>
<div class="techmap" id="techmap"></div>

<div class="card" style="margin-top:20px">
<div class="controls"><input id="q" placeholder="Search by company name or ticker…">
<select id="ind"><option value="">All industries</option></select>
<select id="cat"><option value="">All technologies</option></select>
<select id="lst"><option value="">All companies</option><option value="1">Currently listed</option><option value="0">Historical filers</option></select></div>
<div class="tw"><table><thead><tr><th data-k="name">Company</th><th data-k="ticker">Ticker</th><th data-k="industry">Industry</th>
<th data-k="tdi" class="r">Index</th><th>Trend</th><th data-k="startup" class="r">Startup</th><th data-k="patent" class="r">Patent</th><th data-k="revenue" class="r">Revenue</th></tr></thead><tbody id="tb">__ROWSHTML__</tbody></table></div>
<div class="pager"><span id="pg"></span>
<select id="per"><option value="25">25 per page</option><option value="50" selected>50 per page</option><option value="100">100 per page</option><option value="500">500 per page</option><option value="0">Show all</option></select>
<button id="first" title="First page">«</button><button id="prev" title="Previous page">←</button>
<span>Page <input id="pno" type="number" min="1" value="1"> of <b id="pmax">1</b></span>
<button id="next" title="Next page">→</button><button id="last" title="Last page">»</button></div></div>

<div class="card" style="margin-top:20px"><h3 style="margin:0 0 6px">Score distribution</h3><div id="hist"></div><p class="small muted">Amber bar: industries not linked to any tracked technology category (score 0). Open a company from the table for its profile, industry rank, and history.</p></div>
</section>

<section id="research"><div class="kicker">Research</div><h2>Do markets price technology exposure before fundamentals?</h2>
<p class="sub">Lagged panel regressions: index in year t, outcomes in year t+1, standard errors clustered by company. Coefficients per 10 index points. These are predictive associations, not causal effects.</p>
<div class="g2"><div class="card"><h3 style="margin:0 0 8px">The valuation result, in one picture</h3>
<p class="muted small" style="margin:0 0 12px">Next-year public float, per +10 index points. Green = statistically distinguishable from zero.</p>
<div id="forest"></div>
<div class="tw" id="res" style="margin-top:18px"></div>
<p class="small muted">Coefficients as estimated. Green = p &lt; 0.05. __NREG__ specifications in total incl. robustness checks; full results in the repository.</p></div>
<div class="card"><h3 style="margin:0 0 6px">Average index by industry</h3><div id="inds"></div></div></div>
<div class="note" style="margin-top:20px"><b>Read with care.</b> Patent data cover __NPAT__ companies — those whose patents could be linked to an SEC registrant. For the remaining firms the index reflects industry-level exposure to startup activity only; a blank patent score means “not linked”, not “zero patents”.</div>
</section>

<section id="lab"><div class="kicker">Stress test</div><h2>Trying to break the result</h2>
<p class="sub">Five checks on the headline association (next-year public float vs industry-and-year peers), fixed in advance and re-run by the pipeline. None was picked for its p-value, and none turns a correlation into a cause.</p>
<div class="g2 lab">
<div class="card"><h3 style="margin:0 0 4px">1,000 fake indexes</h3>
<p class="muted small" style="margin:0 0 10px">The index is shuffled between firms inside each industry-year, so a fake score carries the same industry and year mix but no firm information. The model is re-run on every shuffle.</p>
<div id="placebo"></div><p class="small" id="placebocap"></p></div>
<div class="card"><h3 style="margin:0 0 4px">The relationship, binned</h3>
<p class="muted small" style="margin:0 0 10px">__NOBS__ firm-years in 20 equal groups, after removing size (ln assets) and industry×year averages. Each dot is one group; the line is the regression slope.</p>
<div id="binsc"></div></div>
</div>
<div class="g2 lab" style="margin-top:20px">
<div class="card"><h3 style="margin:0 0 4px">Every year on its own</h3>
<p class="muted small" style="margin:0 0 10px">The same model on each single year’s cross-section (industry FE, robust 95% intervals). A result driven by one boom year would show up here.</p>
<div id="byyear"></div></div>
<div class="card"><h3 style="margin:0 0 4px">Drop one industry at a time</h3>
<p class="muted small" style="margin:0 0 10px">Re-estimated without each broad industry. If one sector carried the result, removing it would move the estimate toward zero.</p>
<div id="loo"></div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin:0 0 4px">Specification curve: every model we ran</h3>
<p class="muted small" style="margin:0 0 10px">All estimated specifications for each outcome, sorted by estimate, with 95% intervals: fixed-effect variants, alternative weights, longer horizons, single components, sub-samples. Green intervals exclude zero; amber is the headline model. Hover a point for the specification. The log-patent-count model is left out here because its regressor is not on the 0–100 scale; it is in the CSV.</p>
<div class="chips" id="sctabs"></div><div id="scurve"></div><p class="small muted" id="sctip">&nbsp;</p></div>
<div class="note" style="margin-top:20px"><b>What this does not show.</b> The shuffle test rules out chance and industry-year composition; it does not rule out unobserved firm traits. When firm fixed effects are added, the association disappears (p = __FIRMP__), so the index identifies firms the market already values more, not firms whose value rises as their score rises.</div>
</section>

<section id="replicate"><div class="kicker">Replicate it</div><h2>Run the regression yourself</h2>
<p class="sub">The full research sample (__NOBS__ firm-years) loads into your browser. Change how the index is built and how the model is specified, and the regression is re-estimated on the spot, with standard errors clustered by company. No server, no pre-computed answers.</p>
<div class="rep">
<div class="card repctl">
<label class="rl">Index weights <b id="rwv">Patents 50 · Startups 50</b></label>
<input type="range" id="rw" min="0" max="100" step="5" value="50" aria-label="Patent weight">
<label class="rl">Compare each firm with</label>
<div class="seg" id="rfe">
<button type="button" data-fe="year">Same year</button><button type="button" data-fe="sic2+year">Industry + year</button><button type="button" data-fe="sic2xyear" class="on">Industry × year</button><button type="button" data-fe="firm+year">Itself over time</button>
</div>
<label class="rl">Years <b id="ryv"></b></label>
<div class="ryr"><select id="ry0" aria-label="First year"></select><span>to</span><select id="ry1" aria-label="Last year"></select></div>
<label class="rl">Sample</label>
<label class="ck"><input type="checkbox" id="rsize" checked> Control for firm size (ln assets)</label>
<label class="ck"><input type="checkbox" id="rboth"> Only firms scored on both patents and startups</label>
<label class="ck"><input type="checkbox" id="rbig"> Drop the largest 10% of firms each year</label>
<label class="rl">Industries <span class="muted small">(click to drop)</span></label>
<div class="chips" id="rind"></div>
<button type="button" class="btn s" id="rreset">Reset to the published model</button>
</div>
<div class="card repout">
<div id="rstat" class="muted">Scroll here to load the data…</div>
<div class="rbig"><span id="rfig">–</span><small>next-year public float per +10 index points</small></div>
<div id="rmeta" class="small"></div>
<div id="rbadge"></div>
<h3 style="margin:22px 0 4px">Every model you have run</h3>
<p class="muted small" style="margin:0 0 8px">Each dot is one of your runs, with its 95% interval; amber is the published estimate. Trying many versions and reporting only the best one is p-hacking, so this log keeps all of them.</p>
<div id="rlog"></div><p class="small" id="rlogtxt"></p>
<button type="button" class="btn s" id="rclear" style="margin-top:6px">Clear my runs</button>
</div>
</div>
<p class="small muted" style="margin-top:12px">Same estimator as the paper (OLS with absorbed fixed effects, company-clustered SEs); with the default settings it reproduces the published estimates to the third decimal (the shared file rounds logs to 3 decimals). Results here are exploratory and predictive, not causal. Data: <a href="data/panel.json" download>panel.json</a>.</p>
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
<div><a class="btn p" href="data/company_technology_index_latest.csv" download>Index scores (CSV)</a><a class="btn s" href="data/regression_results.csv" download>Regression results</a><a class="btn s" href="data/extra_tests.json" download>Stress tests (JSON)</a></div></div></section>
</div>
<footer><div class="foot">
<div><a class="logo" href="#"><img src="/favicon.svg" alt="" width="28" height="28">Technology Disruption Index</a>
<p>An open, reproducible measure of technology exposure for __NCOMP__ public companies. Research project; not investment advice.</p></div>
<div><b>Explore</b><a href="#explore">Companies</a><a href="#research">Research results</a><a href="#method">Methodology</a><a href="data/company_technology_index_latest.csv">Download data (CSV)</a></div>
<div><b>Sources</b><a href="https://www.sec.gov/edgar" target="_blank" rel="noopener">SEC EDGAR</a><a href="https://www.uspto.gov/ip-policy/economic-research/patentsview" target="_blank" rel="noopener">USPTO PatentsView</a><a href="https://github.com/songma/patent-firm-link-share" target="_blank" rel="noopener">Patent–firm linkage (Ma, 2025)</a><a href="https://github.com/UmarovMirjalol/quantify" target="_blank" rel="noopener">Source code on GitHub</a></div>
</div></footer>

<div class="ov" id="ov" hidden><aside class="drawer" role="dialog" aria-modal="true"><button type="button" class="ovx" id="ovx" aria-label="Close">×</button><div id="dbody"></div></aside></div>
<div class="pal" id="pal" hidden><div class="pal-box" role="dialog" aria-label="Search companies"><input id="pq" placeholder="Search 13,702 companies by name or ticker…" autocomplete="off"><div class="palhint" id="palhint"></div><div id="pl"></div></div></div>
<div class="tour" id="tour" hidden><p id="tourtxt"></p><button type="button" id="tourx">Skip</button></div>
<script>
__JS__
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
        f'<td></td><td class="r">{num(c[f["startup"]])}</td><td class="r">{num(c[f["patent"]])}</td>'
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
    js = (Path(__file__).with_name("app.js")).read_text(encoding="utf-8").replace("__VER__", version)
    html = (TEMPLATE.replace("__CSS__", css).replace("__JS__", js)
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
    if config.EXTRA_TESTS_JSON.exists():
        shutil.copy(config.EXTRA_TESTS_JSON, OUT_DIR / "data" / "extra_tests.json")
    if config.REPLICATION_PANEL.exists():
        shutil.copy(config.REPLICATION_PANEL, OUT_DIR / "data" / "panel.json")
    (OUT_DIR / "data" / "site.json").write_text(data, encoding="utf-8")
    (OUT_DIR / "vercel.json").write_text('{"cleanUrls": true}\n', encoding="utf-8")
    site_assets.write_all(OUT_DIR, ncomp, f"{y0}–{y1}")
    log.info("Website: %d companies | index.html %.0f KB + data/site.json %.1f MB -> %s",
             len(p["companies"]), OUT.stat().st_size / 1e3, len(data) / 1e6, OUT_DIR)


if __name__ == "__main__":
    main()
