#!/usr/bin/env python3
"""Validate that simulator marginals match published Wikipedia odds.

For each confirmatory-eligible year, runs N simulations and compares the
simulated P(team drawn at position j) against the published probabilities
from lottery_probability_matrix.csv. Flags any (year, team, position) where
the gap exceeds 3x the Monte Carlo standard error.

Usage:
    python scripts/validate_probabilities.py --probs data/processed/lottery_probability_matrix.csv --n 1000000 --seed 0
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from nba_lottery.simulate import load_year_configs, simulate


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probs", type=Path,
                   default=Path("data/processed/lottery_probability_matrix.csv"))
    p.add_argument("--team-year", type=Path,
                   default=Path("data/processed/lottery_team_year.csv"))
    p.add_argument("--n", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tol-sd", type=float, default=3.0,
                   help="Max allowed discrepancy in multiples of MC SE.")
    p.add_argument("--tol-abs", type=float, default=0.002,
                   help="Absolute probability tolerance absorbed before "
                        "applying --tol-sd. Wikipedia publishes probabilities "
                        "rounded to 3 decimals, so we allow ~0.002 rounding.")
    args = p.parse_args()

    configs = load_year_configs(args.team_year, eligible_only=True)

    # Load published probabilities
    published = {}  # (year, team, pick_position) -> probability
    for row in csv.DictReader(args.probs.open()):
        key = (int(row["year"]), row["team"], int(row["pick_position"]))
        published[key] = float(row["probability"])

    rng_seed = args.seed
    problems = 0
    total_checks = 0
    worst = []
    for year, cfg in sorted(configs.items()):
        k = cfg.drawn_picks
        draws = simulate(cfg, args.n, seed=rng_seed + year)
        # Simulated P(team at position j) from draws
        for team_idx, team in enumerate(cfg.teams):
            for j in range(1, k + 1):
                sim_p = float((draws[:, j - 1] == team_idx).mean())
                pub_p = published.get((year, team, j))
                if pub_p is None:
                    continue
                total_checks += 1
                # Binomial SE for the simulated proportion
                se = float(np.sqrt(max(sim_p, 1e-15) * (1 - sim_p) / args.n))
                # Absorb the rounding tolerance first; remaining gap is what
                # actually exceeds source precision.
                raw_gap = abs(sim_p - pub_p)
                gap = max(raw_gap - args.tol_abs, 0.0)
                z = gap / se if se > 0 else 0
                if z > args.tol_sd:
                    problems += 1
                    worst.append((year, team, j, sim_p, pub_p, gap, z))
    worst.sort(key=lambda x: -x[6])
    print(f"Validated {total_checks} (year, team, pick-position) probabilities; {problems} exceeded {args.tol_sd}σ")
    if worst:
        print(f"\nTop {min(10, len(worst))} discrepancies:")
        for year, team, j, sim, pub, gap, z in worst[:10]:
            print(f"  {year} {team} pick {j}: sim={sim:.4f} pub={pub:.4f} gap={gap:.4f} z={z:.1f}")
    if problems > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
