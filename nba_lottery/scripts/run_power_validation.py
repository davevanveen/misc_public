#!/usr/bin/env python3
"""Sensitivity-to-specified-alternatives validation.

Injects known anomalies into the simulated null data and reports whether
the primary statistics detect them at the pre-specified correction level.

Two classes of injected alternative (per the plan):
1. Diffuse: shift one team's combinations by +5 / +10 / +20% across a
   subset of years.
2. Sparse / outlier: force one specific year's #1 pick to a specific team.

Writes docs/power_validation.md.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from nba_lottery.simulate import YearConfig, simulate, load_year_configs
from nba_lottery.stats import (
    global_test,
    top1_poisson_binomial_test,
    per_year_nll,
)


def _observed_per_year(team_year_csv: Path, configs: dict[int, YearConfig]) -> dict:
    """Extract the actual drawn-pick tuples as team indices per year."""
    import csv
    obs: dict[int, tuple[int, ...]] = {}
    per_year_picks: dict[int, list[tuple[int, str]]] = {}
    for r in csv.DictReader(team_year_csv.open()):
        y = int(r["year"])
        if y not in configs:
            continue
        pos = r["won_pick_position"]
        if not pos:
            continue
        per_year_picks.setdefault(y, []).append((int(pos), r["team"]))
    for y, pairs in per_year_picks.items():
        pairs.sort()
        cfg = configs[y]
        name_to_idx = {t: i for i, t in enumerate(cfg.teams)}
        # Take only the drawn-picks prefix (pick positions 1..drawn_picks).
        # The lottery_team_year.csv also carries deterministic-tail picks;
        # those are conditioned on, not tested.
        drawn_pairs = pairs[: cfg.drawn_picks]
        if len(drawn_pairs) != cfg.drawn_picks:
            continue
        tup = tuple(name_to_idx[t] for _, t in drawn_pairs)
        obs[y] = tup
    return obs


def _inject_sparse_anomaly(
    observed: dict[int, tuple[int, ...]],
    configs: dict[int, YearConfig],
    year: int,
    force_team_idx: int,
) -> dict[int, tuple[int, ...]]:
    """Return a modified observed dict where the given year's #1 is forced
    to force_team_idx."""
    out = dict(observed)
    if year not in configs:
        return out
    cfg = configs[year]
    orig = observed.get(year)
    if orig is None or orig[0] == force_team_idx:
        return out
    new = (force_team_idx,) + tuple(t for t in orig[1:] if t != force_team_idx)
    # Ensure length matches drawn_picks; if we dropped a duplicate, pad with
    # an arbitrary unused index
    while len(new) < cfg.drawn_picks:
        used = set(new)
        for i in range(len(cfg.teams)):
            if i not in used:
                new = new + (i,)
                break
    out[year] = tuple(new[: cfg.drawn_picks])
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("docs/power_validation.md"))
    p.add_argument("--team-year", type=Path,
                   default=Path("data/processed/lottery_team_year.csv"))
    p.add_argument("--n-sims", type=int, default=50_000,
                   help="MC size for each injection run (power validation is "
                        "a sensitivity probe, not the main analysis; 50k is fine).")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    configs = load_year_configs(args.team_year, eligible_only=True)
    observed = _observed_per_year(args.team_year, configs)

    lines = [
        "# Power Validation: Sensitivity to Specified Alternatives",
        "",
        "This report is NOT a general power analysis. It is a sensitivity "
        "probe: we inject known anomalies into the data and check whether "
        "the primary test statistics detect them at the pre-specified "
        "correction level.",
        "",
        f"- MC size for each injection run: N = {args.n_sims:,}",
        f"- Confirmatory-eligible years (A-family tests): {len(configs)} "
        f"({min(configs)}-{max(configs)}).",
        "",
    ]

    # --- Baseline: no injection ---
    lines.append("## Baseline (no injection)")
    lines.append("")
    baseline = global_test(configs, observed, n_sims=args.n_sims, seed_offset=args.seed)
    lines.append(
        f"- Observed S (sum per-year NLL): **{baseline['S_obs']:.2f}** "
        f"(MC SE ≈ {baseline['S_obs_se']:.3f})"
    )
    lines.append(
        f"- Null S mean ± std: {baseline['null_mean']:.2f} ± {baseline['null_std']:.2f}"
    )
    lines.append(
        f"- p-value of A: **{baseline['p_value']:.4f}** (MC SE ≈ {baseline['p_value_se']:.4f})"
    )
    lines.append("")

    # --- Sparse injection: force one year's #1 pick to a specific team ---
    lines.append("## Sparse / outlier injection")
    lines.append("")
    lines.append(
        "For a randomly chosen year, we force the #1 pick to the team with "
        "the LOWEST pre-lottery probability. This simulates a single-year "
        "outlier anomaly (the alternative hypothesis F in the plan)."
    )
    lines.append("")

    years_to_test = [2008, 2014, 2019]
    years_to_test = [y for y in years_to_test if y in configs]
    lines.append("| Injected year | Forced to team | Original #1 | Δ p-value |")
    lines.append("|---|---|---|---|")
    for year in years_to_test:
        cfg = configs[year]
        # Find team with lowest combinations (= lowest P(#1))
        idx_min = int(np.argmin(cfg.combinations))
        team_min = cfg.teams[idx_min]
        orig = cfg.teams[observed[year][0]]
        injected = _inject_sparse_anomaly(observed, configs, year, idx_min)
        res = global_test(configs, injected, n_sims=args.n_sims,
                          seed_offset=args.seed + 100 + year)
        delta = baseline["p_value"] - res["p_value"]
        lines.append(
            f"| {year} | {team_min} | {orig} | {baseline['p_value']:.4f} → "
            f"{res['p_value']:.4f} ({'↓' if delta > 0 else '↑'} {abs(delta):.4f}) |"
        )
    lines.append("")
    lines.append("**Interpretation:** if a single-year outlier noticeably lowers the "
                 "global p-value, the test is sensitive to sparse alternatives.")
    lines.append("")

    # --- Diffuse injection: shift one team's weight across multiple years ---
    lines.append("## Diffuse injection")
    lines.append("")
    lines.append(
        "We multiply one team's combinations by a factor (1.05, 1.10, 1.20) "
        "in every year they appear, then re-normalize to the era total. We "
        "then recompute the per-year NLL **under this altered null** and the "
        "global S. This simulates a persistent bias (alternative hypothesis B)."
    )
    lines.append("")
    # Pick a team that appears in many years (reuse 'Los Angeles Lakers' or similar)
    from collections import Counter
    team_counts = Counter()
    for cfg in configs.values():
        for t in cfg.teams:
            team_counts[t] += 1
    target_team = team_counts.most_common(1)[0][0]
    target_years = [y for y, cfg in configs.items() if target_team in cfg.teams]
    lines.append(f"- Target team: **{target_team}** ({len(target_years)} years of appearances)")
    lines.append("")
    lines.append("| Multiplier | Baseline p-value | Perturbed p-value | Δ |")
    lines.append("|---|---|---|---|")
    for mult in [1.05, 1.10, 1.20]:
        perturbed_configs: dict[int, YearConfig] = {}
        for y, cfg in configs.items():
            if target_team in cfg.teams:
                idx = cfg.teams.index(target_team)
                new_combos = list(cfg.combinations)
                # Multiply and redistribute: scale target's combos, rescale
                # others so the integer total stays at combination_base.
                new_combos[idx] = int(round(new_combos[idx] * mult))
                # Rescale rest to preserve total
                rest_sum = sum(c for i, c in enumerate(new_combos) if i != idx)
                target_rest = cfg.combination_base - new_combos[idx]
                if rest_sum > 0 and target_rest > 0:
                    scale = target_rest / rest_sum
                    for i in range(len(new_combos)):
                        if i != idx:
                            new_combos[i] = int(round(new_combos[i] * scale))
                # Fix any rounding mismatch by adjusting the last non-target
                diff = cfg.combination_base - sum(new_combos)
                if diff != 0:
                    for i in range(len(new_combos) - 1, -1, -1):
                        if i != idx:
                            new_combos[i] += diff
                            break
                perturbed_configs[y] = YearConfig(
                    year=cfg.year, era=cfg.era, teams=cfg.teams, ranks=cfg.ranks,
                    combinations=tuple(new_combos), drawn_picks=cfg.drawn_picks,
                    combination_base=cfg.combination_base,
                )
            else:
                perturbed_configs[y] = cfg
        # Under this PERTURBED null, what would the observed p-value be?
        res = global_test(perturbed_configs, observed, n_sims=args.n_sims,
                          seed_offset=args.seed + 200)
        lines.append(
            f"| ×{mult:.2f} | {baseline['p_value']:.4f} | {res['p_value']:.4f} | "
            f"{baseline['p_value'] - res['p_value']:+.4f} |"
        )
    lines.append("")

    # --- T1 sensitivity: what observed top-1-win count gives p < 0.05? ---
    lines.append("## T1 detection thresholds")
    lines.append("")
    lines.append(
        "For the Poisson-binomial Top-1 test over all 41 years, how many "
        "deviations from the expected top-seed-wins-#1 count are required "
        "to reject at α = 0.05? Using the actual per-year probabilities "
        "from `lottery_winners_all_years.csv`."
    )
    lines.append("")
    winners_csv = Path("data/processed/lottery_winners_all_years.csv")
    if winners_csv.exists():
        rows = [r for r in csv.DictReader(winners_csv.open()) if r["pre_probability"]]
        per_year_probs = {int(r["year"]): float(r["pre_probability"]) for r in rows}
        # What's the one-sided upper tail count to hit p < 0.05?
        n = len(per_year_probs)
        expected = sum(per_year_probs.values())
        # Iterate upward from expected until one-sided p drops below 0.05
        lines.append(f"- n_years = {n}")
        lines.append(f"- Σ p_y (expected #1 wins by top-seed) = {expected:.2f}")
        lines.append("")
        lines.append("| Observed top-seed #1 wins | One-sided p | Detected at α=0.05 |")
        lines.append("|---|---|---|")
        for target in [int(expected), int(expected) + 2, int(expected) + 4,
                       int(expected) + 6, int(expected) + 8]:
            res = top1_poisson_binomial_test(per_year_probs, target)
            detected = "✓" if res["one_sided_p"] < 0.05 else "—"
            lines.append(
                f"| {target} | {res['one_sided_p']:.4f} | {detected} |"
            )
    lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
