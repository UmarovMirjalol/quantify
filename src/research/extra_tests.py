"""
Stage 10b: extra diagnostics for the main valuation association (M1, SIC2 x year FE).

  ln(public float)_{t+1} ~ TDI_t + ln(assets)_t + SIC2 x year FE, SEs clustered by company

All tests re-use the exact sample of results/regression_results.csv (main_sic2xyear)
and are pre-specified here; none of them is chosen by its p-value.

  1. Placebo / permutation: the index is shuffled across firms *within* each
     SIC2 x year cell (the variation the FE model actually uses), the model is
     re-estimated PLACEBO_DRAWS times with a fixed seed, and the real coefficient
     is compared with the placebo distribution.
  2. Binned scatter: both sides residualised on ln(assets) and the FE, split into
     BINSCATTER_BINS equal-count bins of the index residual.
  3. Year by year: the same model on each year's cross-section (SIC2 FE,
     heteroskedasticity-robust SEs; one row per firm per year).
  4. Leave one industry out: re-estimated dropping each industry (>= 100 firm-years) in turn.
  5. Specification curve: every estimated row of regression_results.csv whose regressor
     is on the 0-100 index scale.

Predictive associations only; none of these tests make the result causal.
"""
import json

import numpy as np
import pandas as pd

import config
from src.common import get_logger
from src.research.run_regressions import prepare

log = get_logger("extra_tests")

Y, X, Z = "ln_pf_lead1", "technology_disruption_index", "ln_assets"
LOO_MIN_OBS = 100   # dropping an industry with fewer firm-years cannot move the estimate


def demean(v: np.ndarray, codes: np.ndarray) -> np.ndarray:
    sums = np.bincount(codes, weights=v)
    cnt = np.bincount(codes)
    return v - (sums / cnt)[codes]


def fwl(y, x, z, codes):
    """Within-group demeaning + partialling out z. Returns (coef, x residual, y residual)."""
    yd, xd, zd = demean(y, codes), demean(x, codes), demean(z, codes)
    zz = zd @ zd
    xr = xd - (xd @ zd / zz) * zd
    yr = yd - (yd @ zd / zz) * zd
    return (xr @ yr) / (xr @ xr), xr, yr


def cluster_se(xr, e, clusters, n_groups):
    n = len(xr)
    k = n_groups + 2
    score = np.bincount(clusters, weights=xr * e)
    g = len(score)
    adj = g / (g - 1) * (n - 1) / max(n - k, 1)
    return float(np.sqrt(adj * (score @ score)) / (xr @ xr))


def hc1_se(xr, e, n_groups):
    n = len(xr)
    k = n_groups + 2
    return float(np.sqrt(n / max(n - k, 1) * ((xr * e) ** 2).sum()) / (xr @ xr))


def estimate(d: pd.DataFrame, fe_cols, cluster=True):
    codes = pd.factorize(pd.MultiIndex.from_frame(d[fe_cols]))[0] if len(fe_cols) > 1 \
        else pd.factorize(d[fe_cols[0]])[0]
    y, x = d[Y].to_numpy(float), d[X].to_numpy(float) / config.INDEX_SCALE_FOR_REGRESSION
    coef, xr, yr = fwl(y, x, d[Z].to_numpy(float), codes)
    e = yr - coef * xr
    n_groups = codes.max() + 1
    se = cluster_se(xr, e, pd.factorize(d["company_id"])[0], n_groups) if cluster \
        else hc1_se(xr, e, n_groups)
    return {"coef": float(coef), "se": se, "ci_low": float(coef - 1.96 * se),
            "ci_high": float(coef + 1.96 * se), "n_obs": int(len(d)),
            "n_firms": int(d["company_id"].nunique())}, codes, xr, yr


def pct(coef):
    return float((np.exp(coef) - 1) * 100)


