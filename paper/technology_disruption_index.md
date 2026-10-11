# Do Markets Price Technology Exposure Before Fundamentals? Evidence from a Technology Disruption Index for 7,385 U.S.-Listed Companies

*Draft research paper. All figures are generated automatically from the project pipeline.*

## Abstract

I construct a reproducible, company-year Technology Disruption Index (TDI) for 7,385 SEC-registered
public companies over 2015-2024. The index combines (i) patent volume and momentum and (ii) the intensity of
startup activity, measured across 19,820 accelerator-backed startups, in the technology domains
in which each company operates. Linking the index to SEC XBRL fundamentals, I test whether technology exposure
predicts market valuation before it predicts revenue growth, R&D intensity and capital expenditure. A 10-point
higher index is associated with about 2.8% higher public float one year later (p < 0.001)
and with 0.57 percentage points higher revenue growth (p < 0.001), controlling for
size and year effects. Associations with valuation survive industry, industry-by-year and firm fixed effects, while associations with fundamentals disappear within firms. Because patent data currently cover few firms,
the index is mainly an industry-level exposure measure; results are predictive associations, not causal effects.

## 1. Introduction

Technological change is widely believed to reshape industries before it is visible in accounting statements.
If investors recognise technological opportunities early, market valuations should anticipate later changes in
revenues and investment. If instead investors under-react to hard-to-value innovation, fundamentals may move first
and valuations follow. The question has a long history in finance and economics, from the link between patents and
market value (Griliches, 1981; Hall, Jaffe and Trajtenberg, 2005) to evidence that markets misvalue innovative
firms (Eberhart, Maxwell and Siddique, 2004; Cohen, Diether and Malloy, 2013) and that the value of patents is
priced at grant (Kogan, Papanikolaou, Seru and Stoffman, 2017).

This project contributes a transparent, fully reproducible measurement pipeline that scores every listed company
rather than a hand-picked sample of technology firms. Its main design principles are: (1) the full company
universe is preserved and missing data are never treated as zero; (2) every methodological choice is configurable
and documented; (3) results are reported for every specification, without selecting on significance.

## 2. Data

**Company universe.** SEC's public ticker list, cleaned of ETFs, funds, warrants, units and SPAC shells, and
collapsed to one record per Central Index Key (CIK): 7,385 companies. Industry (SIC), country and entity type
come from the SEC submissions API.

**Startups.** 19,820 unique startups from seven accelerators (Y Combinator, Techstars, Plug and Play,
500 Global, Antler, Alchemist, Entrepreneur First), deduplicated by website domain. 57%
are assigned to at least one of nine technology categories (AI, Fintech, Cloud, Robotics, Cybersecurity, Biotech,
Semiconductors, Energy, Quantum) using word-bounded keyword rules on tags and descriptions.

**Patents.** U.S. patent counts from Google Patents Public Data (BigQuery). In the current version patent data are
available for 9 companies; the extraction query for the full universe is part of the pipeline.

**Fundamentals.** Revenue, total assets, R&D, capital expenditure, cash, long-term debt and public float from the
SEC XBRL frames API for 5,646 companies. Market capitalisation is not used because SEC does
not publish prices; public float (the market value of non-affiliate equity reported by the company) is the
valuation measure.

## 3. Methodology

**Startup-ecosystem score.** Each company receives exposure weights w(i,c) in {0, 0.5, 1} for each technology category c
from documented SIC-to-category rules (1 = core activity, 0.5 = adjacent industry), supplemented by weak evidence
from the company's legal name. Category activity in year t is intensity(c,t) = log(1+n(c,t)) / log(1+N(t)), where n
counts startups of category c in cohorts t-2..t. The company's raw activity is the exposure-weighted sum, converted to a
within-year percentile (0-100). Companies whose industry is known but not linked to any category score 0
(2,714 firms, flagged); companies without a usable industry code are missing
(964 firms).

