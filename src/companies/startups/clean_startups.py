"""
Stage 3: clean the accelerator startup dataset (raw file is never modified).

Deduplication key = website domain when present, otherwise normalized name.
The earlier version deduplicated on the raw name only, which merged distinct
startups sharing a common name while keeping the same startup twice when the
name was spelled differently across accelerators.
"""
import re

import pandas as pd

import config
from src.common import get_logger, normalize_company_name, write_csv

log = get_logger("clean_startups")

COLUMNS = ["source", "name", "description", "website", "city", "state", "country",
           "region", "subregion", "tags", "year", "program", "isExit", "isUnicorn"]


def domain_of(url) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    url = re.sub(r"^https?://", "", url.strip().lower())
    url = re.sub(r"^www\.", "", url)
    return url.split("/")[0].split("?")[0]


def main() -> None:
    df = pd.read_csv(config.STARTUPS_RAW, usecols=lambda c: c in COLUMNS)
    log.info("Loaded startups: %d", len(df))

    df = df.dropna(subset=["name"])
    df["name"] = df["name"].astype(str).str.strip()
    for col in ["description", "tags", "country", "region", "website"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    lo, hi = config.STARTUP_VALID_YEARS
    df.loc[(df["year"] < lo) | (df["year"] > hi), "year"] = pd.NA

    df["domain"] = df["website"].map(domain_of)
    df["name_key"] = df["name"].map(normalize_company_name)
    df["dedupe_key"] = df["domain"].where(df["domain"] != "", "name:" + df["name_key"])
    # keep the record with the earliest cohort year (first accelerator entry)
    df = df.sort_values(["dedupe_key", "year"], na_position="last")
    before = len(df)
    df = df.drop_duplicates(subset=["dedupe_key"], keep="first")
    df["startup_id"] = range(1, len(df) + 1)

    write_csv(df[["startup_id"] + COLUMNS + ["domain", "dedupe_key"]], config.STARTUPS_CLEAN)
    log.info("Duplicates removed: %d | clean startups: %d | with cohort year: %d",
             before - len(df), len(df), df["year"].notna().sum())
    log.info("Sources: %s", df["source"].value_counts().to_dict())


if __name__ == "__main__":
    main()
