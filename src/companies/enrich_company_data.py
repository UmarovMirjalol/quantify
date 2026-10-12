"""
Stage 2a: collapse the ticker-level universe to one row per company (CIK).

A single SEC registrant can have several tickers (share classes, preferreds,
foreign OTC lines). company_id = CIK is the canonical key; all tickers are kept
in `tickers`, and the primary ticker follows SEC's own ordering of the ticker
file (first listing per CIK), falling back to the shortest plain ticker.
"""
import pandas as pd

import config
from src.common import get_logger, normalize_cik, write_csv
from src.companies.build_companies import load_exchange_json

log = get_logger("enrich_company_data")


def xbrl_filers(known: set) -> pd.DataFrame:
    """Companies with us-gaap:Assets in any index year (cached SEC frames), not in the ticker list."""
    ciks = set()
    for year in config.INDEX_YEARS:
        path = config.RAW_FRAMES / f"us-gaap_Assets_CY{year}Q4I.csv.gz"
        if path.exists():
            ciks |= set(pd.read_csv(path, usecols=["cik"])["cik"].astype(int))
        else:
            log.warning("Missing cached frame %s; run the financials step first.", path.name)
    extra = pd.DataFrame({"company_id": sorted(ciks - known)})
    extra["n_tickers"] = 0   # names and tickers are filled from SEC submissions
    extra["universe_source"] = "xbrl_filer"
    log.info("Added %d XBRL filers not on the current ticker list", len(extra))
    return extra


def main() -> None:
    df = pd.read_csv(config.COMPANIES_CLEAN)
    df["company_id"] = normalize_cik(df["company_id"])
    log.info("Loaded %d tickers / %d companies", len(df), df["company_id"].nunique())

    exchange = load_exchange_json()[["cik", "ticker", "exchange", "sec_rank"]]
    exchange = exchange.rename(columns={"cik": "company_id"})
    exchange["company_id"] = exchange["company_id"].astype("Int64")
    df = df.merge(exchange, on=["company_id", "ticker"], how="left")

    df["_plain"] = ~df["ticker"].astype(str).str.contains(r"[-.]", regex=True)
    df["_len"] = df["ticker"].astype(str).str.len()
    df["_rank"] = df["sec_rank"].fillna(10**9)
    df = df.sort_values(["company_id", "_rank", "_plain", "_len", "ticker"],
                        ascending=[True, True, False, True, True])

    grouped = df.groupby("company_id", sort=True)
    out = grouped.agg(
        company_name=("company_name", "first"),
        ticker=("ticker", "first"),
        exchange=("exchange", "first"),
        n_tickers=("ticker", "size"),
        tickers=("ticker", lambda s: ";".join(s)),
    ).reset_index()
    out["universe_source"] = "sec_ticker_list"
    if config.INCLUDE_XBRL_FILERS:
        out = pd.concat([out, xbrl_filers(set(out["company_id"].astype(int)))], ignore_index=True)
    out["cik"] = out["company_id"].astype(str).str.zfill(10)
    out = out[["company_id", "company_name", "ticker", "tickers", "n_tickers", "cik", "exchange",
               "universe_source"]]

    write_csv(out, config.COMPANIES_ENRICHED)
    log.info("Companies (unique CIK): %d | with >1 ticker: %d | exchange known: %d -> %s",
             len(out), (out["n_tickers"] > 1).sum(), out["exchange"].notna().sum(),
             config.COMPANIES_ENRICHED.name)


if __name__ == "__main__":
    main()
