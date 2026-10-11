"""
Stage 10: predictive (NOT causal) tests of the research hypothesis.

Does the Technology Disruption Index at t predict market valuation and firm
fundamentals at t+h?

  M1  ln(public float)_{t+h}                    ~ TDI_t + ln(assets)_t + FE
  M1b ln(public float)_{t+h}                    ~ TDI_t + ln(assets)_t + ln(public float)_t + FE
  M2  revenue growth_{t+h} = dln(revenue)       ~ TDI_t + ln(assets)_t + FE
  M3  (R&D / assets)_{t+h}                      ~ TDI_t + ln(assets)_t + FE
  M4  (CAPEX / assets)_{t+h}                    ~ TDI_t + ln(assets)_t + FE

TDI is scaled per 10 index points. Standard errors are clustered by company.
Specifications: year FE (main), year + SIC2 FE, company + year FE (PanelOLS).
Robustness: unwinsorized ratios, alternative index weights, excluding the
largest firms, horizons t+2/t+3, component-only regressors, log patent counts,
technology-linked industries only, both-components-only sample.
Every row reports its own sample size. Nothing is selected on significance.
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config
from src.common import get_logger, winsorize, write_csv
from src.technology_index.build_index import combine

warnings.filterwarnings("ignore", category=FutureWarning)
log = get_logger("run_regressions")

RATIO_OUTCOMES = ["rev_growth", "rd_assets", "capex_assets"]
MODELS = {
    "M1": ("Market valuation (ln public float)", "ln_pf", ["ln_assets"]),
    "M1b": ("Valuation change (ln public float, controlling ln public float_t)", "ln_pf",
            ["ln_assets", "ln_pf"]),
    "M2": ("Revenue growth (dln revenue)", "rev_growth", ["ln_assets"]),
    "M3": ("R&D / assets", "rd_assets", ["ln_assets"]),
    "M4": ("CAPEX / assets", "capex_assets", ["ln_assets"]),
}
MIN_OBS, MIN_FIRMS = 30, 5


def prepare(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.sort_values(["company_id", "year"]).copy()
    pos_assets = df["assets"].where(df["assets"] > 0)
    df["ln_assets"] = np.log(pos_assets)
    df["ln_pf"] = np.log(df["public_float"].where(df["public_float"] > 0))
    df["ln_rev"] = np.log(df["revenue"].where(df["revenue"] > 0))
    df["rd_assets"] = df["rd"] / pos_assets
    df["capex_assets"] = df["capex"] / pos_assets
    g = df.groupby("company_id")
    df["rev_growth"] = df["ln_rev"] - g["ln_rev"].shift(1)
    df["log_patent_count"] = np.log1p(df["patent_count"])

    for key, weights in config.ALTERNATIVE_WEIGHTS.items():
        df[f"tdi_{key}"] = combine(df, weights)["index"]

    g = df.groupby("company_id")
    for h in config.LEAD_HORIZONS:
        for v in ["ln_pf"] + RATIO_OUTCOMES:
            df[f"{v}_lead{h}"] = g[v].shift(-h)
            if v in RATIO_OUTCOMES:
                df[f"{v}_lead{h}_w"] = df.groupby("year")[f"{v}_lead{h}"].transform(winsorize)

    threshold = df.groupby("year")["assets"].transform(
        lambda s: s.quantile(config.LARGEST_FIRMS_QUANTILE))
    df["is_largest"] = df["assets"] > threshold

    sample = df[~df["is_non_operating"].fillna(False).astype(bool)
                & df["year"].isin(config.INDEX_YEARS)].copy()
    return sample


def empty_row(**meta):
    return {**meta, "coef": np.nan, "std_err": np.nan, "t_stat": np.nan, "p_value": np.nan,
            "ci_low": np.nan, "ci_high": np.nan, "n_obs": 0, "n_firms": 0, "r2": np.nan}


def run_one(df, y, x, controls, fe, meta):
    cols = [y, x, "company_id", "year", "sic2"] + controls
    d = df[cols].replace([np.inf, -np.inf], np.nan).dropna()
    meta = {**meta, "dependent": y, "regressor": x, "controls": "+".join(controls),
            "fixed_effects": fe, "cluster": "company"}
    n_firms = d["company_id"].nunique()
    if len(d) < MIN_OBS or n_firms < MIN_FIRMS or d[x].std() == 0:
        row = empty_row(**meta)
        row.update(n_obs=len(d), n_firms=n_firms, note="insufficient sample / no variation")
        return row
    d = d.assign(x_scaled=d[x] / config.INDEX_SCALE_FOR_REGRESSION)
    try:
        if fe == "firm+year":
            from linearmodels.panel import PanelOLS
            pdata = d.set_index(["company_id", "year"])
            res = PanelOLS(pdata[y], pdata[["x_scaled"] + controls],
                           entity_effects=True, time_effects=True,
                           drop_absorbed=False).fit(cov_type="clustered", cluster_entity=True)
            coef, se = res.params["x_scaled"], res.std_errors["x_scaled"]
            tval, pval = res.tstats["x_scaled"], res.pvalues["x_scaled"]
            ci = res.conf_int().loc["x_scaled"].tolist()
            r2 = res.rsquared_within
        elif fe == "sic2xyear":
            from linearmodels.iv.absorbing import AbsorbingLS
            groups = pd.Categorical(d["sic2"].astype(int).astype(str) + "_" + d["year"].astype(str))
            res = AbsorbingLS(d[y], d[["x_scaled"] + controls],
                              absorb=pd.DataFrame({"g": groups}, index=d.index),
                              drop_absorbed=True).fit(cov_type="clustered",
                                                      clusters=d[["company_id"]])
            coef, se = res.params["x_scaled"], res.std_errors["x_scaled"]
            tval, pval = res.tstats["x_scaled"], res.pvalues["x_scaled"]
            ci = res.conf_int().loc["x_scaled"].tolist()
            r2 = res.rsquared
        else:
            fe_terms = " + C(year)" + (" + C(sic2)" if fe == "year+sic2" else "")
            formula = f"{y} ~ x_scaled" + "".join(f" + {c}" for c in controls) + fe_terms
            res = smf.ols(formula, data=d).fit(cov_type="cluster",
                                               cov_kwds={"groups": d["company_id"]})
            coef, se = res.params["x_scaled"], res.bse["x_scaled"]
            tval, pval = res.tvalues["x_scaled"], res.pvalues["x_scaled"]
            ci = res.conf_int().loc["x_scaled"].tolist()
            r2 = res.rsquared
    except Exception as exc:
        row = empty_row(**meta)
        row.update(n_obs=len(d), n_firms=n_firms, note=f"estimation failed: {exc}"[:200])
        return row
    within_sd = d.groupby("company_id")["x_scaled"].transform(lambda s: s - s.mean()).std()
    note = ""
    if n_firms < 30:
        note = "few clusters: clustered SEs unreliable"
    return {**meta, "coef": coef, "std_err": se, "t_stat": tval, "p_value": pval,
            "ci_low": ci[0], "ci_high": ci[1], "n_obs": len(d), "n_firms": n_firms,
            "n_years": d["year"].nunique(), "r2": r2,
            "within_firm_sd_x": within_sd, "note": note}


def outcome_col(base, h, winsorized=True):
    if base in RATIO_OUTCOMES:
        return f"{base}_lead{h}" + ("_w" if winsorized else "")
    return f"{base}_lead{h}"


def run_all(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    x_main = "technology_disruption_index"
    linked = sample["startup_coverage_flag"].isin(["sic_linked", "sic_linked+name", "name_only"])

    for model, (label, base, controls) in MODELS.items():
        common = {"model": model, "outcome": label}
        y1 = outcome_col(base, 1)
        # main + fixed-effect variants
        for fe in ["year", "year+sic2", "sic2xyear", "firm+year"]:
            rows.append(run_one(sample, y1, x_main, controls, fe,
                                {**common, "spec": f"main_{fe.replace('+', '_')}", "horizon": 1}))
        # robustness (year FE)
        rob = {"horizon": 1}
        if base in RATIO_OUTCOMES:
            rows.append(run_one(sample, outcome_col(base, 1, False), x_main, controls, "year",
                                {**common, **rob, "spec": "unwinsorized"}))
        for key in config.ALTERNATIVE_WEIGHTS:
            rows.append(run_one(sample, y1, f"tdi_{key}", controls, "year",
                                {**common, **rob, "spec": f"weights_{key}"}))
        rows.append(run_one(sample[~sample["is_largest"].fillna(False)], y1, x_main, controls,
                            "year", {**common, **rob, "spec": "exclude_largest_10pct"}))
        for h in config.LEAD_HORIZONS[1:]:
            rows.append(run_one(sample, outcome_col(base, h), x_main, controls, "year",
                                {**common, "spec": f"horizon_t+{h}", "horizon": h}))
        rows.append(run_one(sample, y1, "startup_score", controls, "year",
                            {**common, **rob, "spec": "startup_component_only"}))
        rows.append(run_one(sample, y1, "patent_score", controls, "year",
                            {**common, **rob, "spec": "patent_component_only"}))
        rows.append(run_one(sample, y1, "log_patent_count", controls, "year",
                            {**common, **rob, "spec": "log_patent_count"}))
        rows.append(run_one(sample[linked], y1, x_main, controls, "year",
                            {**common, **rob, "spec": "tech_linked_industries_only"}))
        rows.append(run_one(sample[sample["components_available"] == 2], y1, x_main, controls,
                            "year", {**common, **rob, "spec": "both_components_only"}))
    out = pd.DataFrame(rows)
    order = ["model", "outcome", "spec", "horizon", "dependent", "regressor", "controls",
             "fixed_effects", "cluster", "coef", "std_err", "t_stat", "p_value", "ci_low",
             "ci_high", "n_obs", "n_firms", "n_years", "r2", "within_firm_sd_x", "note"]
    return out.reindex(columns=order)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def fmt(v, nd=3):
    if pd.isna(v):
        return ""
    return f"{v:.{nd}f}"


def stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def table(df: pd.DataFrame) -> str:
    lines = ["| Model | Spec | h | Coef (per 10 pts) | SE | p | 95% CI | N obs | N firms | R2 | Note |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples(index=False):
        ci = f"[{fmt(r.ci_low)}, {fmt(r.ci_high)}]" if pd.notna(r.ci_low) else ""
        lines.append(f"| {r.model} | {r.spec} | {r.horizon} | {fmt(r.coef, 4)}{stars(r.p_value)} | "
                     f"{fmt(r.std_err, 4)} | {fmt(r.p_value)} | {ci} | {int(r.n_obs)} | "
                     f"{int(r.n_firms)} | {fmt(r.r2)} | {r.note if isinstance(r.note, str) else ''} |")
    return "\n".join(lines)


def interpret(results: pd.DataFrame) -> list:
    text = []
    for model, (label, _, _) in MODELS.items():
        sub = results[results["model"] == model].set_index("spec")
        main = sub.loc["main_year"] if "main_year" in sub.index else None
        if main is None or pd.isna(main["coef"]):
            text.append(f"- **{model} ({label})**: not estimable with the available sample.")
            continue
        direction = "positive" if main["coef"] > 0 else "negative"
        sig = main["p_value"] < 0.05
        sentence = (f"- **{model} ({label})**: with year FE, a 10-point higher index at t is "
                    f"associated with a {direction} difference of {main['coef']:.4f} in the t+1 "
                    f"outcome (p = {main['p_value']:.3f}, N = {int(main['n_obs'])}); "
                    f"{'statistically distinguishable from zero at 5%' if sig else 'not statistically distinguishable from zero at 5%'}.")
        for spec, name in [("main_year_sic2", "Adding SIC2 industry FE"),
                           ("main_sic2xyear", "With SIC2 x year FE (sector cycles absorbed)"),
                           ("main_firm_year", "With company + year FE")]:
            if spec in sub.index and pd.notna(sub.loc[spec, "coef"]):
                r = sub.loc[spec]
                sentence += f" {name}: {r['coef']:.4f} (p = {r['p_value']:.3f})."
        informative = sub[sub["n_firms"] >= 30].drop(index="main_year", errors="ignore")
        informative = informative[informative["coef"].notna()]
        same = (np.sign(informative["coef"]) == np.sign(main["coef"])).sum()
        sig_same = ((np.sign(informative["coef"]) == np.sign(main["coef"]))
                    & (informative["p_value"] < 0.05)).sum()
        sentence += (f" Across the other {len(informative)} specifications with >= 30 firms, "
                     f"{same} have the same sign and {sig_same} of those have p < 0.05.")
        text.append(sentence)
    return text


def timing_table(results: pd.DataFrame) -> str:
    lines = ["| Model | h = 1 | h = 2 | h = 3 |", "|---|---|---|---|"]
    for model in MODELS:
        sub = results[results["model"] == model]
        cells = []
        for h, spec in [(1, "main_year"), (2, "horizon_t+2"), (3, "horizon_t+3")]:
            r = sub[sub["spec"] == spec]
            if r.empty or pd.isna(r["coef"].iloc[0]):
                cells.append("")
            else:
                r = r.iloc[0]
                cells.append(f"{r['coef']:.4f}{stars(r['p_value'])} (N={int(r['n_obs'])})")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(results: pd.DataFrame, sample: pd.DataFrame) -> None:
    cov = pd.read_csv(config.COVERAGE_REPORT)
    any_year = cov[cov["scope"] == "any_year"].iloc[0]
    tdi = sample["technology_disruption_index"]
    main = results[results["spec"].str.startswith("main_")]
    robust = results[~results["spec"].str.startswith("main_")]
    n_tests = results["p_value"].notna().sum()
    n_sig = (results["p_value"] < 0.05).sum()

    lines = [
        "# Technology Disruption Index - Research Report",
        "",
        "_Auto-generated by `src/research/run_regressions.py`. All results are predictive "
        "associations, not causal effects._",
        "",
        "## 1. Question",
        "",
        "Do financial markets price technological disruption before it shows up in traditional "
        "firm fundamentals? Operationally: does the index at year t predict market valuation "
        "(public float) and fundamentals (revenue growth, R&D intensity, CAPEX intensity) at t+1..t+3?",
        "",
        "## 2. Data coverage",
        "",
        f"- Company universe: **{int(any_year['total_companies'])}** SEC registrants (unique CIK).",
        f"- Startup-ecosystem component available: {int(any_year['startup_coverage'])} "
        f"({any_year['startup_coverage_pct']}%).",
        f"- Patent component available: {int(any_year['patent_coverage'])} "
        f"({any_year['patent_coverage_pct']}%).",
        f"- Index available (>=1 component): {int(any_year['index_coverage'])} "
        f"({any_year['index_coverage_pct']}%); both components: {int(any_year['both_components'])}.",
        f"- Regression sample (operating firms, {min(config.INDEX_YEARS)}-{max(config.INDEX_YEARS)}): "
        f"{len(sample)} company-years; index non-missing in {int(tdi.notna().sum())}.",
        "",
    ]
    if any_year["patent_coverage_pct"] < 5:
        lines += [
            "> **Important:** patent data currently cover only a handful of firms, so for almost "
            "every company the index equals the startup-ecosystem component. The startup component "
            "is an *industry-level technology-exposure* measure (SIC -> technology category -> "
            "accelerator activity) that varies little over time within a firm. The tests below are "
            "therefore mainly tests of whether firms in technology-exposed industries show different "
            "subsequent valuation/fundamentals - not tests of firm-specific innovation. Company fixed-"
            "effect estimates rely on the small within-firm variation and should be read with care.",
            "",
        ]
    lines += [
        "## 3. Index distribution (regression sample)",
        "",
        f"- mean {tdi.mean():.1f}, sd {tdi.std():.1f}, median {tdi.median():.1f}, "
        f"share exactly 0 (industry not linked to tracked technologies): {(tdi == 0).mean():.1%}",
        "",
        "## 4. Main results (t -> t+1)",
        "",
        "Coefficients are per 10 index points; SEs clustered by company; * p<0.10, ** p<0.05, *** p<0.01.",
        "",
        table(main),
        "",
        "### Reading the main results",
        "",
        *interpret(results),
        "",
        "How to read the fixed-effect columns: the year-FE estimate mixes differences *between* "
        "industries with differences within them. SIC2 FE keep only variation across 4-digit SIC "
        "codes and name evidence inside a 2-digit industry. SIC2 x year FE additionally remove "
        "industry-wide valuation/fundamental cycles (e.g. the 2020-21 technology boom). Company + "
        "year FE use only within-firm changes in the index, which for the startup component come "
        "from shifts in accelerator category composition over time - i.e. industry-level "
        "variation, not firm-specific news.",
        "",
        "## 5. Timing: does valuation move before fundamentals?",
        "",
        "Year-FE coefficients per 10 index points by horizon (index at t, outcome at t+h). "
        "The hypothesis predicts valuation associations (M1/M1b) that appear at shorter horizons "
        "than, or independently of, associations with fundamentals (M2-M4).",
        "",
        timing_table(results),
        "",
        "These are separate regressions on different samples; they describe predictive "
        "patterns and are not a formal test of lead-lag ordering.",
        "",
        "## 6. Robustness",
        "",
        table(robust),
        "",
        "Note: alternative index weights (25/75, 50/50, 75/25) change the index only for firms that "
        "have both components; with the current patent coverage those rows are nearly identical "
        "by construction and are not informative about weighting.",
        "",
        "Rows marked 'few clusters' (patent-based regressors) rely on fewer than 30 firms; their "
        "p-values are not reliable and should not be interpreted.",
        "",
        f"In total {n_tests} coefficients were estimated and {n_sig} have p < 0.05. With this many "
        "tests, some nominally significant coefficients are expected by chance alone; conclusions "
        "should rest on patterns that are consistent across specifications, not on individual "
        "p-values.",
        "",
        "## 7. Interpretation limits",
        "",
        "- **No causal identification.** These are lagged panel regressions with fixed effects; "
        "omitted firm characteristics correlated with industry technology exposure can drive them.",
        "- **Survivorship bias.** The universe is today's SEC ticker list, so firms that delisted "
        "during 2015-2024 are missing.",
        "- **Static industry codes.** SIC codes are current, not point-in-time.",
        "- **Valuation measure.** Public float (non-affiliate equity value, measured at the end of "
        "the second fiscal quarter) is used because SEC does not publish prices; it is not full "
        "market capitalization.",
        "- **R&D sample selection.** Many firms do not report R&D separately; M3 is estimated on "
        "reporters only (missing R&D is not treated as zero).",
        "- **Patent coverage.** See the coverage section; until the BigQuery extraction is run "
        "for the full universe, patent-related robustness rows have very few firms.",
        "- **Foreign filers.** SEC frames only cover US-GAAP facts in USD, so most IFRS filers "
        "(20-F) have no fundamentals and drop out of the regressions.",
        "- **Winsorization sensitivity.** Ratio outcomes are winsorized 1%/99% by year in the main "
        "specification; compare the 'unwinsorized' rows - where they differ in sign, the main "
        "estimate is driven by the bulk of the distribution and not robust to extreme observations.",
        "",
    ]
    config.RESEARCH_REPORT.parent.mkdir(parents=True, exist_ok=True)
    config.RESEARCH_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    panel = pd.read_csv(config.FINAL_PANEL)
    sample = prepare(panel)
    results = run_all(sample)
    write_csv(results, config.REGRESSION_RESULTS)
    write_report(results, sample)
    est = results["coef"].notna().sum()
    log.info("Regressions: %d specifications, %d estimated -> %s", len(results), est,
             config.REGRESSION_RESULTS)
    log.info("Main results:\n%s", results[results["spec"].str.startswith("main_")][
        ["model", "spec", "coef", "std_err", "p_value", "n_obs", "n_firms"]].to_string(index=False))


if __name__ == "__main__":
    main()
