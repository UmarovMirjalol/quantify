"""
Stage 7b: fundamentals for companies absent from the XBRL frames (IFRS filers such as
20-F/40-F foreign issuers, and filers whose periods never align to a calendar frame).

Source: SEC companyfacts API (one request per company, cached and restartable in
data/raw/sec/companyfacts_cache.jsonl; only extracted annual values are stored).

Rules (kept close to the frames definitions):
  * annual facts only (forms 10-K, 20-F, 40-F, 10-KT and amendments; duration 330-400 days);
    the latest filed value per period wins;
  * year = calendar year of the period mid-point (end - 182 days) for durations and for
    fiscal-year-end balances, so a March-2024 year end counts as 2023;
  * us-gaap concepts as in config.FINANCIAL_CONCEPTS, ifrs-full equivalents in
    config.IFRS_CONCEPTS; dei:EntityPublicFloat dated within the year;
  * non-USD values are converted with FRED annual-average exchange rates (ECB reference
    rates via frankfurter.app for currencies FRED lacks); currencies or years without a
    published rate (e.g. ARS, CLP, COP, PEN) stay missing (never guessed).
"""
import argparse
import io
import json

import numpy as np
import pandas as pd
import requests

import config
from src.common import SecClient, get_logger, write_csv

log = get_logger("fetch_companyfacts")
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
CACHE = config.RAW / "sec" / "companyfacts_cache.jsonl"
FX_CACHE = config.RAW / "fx" / "fred_annual_fx.csv"
FX_CACHE_ECB = config.RAW / "fx" / "ecb_annual_fx.csv"
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT", "10-KT/A"}
VALUES = ["revenue", "assets", "rd", "capex", "cash", "debt", "public_float"]


def extract(facts: dict) -> list:
    rows = []
    sources = {var: [("us-gaap", c) for c in spec["concepts"]] if spec["taxonomy"] == "us-gaap"
               else [(spec["taxonomy"], c) for c in spec["concepts"]]
               for var, spec in config.FINANCIAL_CONCEPTS.items()}
    for var, concepts in config.IFRS_CONCEPTS.items():
        sources[var] = sources[var] + [("ifrs-full", c) for c in concepts]
    for var, concepts in sources.items():
        period = config.FINANCIAL_CONCEPTS[var]["period"]
        for priority, (tax, concept) in enumerate(concepts):
            units = facts.get(tax, {}).get(concept, {}).get("units", {})
            for unit, items in units.items():
                if len(unit) != 3 or not unit.isalpha():
                    continue
                for it in items:
                    if period != "public_float" and it.get("form") not in ANNUAL_FORMS:
                        continue
                    end = pd.Timestamp(it["end"])
                    if period == "duration":
                        if "start" not in it:
                            continue
                        days = (end - pd.Timestamp(it["start"])).days
                        if not 330 <= days <= 400:
                            continue
                    year = end.year if period == "public_float" else (end - pd.Timedelta(days=182)).year
                    rows.append([var, year, it["val"], unit, it.get("filed", ""), it["end"],
                                 priority, f"{tax}:{concept}"])
    return rows


