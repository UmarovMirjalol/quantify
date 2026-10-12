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
  percentile : within-year percentile ranks of log1p(volume) and log(momentum)

The log transform means a firm with 10x the patents does not get 10x the score.
patent_score = weighted mean of the available sub-scores (flagged when momentum
is unavailable because the firm lacks 6 years of history).
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
            rows.append({
                "company_id": cid, "year": year, "patent_count": s[year],
                "log_patent_count": np.log1p(s[year]),
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
    elif config.PATENT_NORMALIZATION == "percentile":
        raw["volume_score"] = raw.groupby("year")["log_patent_count"].transform(percentile_score)
        raw["log_momentum"] = np.log(raw["momentum"])
        raw["momentum_score"] = raw.groupby("year")["log_momentum"].transform(percentile_score)
    else:
        raise ValueError(config.PATENT_NORMALIZATION)

    w = config.PATENT_SUBWEIGHTS
    parts = raw[list(w)]
    weights = pd.DataFrame({c: np.where(parts[c].notna(), w[c], 0.0) for c in w}, index=raw.index)
    raw["patent_score"] = (parts.fillna(0) * weights).sum(axis=1) / weights.sum(axis=1)
    raw.loc[weights.sum(axis=1) == 0, "patent_score"] = np.nan
    raw["patent_momentum_available"] = raw["momentum_score"].notna()
    for col in ["volume_score", "momentum_score", "patent_score"]:
        raw[col] = raw[col].round(config.SCORE_DECIMALS)
    return raw


def main() -> None:
    counts = pd.read_csv(config.PATENT_COUNTS)
    counts = counts[counts["year"] <= config.LAST_COMPLETE_PATENT_YEAR]
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
            "recent_avg", "historical_avg", "momentum", "volume_score", "momentum_score",
            "patent_score", "patent_momentum_available"]
    snap = snap.reindex(columns=cols).sort_values("patent_score", ascending=False)
    write_csv(snap, config.PATENT_SCORES)

    log.info("Normalization: %s | company-year scores: %d | companies: %d | snapshot %d rows",
             config.PATENT_NORMALIZATION, len(scores), scores["company_id"].nunique(), len(snap))
    if not snap.empty:
        log.info("Snapshot %d (top 20):\n%s", config.PATENT_SNAPSHOT_YEAR,
                 snap.drop(columns=["company_id"]).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
