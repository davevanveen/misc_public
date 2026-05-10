#!/usr/bin/env python3
"""Write docs/analysis_plan_hashes.txt recording SHA-256 of the analysis-plan docs.

This is an audit-trail artifact: once the freeze commit lands, any later
change to the listed docs is detectable by comparing current SHA-256 values
against this file. Git is the authoritative timeline; this file serves as
machine-readable co-location with results.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--docs", type=Path, nargs="+",
        default=[
            Path("docs/statistical_analysis_plan.md"),
            Path("docs/hypotheses.md"),
            Path("docs/multiple_testing_plan.md"),
            Path("docs/estimand_choice.md"),
        ],
    )
    p.add_argument("--out", type=Path, default=Path("docs/analysis_plan_hashes.txt"))
    args = p.parse_args()

    lines = [
        "# Analysis Plan Hashes",
        "# Written by scripts/freeze_plan.py; any subsequent change to the",
        "# listed files can be detected by recomputing SHA-256 and comparing.",
        f"# Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
    ]
    missing = False
    for doc in args.docs:
        if not doc.exists():
            print(f"ERROR: {doc} not found", file=sys.stderr)
            missing = True
            continue
        sha = hashlib.sha256(doc.read_bytes()).hexdigest()
        lines.append(f"{sha}  {doc}")
    if missing:
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
