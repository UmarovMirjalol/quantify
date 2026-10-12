# Technology Disruption Index

A reproducible, company-year **proxy signal** of technology-disruption exposure for the
universe of SEC-registered public companies, and a research panel that tests whether that
signal predicts market valuation before it predicts traditional fundamentals.

> The index does **not** measure "true technological disruption". It combines two
> observable, imperfect signals: patenting activity and the intensity of startup activity
> in the technology domains a company operates in. Read every score as a measurable proxy.

---

## 1. What the index measures

For each company *i* and year *t* (2015-2024):

| Component | Question it answers | Level |
|---|---|---|
| `patent_score` | How much, and how increasingly, does the firm itself patent? | firm-specific |
| `startup_score` | How much emerging-startup activity is happening in the technology domains of the firm's industry? | industry exposure, firm-level refinements |
| `technology_disruption_index` | Weighted combination (default 50/50) of the available components | 0-100 |

## 2. Why patents

Patents are a standardized, dated, legally verified record of inventive output, available for
decades and for all firms that patent. Limits: propensity to patent differs strongly across
industries (software and services patent less than semiconductors and pharma); patents measure
inventions, not commercial impact; counts are skewed (a few firms hold most patents).

## 3. Why startup-ecosystem activity

Accelerator cohorts (Y Combinator, Techstars, Plug and Play, 500 Global, Antler, Alchemist,
Entrepreneur First; ~19,800 unique startups) show where entrepreneurs and early-stage capital
are moving. High startup activity in a firm's technology domain signals that the domain is
being contested by new entrants, whether the firm is the disruptor or the incumbent.
Limits: accelerators over-represent software, fintech and AI; cohort years for 2025/2026 are
incomplete; ~28% of startups have no cohort year.

## 4. How companies are matched