**Patent score.** volume score = 100 * log(1+patents) / log(1+10,000); momentum = (recent 3-year mean + 1) / (previous
3-year mean + 1), mapped to 0-100 through log2; patent score = average of the two. Only complete patent years are used.

**Index.** TDI = weighted average of available components (default 50/50), with the number of available components
and a coverage score reported for every company-year. In 2024, the index is available for
6,421 companies (mean 28.9, median 17.7).

**Empirical model.** For outcome Y and horizon h:

Y(i,t+h) = b * TDI(i,t)/10 + g * ln(assets)(i,t) + fixed effects + e(i,t+h)

with standard errors clustered by company. Outcomes: ln public float (M1), ln public float controlling for its current
level (M1b, a valuation-change model), revenue growth (M2), R&D/assets (M3), CAPEX/assets (M4). Ratios are winsorised
at 1%/99% by year. Non-operating entities are excluded.

## 4. Results

**Table 1. Technology index at t and outcomes at t+1** (coefficient per 10 index points, clustered SE in parentheses;
* p<0.10, ** p<0.05, *** p<0.01)

| Outcome (t+1) | Year FE | Year + SIC2 FE | SIC2 x year FE | Firm + year FE | N obs | N firms |
|---|---|---|---|---|---|---|
| M1: ln public float | 0.0284***<br>(0.0067) | 0.0406***<br>(0.0108) | 0.0402***<br>(0.0110) | 0.0612***<br>(0.0215) | 33,678 | 4,373 |
| M1b: valuation change | 0.0078***<br>(0.0027) | 0.0142***<br>(0.0048) | 0.0142***<br>(0.0048) | 0.0532***<br>(0.0186) | 31,572 | 4,183 |
| M2: revenue growth | 0.0057***<br>(0.0011) | 0.0062***<br>(0.0016) | 0.0063***<br>(0.0016) | 0.0120<br>(0.0074) | 31,122 | 4,332 |
| M3: R&D / assets | 0.0143***<br>(0.0017) | 0.0134***<br>(0.0027) | 0.0138***<br>(0.0027) | 0.0010<br>(0.0030) | 17,240 | 2,483 |
| M4: CAPEX / assets | -0.0022***<br>(0.0001) | -0.0006***<br>(0.0002) | -0.0006***<br>(0.0002) | 0.0004<br>(0.0005) | 30,535 | 4,283 |

With year effects, a 10-point higher index is associated with about 2.8% higher public float
one year later (p < 0.001). The valuation-change model (M1b), which conditions on current public float,
yields a coefficient of 0.0078 (p = 0.004), i.e. the index is also associated with subsequent
valuation *changes*, not only levels. Comparing firms within the same two-digit industry, and absorbing
industry-specific annual shocks (SIC2 x year), makes a pure sector-cycle explanation less likely, although it
cannot rule out other omitted firm characteristics.

Fundamentals show a different pattern. Revenue growth and R&D intensity are higher and CAPEX intensity lower for technology-exposed firms across firms, but these associations become small and statistically insignificant once firm fixed effects are included, while the valuation associations do not.

**Table 2. Horizons** (year FE)

| Outcome | t+1 | t+2 | t+3 |
|---|---|---|---|
| M1: ln public float | 0.0284***<br>(0.0067) | 0.0286***<br>(0.0072) | 0.0274***<br>(0.0078) |
| M1b: valuation change | 0.0078***<br>(0.0027) | 0.0119***<br>(0.0040) | 0.0125**<br>(0.0052) |
| M2: revenue growth | 0.0057***<br>(0.0011) | 0.0047***<br>(0.0011) | 0.0043***<br>(0.0012) |
| M3: R&D / assets | 0.0143***<br>(0.0017) | 0.0144***<br>(0.0018) | 0.0143***<br>(0.0018) |
| M4: CAPEX / assets | -0.0022***<br>(0.0001) | -0.0023***<br>(0.0001) | -0.0023***<br>(0.0001) |

