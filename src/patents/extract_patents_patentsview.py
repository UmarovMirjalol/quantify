"""
Stage 5a (public, no credentials): company-year patent grants from the open
PatentsView-to-public-firm linkage of Ma (2025), mapped to SEC CIK.

Sources (downloaded once into data/raw/patents/ma_patentsview/, never overwritten):
  * patent_level.csv - Song Ma, "patent-firm-link-share" (GitHub, Git LFS, ~1 GB):
    every US utility patent granted 1976-2025 from PatentsView (release 2026-04-10)
    with its Compustat gvkey when the assignee was matched to a public firm
    (historical names, subsidiaries, fuzzy cascade, manual rescues, KPSS overlay).
    Cite: Ma, S. "Technological Obsolescence." Review of Financial Studies (2025).
  * gvkey_ciks.rda - gvkey <-> CIK links from the `farr` R package (Ian Gow).

Counting: patents by GRANT year (consistent with the BigQuery route). A gvkey linked
to more than one CIK in our universe is assigned year by year to the CIK whose filing
date range covers the grant year (skipped when none or several do); patents of several
gvkeys linked to the same CIK are summed. Companies without a link are absent
(missing downstream), never zero.

Output: config.PATENTS_PATENTSVIEW_COUNTS (company_id, year, patent_count).
"""
import argparse
import subprocess

import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("extract_patents_patentsview")
RAW = config.RAW_PATENTS / "ma_patentsview"
PATENTS_URL = ("https://media.githubusercontent.com/media/songma/patent-firm-link-share/"
               "main/patent_level.csv")
CROSSWALK_URL = "https://raw.githubusercontent.com/iangow/farr/main/data/gvkey_ciks.rda"


def download(url: str, path, offline: bool) -> bool:
    if path.exists() and path.stat().st_size > 0:
        return True
    if offline:
        log.warning("SKIPPED (offline): %s not cached", path.name)
        return False
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    log.info("Downloading %s ...", url)
    subprocess.run(["curl", "-L", "-s", "-f", "-o", str(tmp), url], check=True)
    tmp.replace(path)
    return True


def gvkey_links(master_ids: set) -> pd.DataFrame:
    import pyreadr
    cw = next(iter(pyreadr.read_r(str(RAW / "gvkey_ciks.rda")).values()))
    cw["gvkey"] = pd.to_numeric(cw["gvkey"], errors="coerce")
    cw = cw.dropna(subset=["gvkey"])
    cw = cw[cw["cik"].isin(master_ids)]
    cw["fy"] = pd.to_datetime(cw["first_date"], errors="coerce").dt.year.fillna(1900)
    cw["ly"] = pd.to_datetime(cw["last_date"], errors="coerce").dt.year.fillna(2100)
    return (cw.groupby(["gvkey", "cik"], as_index=False).agg(fy=("fy", "min"), ly=("ly", "max"))
            .astype(int))


def map_to_cik(by_gvkey: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    """A gvkey linked to one CIK maps in every year. A gvkey linked to several CIKs maps a
    year only when exactly one link's SEC filing date range covers it; otherwise skipped."""
    n_cik = links.groupby("gvkey")["cik"].transform("nunique")
    single, multi = links[n_cik == 1], links[n_cik > 1]
    a = by_gvkey.merge(single[["gvkey", "cik"]], on="gvkey")
    b = by_gvkey.merge(multi, on="gvkey")
    b = b[(b["grant_year"] >= b["fy"]) & (b["grant_year"] <= b["ly"])]
    b = b[b.groupby(["gvkey", "grant_year"])["cik"].transform("size") == 1]
    log.info("gvkey->CIK: %d single-CIK gvkeys, %d multi-CIK gvkeys (%d resolved by date)",
             single["gvkey"].nunique(), multi["gvkey"].nunique(), b["gvkey"].nunique())
    return pd.concat([a, b[a.columns]], ignore_index=True).rename(columns={"cik": "company_id"})


def main(offline: bool = False) -> None:
    pat, xw = RAW / "patent_level.csv", RAW / "gvkey_ciks.rda"
    if not (download(PATENTS_URL, pat, offline) and download(CROSSWALK_URL, xw, offline)):
        return
    master = pd.read_csv(config.COMPANIES_MASTER, usecols=["company_id"])
    links = gvkey_links(set(master["company_id"]))

    lo, hi = config.PATENT_COUNT_YEARS
    parts = []
    for chunk in pd.read_csv(pat, usecols=["grant_year", "gvkey"], chunksize=2_000_000):
        chunk = chunk.dropna(subset=["gvkey"])
        chunk = chunk[chunk["grant_year"].between(lo, hi + 1)]
        parts.append(chunk.groupby(["gvkey", "grant_year"]).size())
    by_gvkey = pd.concat(parts).groupby(level=[0, 1]).sum().rename("patent_count").reset_index()
    by_gvkey["gvkey"] = pd.to_numeric(by_gvkey["gvkey"], errors="coerce")
    hit = map_to_cik(by_gvkey.dropna(subset=["gvkey"]).astype({"gvkey": int}), links)
    counts = (hit.groupby(["company_id", "grant_year"], as_index=False)["patent_count"].sum()
              .rename(columns={"grant_year": "year"}).astype(int))
    # explicit zero years only where the company's link is valid (single-CIK gvkey: whole
    # window; multi-CIK gvkey: the link's filing date range)
    n_cik = links.groupby("gvkey")["cik"].transform("nunique")
    span = links.assign(fy=links["fy"].where(n_cik > 1, lo).clip(lower=lo),
                        ly=links["ly"].where(n_cik > 1, hi).clip(upper=hi))
    span = span[span["cik"].isin(counts["company_id"])]
    grid = {(c, y) for c, f, l in zip(span["cik"], span["fy"], span["ly"])
            for y in range(f, l + 1)}
    grid = pd.DataFrame(sorted(grid), columns=["company_id", "year"])
    counts = grid.merge(counts, on=["company_id", "year"], how="outer").fillna(0).astype(int)
    log.info("Linked patents %d-%d: %d of %d gvkey-matched (%.1f%%) -> %d companies",
             lo, hi + 1, hit["patent_count"].sum(), by_gvkey["patent_count"].sum(),
             100 * hit["patent_count"].sum() / by_gvkey["patent_count"].sum(),
             counts["company_id"].nunique())
    write_csv(counts, config.PATENTS_PATENTSVIEW_COUNTS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    main(ap.parse_args().offline)