def placebo(d: pd.DataFrame, codes: np.ndarray, actual: float):
    rng = np.random.default_rng(config.PLACEBO_SEED)
    x = d[X].to_numpy(float) / config.INDEX_SCALE_FOR_REGRESSION
    y, z = d[Y].to_numpy(float), d[Z].to_numpy(float)
    yd, zd = demean(y, codes), demean(z, codes)
    zz = zd @ zd
    yr = yd - (yd @ zd / zz) * zd
    xd = demean(x, codes)
    draws = np.empty(config.PLACEBO_DRAWS)
    order = np.argsort(codes, kind="stable")
    for i in range(config.PLACEBO_DRAWS):
        perm = np.lexsort((rng.random(len(x)), codes))
        xp = np.empty_like(xd)
        xp[order] = xd[perm]
        xr = xp - (xp @ zd / zz) * zd
        draws[i] = (xr @ yr) / (xr @ xr)
    p = (1 + np.sum(np.abs(draws) >= abs(actual))) / (len(draws) + 1)
    hist, edges = np.histogram(draws, bins=40)
    return {"draws": int(len(draws)), "seed": config.PLACEBO_SEED, "actual": actual,
            "mean": float(draws.mean()), "sd": float(draws.std(ddof=1)),
            "p05": float(np.quantile(draws, 0.05)), "p95": float(np.quantile(draws, 0.95)),
            "max_abs": float(np.abs(draws).max()), "perm_p": float(p),
            "z": float((actual - draws.mean()) / draws.std(ddof=1)),
            "hist": hist.tolist(), "edges": edges.tolist()}


def binscatter(d, xr, yr, coef):
    bins = config.BINSCATTER_BINS
    q = pd.qcut(pd.Series(xr).rank(method="first"), bins, labels=False).to_numpy()
    out = []
    for b in range(bins):
        m = q == b
        out.append({"x": float(xr[m].mean() * config.INDEX_SCALE_FOR_REGRESSION),
                    "y": float(yr[m].mean()), "n": int(m.sum())})
    return {"bins": out, "slope_per_point": float(coef / config.INDEX_SCALE_FOR_REGRESSION)}


def by_year(d):
    rows = []
    for yr in sorted(d["year"].unique()):
        s = d[d["year"] == yr]
        if len(s) < 100:
            continue
        r = estimate(s, ["sic2"], cluster=False)[0]
        rows.append({"year": int(yr), **r, "pct": pct(r["coef"])})
    return rows


def leave_one_out(d):
    rows = []
    for ind, n in d["industry"].value_counts().items():
        if n < LOO_MIN_OBS:
            continue
        r = estimate(d[d["industry"] != ind], ["sic2", "year"])[0]
        rows.append({"dropped": ind, "dropped_obs": int(n), **r, "pct": pct(r["coef"])})
    return sorted(rows, key=lambda r: r["coef"])


def spec_curve():
    """Rows whose regressor is on the 0-100 index scale. log_patent_count is excluded because
    'per 10 units' of a log count is not comparable; it stays in regression_results.csv."""
    res = pd.read_csv(config.REGRESSION_RESULTS).dropna(subset=["coef"])
    res = res[res["regressor"] != "log_patent_count"]
    rows = []
    for r in res.itertuples():
        rows.append({"model": r.model, "spec": r.spec, "coef": float(r.coef),
                     "ci_low": float(r.ci_low), "ci_high": float(r.ci_high),
                     "p": float(r.p_value), "n_obs": int(r.n_obs)})
    return rows


def write_md(out):
    m, pl = out["main"], out["placebo"]
    lines = [
        "# Extra diagnostics for the main valuation association", "",
        "Model: ln(public float)_{t+1} ~ TDI_t (per 10 points) + ln(assets)_t + SIC2 x year FE, "
        "SEs clustered by company. Predictive association, not a causal effect.", "",
        f"Re-estimated coefficient: {m['coef']:.4f} (SE {m['se']:.4f}), "
        f"{m['pct']:+.1f}% per 10 index points; N = {m['n_obs']:,}, firms = {m['n_firms']:,}.", "",
        "## Placebo (index shuffled within SIC2 x year)", "",
        f"{pl['draws']} draws, seed {pl['seed']}. Placebo mean {pl['mean']:.4f}, "
        f"SD {pl['sd']:.4f}, 5-95% [{pl['p05']:.4f}, {pl['p95']:.4f}], "
        f"largest |placebo| {pl['max_abs']:.4f}. Permutation p = {pl['perm_p']:.4f} "
        f"(minimum possible {1 / (pl['draws'] + 1):.4f}).", "",
        "## Year by year (SIC2 FE, HC1 SEs)", "", "| year | coef | 95% CI | % per 10 pts | N |",
        "|---|---|---|---|---|",
    ]
    for r in out["by_year"]:
        lines.append(f"| {r['year']} | {r['coef']:.4f} | [{r['ci_low']:.4f}, {r['ci_high']:.4f}] "
                     f"| {r['pct']:+.1f}% | {r['n_obs']:,} |")
    lines += ["", "## Leave one industry out", "", "| dropped | coef | 95% CI | N |",
              "|---|---|---|---|"]
    for r in out["leave_one_out"]:
        lines.append(f"| {r['dropped']} | {r['coef']:.4f} | [{r['ci_low']:.4f}, "
                     f"{r['ci_high']:.4f}] | {r['n_obs']:,} |")
    lines += ["", "Binned scatter and the full specification curve are in extra_tests.json.", ""]
    config.EXTRA_TESTS_MD.write_text("\n".join(lines), encoding="utf-8")


