"""
Stage 6: Technology Disruption Index (company-year) + coverage report.

The grid is the FULL company universe x INDEX_YEARS; no company is dropped.

  index = sum_k w_k * score_k / sum_k(available) w_k        (k in patent, startup)
  components_available = number of non-missing components
  coverage_score       = sum of weights of available components / sum of all weights

Missing components are never imputed; a one-component index is reported but
visibly flagged through components_available / coverage_score.
"""
import numpy as np
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("build_index")


def combine(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    total = sum(weights.values())
    num = pd.Series(0.0, index=df.index)
    den = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        ok = df[col].notna()
        num[ok] += w * df.loc[ok, col]
        den[ok] += w
    n = sum(df[c].notna().astype(int) for c in weights)
    index = (num / den.replace(0, np.nan)).where(n >= config.MIN_COMPONENTS_FOR_INDEX)
    return pd.DataFrame({"index": index.round(config.SCORE_DECIMALS),
                         "components_available": n,
                         "coverage_score": (den / total).round(2)})


def coverage_report(idx: pd.DataFrame) -> pd.DataFrame:
    def summarize(g, label):
        total = g["company_id"].nunique()
        has_p = g.groupby("company_id")["patent_score"].apply(lambda s: s.notna().any())
        has_s = g.groupby("company_id")["startup_score"].apply(lambda s: s.notna().any())
        has_i = g.groupby("company_id")["technology_disruption_index"].apply(
            lambda s: s.notna().any())
        return {
            "scope": label, "total_companies": total,
            "patent_coverage": int(has_p.sum()), "startup_coverage": int(has_s.sum()),
            "index_coverage": int(has_i.sum()),
            "both_components": int((has_p & has_s).sum()),
            "missing_patent": int((~has_p).sum()), "missing_startup": int((~has_s).sum()),
            "missing_both": int((~has_p & ~has_s).sum()),
            "patent_coverage_pct": round(100 * has_p.mean(), 2),
            "startup_coverage_pct": round(100 * has_s.mean(), 2),
            "index_coverage_pct": round(100 * has_i.mean(), 2),
        }
    rows = [summarize(idx, "any_year")]
    rows += [summarize(g, f"year_{y}") for y, g in idx.groupby("year")]
    return pd.DataFrame(rows)


def main() -> None:
    master = pd.read_csv(config.COMPANIES_MASTER)
    startup = pd.read_csv(config.COMPANY_STARTUP_SCORES_BY_YEAR,
                          usecols=["company_id", "year", "startup_score", "coverage_flag"])
    patent = pd.read_csv(config.PATENT_SCORES_BY_YEAR)
    patent = patent.reindex(columns=["company_id", "year", "patent_score", "patent_count",
                                     "patent_momentum_available"])

    grid = master[["company_id", "company_name", "ticker", "sic", "industry",
                   "is_non_operating"]].merge(pd.DataFrame({"year": config.INDEX_YEARS}),
                                              how="cross")
    idx = grid.merge(patent, on=["company_id", "year"], how="left") \
              .merge(startup, on=["company_id", "year"], how="left")
    idx = idx.rename(columns={"coverage_flag": "startup_coverage_flag"})
    parts = combine(idx, config.INDEX_WEIGHTS)
    idx["technology_disruption_index"] = parts["index"]
    idx["components_available"] = parts["components_available"]
    idx["coverage_score"] = parts["coverage_score"]

    cols = ["company_id", "company_name", "ticker", "year", "patent_score", "startup_score",
            "technology_disruption_index", "components_available", "coverage_score",
            "startup_coverage_flag", "patent_count", "patent_momentum_available",
            "sic", "industry", "is_non_operating"]
    idx = idx[cols].sort_values(["company_id", "year"])
    write_csv(idx, config.TECH_INDEX)
    write_csv(idx[idx["year"] == max(config.INDEX_YEARS)], config.TECH_INDEX_LATEST)

    report = coverage_report(idx)
    write_csv(report, config.COVERAGE_REPORT)
    log.info("Index rows: %d | companies: %d | years: %d-%d",
             len(idx), idx["company_id"].nunique(), min(config.INDEX_YEARS), max(config.INDEX_YEARS))
    log.info("Coverage:\n%s", report.iloc[[0, -1]].T.to_string())


if __name__ == "__main__":
    main()
