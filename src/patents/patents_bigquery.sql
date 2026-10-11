-- US granted patents per harmonized assignee name and grant year.
-- Source: Google Patents Public Data (patents-public-data.patents.publications).
--
-- Run manually in the BigQuery console, or via src/patents/extract_patents_bigquery.py.
-- Manual route: export the result as CSV (to Google Drive / Cloud Storage for large
-- results) and save it as data/raw/patents/assignee_year_counts.csv.gz
-- (plain .csv is also accepted: data/raw/patents/assignee_year_counts.csv).
--
-- Notes
--  * kind codes B1/B2 = granted utility patents; counted by GRANT year, which avoids
--    the right-truncation bias of filing-year counts of granted patents.
--  * co-assigned patents count once for every assignee (full counting).
--  * only columns needed are selected to keep the scanned bytes low.

SELECT
  UPPER(TRIM(a.name))                           AS assignee_name,
  CAST(DIV(p.grant_date, 10000) AS INT64)       AS year,
  COUNT(DISTINCT p.publication_number)          AS patent_count,
  COUNT(DISTINCT p.family_id)                   AS family_count
FROM `patents-public-data.patents.publications` AS p,
     UNNEST(p.assignee_harmonized) AS a
WHERE p.country_code = 'US'
  AND p.kind_code IN ('B1', 'B2')
  AND p.grant_date BETWEEN {start_year}0101 AND {end_year}1231
  AND a.name IS NOT NULL
GROUP BY assignee_name, year
