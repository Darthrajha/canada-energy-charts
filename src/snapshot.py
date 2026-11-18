"""Record hand-downloaded source files as committed, timestamped snapshots.

Statistics Canada blocks automated clients, so its tables are downloaded in a
browser and registered here. Each snapshot is copied into ``data/snapshots``
and listed in ``MANIFEST.json`` with its source URL, retrieval time (UTC),
size and SHA-256. The pipelines verify the checksum whenever they read one.

Usage (from ``src/``)::

    python snapshot.py add ~/Downloads/38100019-eng.zip \\
        --name 38100019-eng.zip \\
        --url https://www150.statcan.gc.ca/n1/tbl/csv/38100019-eng.zip

    python snapshot.py url-affordability ~/Downloads/<metadata>.csv
        # prints the browser URL for the affordability-gap member selection

    python snapshot.py list
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from common import BASE, MANIFEST, SNAPSHOT_DIR, load_manifest, province_member_ids, sha256_of


def add(source: Path, name: str, url: str, note: str = "") -> dict:
    """Copy ``source`` into the snapshot directory and record it in the manifest."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    # The file's modification time is when the browser finished downloading it.
    retrieved = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
    dest = SNAPSHOT_DIR / name
    if source.resolve() != dest.resolve():
        shutil.copyfile(source, dest)
    entry = {
        "source_url": url,
        "retrieved_at": retrieved.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": dest.stat().st_size,
        "sha256": sha256_of(dest),
    }
    if note:
        entry["note"] = note
    manifest = load_manifest()
    manifest[name] = entry
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def affordability_url(metadata_csv: Path) -> str:
    """Build the member-selection download URL from a downloaded cube-metadata CSV."""
    import affordability_gap as ag

    provinces = province_member_ids(metadata_csv.read_text(encoding="utf-8-sig"))
    if len(provinces) != 13:
        raise ValueError(f"expected 13 provinces/territories in metadata, found {len(provinces)}")
    params = {
        "pid": ag.PID,
        "latestN": 1,
        "csvLocale": "en",
        "selectedMembers": json.dumps(ag.selection(provinces), separators=(",", ":")),
    }
    return f"{BASE}/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action?{urlencode(params)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="register a downloaded file as a snapshot")
    p_add.add_argument("source", type=Path)
    p_add.add_argument("--name", required=True, help="file name inside data/snapshots")
    p_add.add_argument("--url", required=True, help="where the file was downloaded from")
    p_add.add_argument("--note", default="")
    p_url = sub.add_parser("url-affordability", help="print the affordability-gap download URL")
    p_url.add_argument("metadata", type=Path)
    sub.add_parser("list", help="show recorded snapshots")
    args = parser.parse_args()

    if args.cmd == "add":
        print(json.dumps(add(args.source.expanduser(), args.name, args.url, args.note), indent=2))
    elif args.cmd == "url-affordability":
        print(affordability_url(args.metadata.expanduser()))
    else:
        for name, entry in sorted(load_manifest().items()):
            print(f"{entry['retrieved_at']}  {entry['bytes']:>10,} B  {name}")


if __name__ == "__main__":
    main()
