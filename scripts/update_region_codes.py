#!/usr/bin/env python3
"""Convert an official/upstream 10-digit legal-district TSV to the packaged 5-digit table.

Usage:
    python scripts/update_region_codes.py path/to/region_codes.txt
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/kr_apartment_market/resources/region_codes.tsv"),
    )
    args = parser.parse_args()

    rows: dict[str, str] = {}
    with args.source.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        next(reader, None)
        for row in reader:
            if len(row) < 3 or row[2].strip() != "존재":
                continue
            code10, name = row[0].strip(), row[1].strip()
            if len(code10) == 10 and code10.endswith("00000"):
                rows[code10[:5]] = name

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["code", "name"])
        writer.writerows(sorted(rows.items()))
    print(f"wrote {len(rows)} regions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
