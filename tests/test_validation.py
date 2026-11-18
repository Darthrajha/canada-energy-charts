"""Validate pipeline outputs against the values in the published charts.

Three things are tied together here so they cannot drift apart unnoticed:

1. pipeline output (``data/processed/*.csv``) vs ``tests/expected_values.json``
2. the values hardcoded in ``charts/*.html`` vs ``tests/expected_values.json``
3. ``charts/`` in this repo vs the copies served at darthrajha.github.io

Run the pipelines first (they write data/processed/*.csv), then ``pytest``.
Failures on a scheduled CI run may indicate upstream data revisions by
Statistics Canada or NRCan rather than a pipeline bug - review before "fixing".
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from common import PROVINCE_CODES  # noqa: E402

EXPECTED = json.loads((ROOT / "tests" / "expected_values.json").read_text())
CHARTS = ROOT / "charts"
SITE_CHARTS = "https://darthrajha.github.io/charts/"


def _processed(name: str) -> pd.DataFrame:
    path = ROOT / "data" / "processed" / name
    if not path.exists():
        pytest.skip(f"{name} not generated yet - run the pipeline first")
    return pd.read_csv(path).set_index("code")


# --- 1. pipeline output vs expected values ---------------------------------

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


# --- 2. values hardcoded in the chart HTML vs expected values --------------

def _chart_values(filename: str, value_pattern: str, block_pattern: str | None = None) -> dict:
    """Extract {province code: value} from a chart's inline data.

    ``value_pattern`` must capture (province name, number). ``block_pattern``
    optionally narrows the search to one JS object literal.
    """
    text = (CHARTS / filename).read_text(encoding="utf-8")
    if block_pattern:
        block = re.search(block_pattern, text, re.S)
        assert block, f"data block not found in {filename}"
        text = block.group(1)
    found = {
        PROVINCE_CODES[name]: float(value)
        for name, value in re.findall(value_pattern, text)
        if name in PROVINCE_CODES  # skips the accented "Québec" alias
    }
    assert found, f"no values parsed from {filename} - has the data format changed?"
    return found


@pytest.mark.parametrize(
    "key, filename, value_pattern, block_pattern",
    [
        ("affordability_gap_per_100", "canada-affordable-available-rental.html",
         r'"([^"]+)":\s*([\d.]+)', r"var V=\{(.*?)\};"),
        ("pct_with_ac_2021", "canada-households-without-ac.html",
         r'"([^"]+)":\s*\{\s*withAC:\s*([\d.]+)', None),
        ("ghg_per_household_t", "canada-residential-ghg-per-household.html",
         r'"([^"]+)":\s*\{\s*ghg:\s*([\d.]+)', None),
    ],
)
def test_chart_matches_expected(key, filename, value_pattern, block_pattern):
    assert _chart_values(filename, value_pattern, block_pattern) == EXPECTED[key]


# --- 3. this repo's charts/ vs the copies on the live site ------------------

@pytest.mark.parametrize("path", sorted(CHARTS.iterdir()), ids=lambda p: p.name)
def test_site_copy_in_sync(path):
    try:
        r = requests.get(SITE_CHARTS + path.name, timeout=30)
    except requests.RequestException as exc:
        pytest.skip(f"site unreachable: {exc}")
    assert r.status_code == 200, f"{path.name} is not published on the site ({r.status_code})"
    local = path.read_bytes().replace(b"\r\n", b"\n")
    assert r.content.replace(b"\r\n", b"\n") == local, (
        f"{path.name} differs between this repo and darthrajha.github.io - "
        "copy the newer version across"
    )
