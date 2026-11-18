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

from common import PROVINCE_CODES, get, write_processed

YEAR = "2023"
JURIS = {  # CEUD jurisdiction slugs (no territories in provincial tables)
    "nl": "Newfoundland and Labrador", "pe": "Prince Edward Island",
    "ns": "Nova Scotia", "nb": "New Brunswick", "qc": "Quebec",
    "on": "Ontario", "mb": "Manitoba", "sk": "Saskatchewan",
    "ab": "Alberta", "bc": "British Columbia",
}
URL = ("https://oee.nrcan.gc.ca/corporate/statistics/neud/dpa/showTable.cfm"
       "?type=CP&sector=res&juris={juris}&year={year}&rn=1&page=0")
MAX_DRIFT_MT = 0.15  # CEUD publishes totals rounded to 0.1 Mt


def _row(table: pd.DataFrame, pattern: str) -> pd.Series:
    """Find a row by regex on the label column.

    Labels are matched loosely because NRCan wraps abbreviations in <abbr>
    markup ("GHG Intensity" may or may not render with an expansion) and cells
    can contain footnote markers and non-breaking spaces.
    """
    labels = (table.iloc[:, 0].astype(str)
              .str.replace("\xa0", " ", regex=False)
              .str.strip())
    hit = table[labels.str.contains(pattern, regex=True, na=False)]
    if hit.empty:
        raise ValueError(f"row not found: {pattern!r} in {labels.tolist()[:8]}...")
    return hit.iloc[0]


def _num(value) -> float:
    return float(str(value).replace(",", ""))


def fetch_province(slug: str) -> dict:
    html = get(URL.format(juris=slug, year=YEAR)).text
    tables = pd.read_html(io.StringIO(html), thousands=",")
    table = max(tables, key=len)  # the data table is the largest on the page
    year_cols = [c for c in table.columns if str(c).strip() == YEAR]
    if not year_cols:
        raise ValueError(f"no {YEAR} column for {slug!r}; columns: {list(table.columns)}")
    year_col = year_cols[0]

    energy_pj = _num(_row(table, r"^Total Energy Use")[year_col])
    households_k = _num(_row(table, r"^Total Households")[year_col])
    intensity_t_per_tj = _num(_row(table, r"GHG\b.*Intensity")[year_col])
    published_mt = _num(_row(table, r"Total GHG\b.*Excluding Electricity")[year_col])

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
    return df.reset_index(drop=True)


def check_consistency(df: pd.DataFrame) -> None:
    """Derived provincial totals must match the published CEUD totals."""
    drift = (df["derived_total_mt"] - df["published_total_mt"]).abs()
    if (drift > MAX_DRIFT_MT).any():
        bad = df.loc[drift > MAX_DRIFT_MT, "province"].tolist()
        raise AssertionError(f"derived GHG total drifts from published value: {bad}")


if __name__ == "__main__":
    result = transform()
    # Write first so the CSV is available for inspection even when the check fails.
    write_processed(result, "residential_ghg.csv")
    check_consistency(result)
