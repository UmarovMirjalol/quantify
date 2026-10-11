"""
Stage 4b: company-level startup-ecosystem exposure signal.

This measures how much emerging-startup activity takes place in the technology
domains a company operates in. It does NOT claim any company-startup
relationship, and it does not rely on direct name matches.

  1. Exposure weights w_i,c in {0, 0.5, 1}:
       - SIC -> category rules (config.SIC_TECHNOLOGY_RULES), industry level;
       - weak evidence from the company's own legal name (weight 0.5);
       combined by taking the max per category.
  2. Raw activity   a_i,t = sum_c w_i,c * intensity_c,t   (intensity from calculate_startup)
  3. startup_score_i,t = within-year percentile of a_i,t among firms with a_i,t > 0,
     on a (0, 100] scale. Firms whose SIC is known but not linked to any category
     get 0 (policy "zero", flagged) or NaN (policy "missing"). Firms with no SIC
     and no name evidence are MISSING, never zero; so are firms whose SIC is a catch-all
     or placeholder code (config.UNINFORMATIVE_SIC, e.g. 7389 "Business Services, NEC").
"""
import re

import numpy as np
import pandas as pd

import config
from src.common import get_logger, write_csv

log = get_logger("company_startup_scores")
CATS = config.TECHNOLOGY_CATEGORIES


def sic_informative(sic) -> bool:
    return not pd.isna(sic) and int(sic) not in config.UNINFORMATIVE_SIC


def sic_weights(sic) -> dict:
    weights = {}
    if not sic_informative(sic):
        return weights
    sic = int(sic)
    for lo, hi, cats, _ in config.SIC_TECHNOLOGY_RULES:
        if lo <= sic <= hi:
            for cat, w in cats.items():
                weights[cat] = max(weights.get(cat, 0.0), w)
    return weights


def name_weights(name) -> dict:
    text = str(name).lower()
    weights = {}
    for cat, patterns in config.COMPANY_NAME_TECH_PATTERNS.items():
        if any(re.search(p, text) for p in patterns):
            weights[cat] = config.COMPANY_NAME_EVIDENCE_WEIGHT
    return weights


