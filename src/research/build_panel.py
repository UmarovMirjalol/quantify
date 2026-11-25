"""
Stage 8: research panel = full universe x PANEL_YEARS, with index and fundamentals.

No company is dropped; years without index or financial data carry NaN.

Valuation measures:
  * public_float — EntityPublicFloat from SEC (market value of non-affiliate equity).
  * tobins_q — approximate Tobin's Q = (public_float + debt - cash) / assets.
    SEC publishes no share prices, so public_float stands in for market equity.
    Non-positive Q is set to missing. Extreme ratios are winsorized in regressions.
  * market_cap — schema placeholder, empty (no reliable SEC price source).
"""
import numpy as np
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("build_panel")


def approx_tobins_q(fin: pd.DataFrame) -> pd.Series:
    assets = fin["assets"]
    equity = fin["public_float"]
    debt = fin["debt"].fillna(0)
    cash = fin["cash"].fillna(0)
    q = (equity + debt - cash) / assets
    ok = (assets > 0) & (equity > 0) & q.notna() & (q >= config.TOBIN_Q_FLOOR)
    return q.where(ok)


def main() -> None:
    master = pd.read_csv(config.COMPANIES_MASTER)
    index = pd.read_csv(config.TECH_INDEX, low_memory=False)
    fin = pd.read_csv(config.FINANCIALS)
    startup = pd.read_csv(config.COMPANY_STARTUP_SCORES_BY_YEAR,
                          usecols=["company_id", "year", "startup_score_within_sic2",
                                   "firm_match_boost"])
    patent = pd.read_csv(config.PATENT_SCORES_BY_YEAR,
                         usecols=lambda c: c in {"company_id", "year", "citation_count",
                                                 "quality_score", "volume_score",
                                                 "momentum_score"})

    grid = master[["company_id", "company_name", "ticker", "sic", "sic2", "industry", "country",
                   "exchange", "is_non_operating"]].merge(
        pd.DataFrame({"year": config.PANEL_YEARS}), how="cross")
    idx_cols = ["company_id", "year", "technology_disruption_index", "patent_score",
                "startup_score", "components_available", "coverage_score",
                "startup_coverage_flag", "patent_count"]
    panel = grid.merge(index[idx_cols], on=["company_id", "year"], how="left")
    panel = panel.merge(startup, on=["company_id", "year"], how="left")
    if not patent.empty:
        panel = panel.merge(patent, on=["company_id", "year"], how="left")
    else:
        panel["citation_count"] = np.nan
        panel["quality_score"] = np.nan

    fin = fin[["company_id", "year", "revenue", "assets", "rd", "capex", "cash", "debt",
               "public_float", "market_cap"]].copy()
    fin["tobins_q"] = approx_tobins_q(fin)
    panel = panel.merge(fin, on=["company_id", "year"], how="left")

    cols = ["company_id", "company_name", "ticker", "year", "technology_disruption_index",
            "patent_score", "startup_score", "startup_score_within_sic2", "firm_match_boost",
            "quality_score", "citation_count",
            "revenue", "assets", "rd", "capex", "cash", "debt",
            "market_cap", "public_float", "tobins_q",
            "components_available", "coverage_score",
            "startup_coverage_flag", "patent_count", "sic", "sic2", "industry", "country",
            "exchange", "is_non_operating"]
    for c in cols:
        if c not in panel.columns:
            panel[c] = np.nan
    panel = panel[cols].sort_values(["company_id", "year"])
    write_csv(panel, config.FINAL_PANEL)

    both = panel["technology_disruption_index"].notna() & panel["assets"].notna()
    log.info("Panel rows: %d | companies: %d | years %d-%d", len(panel),
             panel["company_id"].nunique(), min(config.PANEL_YEARS), max(config.PANEL_YEARS))
    log.info("Rows with index: %d | with assets: %d | with index & assets: %d | "
             "with public float: %d | with Tobin's Q approx: %d",
             panel["technology_disruption_index"].notna().sum(), panel["assets"].notna().sum(),
             both.sum(), panel["public_float"].notna().sum(), panel["tobins_q"].notna().sum())


if __name__ == "__main__":
    main()
