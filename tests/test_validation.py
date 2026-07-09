"""Validate pipeline outputs against the values in the published charts.

Run the pipelines first (they write data/processed/*.csv), then ``pytest``.
Failures on a scheduled CI run may indicate upstream data revisions by
Statistics Canada or NRCan rather than a pipeline bug - review before "fixing".
"""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = json.loads((ROOT / "tests" / "expected_values.json").read_text())


def _processed(name: str) -> pd.DataFrame:
    path = ROOT / "data" / "processed" / name
    if not path.exists():
        pytest.skip(f"{name} not generated yet - run the pipeline first")
    return pd.read_csv(path).set_index("code")


def test_affordability_gap():
    df = _processed("affordability_gap.csv")
    for code, expected in EXPECTED["affordability_gap_per_100"].items():
        got = df.loc[code, "affordable_available_per_100"]
        assert got == pytest.approx(expected, abs=0.15), f"{code}: {got} != {expected}"


def test_ac_coverage():
    df = _processed("ac_coverage.csv")
    for code, expected in EXPECTED["pct_with_ac_2021"].items():
        got = df.loc[code, "pct_with_ac_2021"]
        assert got == pytest.approx(expected, abs=0.5), f"{code}: {got} != {expected}"


def test_residential_ghg():
    df = _processed("residential_ghg.csv")
    for code, expected in EXPECTED["ghg_per_household_t"].items():
        got = df.loc[code, "ghg_per_household_t"]
        assert got == pytest.approx(expected, abs=0.03), f"{code}: {got} != {expected}"


def test_ghg_internal_consistency():
    df = _processed("residential_ghg.csv")
    drift = (df["derived_total_mt"] - df["published_total_mt"]).abs()
    assert (drift <= 0.15).all(), "derived totals drift from published CEUD totals"
