"""
Stage 7: company-year fundamentals from SEC XBRL "frames".

One frames request returns a single concept for every filer in one calendar
period, so the whole universe costs a few hundred cached requests instead of
thousands of per-company calls.

  duration items (revenue, R&D, capex) : frame CY{year}   (~365-day periods aligned to calendar year)
  instant items (assets, cash, debt)   : frame CY{year}Q4I (balance closest to calendar year-end)
  public float (dei:EntityPublicFloat) : frames CY{year}Q1I..Q4I, value dated within the year

Market capitalization is NOT derived: SEC does not publish prices, and combining
split-adjusted third-party prices with as-reported share counts is unreliable.
Public float (market value of non-affiliate equity, reported by the company)
is used as the market-valuation measure and `market_cap` is left empty.
"""
import argparse
import datetime as dt

import numpy as np
import pandas as pd

import config
from src.common import SecClient, get_logger, write_csv

log = get_logger("fetch_sec_financials")
BASE = "https://data.sec.gov/api/xbrl/frames/{tax}/{concept}/USD/{frame}.json"
FRAME_COLUMNS = ["cik", "val", "start", "end", "accn", "loc"]


def frames_for(period: str, year: int):
    if period == "duration":
        return [f"CY{year}"]
    if period == "instant":
        return [f"CY{year}Q4I"]
    if period == "public_float":
        return [f"CY{year}Q{q}I" for q in (1, 2, 3, 4)]
    raise ValueError(period)


def fetch_frame(client, taxonomy, concept, frame, refresh_years) -> pd.DataFrame:
    path = config.RAW_FRAMES / f"{taxonomy}_{concept}_{frame}.csv.gz"
    year = int(frame[2:6])
    if path.exists() and year not in refresh_years:
        return pd.read_csv(path)
    response = client.get(BASE.format(tax=taxonomy, concept=concept, frame=frame))
    if response is None:
        df = pd.DataFrame(columns=FRAME_COLUMNS)
    else:
        df = pd.DataFrame(response.json().get("data", []))
        df = df.reindex(columns=FRAME_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")
    return df


def build_variable(client, var, spec, refresh_years) -> pd.DataFrame:
    pieces = []
    for priority, concept in enumerate(spec["concepts"]):
        for year in config.FINANCIAL_YEARS:
            for frame in frames_for(spec["period"], year):
                df = fetch_frame(client, spec["taxonomy"], concept, frame, refresh_years)
                if df.empty:
                    continue
                df = df.assign(year=year, priority=priority, concept=concept)
                pieces.append(df[["cik", "year", "val", "end", "priority", "concept"]])
    if not pieces:
        return pd.DataFrame(columns=["company_id", "year", var, f"{var}_concept"])
    data = pd.concat(pieces, ignore_index=True)
    if spec["period"] == "public_float":
        data = data[pd.to_datetime(data["end"], errors="coerce").dt.year == data["year"]]
        data = data.sort_values(["cik", "year", "priority", "end"],
                                ascending=[True, True, True, False])
    else:
        data = data.sort_values(["cik", "year", "priority"])
    best = data.drop_duplicates(["cik", "year"], keep="first")
    log.info("  %-13s %6d company-years from %d concept(s)", var, len(best), len(spec["concepts"]))
    return best.rename(columns={"cik": "company_id", "val": var, "concept": f"{var}_concept"})[
        ["company_id", "year", var, f"{var}_concept"]]


def main(refresh_recent: bool = False) -> None:
    client = SecClient()
    this_year = dt.date.today().year
    refresh_years = {this_year - 1, this_year} if refresh_recent else set()

    universe = pd.read_csv(config.COMPANIES_MASTER, usecols=["company_id"])
    ids = set(universe["company_id"].astype(int))

    panel = None
    for var, spec in config.FINANCIAL_CONCEPTS.items():
        log.info("Variable %s", var)
        df = build_variable(client, var, spec, refresh_years)
        df["company_id"] = df["company_id"].astype(int)
        df = df[df["company_id"].isin(ids)]
        panel = df if panel is None else panel.merge(df, on=["company_id", "year"], how="outer")

    negatives = {}
    for var in config.NONNEGATIVE_FINANCIALS:
        bad = panel[var] < 0
        negatives[var] = int(bad.sum())
        panel.loc[bad, var] = np.nan
    log.info("Negative values set to NaN (impossible for these items): %s", negatives)

    panel["market_cap"] = np.nan
    values = ["revenue", "assets", "rd", "capex", "cash", "debt", "public_float", "market_cap"]
    concepts = [c for c in panel.columns if c.endswith("_concept")]
    panel = panel[["company_id", "year"] + values + concepts].sort_values(["company_id", "year"])
    write_csv(panel, config.FINANCIALS)

    log.info("Financial rows: %d | companies: %d of %d universe (%.1f%%)",
             len(panel), panel["company_id"].nunique(), len(ids),
             100 * panel["company_id"].nunique() / len(ids))
    for var in values:
        log.info("  %-13s non-missing: %6d", var, panel[var].notna().sum())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-recent", action="store_true",
                        help="re-download frames for the current and previous year")
    main(parser.parse_args().refresh_recent)
