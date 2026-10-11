"""
Run the Technology Disruption Index pipeline end-to-end from the project root.

    python run_pipeline.py                 # all steps (uses caches; network only for missing data)
    python run_pipeline.py --list          # show steps
    python run_pipeline.py --from index    # resume from a step
    python run_pipeline.py --only financials
    python run_pipeline.py --offline       # never touch the network (caches only)

Each step runs in its own process (`python -m <module>`), so a failure is
isolated and the pipeline can be resumed from that step.
"""
import argparse
import subprocess
import sys
import time

import config
from src.common import get_logger

log = get_logger("run_pipeline")

# (name, module, description, optional, network, offline_args)
STEPS = [
    ("companies", "src.companies.build_companies", "1. company universe (SEC tickers)", False, True, None),
    ("clean", "src.companies.clean_companies", "1. clean company universe", False, False, []),
    ("enrich", "src.companies.enrich_company_data", "2. one row per company (CIK)", False, False, []),
    ("industries", "src.companies.get_company_industries", "2. SIC / country enrichment", False, True, ["--offline"]),
    ("startups_clean", "src.companies.startups.clean_startups", "3. startup cleaning", False, False, []),
    ("startups_tag", "src.companies.startups.calculate_startup", "4. startup technology tagging", False, False, []),
    ("startups_company", "src.companies.startups.build_company_startup_scores", "4. company startup exposure", False, False, []),
    ("patents_bigquery", "src.patents.extract_patents_bigquery", "5. patent extraction (BigQuery, optional)", True, True, None),
    ("patents_process", "src.patents.process_patents", "5. patent company-year counts", False, False, []),
    ("patents_score", "src.patents.calculate_patent_scores", "5. patent scores", False, False, []),
    ("index", "src.technology_index.build_index", "6. technology disruption index", False, False, []),
    ("financials", "src.financials.fetch_sec_financials", "7. SEC financials", False, True, []),
    ("panel", "src.research.build_panel", "8. research panel", False, False, []),
    ("validate", "src.validate_data", "9. validation", True, False, []),
    ("research", "src.research.run_regressions", "10. research analysis", False, False, []),
    ("dashboard", "src.dashboard.build_dashboard", "11. interactive dashboard (docs/index.html)", True, False, []),
    ("paper", "src.research.write_paper", "12. research paper draft (paper/)", True, False, []),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--from", dest="start", help="start at this step")
    parser.add_argument("--only", help="run a single step")
    parser.add_argument("--offline", action="store_true", help="skip network steps; use caches")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    names = [s[0] for s in STEPS]
    if args.list:
        for name, _, desc, optional, network, _ in STEPS:
            print(f"{name:18s} {desc}{'  [optional]' if optional else ''}{'  [network]' if network else ''}")
        return
    for value in (args.start, args.only):
        if value and value not in names:
            parser.error(f"unknown step '{value}'. Choose from: {', '.join(names)}")

    steps = STEPS
    if args.only:
        steps = [s for s in STEPS if s[0] == args.only]
    elif args.start:
        steps = STEPS[names.index(args.start):]

    for name, module, desc, optional, network, offline_args in steps:
        cmd = [sys.executable, "-m", module]
        if args.offline and network:
            if offline_args is None:
                log.info("SKIP %-18s (network step, --offline)", name)
                continue
            cmd += offline_args
        log.info("RUN  %-18s %s", name, desc)
        t0 = time.time()
        result = subprocess.run(cmd, cwd=config.ROOT)
        took = time.time() - t0
        if result.returncode != 0:
            if optional:
                log.warning("WARN %-18s exited with %d after %.0fs (optional step, continuing)",
                            name, result.returncode, took)
                continue
            log.error("FAIL %-18s exited with %d after %.0fs. Fix and resume with: "
                      "python run_pipeline.py --from %s", name, result.returncode, took, name)
            sys.exit(result.returncode)
        log.info("DONE %-18s %.0fs", name, took)
    log.info("Pipeline finished.")


if __name__ == "__main__":
    main()
