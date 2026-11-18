"""Affordable & available rental homes per 100 lowest-income renter households.

Canadian recreation of the NLIHC "Gap" measure from the 2021 Census.

Source: Statistics Canada, Census of Population 2021, Table 98-10-0252-01
(shelter-cost-to-income ratio by tenure and household income group).
DOI: 10.25318/9810025201-eng

Method
------
For each province/territory, among RENTER households:

1. Total renters ``r`` = income Total x STIR Total.
2. Lowest-income quintile ``q`` = 0.2 x r. The census publishes 11 dollar
   brackets rather than quintiles, so brackets are accumulated from the bottom
   and the boundary bracket is included pro-rata.
3. Affordable & available ``a`` = renters within that bottom quintile whose
   shelter-cost-to-income ratio (STIR) is below 30%, with the boundary
   bracket's sub-30% count scaled by the same pro-rata fraction.
4. Gap measure = 100 x a / q.

Bracket totals use the STIR "Total" column, which includes the small
"not applicable" group (zero/negative income, farm-operated dwellings).
"""

from __future__ import annotations

import pandas as pd
import requests

from common import (
    PROVINCE_CODES,
    fetch_metadata,
    fetch_selected,
    province_member_ids,
    snapshot_path,
    write_processed,
)

PID = "9810025201"
SNAPSHOT = f"{PID}-selected.csv"  # the member selection built in selection() below

# Dimension members (from cube metadata):
INCOME_BRACKETS = list(range(2, 13))  # "Under $10,000" ... "$100,000 and over"
INCOME_TOTAL = 1
STIR_TOTAL, STIR_UNDER30, STIR_30PLUS = 1, 2, 3
DIM_TOTAL = 1  # household type / suitability / condition totals
STAT_COUNT = 1  # "Number of private households"
TENURE_RENTER = 3

INCOME_ORDER = [
    "Under $10,000", "$10,000 to $19,999", "$20,000 to $29,999",
    "$30,000 to $39,999", "$40,000 to $49,999", "$50,000 to $59,999",
    "$60,000 to $69,999", "$70,000 to $79,999", "$80,000 to $89,999",
    "$90,000 to $99,999", "$100,000 and over",
]


def selection(provinces: dict[str, int]) -> list[list[int]]:
    """Member selection for the download endpoint, one list per cube dimension."""
    return [
        sorted(provinces.values()),
        [INCOME_TOTAL] + INCOME_BRACKETS,
        [DIM_TOTAL], [DIM_TOTAL], [DIM_TOTAL],
        [STAT_COUNT],
        [STIR_TOTAL, STIR_UNDER30, STIR_30PLUS],
        [TENURE_RENTER],
    ]


def fetch() -> pd.DataFrame:
    """Live member-selection download, or the committed snapshot if that fails."""
    try:
        provinces = province_member_ids(fetch_metadata(PID))
        return fetch_selected(PID, selection(provinces))
    except requests.RequestException as exc:
        return pd.read_csv(snapshot_path(SNAPSHOT, reason=exc))


def transform(df: pd.DataFrame) -> pd.DataFrame:
    inc_col = "Household total income groups (14)"
    stir_col = "Shelter-cost-to-income ratio (5)"
    rows = []
    for geo, g in df.groupby("GEO"):
        if geo not in PROVINCE_CODES:
            continue
        total_lbl = "Total - Total income of household"
        under30_lbl = "Spending less than 30% of income on shelter costs"
        stir_total_lbl = "Total - Shelter-cost-to-income ratio"
        over30_lbl = "Spending 30% or more of income on shelter costs"
        cell = g.pivot_table(index=inc_col, columns=stir_col, values="VALUE", aggfunc="first")
        # pivot_table drops any bracket whose cells are all suppressed. Restore the
        # full grid so every lookup below resolves (to NaN) instead of raising.
        cell = cell.reindex(
            index=[total_lbl] + INCOME_ORDER,
            columns=[stir_total_lbl, under30_lbl, over30_lbl],
        )

        r = float(cell.loc[total_lbl, stir_total_lbl])
        if not r > 0:
            raise ValueError(f"missing renter total for {geo}")
        # Small-area cells can be suppressed or omitted under census
        # confidentiality rules (e.g. territory income brackets); treat those
        # as zero when accumulating. Totals are verified present above.
        cell = cell.fillna(0.0)
        q = 0.2 * r

        cum, affordable = 0.0, 0.0
        for bracket in INCOME_ORDER:
            b_total = float(cell.loc[bracket, stir_total_lbl])
            b_under30 = float(cell.loc[bracket, under30_lbl])
            if cum + b_total < q:
                cum += b_total
                affordable += b_under30
            else:  # boundary bracket: include pro-rata
                frac = (q - cum) / b_total if b_total else 0.0
                affordable += frac * b_under30
                break

        rows.append({
            "province": geo,
            "code": PROVINCE_CODES[geo],
            "renter_households": int(r),
            "lowest_income_quintile": int(round(q)),
            "affordable_available_per_100": round(100 * affordable / q, 1),
            "pct_burdened_incl_na": round(100 * (1 - float(cell.loc[total_lbl, under30_lbl]) / r), 1),
            "pct_burdened_strict": round(100 * float(cell.loc[total_lbl, over30_lbl]) / r, 1),
        })
    return pd.DataFrame(rows).sort_values("affordable_available_per_100").reset_index(drop=True)


if __name__ == "__main__":
    write_processed(transform(fetch()), "affordability_gap.csv")