def exposure_table(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rec in master.itertuples(index=False):
        by_sic = sic_weights(rec.sic)
        by_name = name_weights(rec.company_name)
        combined = {c: max(by_sic.get(c, 0.0), by_name.get(c, 0.0)) for c in CATS}
        if by_sic and by_name:
            flag = "sic_linked+name"
        elif by_sic:
            flag = "sic_linked"
        elif by_name:
            flag = "name_only"
        elif sic_informative(rec.sic):
            flag = "industry_unlinked"
        elif not pd.isna(rec.sic):
            flag = "uninformative_sic"
        else:
            flag = "missing_sic"
        row = {"company_id": rec.company_id, "coverage_flag": flag}
        row.update({f"w_{c}": combined[c] for c in CATS})
        rows.append(row)
    exp = pd.DataFrame(rows)
    wcols = [f"w_{c}" for c in CATS]
    exp["technology_exposure"] = exp[wcols].sum(axis=1)
    exp["technology_categories"] = exp[wcols].apply(
        lambda r: "; ".join(f"{c}={r[f'w_{c}']:.1f}" for c in CATS if r[f"w_{c}"] > 0), axis=1)
    exp["startup_confidence"] = exp["coverage_flag"].map({
        "sic_linked+name": "high", "sic_linked": "high", "name_only": "low",
        "industry_unlinked": "medium", "uninformative_sic": "none", "missing_sic": "none"})
    return exp


def score_year(exp: pd.DataFrame, intensity: pd.Series) -> pd.DataFrame:
    wcols = [f"w_{c}" for c in CATS]
    raw = exp[wcols].to_numpy() @ intensity.reindex(CATS).fillna(0).to_numpy()
    out = exp[["company_id", "coverage_flag"]].copy()
    out["startup_activity_raw"] = raw
    positive = out["startup_activity_raw"] > 0
    n_pos = positive.sum()
    out["startup_score"] = np.nan
    if n_pos:
        ranks = out.loc[positive, "startup_activity_raw"].rank(method="average")
        out.loc[positive, "startup_score"] = ranks / n_pos * 100
    linked_no_activity = ~positive & out["coverage_flag"].isin(
        ["sic_linked", "sic_linked+name", "name_only"])
    out.loc[linked_no_activity, "startup_score"] = 0.0
    unlinked = out["coverage_flag"] == "industry_unlinked"
    out.loc[unlinked, "startup_activity_raw"] = 0.0
    out.loc[unlinked, "startup_score"] = 0.0 if config.UNLINKED_INDUSTRY_POLICY == "zero" else np.nan
    missing = out["coverage_flag"].isin(["missing_sic", "uninformative_sic"])
    out.loc[missing, ["startup_activity_raw", "startup_score"]] = np.nan
    return out


def export_sic_map(master: pd.DataFrame) -> None:
    sics = master[["sic", "sic_description"]].dropna(subset=["sic"]).drop_duplicates("sic")
    rows = []
    for rec in sics.itertuples(index=False):
        w = sic_weights(rec.sic)
        rules = [r[3] for r in config.SIC_TECHNOLOGY_RULES if r[0] <= int(rec.sic) <= r[1]]
        rows.append({"sic": int(rec.sic), "sic_description": rec.sic_description,
                     "n_companies": int((master["sic"] == rec.sic).sum()),
                     "categories": "; ".join(f"{c}={v:.1f}" for c, v in w.items()),
                     "rules": " | ".join(rules)})
    write_csv(pd.DataFrame(rows).sort_values("sic"), config.SIC_TECHNOLOGY_MAP_OUT)


def main() -> None:
    master = pd.read_csv(config.COMPANIES_MASTER)
    activity = pd.read_csv(config.STARTUP_CATEGORY_ACTIVITY)
    exp = exposure_table(master)
    export_sic_map(master)

    frames = []
    for year in config.INDEX_YEARS:
        intensity = activity[activity["year"] == year].set_index("technology")["activity_intensity"]
        scored = score_year(exp, intensity)
        scored["year"] = year
        frames.append(scored)
    by_year = pd.concat(frames, ignore_index=True)
    by_year["startup_score"] = by_year["startup_score"].round(config.SCORE_DECIMALS)
    by_year = by_year.merge(master[["company_id", "company_name", "ticker"]], on="company_id")
    by_year = by_year[["company_id", "company_name", "ticker", "year", "startup_activity_raw",
                       "startup_score", "coverage_flag"]]
    write_csv(by_year, config.COMPANY_STARTUP_SCORES_BY_YEAR)

    latest = by_year[by_year["year"] == max(config.INDEX_YEARS)].drop(columns="coverage_flag")
    snap = master[["company_id", "company_name", "ticker", "sic", "sic_description"]].merge(
        exp, on="company_id").merge(
        latest.drop(columns=["company_name", "ticker"]), on="company_id", how="left")
    snap["startup_activity_score"] = (100 * snap["startup_activity_raw"]).round(1)
    cols = ["company_id", "company_name", "ticker", "sic", "sic_description",
            "technology_exposure", "startup_activity_score", "startup_score",
            "technology_categories", "coverage_flag", "startup_confidence", "year"] + \
           [f"w_{c}" for c in CATS]
    snap = snap[cols].rename(columns={"year": "reference_year"})
    snap["reference_year"] = max(config.INDEX_YEARS)
    write_csv(snap, config.COMPANY_STARTUP_SCORES)

    counts = snap["coverage_flag"].value_counts()
    have = snap["startup_score"].notna().sum()
    log.info("Companies: %d | startup component available: %d (%.1f%%)",
             len(snap), have, 100 * have / len(snap))
    log.info("Coverage flags: %s", counts.to_dict())
    log.info("Company-year rows: %d -> %s", len(by_year), config.COMPANY_STARTUP_SCORES_BY_YEAR.name)


if __name__ == "__main__":
    main()
