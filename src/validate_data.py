"""
Stage 9: data-quality validation.

Writes data/validation/validation_report.csv (one row per check) and a concise
validation_report.md. Status: PASS / WARN (documented limitation) / FAIL (bug).
Exit code is 1 if any FAIL is found.
"""
import datetime as dt
import sys

import numpy as np
import pandas as pd

import config
from src.common import get_logger, normalize_company_name, write_csv

log = get_logger("validate_data")
CURRENT_YEAR = dt.date.today().year
results = []


def check(dataset, name, n_bad, total, fail_if_bad=True, detail=""):
    status = "PASS" if n_bad == 0 else ("FAIL" if fail_if_bad else "WARN")
    results.append({"dataset": dataset, "check": name, "status": status,
                    "n_flagged": int(n_bad), "n_total": int(total), "detail": detail})


def read(path):
    return pd.read_csv(path, low_memory=False) if path.exists() else None


def numeric_checks(dataset, df, cols, nonneg=()):
    for col in cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        check(dataset, f"infinite values in {col}", np.isinf(s).sum(), len(df))
        if col in nonneg:
            check(dataset, f"negative {col}", (s < 0).sum(), len(df))


def main() -> None:
    master = read(config.COMPANIES_MASTER)
    if master is not None:
        n = len(master)
        check("companies_master", "duplicate company_id", master["company_id"].duplicated().sum(), n)
        check("companies_master", "missing CIK", master["cik"].isna().sum(), n)
        listed = master.get("universe_source", pd.Series("sec_ticker_list", index=master.index)) \
            == "sec_ticker_list"
        check("companies_master", "missing ticker (listed companies)",
              master.loc[listed, "ticker"].isna().sum(), int(listed.sum()))
        check("companies_master", "missing ticker (historical XBRL filers, expected)",
              master.loc[~listed, "ticker"].isna().sum(), int((~listed).sum()), False,
              "delisted/historical filers often have no current ticker")
        check("companies_master", "missing SIC", master["sic"].isna().sum(), n, False,
              "SEC submissions without SIC (mostly foreign/non-operating filers)")
        check("companies_master", "missing country", master["country"].isna().sum(), n, False)

    startups = read(config.STARTUPS_CLEAN)
    if startups is not None:
        n = len(startups)
        check("startups_clean", "duplicate dedupe_key", startups["dedupe_key"].duplicated().sum(), n)
        dup_names = startups["name"].map(normalize_company_name).duplicated().sum()
        check("startups_clean", "duplicate normalized startup names (distinct websites)",
              dup_names, n, False, "kept: same name, different domain = different startup")
        y = startups["year"]
        check("startups_clean", "impossible cohort years",
              ((y < config.STARTUP_VALID_YEARS[0]) | (y > CURRENT_YEAR)).sum(), n)

    patents = read(config.PATENT_COUNTS)
    if patents is not None:
        n = len(patents)
        check("patent_counts", "duplicate company-year observations",
              patents.duplicated(["company_id", "year"]).sum(), n)
        check("patent_counts", "negative patent counts", (patents["patent_count"] < 0).sum(), n)
        check("patent_counts", "impossible years",
              ((patents["year"] < 1976) | (patents["year"] > CURRENT_YEAR)).sum(), n)
        if master is not None:
            cov = patents["company_id"].nunique()
            check("patent_counts", "companies without patent data (treated as missing)",
                  len(master) - cov, len(master), False,
                  "BigQuery extraction not yet run for the full universe")

    idx = read(config.TECH_INDEX)
    if idx is not None:
        n = len(idx)
        check("technology_index", "duplicate company-year rows",
              idx.duplicated(["company_id", "year"]).sum(), n)
        check("technology_index", "years outside INDEX_YEARS",
              (~idx["year"].isin(config.INDEX_YEARS)).sum(), n)
        for col in ["patent_score", "startup_score", "technology_disruption_index"]:
            s = idx[col]
            check("technology_index", f"{col} outside [0,100]", ((s < 0) | (s > 100)).sum(), n)
        numeric_checks("technology_index", idx,
                       ["patent_score", "startup_score", "technology_disruption_index"])
        has_comp = idx["patent_score"].notna() | idx["startup_score"].notna()
        check("technology_index", "NaN propagation: component present but index NaN",
              (has_comp & idx["technology_disruption_index"].isna()).sum(), n)
        check("technology_index", "index present without any component",
              (~has_comp & idx["technology_disruption_index"].notna()).sum(), n)
        n_comp = idx["patent_score"].notna().astype(int) + idx["startup_score"].notna().astype(int)
        check("technology_index", "components_available inconsistent",
              (n_comp != idx["components_available"]).sum(), n)
        if master is not None:
            missing_cos = len(set(master["company_id"]) - set(idx["company_id"]))
            check("technology_index", "universe companies missing from index", missing_cos,
                  len(master))
        check("technology_index", "company-years without any component",
              (~has_comp).sum(), n, False, "kept in file with NaN index")

    fin = read(config.FINANCIALS)
    if fin is not None:
        n = len(fin)
        check("financials", "duplicate company-year rows",
              fin.duplicated(["company_id", "year"]).sum(), n)
        check("financials", "impossible years",
              ((fin["year"] < 1990) | (fin["year"] > CURRENT_YEAR)).sum(), n)
        numeric_checks("financials", fin,
                       ["revenue", "assets", "rd", "capex", "cash", "debt", "public_float"],
                       nonneg=config.NONNEGATIVE_FINANCIALS)
        check("financials", "zero assets (division by zero risk in ratios)",
              (fin["assets"] == 0).sum(), n, False, "ratios use assets > 0 only")
        check("financials", "market_cap unavailable", fin["market_cap"].isna().sum(), n, False,
              "no reliable SEC price source; public_float used instead")

    panel = read(config.FINAL_PANEL)
    if panel is not None:
        n = len(panel)
        check("final_panel", "duplicate company-year rows",
              panel.duplicated(["company_id", "year"]).sum(), n)
        if master is not None:
            check("final_panel", "universe companies missing from panel",
                  len(set(master["company_id"]) - set(panel["company_id"])), len(master))
        numeric_checks("final_panel", panel, ["technology_disruption_index", "revenue", "assets"])

    report = pd.DataFrame(results)
    config.VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(report, config.VALIDATION_REPORT_CSV)
    counts = report["status"].value_counts().to_dict()
    md = ["# Validation report", "",
          f"Generated {dt.datetime.now():%Y-%m-%d %H:%M}. Summary: {counts}", "",
          "| Dataset | Check | Status | Flagged | Total | Detail |", "|---|---|---|---|---|---|"]
    md += [f"| {r.dataset} | {r.check} | {r.status} | {r.n_flagged} | {r.n_total} | {r.detail} |"
           for r in report.itertuples(index=False)]
    config.VALIDATION_REPORT_MD.write_text("\n".join(md), encoding="utf-8")

    for r in report.itertuples(index=False):
        if r.status != "PASS":
            log.info("%-4s %-18s %s: %d/%d", r.status, r.dataset, r.check, r.n_flagged, r.n_total)
    log.info("Validation summary: %s -> %s", counts, config.VALIDATION_REPORT_MD)
    if counts.get("FAIL", 0):
        sys.exit(1)


if __name__ == "__main__":
    main()
