# Extra diagnostics for the main valuation association

Model: ln(public float)_{t+1} ~ TDI_t (per 10 points) + ln(assets)_t + SIC2 x year FE, SEs clustered by company. Predictive association, not a causal effect.

Re-estimated coefficient: 0.0831 (SE 0.0100), +8.7% per 10 index points; N = 47,627, firms = 7,934.

## Placebo (index shuffled within SIC2 x year)

1000 draws, seed 20240101. Placebo mean -0.0000, SD 0.0053, 5-95% [-0.0084, 0.0084], largest |placebo| 0.0178. Permutation p = 0.0010 (minimum possible 0.0010).

## Year by year (SIC2 FE, HC1 SEs)

| year | coef | 95% CI | % per 10 pts | N |
|---|---|---|---|---|
| 2015 | 0.0585 | [0.0263, 0.0907] | +6.0% | 4,987 |
| 2016 | 0.0787 | [0.0436, 0.1137] | +8.2% | 4,839 |
| 2017 | 0.0968 | [0.0627, 0.1309] | +10.2% | 4,771 |
| 2018 | 0.1062 | [0.0715, 0.1408] | +11.2% | 4,671 |
| 2019 | 0.1493 | [0.1130, 0.1856] | +16.1% | 4,687 |
| 2020 | 0.1295 | [0.0942, 0.1647] | +13.8% | 5,004 |
| 2021 | 0.0617 | [0.0282, 0.0952] | +6.4% | 5,069 |
| 2022 | 0.0435 | [0.0074, 0.0795] | +4.4% | 4,769 |
| 2023 | 0.0751 | [0.0415, 0.1088] | +7.8% | 4,537 |
| 2024 | 0.0462 | [0.0126, 0.0797] | +4.7% | 4,293 |

## Leave one industry out

| dropped | coef | 95% CI | N |
|---|---|---|---|
| Retail Trade | 0.0790 | [0.0593, 0.0987] | 45,315 |
| Transportation, Communications & Utilities | 0.0803 | [0.0602, 0.1003] | 44,523 |
| Wholesale Trade | 0.0826 | [0.0629, 0.1023] | 46,459 |
| Finance, Insurance & Real Estate | 0.0827 | [0.0628, 0.1026] | 37,668 |
| Agriculture, Forestry & Fishing | 0.0833 | [0.0636, 0.1029] | 47,345 |
| Mining | 0.0834 | [0.0637, 0.1031] | 45,125 |
| Construction | 0.0835 | [0.0638, 0.1031] | 47,056 |
| Services | 0.0842 | [0.0583, 0.1100] | 39,501 |
| Manufacturing | 0.0931 | [0.0659, 0.1204] | 28,029 |

Binned scatter and the full specification curve are in extra_tests.json.
