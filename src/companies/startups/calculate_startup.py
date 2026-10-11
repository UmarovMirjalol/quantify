"""
Stage 4a: tag startups with technology categories and measure category activity.

Each startup is tagged from its tags + description using word-bounded regexes
(config.STARTUP_TECH_PATTERNS); a startup may belong to several categories.

Category activity in year t uses accelerator cohorts t-2..t:
  share_c,t     = startups tagged c / all startups with a cohort year in the window
  intensity_c,t = log1p(n_c,t) / log1p(n_total,t)
The log form keeps software-heavy categories (AI, Fintech) from swamping
scarcer ones (Quantum, Energy) purely because accelerators skew to software.
"""
import re

import numpy as np
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("calculate_startup")


def tag_startups(df: pd.DataFrame) -> pd.DataFrame:
    text = (df["tags"].fillna("") + " " + df["description"].fillna("")).str.lower()
    for category in config.TECHNOLOGY_CATEGORIES:
        pattern = "|".join(re.sub(r"\((?!\?)", "(?:", p)
                           for p in config.STARTUP_TECH_PATTERNS[category])
        df[category] = text.str.contains(pattern, flags=re.IGNORECASE, regex=True).astype(int)
    df["technology_count"] = df[config.TECHNOLOGY_CATEGORIES].sum(axis=1)
    df["has_text"] = text.str.strip() != ""
    return df


def category_activity(df: pd.DataFrame) -> pd.DataFrame:
    dated = df[df["year"].notna()]
    years = range(min(config.INDEX_YEARS) - 3, max(config.INDEX_YEARS) + 1)
    rows = []
    for year in years:
        window = dated[dated["year"].between(year - config.STARTUP_WINDOW + 1, year)]
        total = len(window)
        for category in config.TECHNOLOGY_CATEGORIES:
            n = int(window[category].sum())
            rows.append({
                "year": year, "technology": category,
                "startups_in_window": n, "total_in_window": total,
                "share": n / total if total else np.nan,
                "activity_intensity": np.log1p(n) / np.log1p(total) if total else np.nan,
            })
    out = pd.DataFrame(rows).sort_values(["technology", "year"])
    out["share_growth_3y"] = out.groupby("technology")["share"].transform(
        lambda s: s / s.shift(3))
    return out


def main() -> None:
    df = pd.read_csv(config.STARTUPS_CLEAN)
    df = tag_startups(df)
    write_csv(df, config.STARTUPS_TAGGED)
    log.info("Tagged startups: %d | with >=1 category: %d (%.1f%%) | without text: %d",
             len(df), (df["technology_count"] > 0).sum(),
             100 * (df["technology_count"] > 0).mean(), (~df["has_text"]).sum())

    activity = category_activity(df)
    write_csv(activity, config.STARTUP_CATEGORY_ACTIVITY)

    total = len(df)
    summary = pd.DataFrame({
        "technology": config.TECHNOLOGY_CATEGORIES,
        "startup_count": [int(df[c].sum()) for c in config.TECHNOLOGY_CATEGORIES],
    })
    summary["share"] = summary["startup_count"] / total
    summary["activity_intensity"] = np.log1p(summary["startup_count"]) / np.log1p(total)
    summary["startup_activity_score"] = (100 * summary["activity_intensity"]).round(1)
    summary = summary.sort_values("startup_count", ascending=False)
    write_csv(summary, config.STARTUP_SCORES)
    log.info("Category summary:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
