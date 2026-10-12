"""
Stage 2b: SIC industry, country and entity metadata from SEC submissions API.

Restartable: every successful lookup is appended to
data/raw/sec/submissions_cache.jsonl; only CIKs missing from the cache are
requested. Writes the canonical company universe data/companies_master.csv.
"""
import argparse
import json

import pandas as pd

import config
from src.common import SecClient, get_logger, sic_division, write_csv

log = get_logger("get_company_industries")

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE",
    "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD",
    "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "PR", "VI", "GU", "AS", "MP",
}


def load_cache() -> dict:
    cache = {}
    path = config.SEC_SUBMISSIONS_CACHE
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    cache[int(record["cik"])] = record
    return cache


def extract(cik: int, data: dict) -> dict:
    business = (data.get("addresses") or {}).get("business") or {}
    return {
        "cik": cik,
        "status": "ok",
        "name": data.get("name"),
        "sec_tickers": ";".join(t for t in (data.get("tickers") or []) if t),
        "sic": data.get("sic") or None,
        "sic_description": data.get("sicDescription") or None,
        "entity_type": data.get("entityType"),
        "state_of_incorporation": data.get("stateOfIncorporation") or None,
        "business_state_or_country": business.get("stateOrCountry"),
        "business_country_description": business.get("stateOrCountryDescription"),
        "sec_exchanges": ";".join(x for x in (data.get("exchanges") or []) if x),
        "fiscal_year_end": data.get("fiscalYearEnd"),
    }


def fetch_missing(ciks, cache: dict, retry_failed: bool) -> None:
    todo = [c for c in ciks if c not in cache
            or (retry_failed and cache[c].get("status") != "ok")]
    log.info("Submissions: %d cached, %d to fetch", len(ciks) - len(todo), len(todo))
    if not todo:
        return
    client = SecClient()
    config.SEC_SUBMISSIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.SEC_SUBMISSIONS_CACHE, "a", encoding="utf-8") as fh:
        for i, cik in enumerate(todo, 1):
            url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
            try:
                response = client.get(url)
                record = extract(cik, response.json()) if response is not None \
                    else {"cik": cik, "status": "not_found"}
            except Exception as exc:  # keep going; failure is recorded, not fatal
                log.warning("CIK %s failed: %s", cik, exc)
                record = {"cik": cik, "status": "error"}
            cache[cik] = record
            fh.write(json.dumps(record) + "\n")
            if i % 250 == 0:
                fh.flush()
                log.info("  fetched %d/%d", i, len(todo))


def country_from(row) -> str:
    code = row.get("business_state_or_country")
    if not isinstance(code, str) or not code:
        return None
    if code.upper() in US_STATES:
        return "United States"
    desc = row.get("business_country_description")
    if not isinstance(desc, str) or not desc:
        return code
    return desc.split(",")[-1].strip().title()     # "BRITISH COLUMBIA, CANADA" -> "Canada"


def main(retry_failed: bool = False, offline: bool = False) -> None:
    companies = pd.read_csv(config.COMPANIES_ENRICHED)
    ciks = companies["company_id"].astype(int).tolist()
    cache = load_cache()
    if not offline:
        fetch_missing(ciks, cache, retry_failed)

    meta = pd.DataFrame([cache[c] for c in ciks if c in cache])
    if meta.empty:
        meta = pd.DataFrame(columns=["cik"])
    meta = meta.rename(columns={"cik": "company_id"})
    master = companies.merge(meta, on="company_id", how="left")
    for col in ["name", "sec_tickers"]:
        if col not in master:
            master[col] = None
    master["company_name"] = master["company_name"].fillna(master["name"])
    master["ticker"] = master["ticker"].fillna(
        master["sec_tickers"].replace("", None).str.split(";").str[0])
    master["tickers"] = master["tickers"].fillna(master["sec_tickers"].replace("", None))
    master["sic"] = pd.to_numeric(master.get("sic"), errors="coerce").astype("Int64")
    master["sic2"] = (master["sic"] // 100).astype("Int64")
    master["industry"] = master["sic"].map(sic_division)
    master["country"] = master.apply(country_from, axis=1)
    master["is_non_operating"] = master["sic"].isin(config.NON_OPERATING_SIC)
    master["exchange"] = master["exchange"].fillna(
        master.get("sec_exchanges", pd.Series(dtype=str)).str.split(";").str[0])

    cols = ["company_id", "company_name", "ticker", "tickers", "n_tickers", "cik",
            "exchange", "sic", "sic2", "sic_description", "industry", "country",
            "state_of_incorporation", "entity_type", "fiscal_year_end",
            "is_non_operating", "universe_source", "status"]
    master = master[[c for c in cols if c in master.columns]].rename(
        columns={"status": "sec_lookup_status"})
    write_csv(master, config.COMPANIES_MASTER)

    log.info("Master universe: %d companies | SIC known: %d (%.1f%%) | country known: %d | "
             "non-operating flagged: %d -> %s",
             len(master), master["sic"].notna().sum(), 100 * master["sic"].notna().mean(),
             master["country"].notna().sum(), master["is_non_operating"].sum(),
             config.COMPANIES_MASTER.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--offline", action="store_true", help="use cache only")
    args = parser.parse_args()
    main(args.retry_failed, args.offline)
