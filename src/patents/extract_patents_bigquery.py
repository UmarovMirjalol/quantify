"""
Stage 5a (optional, credentialed): pull assignee-year patent counts from BigQuery.

Requires `pip install google-cloud-bigquery` and Google Application Default
Credentials (GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`)
plus BIGQUERY_PROJECT set to a billing project. Nothing is hard-coded.

If those are unavailable the step is skipped (not failed) and the pipeline
continues with whatever patent data already exists. The cached export is
reused unless --refresh is passed.
"""
import argparse

import config
from src.common import get_logger

log = get_logger("extract_patents_bigquery")
SQL_FILE = config.ROOT / "src" / "patents" / "patents_bigquery.sql"


def main(refresh: bool = False) -> None:
    out = config.PATENTS_BIGQUERY_EXPORT
    if out.exists() and not refresh:
        log.info("Using cached BigQuery export %s", out)
        return
    try:
        from google.cloud import bigquery  # noqa: WPS433 (optional dependency)
    except ImportError:
        log.warning("SKIPPED: google-cloud-bigquery not installed. Run %s manually in the "
                    "BigQuery console and save the result to %s", SQL_FILE.name, out)
        return
    if not config.BIGQUERY_PROJECT:
        log.warning("SKIPPED: BIGQUERY_PROJECT environment variable not set.")
        return

    start, end = config.PATENT_COUNT_YEARS[0], config.PATENT_COUNT_YEARS[1] + 1
    sql = SQL_FILE.read_text(encoding="utf-8").format(start_year=start, end_year=end)
    try:
        client = bigquery.Client(project=config.BIGQUERY_PROJECT)
        log.info("Running BigQuery patent aggregation (grant years %d-%d)...", start, end)
        df = client.query(sql).to_dataframe()
    except Exception as exc:  # credentials / quota / network
        log.warning("SKIPPED: BigQuery query failed: %s", exc)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, compression="gzip")
    log.info("Saved %d assignee-year rows to %s", len(df), out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    main(parser.parse_args().refresh)
