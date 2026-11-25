# Extra diagnostics for the main valuation association

Model: ln(public float)_{t+1} ~ TDI_t (per 10 points) + ln(assets)_t + SIC2 x year FE, SEs clustered by company. Predictive association, not a causal effect.

Re-estimated coefficient: 0.0826 (SE 0.0104), +8.6% per 10 index points; N = 47,632, firms = 7,935.

## Placebo (index shuffled within SIC2 x year)

1000 draws, seed 20240101. Placebo mean -0.0001, SD 0.0053, 5-95% [-0.0089, 0.0086], largest |placebo| 0.0169. Permutation p = 0.0010 (minimum possible 0.0010).

## Year by year (SIC2 FE, HC1 SEs)

| year | coef | 95% CI | % per 10 pts | N |
|---|---|---|---|---|
| 2015 | 0.0599 | [0.0264, 0.0934] | +6.2% | 4,987 |
| 2016 | 0.0852 | [0.0494, 0.1211] | +8.9% | 4,839 |
| 2017 | 0.1029 | [0.0677, 0.1382] | +10.8% | 4,771 |
| 2018 | 0.1113 | [0.0754, 0.1473] | +11.8% | 4,671 |
| 2019 | 0.1506 | [0.1141, 0.1871] | +16.3% | 4,687 |
| 2020 | 0.1281 | [0.0921, 0.1641] | +13.7% | 5,005 |
| 2021 | 0.0607 | [0.0261, 0.0954] | +6.3% | 5,070 |
| 2022 | 0.0357 | [-0.0017, 0.0731] | +3.6% | 4,770 |
| 2023 | 0.0698 | [0.0353, 0.1042] | +7.2% | 4,538 |
| 2024 | 0.0438 | [0.0096, 0.0781] | +4.5% | 4,294 |

## Leave one industry out

| dropped | coef | 95% CI | N |
|---|---|---|---|
| Retail Trade | 0.0786 | [0.0582, 0.0990] | 45,320 |
| Transportation, Communications & Utilities | 0.0801 | [0.0594, 0.1008] | 44,528 |
| Wholesale Trade | 0.0820 | [0.0616, 0.1024] | 46,464 |
| Manufacturing | 0.0823 | [0.0542, 0.1103] | 28,034 |
| Agriculture, Forestry & Fishing | 0.0827 | [0.0624, 0.1030] | 47,350 |
| Construction | 0.0828 | [0.0624, 0.1031] | 47,061 |
| Mining | 0.0829 | [0.0625, 0.1033] | 45,130 |
| Finance, Insurance & Real Estate | 0.0855 | [0.0649, 0.1062] | 37,673 |
| Services | 0.0872 | [0.0599, 0.1146] | 39,501 |

Binned scatter and the full specification curve are in extra_tests.json.
