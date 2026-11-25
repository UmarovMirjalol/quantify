"""
Stage 5c: patent volume, momentum and patent_score per company-year.

For index year t (only complete patent years <= LAST_COMPLETE_PATENT_YEAR):
  volume_t       = patent_count_t
  recent_avg     = mean(count, t-2..t)        (all 3 years must be observed)
  historical_avg = mean(count, t-5..t-3)      (all 3 years must be observed)
  momentum       = (recent_avg + k) / (historical_avg + k), k = pseudocount

Normalization (config.PATENT_NORMALIZATION):
  fixed_log  : volume_score   = 100 * min(1, log1p(volume) / log1p(REFERENCE))
               momentum_score = 50 + 50 * clip(log2(momentum) / CAP, -1, 1)
               quality_score  = 100 * min(1, log1p(forward cites) / log1p(QUALITY_REF))
  percentile : within-year percentile ranks of log1p(volume), log(momentum), log1p(cites)

The log transform means a firm with 10x the patents does not get 10x the score.
patent_score = weighted mean of the available sub-scores (flagged when momentum
or citation quality is unavailable). Citation counts come from Ma (2025) /
PatentsView; other patent sources leave quality missing, never zero.
"""
import numpy as np
import pandas as pd

import config
from src.common import get_logger, percentile_score, write_csv

log = get_logger("calculate_patent_scores")


def window_mean(series: pd.Series, year: int, back_from: int, width: int):
    years = list(range(year - back_from - width + 1, year - back_from + 1))
    values = series.reindex(years)
    return values.mean() if values.notna().all() else np.nan


def compute_raw(counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rw, hw = config.PATENT_RECENT_WINDOW, config.PATENT_HISTORICAL_WINDOW
    k = config.PATENT_MOMENTUM_PSEUDOCOUNT
    for cid, grp in counts.groupby("company_id"):
        s = grp.set_index("year")["patent_count"].astype(float)
        for year in config.INDEX_YEARS:
            if year not in s.index:
                continue
            recent = window_mean(s, year, 0, rw)
            hist = window_mean(s, year, rw, hw)
            cites = grp.set_index("year")["citation_count"] if "citation_count" in grp.columns \
                else pd.Series(dtype=float)
            cite = cites[year] if year in cites.index else np.nan
            rows.append({
                "company_id": cid, "year": year, "patent_count": s[year],
                "citation_count": cite,
                "log_patent_count": np.log1p(s[year]),
                "log_citation_count": np.log1p(cite) if pd.notna(cite) else np.nan,
                "recent_avg": recent, "historical_avg": hist,
                "momentum": (recent + k) / (hist + k) if pd.notna(recent) and pd.notna(hist)
                else np.nan,
            })
    return pd.DataFrame(rows)


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    if config.PATENT_NORMALIZATION == "fixed_log":
        raw["volume_score"] = 100 * np.minimum(
            1.0, raw["log_patent_count"] / np.log1p(config.PATENT_VOLUME_REFERENCE))
        cap = config.PATENT_MOMENTUM_LOG2_CAP
        raw["momentum_score"] = 50 + 50 * np.clip(np.log2(raw["momentum"]) / cap, -1, 1)
        raw["quality_score"] = 100 * np.minimum(
            1.0, raw["log_citation_count"] / np.log1p(config.PATENT_QUALITY_REFERENCE))
    elif config.PATENT_NORMALIZATION == "percentile":
        raw["volume_score"] = raw.groupby("year")["log_patent_count"].transform(percentile_score)
        raw["log_momentum"] = np.log(raw["momentum"])
        raw["momentum_score"] = raw.groupby("year")["log_momentum"].transform(percentile_score)
        raw["quality_score"] = raw.groupby("year")["log_citation_count"].transform(percentile_score)
    else:
        raise ValueError(config.PATENT_NORMALIZATION)

    w = config.PATENT_SUBWEIGHTS
    parts = raw[list(w)]
    weights = pd.DataFrame({c: np.where(parts[c].notna(), w[c], 0.0) for c in w}, index=raw.index)
    raw["patent_score"] = (parts.fillna(0) * weights).sum(axis=1) / weights.sum(axis=1)
    raw.loc[weights.sum(axis=1) == 0, "patent_score"] = np.nan
    raw["patent_momentum_available"] = raw["momentum_score"].notna()
    raw["patent_quality_available"] = raw["quality_score"].notna()
    for col in ["volume_score", "momentum_score", "quality_score", "patent_score"]:
        if col in raw.columns:
            raw[col] = raw[col].round(config.SCORE_DECIMALS)
    return raw


def main() -> None:
    counts = pd.read_csv(config.PATENT_COUNTS)
    counts = counts[counts["year"] <= config.LAST_COMPLETE_PATENT_YEAR]
    if "citation_count" not in counts.columns:
        counts["citation_count"] = np.nan
    names = pd.read_csv(config.COMPANIES_MASTER, usecols=["company_id", "company_name", "ticker"])

    if counts.empty:
        log.warning("No patent counts; writing empty score files.")
        scores = pd.DataFrame(columns=["company_id", "year", "patent_score"])
    else:
        scores = normalize(compute_raw(counts))
    scores = names.merge(scores, on="company_id", how="inner")
    write_csv(scores.sort_values(["company_id", "year"]), config.PATENT_SCORES_BY_YEAR)

    snap = scores[scores["year"] == config.PATENT_SNAPSHOT_YEAR].rename(
        columns={"patent_count": f"volume_{config.PATENT_SNAPSHOT_YEAR}"})
    cols = ["company_id", "company_name", "ticker", f"volume_{config.PATENT_SNAPSHOT_YEAR}",
            "citation_count", "recent_avg", "historical_avg", "momentum", "volume_score",
            "momentum_score", "quality_score", "patent_score", "patent_momentum_available",
            "patent_quality_available"]
    snap = snap.reindex(columns=cols).sort_values("patent_score", ascending=False)
    write_csv(snap, config.PATENT_SCORES)

    n_q = int(scores["quality_score"].notna().sum()) if "quality_score" in scores else 0
    log.info("Normalization: %s | company-year scores: %d | with quality: %d | companies: %d",
             config.PATENT_NORMALIZATION, len(scores), n_q, scores["company_id"].nunique())
    if not snap.empty:
        log.info("Snapshot %d (top 20):\n%s", config.PATENT_SNAPSHOT_YEAR,
                 snap.drop(columns=["company_id"]).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