**Table 3. Robustness** (year FE, t+1)

| Outcome | Unwinsorized ratios | Excl. largest 10% | Tech-linked industries only | Startup component only |
|---|---|---|---|---|
| M1: ln public float | n/a | 0.0316***<br>(0.0068) | 0.0626***<br>(0.0107) | 0.0282***<br>(0.0067) |
| M1b: valuation change | n/a | 0.0091***<br>(0.0029) | 0.0178***<br>(0.0045) | 0.0078***<br>(0.0027) |
| M2: revenue growth | 0.0056***<br>(0.0013) | 0.0056***<br>(0.0011) | 0.0049***<br>(0.0015) | 0.0056***<br>(0.0011) |
| M3: R&D / assets | -0.1684<br>(0.1676) | 0.0151***<br>(0.0018) | 0.0098***<br>(0.0022) | 0.0143***<br>(0.0017) |
| M4: CAPEX / assets | -0.0005<br>(0.0081) | -0.0022***<br>(0.0001) | -0.0012***<br>(0.0002) | -0.0022***<br>(0.0001) |

## 5. Discussion

Taken together, the evidence is *consistent with* markets assigning higher and rising valuations to firms in technology-exposed domains, while the corresponding differences in fundamentals are mostly cross-sectional (technology firms are asset-light and R&D-intensive) rather than changes within firms. This is the pattern one would expect if valuations respond to technology exposure before fundamentals do. However, three cautions apply.

First, the within-firm variation of the index comes from shifts in the composition of accelerator cohorts, an
industry-level signal; it does not identify firm-specific innovation. Second, the R&D result is sensitive to extreme
values: without winsorisation its coefficient is -0.168 (p = 0.315). Third, 60 of
78 estimated coefficients have p < 0.05; consistent patterns across specifications are more informative than
any single p-value.

## 6. Limitations

1. Patent data currently cover 9 companies, so the index is predominantly the startup component.
2. The SIC-to-technology mapping is expert judgement, documented rule by rule, not an estimated model; SIC codes are current rather than historical.
3. Accelerator data over-represent software and U.S. startups.
4. The universe consists of currently listed firms (survivorship bias).
5. Public float is not market capitalisation; IFRS filers lack fundamentals in the SEC frames data.
6. No causal identification strategy is implemented.

## 7. Conclusion

A transparent technology-exposure index covering 7,385 listed companies is associated with subsequent
valuations and fundamentals in the ways summarised in Tables 1-3. Associations with valuation survive industry, industry-by-year and firm fixed effects, while associations with fundamentals disappear within firms. Extending patent coverage to the full universe would turn the index into a firm-specific
measure and allow a sharper test of whether markets price technological disruption before fundamentals.

## References

- Cohen, L., Diether, K., & Malloy, C. (2013). Misvaluing innovation. *Review of Financial Studies*, 26(3), 635-666.
- Eberhart, A. C., Maxwell, W. F., & Siddique, A. R. (2004). An examination of long-term abnormal stock returns and operating performance following R&D increases. *Journal of Finance*, 59(2), 623-650.
- Griliches, Z. (1981). Market value, R&D, and patents. *Economics Letters*, 7(2), 183-187.
- Hall, B. H., Jaffe, A., & Trajtenberg, M. (2005). Market value and patent citations. *RAND Journal of Economics*, 36(1), 16-38.
- Kogan, L., Papanikolaou, D., Seru, A., & Stoffman, N. (2017). Technological innovation, resource allocation, and growth. *Quarterly Journal of Economics*, 132(2), 665-712.

## Appendix: reproducibility

Code, configuration and data: project repository. Run `python run_pipeline.py`. All parameters are in `config.py`;
the SIC-to-technology mapping actually applied is exported to `data/startups/sic_technology_map.csv`.