def export_replication_panel(sample: pd.DataFrame) -> None:
    """Compact column arrays for the in-browser replication lab: the two index components
    (so visitors can re-weight the index), ln(assets), next-year ln(public float), firm,
    year, SIC2 and industry. Scores are stored x10 and logs x1000 as integers."""
    d = sample[["company_id", "year", "sic2", "industry", "patent_score", "startup_score",
                Z, Y, X]].replace([np.inf, -np.inf], np.nan)
    d = d.dropna(subset=[Y, Z, "sic2"])
    d = d[d["patent_score"].notna() | d["startup_score"].notna()].copy()
    d["industry"] = d["industry"].fillna("Unclassified")
    inds = sorted(d["industry"].unique())
    years = sorted(int(y) for y in d["year"].unique())
    to_int = lambda s, k: [None if pd.isna(v) else int(round(v * k)) for v in s]
    out = {
        "note": "Derived from SEC XBRL, PatentsView and accelerator data; see README.",
        "years": years, "industries": inds,
        "firm": pd.factorize(d["company_id"])[0].tolist(),
        "year": (d["year"].astype(int) - years[0]).tolist(),
        "sic2": d["sic2"].astype(int).tolist(),
        "ind": d["industry"].map({k: i for i, k in enumerate(inds)}).tolist(),
        "p": to_int(d["patent_score"], 10), "s": to_int(d["startup_score"], 10),
        "a": to_int(d[Z], 1000), "y": to_int(d[Y], 1000),
        "weights": config.INDEX_WEIGHTS,
    }
    config.REPLICATION_PANEL.parent.mkdir(parents=True, exist_ok=True)
    config.REPLICATION_PANEL.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    log.info("Replication panel: %d rows, %d firms -> %s", len(d), d["company_id"].nunique(),
             config.REPLICATION_PANEL)


def main() -> None:
    sample = prepare(pd.read_csv(config.FINAL_PANEL))
    export_replication_panel(sample)
    d = sample[[Y, X, Z, "company_id", "year", "sic2", "industry"]] \
        .replace([np.inf, -np.inf], np.nan).dropna(subset=[Y, X, Z, "sic2"]).copy()
    d["industry"] = d["industry"].fillna("Unclassified")
    d["sic2"] = d["sic2"].astype(int)
    main_r, codes, xr, yr = estimate(d, ["sic2", "year"])
    main_r["pct"] = pct(main_r["coef"])
    log.info("Main re-estimate: coef %.4f se %.4f N %d", main_r["coef"], main_r["se"], len(d))
    out = {"main": main_r,
           "placebo": placebo(d, codes, main_r["coef"]),
           "binscatter": binscatter(d, xr, yr, main_r["coef"]),
           "by_year": by_year(d),
           "leave_one_out": leave_one_out(d),
           "spec_curve": spec_curve()}
    config.EXTRA_TESTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    config.EXTRA_TESTS_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    write_md(out)
    pl = out["placebo"]
    log.info("Placebo: mean %.4f sd %.4f max|b| %.4f perm p %.4f", pl["mean"], pl["sd"],
             pl["max_abs"], pl["perm_p"])
    log.info("Wrote %s and %s", config.EXTRA_TESTS_JSON, config.EXTRA_TESTS_MD)


if __name__ == "__main__":
    main()
