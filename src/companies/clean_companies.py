"""
Stage 1b: clean the ticker-level universe.

Removes rows without ticker/name and obvious non-operating listings by name
(ETFs, funds, warrants, units, depositary receipts, SPAC shells). Patterns are
word-bounded: the earlier substring version removed operating companies such
as "BankUnited", "Community Health Systems" (UNIT) and "AST SpaceMobile" (SPAC).
"TRUST" is deliberately not a name filter (it removed banks and REITs);
commodity trusts and funds are flagged later via SIC codes instead.
"""
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("clean_companies")

EXCLUDE_PATTERN = (
    r"\bETFS?\b|\bFUNDS?\b|\bACQUISITION CORP\b|\bACQUISITION COMPANY\b|\bSPAC\b"
    r"|\bWARRANTS?\b|\bUNITS?\b|\bDEPOSITARY\b"
)


def main() -> None:
    df = pd.read_csv(config.COMPANIES_RAW)
    log.info("Loaded %d SEC tickers (%d unique CIKs)", len(df), df["company_id"].nunique())

    df = df.dropna(subset=["ticker", "company_name"])
    mask = ~df["company_name"].str.upper().str.contains(EXCLUDE_PATTERN, regex=True, na=False)
    removed = df[~mask]
    df = df[mask].drop_duplicates(subset=["ticker"]).sort_values("ticker")

    write_csv(df, config.COMPANIES_CLEAN)
    log.info("Removed by name filter: %d tickers", len(removed))
    log.info("Clean: %d tickers, %d unique companies (CIK) -> %s",
             len(df), df["company_id"].nunique(), config.COMPANIES_CLEAN.name)


if __name__ == "__main__":
    main()
