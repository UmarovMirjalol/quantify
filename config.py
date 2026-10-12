"""
Central configuration for the Technology Disruption Index pipeline.

Every tunable number (weights, year windows, thresholds, taxonomies, paths)
lives here so the methodology can be audited in one place.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"                      # downloaded / manually supplied inputs, never overwritten
RAW_SEC = RAW / "sec"
RAW_FRAMES = RAW / "sec_frames"
RAW_PATENTS = RAW / "patents"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"

# Company universe
COMPANIES_RAW = DATA / "companies.csv"                 # SEC ticker snapshot (ticker level)
COMPANIES_CLEAN = DATA / "companies_clean.csv"         # cleaned, ticker level
COMPANIES_ENRICHED = DATA / "companies_enriched.csv"   # one row per company_id (CIK)
COMPANIES_MASTER = DATA / "companies_master.csv"       # + SIC, country, industry, flags
# Add every company that filed XBRL total assets in any index year (incl. delisted firms).
# Reduces survivorship bias; such firms may have no current ticker.
INCLUDE_XBRL_FILERS = True
SEC_TICKERS_EXCHANGE_JSON = RAW_SEC / "company_tickers_exchange.json"
SEC_SUBMISSIONS_CACHE = RAW_SEC / "submissions_cache.jsonl"

# Startups
STARTUPS_RAW = DATA / "startups" / "startups_raw.csv"
STARTUPS_CLEAN = DATA / "startups" / "startups_clean.csv"
STARTUPS_TAGGED = DATA / "startups" / "startups_tagged.csv"
STARTUP_CATEGORY_ACTIVITY = DATA / "startups" / "startup_category_activity.csv"
STARTUP_SCORES = DATA / "startups" / "startup_scores.csv"   # category-level summary
COMPANY_STARTUP_SCORES = DATA / "startups" / "company_startup_scores.csv"
COMPANY_STARTUP_SCORES_BY_YEAR = DATA / "startups" / "company_startup_scores_by_year.csv"
SIC_TECHNOLOGY_MAP_OUT = DATA / "startups" / "sic_technology_map.csv"

# Patents
PATENTS_LEGACY_BY_YEAR = DATA / "patents" / "patents_by_year.csv"   # manual BigQuery pull, name keyed
PATENTS_BIGQUERY_EXPORT = RAW_PATENTS / "assignee_year_counts.csv.gz"
PATENTS_ASSIGNEE_CROSSWALK = RAW_PATENTS / "assignee_crosswalk.csv"  # optional curated additions
PATENTS_PATENTSVIEW_COUNTS = DATA / "patents" / "patentsview_company_year_counts.csv"
PATENT_COUNTS = DATA / "patents" / "patent_counts_company_year.csv"
PATENT_MATCHES = DATA / "patents" / "patent_assignee_matches.csv"
PATENT_SCORES = DATA / "patents" / "patent_scores.csv"
PATENT_SCORES_BY_YEAR = DATA / "patents" / "patent_scores_by_year.csv"

# Index
INDEX_DIR = DATA / "technology_index"
TECH_INDEX = INDEX_DIR / "company_technology_index.csv"
TECH_INDEX_LATEST = INDEX_DIR / "company_technology_index_latest.csv"
COVERAGE_REPORT = INDEX_DIR / "coverage_report.csv"

# Financials / research
FINANCIALS = DATA / "financials" / "company_financials.csv"
FINAL_PANEL = DATA / "research" / "final_panel.csv"
REGRESSION_RESULTS = RESULTS / "regression_results.csv"
RESEARCH_REPORT = RESULTS / "research_report.md"
VALIDATION_DIR = DATA / "validation"
VALIDATION_REPORT_MD = VALIDATION_DIR / "validation_report.md"
VALIDATION_REPORT_CSV = VALIDATION_DIR / "validation_report.csv"

# ---------------------------------------------------------------------------
# External services (no credentials are stored here)
# ---------------------------------------------------------------------------
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "TechDisruptionIndex research contact@example.com"
)
SEC_MAX_REQUESTS_PER_SECOND = 8          # SEC fair-access limit is 10/s
HTTP_TIMEOUT = 60
HTTP_RETRIES = 4

# Google BigQuery project used for the optional patent extraction step.
# Credentials come from the standard GOOGLE_APPLICATION_CREDENTIALS / gcloud ADC.
BIGQUERY_PROJECT = os.environ.get("BIGQUERY_PROJECT")

# ---------------------------------------------------------------------------
# Years
# ---------------------------------------------------------------------------
INDEX_YEARS = list(range(2015, 2025))    # company-year index: 2015..2024
LAST_COMPLETE_PATENT_YEAR = 2024         # 2025/2026 patent data are incomplete
PATENT_RECENT_WINDOW = 3                 # recent = t-2..t
PATENT_HISTORICAL_WINDOW = 3             # historical = t-5..t-3
PATENT_SNAPSHOT_YEAR = 2024              # recent 2022-2024 vs historical 2019-2021
PATENT_COUNT_YEARS = (2010, LAST_COMPLETE_PATENT_YEAR)
STARTUP_WINDOW = 3                       # cohorts t-2..t define category activity in t
STARTUP_VALID_YEARS = (1990, 2026)
FINANCIAL_YEARS = list(range(2013, 2026))  # need t+3 leads for the 2015..2024 index
PANEL_YEARS = list(range(2014, 2026))

# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------
INDEX_WEIGHTS = {"patent_score": 0.50, "startup_score": 0.50}
ALTERNATIVE_WEIGHTS = {
    "w25_75": {"patent_score": 0.25, "startup_score": 0.75},
    "w50_50": {"patent_score": 0.50, "startup_score": 0.50},
    "w75_25": {"patent_score": 0.75, "startup_score": 0.25},
}
MIN_COMPONENTS_FOR_INDEX = 1             # index reported when >=1 component exists (flagged)
SCORE_DECIMALS = 1                       # avoid fake precision

# Patent normalization:
#   "fixed_log"  : log1p(count) scaled against a fixed reference volume, and
#                  log2(momentum) mapped to 0..100. Independent of how many
#                  firms currently have patent data (important while coverage is small).
#   "percentile" : within-year percentile rank across firms with patent data.
PATENT_NORMALIZATION = "fixed_log"
PATENT_VOLUME_REFERENCE = 10_000         # ~ annual US grants of the very largest assignees
PATENT_MOMENTUM_PSEUDOCOUNT = 1.0        # (recent + k) / (historical + k) avoids 0-division
PATENT_MOMENTUM_LOG2_CAP = 1.0           # momentum 0.5x -> 0, 1x -> 50, 2x -> 100
PATENT_SUBWEIGHTS = {"volume_score": 0.5, "momentum_score": 0.5}
PATENT_NO_MATCH_AS_ZERO = False          # unmatched firms are MISSING, not zero patents

# Legacy name-keyed patent file -> ticker crosswalk (identifier mapping only).
LEGACY_PATENT_NAME_TO_TICKER = {
    "AMD": "AMD", "Amazon": "AMZN", "Apple": "AAPL", "Intel": "INTC",
    "Meta": "META", "Microsoft": "MSFT", "NVIDIA": "NVDA", "Oracle": "ORCL",
    "Tesla": "TSLA",
}

# ---------------------------------------------------------------------------
# Technology taxonomy
# ---------------------------------------------------------------------------
TECHNOLOGY_CATEGORIES = [
    "AI", "Fintech", "Cloud", "Robotics", "Cybersecurity",
    "Biotech", "Semiconductors", "Energy", "Quantum",
]

# Regexes applied (case-insensitive, word-bounded) to startup tags + description.
STARTUP_TECH_PATTERNS = {
    "AI": [r"artificial intelligence", r"machine learning", r"deep learning",
           r"generative ai", r"computer vision", r"natural language processing",
           r"\bnlp\b", r"\bllms?\b", r"\bai\b", r"physical ai", r"ai assistant"],
    "Fintech": [r"fintech", r"financial technology", r"payments?", r"banking",
                r"lending", r"insurtech", r"cryptocurrency", r"blockchain",
                r"web3", r"neobank", r"wealth ?tech", r"regtech"],
    "Cloud": [r"cloud", r"saas", r"devops", r"developer tools", r"data engineering",
              r"\bapi\b", r"infrastructure software", r"serverless", r"kubernetes"],
    "Robotics": [r"robotics?", r"\brobots?\b", r"autonomous", r"drones?",
                 r"industrial automation"],
    "Cybersecurity": [r"cyber ?security", r"information security", r"identity security",
                      r"fraud detection", r"\bsecurity software\b", r"zero trust",
                      r"threat (detection|intelligence)", r"\bcyber\b"],
    "Biotech": [r"biotech(nology)?", r"genomics?", r"drug discovery", r"synthetic biology",
                r"therapeutics", r"gene (therapy|editing)", r"\bcrispr\b", r"biologics?"],
    "Semiconductors": [r"semiconductors?", r"\bchips?\b", r"microchips?",
                       r"integrated circuits?", r"\bfpga\b", r"\basic\b", r"photonics"],
    "Energy": [r"clean ?energy", r"renewable", r"batter(y|ies)", r"energy storage",
               r"\bsolar\b", r"cleantech", r"climate tech", r"hydrogen", r"fuel cells?",
               r"\bev charging\b", r"\bgrid\b", r"\bwind (power|energy|turbines?)\b"],
    "Quantum": [r"quantum computing", r"quantum technolog(y|ies)", r"\bqubits?\b",
                r"quantum sensing", r"quantum software"],
}

# Weak evidence from the company's own legal name (weight capped below SIC core links).
COMPANY_NAME_TECH_PATTERNS = {
    "AI": [r"\bai\b", r"artificial intelligence", r"machine learning"],
    "Fintech": [r"fintech", r"\bpayments?\b", r"\bblockchain\b", r"\bcrypto"],
    "Cloud": [r"\bcloud\b", r"\bdata cent(er|re)s?\b", r"\bsaas\b"],
    "Robotics": [r"robot", r"\bdrones?\b", r"autonomous"],
    "Cybersecurity": [r"cyber", r"\bsecurity software\b"],
    "Biotech": [r"biotech", r"therapeutics", r"genomic", r"biosciences?", r"biopharma"],
    "Semiconductors": [r"semiconductors?", r"\bmicrochip", r"\bsemi\b"],
    "Energy": [r"\bsolar\b", r"batter(y|ies)", r"hydrogen", r"renewable",
               r"fuel cells?", r"clean energy"],
    "Quantum": [r"quantum comput", r"\bqubits?\b"],
}
COMPANY_NAME_EVIDENCE_WEIGHT = 0.5

# SIC -> technology category exposure.
# Each rule: (sic_from, sic_to, {category: weight}, rationale).
# 1.0 = the industry's core activity lies in the technology domain;
# 0.5 = adjacent/adopting industry (supplier, incumbent competing with startups in the domain).
# When several rules hit a SIC, the maximum weight per category is used.
SIC_TECHNOLOGY_RULES = [
    (2833, 2836, {"Biotech": 1.0}, "Drugs, biologicals, in-vitro diagnostics"),
    (8731, 8731, {"Biotech": 1.0}, "Commercial physical & biological research"),
    (8071, 8071, {"Biotech": 0.5}, "Medical laboratories"),
    (3826, 3826, {"Biotech": 0.5}, "Laboratory analytical instruments"),
    (3841, 3845, {"Biotech": 0.5}, "Medical/surgical/electromedical devices"),
    (3674, 3674, {"Semiconductors": 1.0, "Energy": 0.5},
     "Semiconductors & related devices (includes solar cells)"),
    (3670, 3679, {"Semiconductors": 0.5}, "Electronic components"),
    (3559, 3559, {"Semiconductors": 0.5, "Robotics": 0.5},
     "Special industry machinery (incl. semiconductor equipment)"),
    (3825, 3825, {"Semiconductors": 0.5}, "Instruments for measuring/testing electricity"),
    (3570, 3579, {"Cloud": 0.5, "Semiconductors": 0.5}, "Computer & office equipment"),
    (3571, 3571, {"AI": 0.5}, "Electronic computers"),
    (3572, 3572, {"Cloud": 0.5}, "Computer storage devices"),
    (3576, 3576, {"Cybersecurity": 0.5}, "Computer communications equipment"),
    (3578, 3578, {"Fintech": 0.5}, "Calculating & accounting machines (ATMs, POS)"),
    (3661, 3669, {"Cloud": 0.5}, "Communications equipment"),
    (4812, 4813, {"Cloud": 0.5}, "Telephone communications"),
    (4899, 4899, {"Cloud": 0.5}, "Communications services NEC"),
    (7370, 7371, {"AI": 1.0, "Cloud": 1.0, "Cybersecurity": 0.5},
     "Computer programming & services"),
    (7372, 7372, {"AI": 1.0, "Cloud": 1.0, "Cybersecurity": 0.5}, "Prepackaged software"),
    (7373, 7373, {"AI": 0.5, "Cloud": 1.0, "Cybersecurity": 0.5},
     "Computer integrated systems design"),
    (7374, 7374, {"AI": 0.5, "Cloud": 1.0, "Fintech": 0.5},
     "Computer processing & data preparation (incl. payment processing)"),
    (7375, 7379, {"AI": 0.5, "Cloud": 0.5, "Cybersecurity": 0.5},
     "Information retrieval & other computer services"),
    (7382, 7382, {"Cybersecurity": 0.5}, "Security systems services"),
    (3560, 3569, {"Robotics": 0.5}, "General industrial machinery"),
    (3540, 3549, {"Robotics": 0.5}, "Metalworking machinery"),
    (3620, 3629, {"Robotics": 0.5, "Energy": 0.5}, "Electrical industrial apparatus"),
    (3600, 3619, {"Energy": 0.5}, "Electric transmission & distribution equipment"),
    (3690, 3699, {"Energy": 1.0}, "Misc. electrical equipment (incl. storage batteries)"),
    (3510, 3519, {"Energy": 0.5}, "Engines & turbines"),
    (3711, 3716, {"Robotics": 0.5, "Energy": 0.5}, "Motor vehicles (autonomy, electrification)"),
    (3720, 3729, {"Robotics": 0.5}, "Aircraft & parts (incl. drones)"),
    (3760, 3769, {"Robotics": 0.5}, "Guided missiles & space vehicles"),
    (3812, 3812, {"Robotics": 0.5}, "Search, detection, navigation, guidance systems"),
    (3823, 3823, {"Robotics": 0.5}, "Industrial process-control instruments"),
    (3829, 3829, {"Robotics": 0.5}, "Measuring & controlling devices NEC"),
    (4911, 4911, {"Energy": 0.5}, "Electric services"),
    (4931, 4939, {"Energy": 0.5}, "Combination utilities"),
    (4991, 4991, {"Energy": 0.5}, "Cogeneration services"),
    (1311, 1389, {"Energy": 0.5}, "Oil & gas extraction (energy-domain incumbents)"),
    (2911, 2911, {"Energy": 0.5}, "Petroleum refining"),
    (2860, 2869, {"Energy": 0.5}, "Industrial organic chemicals (incl. biofuels)"),
    (6020, 6099, {"Fintech": 0.5}, "Depository institutions"),
    (6100, 6199, {"Fintech": 0.5}, "Non-depository credit institutions"),
    (6200, 6299, {"Fintech": 0.5}, "Security & commodity brokers"),
    (6300, 6411, {"Fintech": 0.5}, "Insurance carriers & agents"),
]

# SIC codes that carry no usable industry information. Companies with these codes are
# treated like companies without SIC (name evidence only, otherwise MISSING - never zero).
#   7389 "Business Services, NEC" is a catch-all that contains Mastercard, Fiserv, FIS,
#        Global Payments, Akamai, eBay next to staffing and auction firms.
#   8880 American Depositary Receipts, 8888 foreign governments, 8900 services NEC,
#   9995 non-operating establishments, 9999 nonclassifiable.
UNINFORMATIVE_SIC = {7389, 8880, 8888, 8900, 9995, 9999}

# Non-operating entity SIC codes: kept in the universe and index, flagged, and
# excluded from the research regressions.
NON_OPERATING_SIC = {6770, 6221, 6722, 6726, 6792}

# Policy for companies whose SIC is known but not linked to any category.
#   "zero"    -> startup_score = 0 (measured: industry has no tracked tech link), flagged
#   "missing" -> startup_score = NaN
UNLINKED_INDUSTRY_POLICY = "zero"

# ---------------------------------------------------------------------------
# Financials (SEC XBRL frames API)
# ---------------------------------------------------------------------------
# Concepts in priority order; the first available concept wins per company-year.
FINANCIAL_CONCEPTS = {
    "revenue": {"period": "duration", "taxonomy": "us-gaap", "concepts": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ]},
    "assets": {"period": "instant", "taxonomy": "us-gaap", "concepts": ["Assets"]},
    "rd": {"period": "duration", "taxonomy": "us-gaap", "concepts": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ]},
    "capex": {"period": "duration", "taxonomy": "us-gaap", "concepts": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ]},
    "cash": {"period": "instant", "taxonomy": "us-gaap", "concepts": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ]},
    "debt": {"period": "instant", "taxonomy": "us-gaap", "concepts": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ]},
    "public_float": {"period": "public_float", "taxonomy": "dei",
                     "concepts": ["EntityPublicFloat"]},
}
# IFRS equivalents used by the companyfacts supplement (foreign 20-F / 40-F filers).
IFRS_CONCEPTS = {
    "revenue": ["Revenue", "RevenueFromContractsWithCustomers"],
    "assets": ["Assets"],
    "rd": ["ResearchAndDevelopmentExpense"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
              "PurchaseOfPropertyPlantAndEquipment"],
    "cash": ["CashAndCashEquivalents"],
    "debt": ["NoncurrentPortionOfNoncurrentBorrowings", "LongtermBorrowings"],
}
# FRED annual-average exchange rates: currency -> (series, True if quoted as USD per unit).
FRED_FX_SERIES = {
    "EUR": ("AEXUSEU", True), "GBP": ("AEXUSUK", True), "AUD": ("AEXUSAL", True),
    "NZD": ("AEXUSNZ", True), "CAD": ("AEXCAUS", False), "JPY": ("AEXJPUS", False),
    "CNY": ("AEXCHUS", False), "TWD": ("AEXTAUS", False), "KRW": ("AEXKOUS", False),
    "INR": ("AEXINUS", False), "MXN": ("AEXMXUS", False), "BRL": ("AEXBZUS", False),
    "CHF": ("AEXSZUS", False), "SEK": ("AEXSDUS", False), "DKK": ("AEXDNUS", False),
    "NOK": ("AEXNOUS", False), "SGD": ("AEXSIUS", False), "HKD": ("AEXHKUS", False),
    "ZAR": ("AEXSFUS", False), "THB": ("AEXTHUS", False), "MYR": ("AEXMAUS", False),
}
# Currencies without a FRED annual series: ECB reference rates (frankfurter.app), annual mean.
ECB_FX_CURRENCIES = ["ILS", "TRY", "IDR", "PHP"]
# Variables that cannot be negative; negative reported values are set to NaN and flagged.
NONNEGATIVE_FINANCIALS = ["assets", "rd", "capex", "cash", "debt", "public_float"]

# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------
WINSORIZE_LIMITS = (0.01, 0.99)          # per-year winsorization of financial ratios
LARGEST_FIRMS_QUANTILE = 0.90            # "exclude largest firms" = top 10% assets per year
LEAD_HORIZONS = [1, 2, 3]
INDEX_SCALE_FOR_REGRESSION = 10.0        # coefficients reported per 10 index points
