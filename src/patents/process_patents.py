"""
Stage 5b: build the company-year patent count dataset keyed on company_id.

Inputs (whichever exist):
  1. data/raw/patents/assignee_year_counts.csv(.gz) - BigQuery export for all assignees.
     Matched to companies by exact normalized name (legal suffixes stripped).
     Normalized names shared by >1 company are treated as ambiguous and skipped.
  2. data/raw/patents/assignee_crosswalk.csv (optional: assignee_name, company_id) -
     curated links, e.g. subsidiaries ("GOOGLE LLC" -> Alphabet).
  3. data/patents/patents_by_year.csv - legacy name-keyed manual BigQuery pull for
     9 firms, mapped via an explicit name->ticker crosswalk in config.

Companies without any patent source are NOT given zero patents; they are
simply absent here and appear as missing patent components downstream.
"""
import pandas as pd

import config
from src.common import get_logger, normalize_company_name, write_csv

log = get_logger("process_patents")


def company_keys(master: pd.DataFrame) -> pd.DataFrame:
    keys = master[["company_id", "company_name"]].copy()
    keys["name_key"] = keys["company_name"].map(normalize_company_name)
    keys = keys[keys["name_key"].str.len() >= 3]
    counts = keys["name_key"].value_counts()
    ambiguous = set(counts[counts > 1].index)
    if ambiguous:
        log.info("Ambiguous normalized company names skipped for matching: %d", len(ambiguous))
    return keys[~keys["name_key"].isin(ambiguous)][["company_id", "name_key"]]


def load_bigquery_export(master: pd.DataFrame):
    path = config.PATENTS_BIGQUERY_EXPORT
    if not path.exists():
        alt = path.with_suffix("")          # .csv without .gz
        path = alt if alt.exists() else None
    if path is None:
        log.warning("No BigQuery patent export found (%s). Patent coverage is limited to "
                    "the legacy file.", config.PATENTS_BIGQUERY_EXPORT)
        return pd.DataFrame(), pd.DataFrame()

    keys = company_keys(master).set_index("name_key")["company_id"]
    crosswalk = {}
    if config.PATENTS_ASSIGNEE_CROSSWALK.exists():
        cw = pd.read_csv(config.PATENTS_ASSIGNEE_CROSSWALK)
        crosswalk = dict(zip(cw["assignee_name"].str.upper().str.strip(), cw["company_id"]))
        log.info("Curated assignee crosswalk entries: %d", len(crosswalk))

    counts, matches = [], []
    lo, hi = config.PATENT_COUNT_YEARS
    for chunk in pd.read_csv(path, chunksize=500_000):
        chunk = chunk[chunk["year"].between(lo, hi + 1)]
        chunk["assignee_name"] = chunk["assignee_name"].astype(str).str.upper().str.strip()
        chunk["company_id"] = chunk["assignee_name"].map(crosswalk)
        chunk["match_method"] = chunk["company_id"].notna().map({True: "crosswalk", False: None})
        need = chunk["company_id"].isna()
        chunk.loc[need, "company_id"] = chunk.loc[need, "assignee_name"].map(
            normalize_company_name).map(keys)
        chunk.loc[need & chunk["company_id"].notna(), "match_method"] = "exact_normalized_name"
        hit = chunk[chunk["company_id"].notna()]
        counts.append(hit[["company_id", "year", "patent_count"]])
        matches.append(hit[["assignee_name", "company_id", "match_method"]].drop_duplicates())
    counts = pd.concat(counts).groupby(["company_id", "year"], as_index=False)["patent_count"].sum()
    matches = pd.concat(matches).drop_duplicates()
    counts["source"] = "bigquery_export"
    log.info("BigQuery export: %d matched assignee names -> %d companies",
             len(matches), counts["company_id"].nunique())
    return counts, matches


def load_legacy(master: pd.DataFrame) -> pd.DataFrame:
    if not config.PATENTS_LEGACY_BY_YEAR.exists():
        return pd.DataFrame()
    legacy = pd.read_csv(config.PATENTS_LEGACY_BY_YEAR)
    ticker_to_id = master.set_index("ticker")["company_id"]
    legacy["ticker"] = legacy["company"].map(config.LEGACY_PATENT_NAME_TO_TICKER)
    legacy["company_id"] = legacy["ticker"].map(ticker_to_id)
    unmapped = legacy[legacy["company_id"].isna()]["company"].unique()
    if len(unmapped):
        log.warning("Legacy patent names without company_id: %s", list(unmapped))
    legacy = legacy.dropna(subset=["company_id"])
    legacy["source"] = "legacy_manual_bigquery"
    return legacy[["company_id", "year", "patent_count", "source"]]


def complete_grid(counts: pd.DataFrame) -> pd.DataFrame:
    """Within each company's observed source span, absent years are genuine zeros."""
    rows = []
    for (cid, source), grp in counts.groupby(["company_id", "source"]):
        years = range(int(grp["year"].min()), int(grp["year"].max()) + 1)
        full = grp.set_index("year").reindex(years)
        full["patent_count"] = full["patent_count"].fillna(0).astype(int)
        full["company_id"], full["source"] = cid, source
        rows.append(full.reset_index().rename(columns={"index": "year"}))
    return pd.concat(rows, ignore_index=True) if rows else counts


def main() -> None:
    master = pd.read_csv(config.COMPANIES_MASTER)
    bq, matches = load_bigquery_export(master)
    legacy = load_legacy(master)
    if not bq.empty and not legacy.empty:
        legacy = legacy[~legacy["company_id"].isin(bq["company_id"])]   # BigQuery wins
    counts = pd.concat([x for x in (bq, legacy) if not x.empty], ignore_index=True)
    if counts.empty:
        log.warning("No patent data available at all.")
        counts = pd.DataFrame(columns=["company_id", "year", "patent_count", "source"])
    else:
        counts["company_id"] = counts["company_id"].astype(int)
        counts = complete_grid(counts)

    counts = counts.merge(master[["company_id", "company_name"]], on="company_id", how="left")
    counts["year_complete"] = counts["year"] <= config.LAST_COMPLETE_PATENT_YEAR
    counts = counts[["company_id", "company_name", "year", "patent_count", "source",
                     "year_complete"]].sort_values(["company_id", "year"])
    write_csv(counts, config.PATENT_COUNTS)
    if not matches.empty:
        write_csv(matches, config.PATENT_MATCHES)

    n = counts["company_id"].nunique()
    log.info("Patent company-year rows: %d | companies with patent data: %d of %d (%.2f%%)",
             len(counts), n, len(master), 100 * n / len(master))


if __name__ == "__main__":
    main()
