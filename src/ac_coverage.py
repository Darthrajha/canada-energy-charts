"""Households with/without air conditioning, by province.

Source: Statistics Canada, Households and the Environment Survey (HES),
Table 38-10-0019-01. DOI: 10.25318/3810001901-eng

Notes
-----
The HES reports the share of households with AT LEAST ONE type of air
conditioner ("Any type of air conditioner, as a percentage of all households");
the chart shows the complement (households without AC). The HES does not cover
the territories.

The original 2021 release individually published six provinces only;
Statistics Canada's September 2025 update added the remaining four and a 2023
reference period. This pipeline uses published values exclusively.
"""

from __future__ import annotations

import pandas as pd

from common import PROVINCE_CODES, fetch_full_table, write_processed

PID8 = "38100019"
MEASURE = "Any type of air conditioner, as a percentage of all households"
YEARS = [2021, 2023]
PROVINCES = [p for p in PROVINCE_CODES if p not in ("Yukon", "Northwest Territories", "Nunavut")]


def fetch() -> pd.DataFrame:
    return fetch_full_table(PID8)


def transform(df: pd.DataFrame) -> pd.DataFrame:
    sel = df[
        df["GEO"].isin(PROVINCES)
        & (df["Air conditioners"] == MEASURE)
        & (df["REF_DATE"].astype(int).isin(YEARS))
    ][["REF_DATE", "GEO", "VALUE"]].copy()

    out = sel.pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
    out.columns = [f"pct_with_ac_{int(c)}" for c in out.columns]
    out = out.reset_index().rename(columns={"GEO": "province"})
    out.insert(1, "code", out["province"].map(PROVINCE_CODES))
    for y in YEARS:
        out[f"pct_without_ac_{y}"] = 100 - out[f"pct_with_ac_{y}"]
    return out.sort_values("pct_without_ac_2021", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    write_processed(transform(fetch()), "ac_coverage.csv")