def fetch(ids: list, offline: bool) -> pd.DataFrame:
    done = {}
    if CACHE.exists():
        with open(CACHE, encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                done[rec["cik"]] = rec["rows"]
    todo = [c for c in ids if c not in done]
    log.info("companyfacts: %d targets, %d cached, %d to fetch", len(ids), len(ids) - len(todo),
             0 if offline else len(todo))
    if todo and not offline:
        client = SecClient()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as fh:
            for i, cik in enumerate(todo, 1):
                resp = client.get(URL.format(cik=cik))
                rows = extract(resp.json().get("facts", {})) if resp is not None else []
                fh.write(json.dumps({"cik": cik, "rows": rows}) + "\n")
                done[cik] = rows
                if i % 200 == 0:
                    fh.flush()
                    log.info("  %d / %d", i, len(todo))
    recs = [[cik] + r for cik in ids for r in done.get(cik, [])]
    return pd.DataFrame(recs, columns=["company_id", "var", "year", "val", "unit", "filed", "end",
                                       "priority", "concept"])


def fx_rates(offline: bool) -> pd.DataFrame:
    """USD per one unit of currency, annual average, from FRED (no API key needed)."""
    if not FX_CACHE.exists():
        if offline:
            return pd.DataFrame(columns=["unit", "year", "usd_per_unit"])
        frames = []
        for cur, (series, usd_per_unit) in config.FRED_FX_SERIES.items():
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}",
                             timeout=60)
            if r.status_code != 200:
                log.warning("FX series %s unavailable (%s)", series, r.status_code)
                continue
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", "rate"]
            df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
            df = df.dropna()
            df["year"] = pd.to_datetime(df["date"]).dt.year
            df["usd_per_unit"] = df["rate"] if usd_per_unit else 1 / df["rate"]
            frames.append(df.assign(unit=cur)[["unit", "year", "usd_per_unit"]])
        FX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(frames).to_csv(FX_CACHE, index=False)
    if not FX_CACHE_ECB.exists() and not offline:
        rows = []
        for year in config.FINANCIAL_YEARS:
            r = requests.get(f"https://api.frankfurter.app/{year}-01-01..{year}-12-31",
                             params={"from": "USD", "to": ",".join(config.ECB_FX_CURRENCIES)},
                             timeout=60)
            if r.status_code != 200:
                continue
            daily = pd.DataFrame(r.json()["rates"]).T.astype(float)
            for cur, units_per_usd in daily.mean().items():
                rows.append({"unit": cur, "year": year, "usd_per_unit": 1 / units_per_usd})
        pd.DataFrame(rows).to_csv(FX_CACHE_ECB, index=False)
    ecb = pd.read_csv(FX_CACHE_ECB) if FX_CACHE_ECB.exists() else pd.DataFrame()
    return pd.concat([pd.read_csv(FX_CACHE), ecb], ignore_index=True)


def build(ids: list, offline: bool) -> pd.DataFrame:
    raw = fetch(ids, offline)
    if raw.empty:
        return raw
    raw = raw[raw["year"].isin(config.FINANCIAL_YEARS)]
    fx = pd.concat([fx_rates(offline),
                    pd.DataFrame({"unit": "USD", "year": config.FINANCIAL_YEARS, "usd_per_unit": 1.0})])
    raw = raw.merge(fx, on=["unit", "year"], how="left")
    n_nofx = int(raw["usd_per_unit"].isna().sum())
    raw["val"] = raw["val"] * raw["usd_per_unit"]
    raw = raw.dropna(subset=["val"])
    raw["usd_rank"] = (raw["unit"] != "USD").astype(int)
    raw = raw.sort_values(["company_id", "var", "year", "priority", "usd_rank", "end", "filed"],
                          ascending=[True, True, True, True, True, False, False])
    best = raw.drop_duplicates(["company_id", "var", "year"], keep="first")
    best = best.assign(concept=np.where(best["unit"] == "USD", best["concept"],
                                        best["concept"] + " (" + best["unit"] + "->USD)"))
    vals = best.pivot(index=["company_id", "year"], columns="var", values="val")
    cons = best.pivot(index=["company_id", "year"], columns="var", values="concept")
    cons.columns = [f"{c}_concept" for c in cons.columns]
    out = vals.join(cons).reset_index()
    for v in VALUES:
        if v not in out:
            out[v], out[f"{v}_concept"] = np.nan, np.nan
    for v in config.NONNEGATIVE_FINANCIALS:
        out.loc[out[v] < 0, v] = np.nan
    log.info("companyfacts supplement: %d company-years, %d companies (%d values without FX rate)",
             len(out), out["company_id"].nunique(), n_nofx)
    return out


def main(offline: bool = False) -> None:
    master = pd.read_csv(config.COMPANIES_MASTER, usecols=["company_id"])
    fin = pd.read_csv(config.FINANCIALS, low_memory=False)
    if "source" in fin:
        fin = fin[fin["source"] != "companyfacts"]
    targets = sorted(set(master["company_id"]) - set(fin["company_id"]))
    sup = build(targets, offline)
    if sup.empty:
        return
    sup["source"] = "companyfacts"
    fin["source"] = "frames"
    sup["market_cap"] = np.nan
    out = pd.concat([fin, sup[fin.columns]], ignore_index=True).sort_values(["company_id", "year"])
    write_csv(out, config.FINANCIALS)
    log.info("Financials now cover %d of %d companies (%.1f%%)", out["company_id"].nunique(),
             len(master), 100 * out["company_id"].nunique() / len(master))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    main(ap.parse_args().offline)
