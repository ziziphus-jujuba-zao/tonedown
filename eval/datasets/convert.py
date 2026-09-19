"""Convert a CSV or JSONL file with arbitrary column names to the golden JSONL shape.

    uv run eval/datasets/convert.py raw/cold.csv --text TEXT --label label --lang zh \
        --map 1=2 --map 0=0 --out ../golden/cold-sample.jsonl --limit 500
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--text", required=True, help="column holding the text")
    p.add_argument("--label", required=True, help="column holding the label")
    p.add_argument("--lang", required=True)
    p.add_argument("--map", action="append", default=[], help="label=level, repeatable (e.g. --map toxic=2)")
    p.add_argument("--category", help="category to attach to every item with level >= 2 (e.g. hate)")
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()
    mapping = dict(m.split("=", 1) for m in args.map)

    src = Path(args.path)
    if src.suffix == ".jsonl":
        rows = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        with src.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

    out = Path(args.out)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for i, row in enumerate(rows):
            label = str(row[args.label])
            if label not in mapping:
                continue
            level = int(mapping[label])
            item = {
                "id": f"{args.lang}-{src.stem}-{i}",
                "text": str(row[args.text]).strip(),
                "level": level,
                "categories": [args.category] if args.category and level >= 2 else [],
                "targeted": False,
                "note": f"from {src.name}, label {label}",
            }
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            n += 1
            if args.limit and n >= args.limit:
                break
    print(f"wrote {n} items to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
