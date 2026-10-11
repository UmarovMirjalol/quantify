"""
Stage 1a: SEC company universe (ticker level).

Downloads SEC's company_tickers_exchange.json into data/raw/sec (cached) and,
only if data/companies.csv does not exist yet (or --refresh is passed), writes the
ticker-level snapshot. The existing snapshot is never silently overwritten,
so the universe stays reproducible.
"""
import argparse
import json

import pandas as pd

import config
from src.common import SecClient, get_logger, write_csv

log = get_logger("build_companies")
URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def load_exchange_json(refresh: bool = False) -> pd.DataFrame:
    path = config.SEC_TICKERS_EXCHANGE_JSON
    if refresh or not path.exists():
        log.info("Downloading %s", URL)
        response = SecClient().get(URL, allow_404=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    payload = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["data"], columns=payload["fields"])
    # SEC lists tickers roughly by size; the first ticker per CIK is the primary listing.
    df["sec_rank"] = range(len(df))
    return df


def main(refresh: bool = False) -> None:
    exchange = load_exchange_json(refresh)
    log.info("SEC ticker file: %d tickers, %d unique CIKs", len(exchange), exchange["cik"].nunique())

    if config.COMPANIES_RAW.exists() and not refresh:
        existing = pd.read_csv(config.COMPANIES_RAW)
        log.info("Keeping existing snapshot %s (%d tickers). Use --refresh to rebuild.",
                 config.COMPANIES_RAW.name, len(existing))
        return

    df = pd.DataFrame({
        "company_id": exchange["cik"],
        "company_name": exchange["name"],
        "ticker": exchange["ticker"],
        "cik": exchange["cik"].astype(str).str.zfill(10),
    }).drop_duplicates(subset=["ticker"]).sort_values("ticker")
    write_csv(df, config.COMPANIES_RAW)
    log.info("Saved %d tickers to %s", len(df), config.COMPANIES_RAW)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="re-download SEC ticker list")
    main(parser.parse_args().refresh)
