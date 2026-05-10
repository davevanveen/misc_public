#!/usr/bin/env python3
"""Fetch raw Wikipedia lottery data and build processed datasets.

Usage:
    python scripts/build_dataset.py --raw-dir data/raw --out-dir data/processed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_lottery.dataset import build


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    p.add_argument("--year-start", type=int, default=1985)
    p.add_argument("--year-end", type=int, default=2025)
    p.add_argument("--throttle", type=float, default=1.5,
                   help="Seconds to wait between uncached Wikipedia requests")
    args = p.parse_args()

    years = list(range(args.year_start, args.year_end + 1))
    summary = build(args.raw_dir, args.out_dir, years=years, throttle_s=args.throttle)

    print("Dataset build summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
