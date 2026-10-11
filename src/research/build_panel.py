"""
Stage 8: research panel = full universe x PANEL_YEARS, with index and fundamentals.

No company is dropped; years without index or financial data carry NaN.
`market_cap` is kept for schema stability but is empty (see fetch_sec_financials);
`public_float` is the market-valuation measure.
"""
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("build_panel")


def main() -> None:
    master = pd.read_csv(config.COMPANIES_MASTER)
    index = pd.read_csv(config.TECH_INDEX, low_memory=False)
    fin = pd.read_csv(config.FINANCIALS)

    grid = master[["company_id", "company_name", "ticker", "sic", "sic2", "industry", "country",
                   "exchange", "is_non_operating"]].merge(
        pd.DataFrame({"year": config.PANEL_YEARS}), how="cross")
    idx_cols = ["company_id", "year", "technology_disruption_index", "patent_score",
                "startup_score", "components_available", "coverage_score",
                "startup_coverage_flag", "patent_count"]
    panel = grid.merge(index[idx_cols], on=["company_id", "year"], how="left")
    fin = fin[
        ["company_id", "year", "revenue", "assets", "rd", "capex", "cash", "debt",
         "public_float", "market_cap"]]
    panel = panel.merge(fin, on=["company_id", "year"], how="left")

    cols = ["company_id", "company_name", "ticker", "year", "technology_disruption_index",
            "patent_score", "startup_score", "revenue", "assets", "rd", "capex", "cash", "debt",
            "market_cap", "public_float", "components_available", "coverage_score",
            "startup_coverage_flag", "patent_count", "sic", "sic2", "industry", "country",
            "exchange", "is_non_operating"]
    panel = panel[cols].sort_values(["company_id", "year"])
    write_csv(panel, config.FINAL_PANEL)

    both = panel["technology_disruption_index"].notna() & panel["assets"].notna()
    log.info("Panel rows: %d | companies: %d | years %d-%d", len(panel),
             panel["company_id"].nunique(), min(config.PANEL_YEARS), max(config.PANEL_YEARS))
    log.info("Rows with index: %d | with assets: %d | with index & assets: %d | with public float: %d",
             panel["technology_disruption_index"].notna().sum(), panel["assets"].notna().sum(),
             both.sum(), panel["public_float"].notna().sum())


if __name__ == "__main__":
    main()