* **Canonical key:** `company_id` = SEC CIK (integer). Names are never used as join keys.
* **Universe:** SEC `company_tickers` snapshot (`data/companies.csv`, never overwritten unless
  `--refresh`), cleaned of ETFs/funds/warrants/units/depositary receipts/SPAC shells with
  word-bounded name filters, then collapsed to **one row per CIK** (a company with several
  share classes/tickers keeps all of them in `tickers`; the primary ticker follows SEC's order).
* **Industry:** SIC code, SIC description, country (business address) and state of incorporation
  from the SEC submissions API (cached, restartable). `industry` = SIC division.
* **Non-operating entities** (SIC 6770 blank checks, 6221 commodity trusts, 6722/6726 funds,
  6792 royalty traders) are **kept** in the universe and index but flagged `is_non_operating`
  and excluded from the regressions.
* **Startups -> companies:** there is **no startup-to-company name matching** and no claimed
  relationship between any startup and any public company. Linkage is through technology
  categories only (next section).
* **Patents -> companies:** exact match of normalized assignee names (upper case, punctuation
  and legal suffixes removed) against normalized company names; names shared by more than one
  company are skipped as ambiguous; an optional curated `data/raw/patents/assignee_crosswalk.csv`
  adds subsidiaries (e.g. "GOOGLE LLC" -> Alphabet). The legacy 9-company file is linked through
  an explicit name->ticker crosswalk in `config.py`.

## 5. Technology categories and the SIC -> technology mapping

Categories: AI, Fintech, Cloud, Robotics, Cybersecurity, Biotech, Semiconductors, Energy, Quantum.

1. **Startups are tagged** from their tags + description with word-bounded regular expressions
   (`config.STARTUP_TECH_PATTERNS`); a startup can belong to several categories.
2. **Category activity** in year *t* uses cohorts *t-2..t*:
   `intensity_c,t = log(1 + n_c,t) / log(1 + n_total,t)`. The log keeps AI/Fintech from swamping
   scarce categories purely because accelerators skew towards software.
3. **Company exposure weights** `w_i,c ∈ {0, 0.5, 1}`:
   * industry rules `config.SIC_TECHNOLOGY_RULES` (each with a written rationale; 1.0 = the
     industry's core activity is in the domain, 0.5 = adjacent / adopting / incumbent industry);
     the applied mapping is exported to `data/startups/sic_technology_map.csv`;
   * weak evidence from the company's own legal name (e.g. "... Therapeutics", "... AI"),
     capped at 0.5; combined with the SIC weights by taking the maximum.
   No score is hard-coded for any individual company.
4. `startup_activity_raw_i,t = Σ_c w_i,c · intensity_c,t`.

Quantum has no SIC code; it can only be detected from company names, so it is under-covered.

## 6. Normalization

* **Startup score:** within-year percentile rank of `startup_activity_raw` among firms with
  positive exposure, on a (0, 100] scale. Firms in industries that the mapping does not link to
  any tracked category get 0 and `coverage_flag = industry_unlinked` (configurable to missing via
  `UNLINKED_INDUSTRY_POLICY`). This is a *measured* industry classification, not a failed match.
* **Patent score** (default `PATENT_NORMALIZATION = "fixed_log"`):
  * `volume_score = 100 · min(1, log(1+patents_t) / log(1+10,000))`
  * `momentum = (recent_avg + 1) / (historical_avg + 1)` with recent = *t-2..t*,
    historical = *t-5..t-3* (for 2024: 2022-2024 vs 2019-2021); all window years must be observed;
    `momentum_score = 50 + 50 · clip(log2(momentum), -1, 1)` (0.5x -> 0, 1x -> 50, 2x -> 100)
  * `patent_score = 0.5 · volume_score + 0.5 · momentum_score` (volume only, flagged by
    `patent_momentum_available = False`, when six years of history are not available).
  * Logs mean Intel's 5,900 grants score 94 vs. NVIDIA's 1,000 at 75, not 6x higher.
  * A fixed log anchor is used instead of cross-sectional percentiles because percentiles
    among a handful of covered firms would be meaningless and would shift whenever coverage
    grows. `"percentile"` is available once the full-universe BigQuery extraction is in place.
  * Only complete patent years (<= 2024) are used; 2025/2026 are never compared to full years.
* Scores are rounded to one decimal to avoid spurious precision.

## 7. Missing data

* **No match ≠ zero.** A company without patent data has `patent_score = NaN`, not 0.
  A company with no SIC code and no name evidence has `startup_score = NaN`
  (`coverage_flag = missing_sic`).
* Every company stays in every output. `components_available` (0/1/2) and `coverage_score`
  (share of index weight backed by data: 0, 0.5 or 1.0) are reported for each company-year.
* Nothing is imputed. Financial items that a company does not report stay missing
  (e.g. R&D is *not* set to 0 when absent).

## 8. Index calculation

```
technology_disruption_index = Σ_k w_k · score_k / Σ_{k available} w_k
default w = {patent_score: 0.50, startup_score: 0.50}  (config.INDEX_WEIGHTS)
```
With one component the index equals that component and `coverage_score = 0.5`.
Alternative weightings (25/75, 50/50, 75/25) are in `config.ALTERNATIVE_WEIGHTS`.

## 9. Financial data

SEC XBRL **frames** API (one request returns one concept for all filers in a calendar period):
revenue (priority list of revenue concepts), total assets, R&D, capital expenditures, cash,
long-term debt and `dei:EntityPublicFloat`. Duration items use frame `CY{year}`, balance-sheet
items `CY{year}Q4I`. Impossible negatives are set to missing and counted.

**Market capitalization is not available**: SEC does not publish prices, and combining
split-adjusted third-party prices with as-reported share counts is unreliable. `market_cap` is
left empty; **public float** (market value of non-affiliate equity as reported by the company)
is used as the market-valuation measure.

## 10. Research hypothesis and tests

*Do financial markets price technological disruption before it appears in fundamentals?*
If so, the index at *t* should predict valuation at *t+1* at least as strongly as, and earlier
than, revenue growth, R&D intensity and CAPEX intensity.

| Model | Dependent variable (t+h) | Controls |
|---|---|---|
| M1 | ln(public float) | ln(assets)_t |
| M1b | ln(public float) | ln(assets)_t, ln(public float)_t (valuation change) |
| M2 | Δ ln(revenue) | ln(assets)_t |
| M3 | R&D / assets | ln(assets)_t |
| M4 | CAPEX / assets | ln(assets)_t |

Year FE (main), year + SIC2 FE, and company + year FE; SEs clustered by company; coefficients
per 10 index points. Robustness: unwinsorized ratios (main spec winsorizes 1%/99% by year),
alternative weights, excluding the largest 10% of firms by assets, horizons *t+2* and *t+3*,
startup-only / patent-only / log-patent-count regressors, technology-linked industries only,
both-components-only sample. Every row reports N. Results are **predictive associations,
not causal effects**. Output: `results/regression_results.csv`, `results/research_report.md`.

## 11. Limitations (please read)

1. **Patent coverage is partial** (3,786 of 13,702 companies, 27.6%). Patents come from the open
   PatentsView-to-Compustat linkage of Ma (2025) mapped to CIK via the `farr` gvkey-CIK table;
   622 gvkeys linked to several CIKs are skipped as ambiguous. Unlinked firms (mostly small,
   foreign or historical registrants) have a missing patent component, so for them the index is
   the startup-exposure component only. Linkage errors in the source cannot be ruled out.
2. The startup component is **industry-level exposure**, nearly time-invariant within a firm; it
   cannot distinguish an innovative firm from a laggard in the same industry. Company fixed
   effects absorb most of it; SIC2 fixed effects absorb most of its cross-section.
3. The SIC -> technology mapping is an expert, documented judgment, not an estimated model.
   SIC codes are current, not point-in-time.
4. Accelerator data over-represent software and the US; cohort year is not founding year.
5. **Survivorship bias** is reduced but not eliminated: historical XBRL filers are included,
   but firms that never filed XBRL total assets in 2015-2024 are not.
6. The current SEC ticker file lists ~8,000 unique registrants; after removing funds/warrants
   about 7,400 unique operating-company CIKs remain. Earlier "8,865 companies" counted tickers
   (1,789 were extra share classes of the same company). Reaching 10,000+ genuine companies
   requires adding historical/delisted filers (e.g. every CIK in the XBRL frames), which the
   code supports architecturally (vectorized joins, cached per-CIK lookups) but is not enabled.
7. Public float is not market capitalization.

## 12. Current status (last full run)

| Item | Value |
|---|---|
| Universe | **13,702** companies = 7,385 currently listed (unique CIK) + 6,317 historical XBRL filers 2015-2024 (`INCLUDE_XBRL_FILERS`) |
| SIC known / country known | 12,769 (93.2%) / 12,599 |
| Startup component available | 12,445 (90.8%): 6,555 SIC-linked, 132 name-only, 5,758 industry-unlinked (score 0) |
| Startup component missing | 1,257 (916 no SIC, 341 catch-all SIC such as 7389) |
| Patent component available | 3,786 (27.6%) - PatentsView linkage (Ma, 2025), grant years 2010-2024 |
| Index available | 12,530 (91.4%) |
| Index rows (company x 2015-2024) | 137,020 (all 13,702 companies) |
| Companies with any SEC financials | 11,963 (87.3%) |
| Research panel rows (2014-2025) | 164,424 |
| Validation | 40 PASS, 8 WARN (documented limitations), 0 FAIL |

Research findings (t -> t+1, per 10 index points; see `results/research_report.md`): with year
FE a higher index is associated with higher subsequent public float (+0.055 log points),
valuation change, revenue growth and R&D intensity and slightly lower CAPEX intensity; these
associations persist with SIC2 and SIC2 x year FE. With company FE the valuation and R&D
associations vanish (valuation coefficient ~0) and the revenue-growth coefficient turns
slightly negative (p = 0.04). The index therefore ranks firms and industries cross-sectionally
but within-firm changes do not predict outcomes. These are predictive associations, not
evidence that markets price firm-specific disruption before fundamentals.

## 13. How to run

Requirements: Python 3.10+, `pandas`, `numpy`, `requests`, `statsmodels`, `linearmodels`
(optional: `google-cloud-bigquery` for the patent extraction).

```bash
# from the project root
python run_pipeline.py --list          # show steps
python run_pipeline.py                 # full run (network only for data not yet cached)
python run_pipeline.py --offline       # caches only
python run_pipeline.py --from index    # resume from a step
python run_pipeline.py --only research # single step
```

Set `SEC_USER_AGENT="Your Name your@email"` (SEC fair-access policy). All downloads are cached
in `data/raw/` and re-used; the SIC lookup is restartable (`data/raw/sec/submissions_cache.jsonl`).

### Patent data

The default source needs no credentials: step `patents_patentsview` downloads (once, ~1 GB,
cached in `data/raw/patents/ma_patentsview/`, git-ignored) the public patent-level file of
Song Ma's [patent-firm-link-share](https://github.com/songma/patent-firm-link-share)
(PatentsView release 2026-04-10, cite Ma, "Technological Obsolescence", RFS 2025) and the
gvkey-CIK table of the [`farr`](https://github.com/iangow/farr) R package (read with `pyreadr`).

Optional additional source for firms not covered by the linkage (credentialed BigQuery):

1. Either `pip install google-cloud-bigquery`, authenticate with
   `gcloud auth application-default login`, set `BIGQUERY_PROJECT=<your-project>` and run
   `python run_pipeline.py --only patents_bigquery`;
2. or paste `src/patents/patents_bigquery.sql` (with `{start_year}`/`{end_year}` replaced, e.g.
   2010/2025) into the BigQuery console, export the result and save it as
   `data/raw/patents/assignee_year_counts.csv.gz` (or `.csv`).
3. Then `python run_pipeline.py --from patents_process`.

### Dashboard and paper

* `docs/index.html` - self-contained interactive dashboard (search any company, score history,
  index distribution, industry averages, regression summary). No external libraries; open it
  locally or publish it with GitHub Pages (Settings -> Pages -> branch `main`, folder `/docs`).
* `paper/technology_disruption_index.md` - research paper draft. Every number and every
  qualitative statement about result patterns is generated from the pipeline outputs, so the
  paper updates automatically after a re-run (e.g. once full patent coverage is added).

## 14. Layout

```
config.py                     all weights, windows, taxonomies, SIC rules, paths
run_pipeline.py               orchestrator
src/common.py                 logging, SEC client, normalization helpers
src/companies/                universe: build -> clean -> enrich (1 row/CIK) -> SIC/country
src/companies/startups/       startup cleaning, tagging, company exposure scores
src/patents/                  BigQuery SQL + extractor, company-year counts, patent scores
src/technology_index/         index + coverage report
src/financials/               SEC XBRL frames -> company-year fundamentals
src/research/                 panel + regressions/report
src/validate_data.py          data-quality checks
src/dashboard/                builds docs/index.html
docs/index.html               interactive dashboard (GitHub Pages ready)
paper/                        auto-generated research paper draft
data/raw/                     cached downloads / manual inputs (never overwritten)
data/technology_index/        company_technology_index.csv, coverage_report.csv
data/research/final_panel.csv
results/                      regression_results.csv, research_report.md
```

Not part of the index: `src/companies/github_activity.py` / `data/github_activity.csv` (GitHub
org matched by first search hit - too unreliable to score without manual verification).
`data/companies_industries.csv` is a superseded legacy file (ticker level, 946 missing SIC);
`data/companies_master.csv` replaces it.
