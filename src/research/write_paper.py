"""
Stage 12: research paper draft (paper/technology_disruption_index.md).

Every number in the text is read from pipeline outputs at build time, so the
paper stays consistent with the data after any re-run.
"""
import numpy as np
import pandas as pd

import config
from src.common import get_logger

log = get_logger("write_paper")
OUT = config.ROOT / "paper" / "technology_disruption_index.md"

LABELS = {"M1": "ln public float", "M1b": "valuation change", "M2": "revenue growth",
          "M3": "R&D / assets", "M4": "CAPEX / assets"}
SPECS = [("main_year", "Year FE"), ("main_year_sic2", "Year + SIC2 FE"),
         ("main_sic2xyear", "SIC2 x year FE"), ("main_firm_year", "Firm + year FE")]


def stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def cell(r):
    if r is None or pd.isna(r["coef"]):
        return "n/a"
    return f"{r['coef']:.4f}{stars(r['p_value'])}<br>({r['std_err']:.4f})"


def pv(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def get(results, model, spec):
    sub = results[(results["model"] == model) & (results["spec"] == spec)]
    return None if sub.empty else sub.iloc[0]


def main_table(results) -> str:
    head = "| Outcome (t+1) | " + " | ".join(s[1] for s in SPECS) + " | N obs | N firms |"
    lines = [head, "|---" * (len(SPECS) + 3) + "|"]
    for model, label in LABELS.items():
        base = get(results, model, "main_year")
        cells = [cell(get(results, model, s)) for s, _ in SPECS]
        lines.append(f"| {model}: {label} | " + " | ".join(cells) +
                     f" | {int(base['n_obs']):,} | {int(base['n_firms']):,} |")
    return "\n".join(lines)


def horizon_table(results) -> str:
    lines = ["| Outcome | t+1 | t+2 | t+3 |", "|---|---|---|---|"]
    for model, label in LABELS.items():
        cells = [cell(get(results, model, s)) for s in ["main_year", "horizon_t+2", "horizon_t+3"]]
        lines.append(f"| {model}: {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def robustness_table(results) -> str:
    specs = [("unwinsorized", "Unwinsorized ratios"), ("exclude_largest_10pct", "Excl. largest 10%"),
             ("tech_linked_industries_only", "Tech-linked industries only"),
             ("startup_component_only", "Startup component only")]
    lines = ["| Outcome | " + " | ".join(s[1] for s in specs) + " |", "|---" * (len(specs) + 1) + "|"]
    for model, label in LABELS.items():
        lines.append(f"| {model}: {label} | " +
                     " | ".join(cell(get(results, model, s)) for s, _ in specs) + " |")
    return "\n".join(lines)


def main() -> None:
    cov = pd.read_csv(config.COVERAGE_REPORT)
    cv = cov[cov["scope"] == "any_year"].iloc[0]
    results = pd.read_csv(config.REGRESSION_RESULTS)
    startups = pd.read_csv(config.STARTUPS_TAGGED, usecols=["technology_count", "year"])
    fin = pd.read_csv(config.FINANCIALS, usecols=["company_id"])
    idx = pd.read_csv(config.TECH_INDEX, low_memory=False)
    flags = pd.read_csv(config.COMPANY_STARTUP_SCORES)["coverage_flag"].value_counts()
    latest = idx[idx["year"] == max(config.INDEX_YEARS)]["technology_disruption_index"]
    m1 = get(results, "M1", "main_year")
    m1b = get(results, "M1b", "main_year")
    m2 = get(results, "M2", "main_year")
    m3u = get(results, "M3", "unwinsorized")
    n_tests = int(results["p_value"].notna().sum())
    n_sig = int((results["p_value"] < 0.05).sum())
    y0, y1 = min(config.INDEX_YEARS), max(config.INDEX_YEARS)
    n_comp = int(cv["total_companies"])

    def sig(model, spec):
        r = get(results, model, spec)
        return r is not None and pd.notna(r["p_value"]) and r["p_value"] < 0.05

    valuation_robust = all(sig(m, s) for m in ["M1", "M1b"]
                           for s in ["main_year_sic2", "main_sic2xyear", "main_firm_year"])
    fundamentals_vanish = all(not sig(m, "main_firm_year") for m in ["M2", "M3", "M4"])
    if valuation_robust and fundamentals_vanish:
        pattern = ("Associations with valuation survive industry, industry-by-year and firm fixed "
                   "effects, while associations with fundamentals disappear within firms.")
        fe_paragraph = ("Fundamentals show a different pattern. Revenue growth and R&D intensity are "
                        "higher and CAPEX intensity lower for technology-exposed firms across firms, but "
                        "these associations become small and statistically insignificant once firm fixed "
                        "effects are included, while the valuation associations do not.")
        discussion = ("Taken together, the evidence is *consistent with* markets assigning higher and "
                      "rising valuations to firms in technology-exposed domains, while the corresponding "
                      "differences in fundamentals are mostly cross-sectional (technology firms are "
                      "asset-light and R&D-intensive) rather than changes within firms. This is the "
                      "pattern one would expect if valuations respond to technology exposure before "
                      "fundamentals do. However, three cautions apply.")
    else:
        pattern = ("The robustness of these associations differs across fixed-effect specifications "
                   "(see Table 1).")
        fe_paragraph = ("Table 1 shows how the associations change when comparing firms within "
                        "industries, within industry-years and within firms; conclusions should rest "
                        "on the specifications in which they are stable.")
        discussion = ("The evidence does not show a uniform pattern across specifications, so it "
                      "neither clearly supports nor rejects the hypothesis that valuations move before "
                      "fundamentals. Three further cautions apply.")

    text = f"""# Do Markets Price Technology Exposure Before Fundamentals? Evidence from a Technology Disruption Index for {n_comp:,} U.S.-Listed Companies

*Draft research paper. All figures are generated automatically from the project pipeline.*

## Abstract

I construct a reproducible, company-year Technology Disruption Index (TDI) for {n_comp:,} SEC-registered
public companies over {y0}-{y1}. The index combines (i) patent volume and momentum and (ii) the intensity of
startup activity, measured across {len(startups):,} accelerator-backed startups, in the technology domains
in which each company operates. Linking the index to SEC XBRL fundamentals, I test whether technology exposure
predicts market valuation before it predicts revenue growth, R&D intensity and capital expenditure. A 10-point
higher index is associated with about {m1['coef']*100:.1f}% higher public float one year later ({pv(m1['p_value'])})
and with {m2['coef']*100:.2f} percentage points higher revenue growth ({pv(m2['p_value'])}), controlling for
size and year effects. {pattern} Because patent data currently cover few firms,
the index is mainly an industry-level exposure measure; results are predictive associations, not causal effects.

## 1. Introduction

Technological change is widely believed to reshape industries before it is visible in accounting statements.
If investors recognise technological opportunities early, market valuations should anticipate later changes in
revenues and investment. If instead investors under-react to hard-to-value innovation, fundamentals may move first
and valuations follow. The question has a long history in finance and economics, from the link between patents and
market value (Griliches, 1981; Hall, Jaffe and Trajtenberg, 2005) to evidence that markets misvalue innovative
firms (Eberhart, Maxwell and Siddique, 2004; Cohen, Diether and Malloy, 2013) and that the value of patents is
priced at grant (Kogan, Papanikolaou, Seru and Stoffman, 2017).

This project contributes a transparent, fully reproducible measurement pipeline that scores every listed company
rather than a hand-picked sample of technology firms. Its main design principles are: (1) the full company
universe is preserved and missing data are never treated as zero; (2) every methodological choice is configurable
and documented; (3) results are reported for every specification, without selecting on significance.

## 2. Data

**Company universe.** SEC's public ticker list, cleaned of ETFs, funds, warrants, units and SPAC shells, and
collapsed to one record per Central Index Key (CIK): {n_comp:,} companies. Industry (SIC), country and entity type
come from the SEC submissions API.

**Startups.** {len(startups):,} unique startups from seven accelerators (Y Combinator, Techstars, Plug and Play,
500 Global, Antler, Alchemist, Entrepreneur First), deduplicated by website domain. {(startups['technology_count'] > 0).mean():.0%}
are assigned to at least one of nine technology categories (AI, Fintech, Cloud, Robotics, Cybersecurity, Biotech,
Semiconductors, Energy, Quantum) using word-bounded keyword rules on tags and descriptions.

**Patents.** U.S. patent counts from Google Patents Public Data (BigQuery). In the current version patent data are
available for {int(cv['patent_coverage'])} companies; the extraction query for the full universe is part of the pipeline.

**Fundamentals.** Revenue, total assets, R&D, capital expenditure, cash, long-term debt and public float from the
SEC XBRL frames API for {fin['company_id'].nunique():,} companies. Market capitalisation is not used because SEC does
not publish prices; public float (the market value of non-affiliate equity reported by the company) is the
valuation measure.

## 3. Methodology

**Startup-ecosystem score.** Each company receives exposure weights w(i,c) in {{0, 0.5, 1}} for each technology category c
from documented SIC-to-category rules (1 = core activity, 0.5 = adjacent industry), supplemented by weak evidence
from the company's legal name. Category activity in year t is intensity(c,t) = log(1+n(c,t)) / log(1+N(t)), where n
counts startups of category c in cohorts t-2..t. The company's raw activity is the exposure-weighted sum, converted to a
within-year percentile (0-100). Companies whose industry is known but not linked to any category score 0
({int(flags.get('industry_unlinked', 0)):,} firms, flagged); companies without a usable industry code are missing
({int(flags.get('missing_sic', 0) + flags.get('uninformative_sic', 0)):,} firms).

**Patent score.** volume score = 100 * log(1+patents) / log(1+10,000); momentum = (recent 3-year mean + 1) / (previous
3-year mean + 1), mapped to 0-100 through log2; patent score = average of the two. Only complete patent years are used.

**Index.** TDI = weighted average of available components (default 50/50), with the number of available components
and a coverage score reported for every company-year. In {y1}, the index is available for
{int(latest.notna().sum()):,} companies (mean {latest.mean():.1f}, median {latest.median():.1f}).

**Empirical model.** For outcome Y and horizon h:

Y(i,t+h) = b * TDI(i,t)/10 + g * ln(assets)(i,t) + fixed effects + e(i,t+h)

with standard errors clustered by company. Outcomes: ln public float (M1), ln public float controlling for its current
level (M1b, a valuation-change model), revenue growth (M2), R&D/assets (M3), CAPEX/assets (M4). Ratios are winsorised
at 1%/99% by year. Non-operating entities are excluded.

## 4. Results

**Table 1. Technology index at t and outcomes at t+1** (coefficient per 10 index points, clustered SE in parentheses;
* p<0.10, ** p<0.05, *** p<0.01)

{main_table(results)}

With year effects, a 10-point higher index is associated with about {m1['coef']*100:.1f}% higher public float
one year later ({pv(m1['p_value'])}). The valuation-change model (M1b), which conditions on current public float,
yields a coefficient of {m1b['coef']:.4f} ({pv(m1b['p_value'])}), i.e. the index is also associated with subsequent
valuation *changes*, not only levels. Comparing firms within the same two-digit industry, and absorbing
industry-specific annual shocks (SIC2 x year), makes a pure sector-cycle explanation less likely, although it
cannot rule out other omitted firm characteristics.

{fe_paragraph}

**Table 2. Horizons** (year FE)

{horizon_table(results)}

**Table 3. Robustness** (year FE, t+1)

{robustness_table(results)}

## 5. Discussion

{discussion}

First, the within-firm variation of the index comes from shifts in the composition of accelerator cohorts, an
industry-level signal; it does not identify firm-specific innovation. Second, the R&D result is sensitive to extreme
values: without winsorisation its coefficient is {m3u['coef']:.3f} ({pv(m3u['p_value'])}). Third, {n_sig} of
{n_tests} estimated coefficients have p < 0.05; consistent patterns across specifications are more informative than
any single p-value.

## 6. Limitations

1. Patent data currently cover {int(cv['patent_coverage'])} companies, so the index is predominantly the startup component.
2. The SIC-to-technology mapping is expert judgement, documented rule by rule, not an estimated model; SIC codes are current rather than historical.
3. Accelerator data over-represent software and U.S. startups.
4. The universe consists of currently listed firms (survivorship bias).
5. Public float is not market capitalisation; IFRS filers lack fundamentals in the SEC frames data.
6. No causal identification strategy is implemented.

## 7. Conclusion

A transparent technology-exposure index covering {n_comp:,} listed companies is associated with subsequent
valuations and fundamentals in the ways summarised in Tables 1-3. {pattern} Extending patent coverage to the full universe would turn the index into a firm-specific
measure and allow a sharper test of whether markets price technological disruption before fundamentals.

## References

- Cohen, L., Diether, K., & Malloy, C. (2013). Misvaluing innovation. *Review of Financial Studies*, 26(3), 635-666.
- Eberhart, A. C., Maxwell, W. F., & Siddique, A. R. (2004). An examination of long-term abnormal stock returns and operating performance following R&D increases. *Journal of Finance*, 59(2), 623-650.
- Griliches, Z. (1981). Market value, R&D, and patents. *Economics Letters*, 7(2), 183-187.
- Hall, B. H., Jaffe, A., & Trajtenberg, M. (2005). Market value and patent citations. *RAND Journal of Economics*, 36(1), 16-38.
- Kogan, L., Papanikolaou, D., Seru, A., & Stoffman, N. (2017). Technological innovation, resource allocation, and growth. *Quarterly Journal of Economics*, 132(2), 665-712.

## Appendix: reproducibility

Code, configuration and data: project repository. Run `python run_pipeline.py`. All parameters are in `config.py`;
the SIC-to-technology mapping actually applied is exported to `data/startups/sic_technology_map.csv`.
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    log.info("Paper draft -> %s (%d words)", OUT, len(text.split()))


if __name__ == "__main__":
    main()
