"""Residential GHG emissions per household from on-site fossil-fuel combustion.

Source: Natural Resources Canada, Comprehensive Energy Use Database (CEUD),
2023 edition, Residential Sector, Table 1 (Secondary Energy Use and GHG
Emissions by Energy Source), per province.

Method
------
GHG per household = GHG intensity (t/TJ) x total energy use (PJ x 1000)
                    / households

All inputs come from the same CEUD table, preserving internal consistency.
The derived provincial total is cross-checked against the published
"Total GHG Emissions Excluding Electricity (Mt)" row (CEUD rounds to 0.1 Mt).
Electricity-related emissions are excluded in the source data.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from common import PROVINCE_CODES, write_processed

YEAR = "2023"
JURIS = {  # CEUD jurisdiction slugs (no territories in provincial tables)
    "nl": "Newfoundland and Labrador", "pe": "Prince Edward Island",
    "ns": "Nova Scotia", "nb": "New Brunswick", "qc": "Quebec",
    "on": "Ontario", "mb": "Manitoba", "sk": "Saskatchewan",
    "ab": "Alberta", "bc": "British Columbia",
}
URL = ("https://oee.nrcan.gc.ca/corporate/statistics/neud/dpa/showTable.cfm"
       "?type=CP&sector=res&juris={juris}&year={year}&rn=1&page=0")
UA = {"User-Agent": "canada-energy-charts (github.com/Darthrajha/canada-energy-charts)"}


def _row(table: pd.DataFrame, label: str) -> pd.Series:
    hit = table[table.iloc[:, 0].astype(str).str.contains(label, regex=False, na=False)]
    if hit.empty:
        raise ValueError(f"row not found: {label}")
    return hit.iloc[0]


def _num(value) -> float:
    return float(str(value).replace(",", ""))


def fetch_province(slug: str) -> dict:
    html = requests.get(URL.format(juris=slug, year=YEAR), headers=UA, timeout=60).text
    tables = pd.read_html(io.StringIO(html), thousands=",")
    table = max(tables, key=len)  # the data table is the largest on the page
    year_col = [c for c in table.columns if str(c).strip() == YEAR][0]

    energy_pj = _num(_row(table, "Total Energy Use")[year_col])
    households_k = _num(_row(table, "Total Households")[year_col])
    intensity_t_per_tj = _num(_row(table, "GHG (Greenhouse Gas) Intensity")[year_col])
    published_mt = _num(_row(table, "Total GHG (Greenhouse Gas) Emissions Excluding Electricity")[year_col])

    derived_t_per_hh = intensity_t_per_tj * energy_pj * 1000 / (households_k * 1000)
    derived_mt = intensity_t_per_tj * energy_pj * 1000 / 1e6

    return {
        "province": JURIS[slug],
        "code": PROVINCE_CODES[JURIS[slug]],
        "energy_use_pj": energy_pj,
        "households_thousands": households_k,
        "ghg_intensity_t_per_tj": intensity_t_per_tj,
        "ghg_per_household_t": round(derived_t_per_hh, 2),
        "derived_total_mt": round(derived_mt, 2),
        "published_total_mt": published_mt,
    }


def transform() -> pd.DataFrame:
    rows = [fetch_province(slug) for slug in JURIS]
    df = pd.DataFrame(rows).sort_values("ghg_per_household_t", ascending=False)
    # internal consistency: derived vs published total (CEUD rounds to 0.1 Mt)
    drift = (df["derived_total_mt"] - df["published_total_mt"]).abs()
    if (drift > 0.15).any():
        bad = df.loc[drift > 0.15, "province"].tolist()
        raise AssertionError(f"derived GHG total drifts from published value: {bad}")
    return df.reset_index(drop=True)


if __name__ == "__main__":
    write_processed(transform(), "residential_ghg.csv")
