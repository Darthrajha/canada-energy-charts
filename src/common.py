"""Shared helpers for Statistics Canada table access.

Two access paths are used:

1. ``fetch_full_table``   - the bulk CSV zip (small cubes only).
2. ``fetch_selected``     - the table-download endpoint that serves a CSV for an
   explicit member selection. Essential for large census cubes, where the full
   crosstab would be tens of millions of rows.

Member IDs are discovered from cube metadata (``fetch_metadata``) rather than
hardcoded, so geography changes upstream don't silently break the pipelines.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www150.statcan.gc.ca"
UA = {"User-Agent": "canada-energy-charts (github.com/Darthrajha/canada-energy-charts)"}

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

PROVINCE_CODES = {
    "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Quebec": "QC",
    "Ontario": "ON",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Alberta": "AB",
    "British Columbia": "BC",
    "Yukon": "YT",
    "Northwest Territories": "NT",
    "Nunavut": "NU",
}


def fetch_full_table(pid8: str) -> pd.DataFrame:
    """Download a full StatCan table as CSV (cached in data/raw)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{pid8}-eng.zip"
    if not cache.exists():
        url = f"{BASE}/n1/tbl/csv/{pid8}-eng.zip"
        r = requests.get(url, headers=UA, timeout=120)
        r.raise_for_status()
        cache.write_bytes(r.content)
    with zipfile.ZipFile(cache) as z:
        with z.open(f"{pid8}.csv") as f:
            return pd.read_csv(f, low_memory=False)


def fetch_metadata(pid10: str) -> str:
    """Return the raw cube-metadata CSV for a 10-digit product id."""
    url = f"{BASE}/t1/tbl1/en/dtl!downloadCubeMetaData-nonTraduit.action"
    r = requests.get(url, params={"pid": pid10, "csvLocale": "en"}, headers=UA, timeout=60)
    r.raise_for_status()
    return r.text


def province_member_ids(metadata_csv: str) -> dict[str, int]:
    """Map province/territory names to geography member IDs.

    Uses the member-attribute section (``GEO_LEVEL_DESC == 'Province or
    territory'``) to identify provinces among the hundreds of CMA/CA members.
    """
    # attribute rows: dim_id, member_id, attr_key, title, label, long_label, value
    level_by_member: dict[int, str] = {}
    name_by_member: dict[int, str] = {}
    for row in csv.reader(io.StringIO(metadata_csv)):
        if len(row) >= 7 and row[0] == "1" and row[2] == "4" and row[3] == "GEO_LEVEL_DESC":
            level_by_member[int(row[1])] = row[6]
        if len(row) >= 7 and row[0] == "1" and row[2] == "12" and row[3] == "GEO_NAME":
            name_by_member[int(row[1])] = row[6]
    return {
        name_by_member[m]: m
        for m, level in level_by_member.items()
        if level == "Province or territory" and m in name_by_member
    }


def fetch_selected(pid10: str, selected_members: list[list[int]], latest_n: int = 1) -> pd.DataFrame:
    """Fetch a member-selection CSV from the table-download endpoint."""
    url = f"{BASE}/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action"
    params = {
        "pid": pid10,
        "latestN": latest_n,
        "csvLocale": "en",
        "selectedMembers": json.dumps(selected_members, separators=(",", ":")),
    }
    r = requests.get(url, params=params, headers=UA, timeout=120)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def write_processed(df: pd.DataFrame, name: str) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / name
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")
    return out
