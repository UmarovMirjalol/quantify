"""Shared helpers: logging, rate-limited SEC HTTP client, IO, normalization."""
import logging
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import config


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    config.LOGS.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(config.LOGS / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class SecClient:
    """requests.Session wrapper honouring SEC fair-access rules."""

    def __init__(self, max_per_second: float = config.SEC_MAX_REQUESTS_PER_SECOND):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.SEC_USER_AGENT,
                                     "Accept-Encoding": "gzip, deflate"})
        self.min_interval = 1.0 / max_per_second
        self._last = 0.0
        self._lock = threading.Lock()

    def get(self, url: str, allow_404: bool = True):
        """Return a Response (or None on 404 when allow_404). Retries on 429/5xx."""
        for attempt in range(config.HTTP_RETRIES):
            with self._lock:
                wait = self.min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            try:
                response = self.session.get(url, timeout=config.HTTP_TIMEOUT)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 404 and allow_404:
                return None
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"GET failed after {config.HTTP_RETRIES} attempts: {url}")


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def write_csv(df: pd.DataFrame, path: Path, **kwargs) -> None:
    """Atomic CSV write (write to temp file, then replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, **kwargs)
    tmp.replace(path)


def normalize_cik(series: pd.Series) -> pd.Series:
    """Any CIK representation -> int64 (canonical company_id)."""
    return pd.to_numeric(series.astype(str).str.replace(r"\.0$", "", regex=True),
                         errors="coerce").astype("Int64")


LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED",
    "LLC", "LP", "PLC", "NV", "N V", "AG", "SA", "SE", "AB", "ASA", "OYJ", "SPA", "BV",
    "HOLDINGS", "HOLDING", "GROUP", "THE", "DE", "NEW", "KK", "GMBH", "ADR", "CL",
}


def normalize_company_name(name) -> str:
    """Upper-case, strip punctuation, state tags (/DE/) and trailing legal suffixes."""
    if not isinstance(name, str):
        return ""
    text = name.upper()
    text = re.sub(r"/[A-Z]{2,3}/?", " ", text)     # /DE/, /NV/ state-of-incorporation tags
    text = re.sub(r"&", " AND ", text)
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    tokens = text.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    while tokens and tokens[0] == "THE":
        tokens.pop(0)
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def percentile_score(series: pd.Series) -> pd.Series:
    """Percentile rank on a 0..100 scale (average ranks for ties); NaN preserved."""
    valid = series.notna()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    n = valid.sum()
    if n == 0:
        return out
    if n == 1:
        out[valid] = 50.0
        return out
    ranks = series[valid].rank(method="average")
    out[valid] = (ranks - 1) / (n - 1) * 100
    return out


def winsorize(series: pd.Series, limits=config.WINSORIZE_LIMITS) -> pd.Series:
    valid = series.dropna()
    if valid.empty:
        return series
    lo, hi = valid.quantile(limits[0]), valid.quantile(limits[1])
    return series.clip(lo, hi)


def sic_division(sic) -> str:
    """Standard Industrial Classification division name."""
    if pd.isna(sic):
        return None
    s = int(sic)
    divisions = [
        (100, 999, "Agriculture, Forestry & Fishing"),
        (1000, 1499, "Mining"),
        (1500, 1799, "Construction"),
        (2000, 3999, "Manufacturing"),
        (4000, 4999, "Transportation, Communications & Utilities"),
        (5000, 5199, "Wholesale Trade"),
        (5200, 5999, "Retail Trade"),
        (6000, 6799, "Finance, Insurance & Real Estate"),
        (7000, 8999, "Services"),
        (9100, 9999, "Public Administration / Nonclassifiable"),
    ]
    for lo, hi, label in divisions:
        if lo <= s <= hi:
            return label
    return None
