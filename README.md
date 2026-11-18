# canada-energy-charts

[![validate](https://github.com/Darthrajha/canada-energy-charts/actions/workflows/validate.yml/badge.svg)](https://github.com/Darthrajha/canada-energy-charts/actions/workflows/validate.yml)

Reproducible data pipelines behind three visualisations of Canadian housing and
residential energy data, published at [darthrajha.github.io](https://darthrajha.github.io)
(Portfolio tab). Each pipeline fetches primary data from Statistics Canada or
Natural Resources Canada, applies a documented transform, and writes a tidy CSV.
A CI workflow re-runs every pipeline and asserts the outputs still match the
published charts.

| Chart | Source | Pipeline |
|---|---|---|
| The Canadian affordability gap | StatCan 2021 Census, Table 98-10-0252-01 | `src/affordability_gap.py` |
| Cooling coverage across Canada | StatCan HES 2021/2023, Table 38-10-0019-01 | `src/ac_coverage.py` |
| What heats Canada's homes | NRCan CEUD 2023, Residential Table 1 | `src/residential_ghg.py` |

## Run it

```bash
pip install -r requirements.txt
python src/affordability_gap.py   # -> data/processed/affordability_gap.csv
python src/ac_coverage.py         # -> data/processed/ac_coverage.csv
python src/residential_ghg.py     # -> data/processed/residential_ghg.csv
pytest                            # validate outputs against published chart values
```

## Methodology

### 1. The Canadian affordability gap

A Canadian recreation of the NLIHC ["Gap"](https://nlihc.org/gap) measure:
**affordable & available rental homes per 100 lowest-income renter households**,
by province and territory.

- **Data:** Census 2021 crosstab of renter households by household total income
  group (11 dollar brackets) × shelter-cost-to-income ratio (STIR), from Table
  98-10-0252-01 (DOI: [10.25318/9810025201-eng](https://doi.org/10.25318/9810025201-eng)),
  retrieved through Statistics Canada's table-download endpoint. Geography
  members are discovered from cube metadata rather than hardcoded.
- **Lowest-income renters:** the bottom **income quintile** of renter households
  in each province (Canada's closest analogue to NLIHC's "extremely low income").
  The census publishes dollar brackets, not quintiles, so the pipeline
  accumulates brackets from the bottom until it reaches 20% of renter
  households, interpolating pro-rata within the boundary bracket.
- **Affordable & available:** renter households in that bottom quintile with
  STIR below 30% — i.e. lowest-income renters actually housed affordably. The
  census counts occupied dwellings only, so vacant-but-affordable units are
  excluded (slightly understating supply relative to NLIHC's method).
- **Worked example (Ontario):** 1,722,000 renter households → quintile
  = 344,400. Cumulative bracket totals cross 344,400 inside the $20,000–$29,999
  bracket (fraction 0.829). Affordably-housed within the quintile
  = 3,970 + 29,810 + 0.829 × 69,940 = 91,774 → **26.6 per 100**.
- **Caveat:** the "cost-burdened" complement reported alongside includes the
  small "STIR not applicable" group (zero/negative-income and farm households),
  which is why it reads slightly higher than StatCan's published burden rates.

### 2. Cooling coverage across Canada

Share of households **without** air conditioning, by province — the complement
of the HES "any type of air conditioner" rate.

- **Data:** Households and the Environment Survey, Table 38-10-0019-01
  (DOI: [10.25318/3810001901-eng](https://doi.org/10.25318/3810001901-eng)),
  full-table CSV download. The pipeline extracts 2021 and 2023 for all ten
  provinces (HES does not cover the territories).
- **History note:** the original 2021 HES release individually published only
  six provinces; the chart initially estimated the other four. Statistics
  Canada's September 2025 table update published all ten (and 2023 data),
  superseding those estimates — the published 2021 values are AB 37%, BC 36%,
  NS 43%, PE 46% with AC. This repo uses published values only.

### 3. What heats Canada's homes

Residential GHG emissions per household from **on-site fossil-fuel combustion**
(natural gas, heating oil, propane, coal, wood), by province. Electricity-related
emissions are excluded in the source data, consistent with how the national
inventory attributes them.

- **Data:** NRCan Comprehensive Energy Use Database, 2023 edition, Residential
  Sector Table 1 per province (server-rendered tables at
  [oee.nrcan.gc.ca](https://oee.nrcan.gc.ca/corporate/statistics/neud/dpa/menus/trends/comprehensive/trends_res_ca.cfm)).
- **Transform:** GHG per household = GHG intensity (t/TJ) × total energy use
  (PJ × 1000) ÷ households. All three inputs come from the same table, which
  preserves internal consistency; the derived total is cross-checked against
  the published "Total GHG Excluding Electricity (Mt)" row.
- **Worked example (Alberta, 2023):** 39.6 t/TJ × 203,500 TJ ÷ 1,671,000
  households = **4.82 t CO₂e/household** (published total: 8.0 Mt ✓).
- **Caveat:** CEUD household counts and GHG figures are model-based estimates
  (Survey of Household Energy Use + StatCan demography), not direct measurements.

## Validation

`tests/test_validation.py` ties three things together so they cannot drift
apart unnoticed:

1. each pipeline's output vs `tests/expected_values.json`;
2. the values hardcoded in `charts/*.html` vs `tests/expected_values.json`;
3. `charts/` in this repo vs the copies served at darthrajha.github.io.

CI runs on every push and monthly (StatCan and NRCan revise tables; a scheduled
failure is a signal to review upstream changes, not necessarily a bug). Fetches
retry with backoff, and the processed CSVs are uploaded as a build artifact even
when a run fails. GitHub pauses scheduled workflows after 60 days without repo
activity; re-enable from the Actions tab if the badge goes stale.

The charts draw their map from `charts/canada-map.js`, a pre-projected,
simplified set of province outlines, so they load no third-party libraries.

## Licences

- **Code:** MIT (see `LICENSE`).
- **Data:** Statistics Canada data reproduced under the
  [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence);
  NRCan data under the [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada).
  This project is not affiliated with or endorsed by Statistics Canada, NRCan,
  or NLIHC.
