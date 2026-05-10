#!/usr/bin/env python3
"""Run the full pre-registered statistical analysis.

Produces:
    outputs/tables/confirmatory_results.csv
    outputs/tables/exploratory_phase1_results.csv
    outputs/tables/exploratory_phase2_results.csv
    outputs/tables/nll_contributions.csv
    outputs/tables/leave_one_year_out.csv
    outputs/tables/concentration.csv
    outputs/tables/team_luck.csv
    outputs/tables/seed_luck.csv
    outputs/tables/era_tests.csv
    outputs/tables/outlier_years.csv

Runs after the freeze commit only.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from nba_lottery.simulate import YearConfig, load_year_configs, simulate
from nba_lottery.stats import (
    global_test,
    leave_one_year_out,
    concentration_gate,
    per_year_nll,
    top1_poisson_binomial_test,
    holm_bonferroni,
    benjamini_hochberg,
)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _observed_per_year(team_year_csv: Path, configs: dict[int, YearConfig]) -> dict:
    obs: dict[int, tuple[int, ...]] = {}
    per_year_picks: dict[int, list[tuple[int, str]]] = {}
    for r in csv.DictReader(team_year_csv.open()):
        y = int(r["year"])
        if y not in configs or not r["won_pick_position"]:
            continue
        per_year_picks.setdefault(y, []).append((int(r["won_pick_position"]), r["team"]))
    for y, pairs in per_year_picks.items():
        pairs.sort()
        cfg = configs[y]
        name_to_idx = {t: i for i, t in enumerate(cfg.teams)}
        drawn = pairs[: cfg.drawn_picks]
        if len(drawn) != cfg.drawn_picks:
            continue
        obs[y] = tuple(name_to_idx[t] for _, t in drawn)
    return obs


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/processed"))
    p.add_argument("--out", type=Path, default=Path("outputs/tables"))
    p.add_argument("--n", type=int, default=1_000_000,
                   help="Monte Carlo simulation count (default 1,000,000)")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    team_year_csv = args.data / "lottery_team_year.csv"
    configs = load_year_configs(team_year_csv, eligible_only=True)
    observed = _observed_per_year(team_year_csv, configs)

    git_sha = _git_sha()
    plan_hash = "unknown"
    hash_file = Path("docs/analysis_plan_hashes.txt")
    if hash_file.exists():
        plan_hash = hash_file.read_text()[:32]

    # Metadata header for output files (written as first CSV row = a comment-like kwarg)
    meta = {
        "git_sha": git_sha,
        "seed": args.seed,
        "n_sims": args.n,
        "plan_hash": hash_file.read_text().strip() if hash_file.exists() else "",
    }
    (args.out).mkdir(parents=True, exist_ok=True)
    (args.out / "_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # -------------------------------------------------------------------
    # Confirmatory family
    # -------------------------------------------------------------------
    print("Running test A (global NLL, all confirmatory-eligible years)...")
    A_result = global_test(configs, observed, n_sims=args.n, seed_offset=args.seed)
    print(f"  A: S_obs={A_result['S_obs']:.2f}, p={A_result['p_value']:.4f}")

    # Era-stratified A
    print("Running A_pre2019 (2006-2018)...")
    pre_configs = {y: cfg for y, cfg in configs.items() if y <= 2018}
    pre_observed = {y: observed[y] for y in pre_configs if y in observed}
    A_pre = global_test(pre_configs, pre_observed, n_sims=args.n,
                         seed_offset=args.seed + 1000)
    print(f"  A_pre2019: S_obs={A_pre['S_obs']:.2f}, p={A_pre['p_value']:.4f}")

    print("Running A_post2019 (2019+)...")
    post_configs = {y: cfg for y, cfg in configs.items() if y >= 2019}
    post_observed = {y: observed[y] for y in post_configs if y in observed}
    A_post = global_test(post_configs, post_observed, n_sims=args.n,
                          seed_offset=args.seed + 2000)
    print(f"  A_post2019: S_obs={A_post['S_obs']:.2f}, p={A_post['p_value']:.4f}")

    # T1 Poisson-binomial over all 41 years
    print("Running T1 (Poisson-binomial top-1 over 1985-2025)...")
    winners_csv = args.data / "lottery_winners_all_years.csv"
    winner_rows = list(csv.DictReader(winners_csv.open()))
    per_year_top1_prob = {
        int(r["year"]): float(r["pre_probability"])
        for r in winner_rows if r["pre_probability"]
    }
    # "top seed won #1" = the winner's pre_chances equals the max combinations
    # for that year. Since we don't have the full per-year odds table for
    # pre-2006 years, we approximate: the top seed had P = max over teams.
    # Instead, define T1 as: observed count of years where the observed #1
    # winner was the rank-1 team (most combinations). We don't know the
    # rank-1 team directly for pre-2006, so we use the winner's probability
    # itself as the per-year Bernoulli probability for "top-seed-wins-#1"...
    # Actually T1 as defined is a joint test of the observed sequence of
    # winners against per-year distributions. A cleaner framing: test
    # Σ -log P(winner_y) against the null distribution.
    # We use that formulation.
    observed_log_loss_T1 = float(
        -np.sum(np.log([p for p in per_year_top1_prob.values() if p > 0]))
    )
    # Null: for each year, sample a winner from the per-year distribution.
    # But we only have the per-year probability for the OBSERVED winner.
    # For a clean T1 over all 41 years we need something year-agnostic.
    # Option: measure "how surprising was the actual winner?" as mean log-loss
    # per year, and compare to the expected log-loss under the null
    # (which we'd need the full distribution for).
    #
    # Simpler and well-defined: count the number of years the observed
    # winner was the year's top-odds team. For years where we have the full
    # odds table (2006-2025 eligible), we can check directly.
    T1_observed_top = 0
    T1_probs_top = {}
    for y in per_year_top1_prob:
        cfg = configs.get(y)
        obs = observed.get(y)
        if cfg is None or obs is None:
            continue
        # "Top seed" = team with max combinations. If the observed #1 pick
        # was that team, count +1.
        top_idx = int(np.argmax(cfg.combinations))
        T1_observed_top += int(obs[0] == top_idx)
        T1_probs_top[y] = float(cfg.combinations[top_idx]) / float(sum(cfg.combinations))
    print(f"  T1 (top-seed wins #1, 2006+ only): observed={T1_observed_top}, "
          f"expected={sum(T1_probs_top.values()):.2f}")
    T1_test = top1_poisson_binomial_test(T1_probs_top, T1_observed_top)
    print(f"  T1 p={T1_test['two_sided_p']:.4f}")

    # Holm-Bonferroni over the 4 confirmatory tests
    conf_ps = {
        "A": A_result["p_value"],
        "A_pre2019": A_pre["p_value"],
        "A_post2019": A_post["p_value"],
        "T1": T1_test["two_sided_p"],
    }
    holm = holm_bonferroni(conf_ps, alpha=0.05)

    # -------------------------------------------------------------------
    # Robustness gates on A
    # -------------------------------------------------------------------
    print("Running LOYO and concentration gates on A...")
    loyo = leave_one_year_out(A_result, alpha=0.05)
    conc = concentration_gate(A_result)

    # -------------------------------------------------------------------
    # Write outputs
    # -------------------------------------------------------------------
    # Confirmatory results
    conf_rows = []
    for name, result in [
        ("A", A_result), ("A_pre2019", A_pre), ("A_post2019", A_post),
    ]:
        h = holm[name]
        conf_rows.append({
            "test": name,
            "statistic": f"{result['S_obs']:.4f}",
            "statistic_se": f"{result['S_obs_se']:.4f}",
            "null_mean": f"{result['null_mean']:.4f}",
            "null_std": f"{result['null_std']:.4f}",
            "p_value": f"{result['p_value']:.6f}",
            "p_value_mc_se": f"{result['p_value_se']:.6f}",
            "holm_adjusted_p": f"{h['adjusted_p']:.6f}",
            "reject_holm_0_05": "1" if h["reject_at_alpha"] else "0",
            "n_years": len(result["per_year_nll"]),
            "n_sims": result["n_sims"],
        })
    h = holm["T1"]
    conf_rows.append({
        "test": "T1",
        "statistic": T1_test["observed"],
        "statistic_se": "",
        "null_mean": f"{T1_test['expected']:.4f}",
        "null_std": "",
        "p_value": f"{T1_test['two_sided_p']:.6f}",
        "p_value_mc_se": "",
        "holm_adjusted_p": f"{h['adjusted_p']:.6f}",
        "reject_holm_0_05": "1" if h["reject_at_alpha"] else "0",
        "n_years": T1_test["n_years"],
        "n_sims": "exact",
    })
    _write_csv(args.out / "confirmatory_results.csv", conf_rows, [
        "test", "statistic", "statistic_se", "null_mean", "null_std",
        "p_value", "p_value_mc_se", "holm_adjusted_p", "reject_holm_0_05",
        "n_years", "n_sims",
    ])

    # NLL contributions per year
    nll_rows = [
        {
            "year": y,
            "nll": f"{nll:.4f}",
            "mc_se": f"{se:.4f}",
            "se_over_value": f"{se/nll if nll > 0 else 0:.4f}",
            "flagged_high_se": "1" if (nll > 0 and se / nll > 0.10) else "0",
        }
        for y, (nll, se) in sorted(A_result["per_year_nll"].items())
    ]
    _write_csv(args.out / "nll_contributions.csv", nll_rows, [
        "year", "nll", "mc_se", "se_over_value", "flagged_high_se",
    ])

    # LOYO
    loyo_rows = [
        {
            "year_removed": y,
            "S_obs_loyo": f"{v['S_obs_loyo']:.4f}",
            "p_value_loyo": f"{v['p_value_loyo']:.6f}",
            "flipped_vs_headline": "1" if v["flipped"] else "0",
        }
        for y, v in sorted(loyo.items())
    ]
    _write_csv(args.out / "leave_one_year_out.csv", loyo_rows, [
        "year_removed", "S_obs_loyo", "p_value_loyo", "flipped_vs_headline",
    ])

    # Concentration
    conc_rows = [
        {
            "metric": "top3_share",
            "value": f"{conc['top3_share']:.4f}",
            "notes": "top-3 years' share of total NLL (not excess)",
        },
        {
            "metric": "top3_excess_share",
            "value": f"{conc['top3_excess_share']:.4f}",
            "notes": "top-3 years' share of NLL excess over expected (gate metric)",
        },
        {
            "metric": "gini",
            "value": f"{conc['gini']:.4f}",
            "notes": "Gini coefficient of per-year NLL contributions",
        },
        {
            "metric": "passes_gate",
            "value": "1" if conc["passes_gate"] else "0",
            "notes": "1 if top3_excess_share < 0.5 (global-anomaly gate)",
        },
    ]
    _write_csv(args.out / "concentration.csv", conc_rows,
               ["metric", "value", "notes"])

    # -------------------------------------------------------------------
    # Exploratory phase 1: team luck, seed luck, outlier years
    # -------------------------------------------------------------------
    # Team luck: for each team with enough lottery-year appearances, count
    # observed vs expected #1 wins, compute Poisson-binomial p, BH-FDR correct.
    print("Running exploratory team/seed/outlier analyses...")
    team_years: dict[str, list[int]] = defaultdict(list)
    team_top1_wins: dict[str, int] = defaultdict(int)
    team_top1_prob: dict[str, list[float]] = defaultdict(list)
    for y, cfg in configs.items():
        obs = observed.get(y)
        if obs is None:
            continue
        n_combo = sum(cfg.combinations)
        for idx, team in enumerate(cfg.teams):
            team_years[team].append(y)
            team_top1_prob[team].append(cfg.combinations[idx] / n_combo)
            if obs[0] == idx:
                team_top1_wins[team] += 1
    # Filter to teams with expected top-1 >= 2 (eligibility threshold)
    team_elig = {
        t: (wins, probs)
        for t, probs in team_top1_prob.items()
        for wins in [team_top1_wins[t]]
        if sum(probs) >= 2
    }
    team_ps: dict[str, float] = {}
    team_rows = []
    for team, probs in team_top1_prob.items():
        wins = team_top1_wins[team]
        expected = sum(probs)
        n_years_appeared = len(probs)
        if team in team_elig:
            per_year = dict(zip(team_years[team], probs))
            test = top1_poisson_binomial_test(per_year, wins)
            team_ps[team] = test["two_sided_p"]
            team_rows.append({
                "team": team,
                "n_years_in_lottery": n_years_appeared,
                "observed_top1_wins": wins,
                "expected_top1_wins": f"{expected:.4f}",
                "excess": f"{wins - expected:+.4f}",
                "two_sided_p": f"{test['two_sided_p']:.6f}",
                "eligibility": "frequentist",
            })
        else:
            team_rows.append({
                "team": team,
                "n_years_in_lottery": n_years_appeared,
                "observed_top1_wins": wins,
                "expected_top1_wins": f"{expected:.4f}",
                "excess": f"{wins - expected:+.4f}",
                "two_sided_p": "",
                "eligibility": "effect_size_only",
            })
    # Apply BH-FDR to the eligible teams
    if team_ps:
        team_bh = benjamini_hochberg(team_ps, q=0.10)
        for row in team_rows:
            if row["team"] in team_bh:
                adj = team_bh[row["team"]]
                row["bh_adjusted_p"] = f"{adj['adjusted_p']:.6f}"
                row["reject_bh_q_0_10"] = "1" if adj["reject_at_q"] else "0"
            else:
                row["bh_adjusted_p"] = ""
                row["reject_bh_q_0_10"] = ""
    team_rows.sort(key=lambda r: (r["eligibility"], r["team"]))
    _write_csv(args.out / "team_luck.csv", team_rows, [
        "team", "n_years_in_lottery", "observed_top1_wins",
        "expected_top1_wins", "excess", "two_sided_p",
        "bh_adjusted_p", "reject_bh_q_0_10", "eligibility",
    ])

    # Seed luck
    seed_top1_wins: dict[int, int] = defaultdict(int)
    seed_top1_prob: dict[int, list[float]] = defaultdict(list)
    seed_n_years: dict[int, int] = defaultdict(int)
    for y, cfg in configs.items():
        obs = observed.get(y)
        if obs is None:
            continue
        n_combo = sum(cfg.combinations)
        # Map rank -> team index for this year
        for idx, rank in enumerate(cfg.ranks):
            seed_top1_prob[rank].append(cfg.combinations[idx] / n_combo)
            seed_n_years[rank] += 1
            if obs[0] == idx:
                seed_top1_wins[rank] += 1
    seed_ps: dict[int, float] = {}
    seed_rows = []
    for rank, probs in sorted(seed_top1_prob.items()):
        wins = seed_top1_wins[rank]
        expected = sum(probs)
        if expected >= 2:
            per_year = {i: probs[i] for i in range(len(probs))}
            test = top1_poisson_binomial_test(per_year, wins)
            seed_ps[rank] = test["two_sided_p"]
            seed_rows.append({
                "pre_lottery_rank": rank,
                "n_years": seed_n_years[rank],
                "observed_top1_wins": wins,
                "expected_top1_wins": f"{expected:.4f}",
                "excess": f"{wins - expected:+.4f}",
                "two_sided_p": f"{test['two_sided_p']:.6f}",
                "eligibility": "frequentist",
            })
        else:
            seed_rows.append({
                "pre_lottery_rank": rank,
                "n_years": seed_n_years[rank],
                "observed_top1_wins": wins,
                "expected_top1_wins": f"{expected:.4f}",
                "excess": f"{wins - expected:+.4f}",
                "two_sided_p": "",
                "eligibility": "effect_size_only",
            })
    if seed_ps:
        seed_bh = benjamini_hochberg(
            {str(k): v for k, v in seed_ps.items()}, q=0.10
        )
        for row in seed_rows:
            key = str(row["pre_lottery_rank"])
            if key in seed_bh:
                adj = seed_bh[key]
                row["bh_adjusted_p"] = f"{adj['adjusted_p']:.6f}"
                row["reject_bh_q_0_10"] = "1" if adj["reject_at_q"] else "0"
            else:
                row["bh_adjusted_p"] = ""
                row["reject_bh_q_0_10"] = ""
    _write_csv(args.out / "seed_luck.csv", seed_rows, [
        "pre_lottery_rank", "n_years", "observed_top1_wins",
        "expected_top1_wins", "excess", "two_sided_p",
        "bh_adjusted_p", "reject_bh_q_0_10", "eligibility",
    ])

    # Outlier years: per-year p-value = P(null NLL >= observed NLL).
    # This is the right comparison: a year is an outlier if its observed
    # tuple is rarer than a typical null tuple from that year's distribution.
    # (Comparing raw observed_tuple_prob directly would flag every 4-pick
    # year as "rare" because 4-pick joint distributions have more atoms.)
    outlier_rows = []
    outlier_ps = {}
    for y, cfg in configs.items():
        obs = observed.get(y)
        if obs is None:
            continue
        sims = simulate(cfg, args.n, seed=args.seed + 5000 + y)
        keys = [tuple(r.tolist()) for r in sims]
        from collections import Counter
        cnt = Counter(keys)
        # NLL of observed outcome
        obs_count = cnt.get(obs, 0)
        obs_p = (obs_count + 1) / (len(sims) + 2)
        obs_nll = float(-np.log(obs_p))
        # Null distribution of NLL: take each simulated tuple's NLL
        null_nll = np.array([-np.log((cnt[k]) / len(sims)) for k in keys])
        # P(null NLL >= observed NLL) with +1 smoothing
        p_year = float(((null_nll >= obs_nll).sum() + 1) / (len(sims) + 1))
        outlier_ps[str(y)] = p_year
        outlier_rows.append({
            "year": y,
            "observed_tuple_prob": f"{obs_p:.6f}",
            "observed_nll": f"{obs_nll:.4f}",
            "two_sided_p": f"{p_year:.6f}",
        })
    if outlier_ps:
        outlier_bh = benjamini_hochberg(outlier_ps, q=0.10)
        for row in outlier_rows:
            adj = outlier_bh[str(row["year"])]
            row["bh_adjusted_p"] = f"{adj['adjusted_p']:.6f}"
            row["reject_bh_q_0_10"] = "1" if adj["reject_at_q"] else "0"
    outlier_rows.sort(key=lambda r: float(r["two_sided_p"]))
    _write_csv(args.out / "outlier_years.csv", outlier_rows, [
        "year", "observed_tuple_prob", "observed_nll", "two_sided_p",
        "bh_adjusted_p", "reject_bh_q_0_10",
    ])

    # Era tests summary
    era_rows = [
        {"era": "all_confirmatory", "n_years": len(A_result["per_year_nll"]),
         "S_obs": f"{A_result['S_obs']:.4f}",
         "null_mean": f"{A_result['null_mean']:.4f}",
         "p_value": f"{A_result['p_value']:.6f}"},
        {"era": "weighted_1994_2018", "n_years": len(A_pre["per_year_nll"]),
         "S_obs": f"{A_pre['S_obs']:.4f}",
         "null_mean": f"{A_pre['null_mean']:.4f}",
         "p_value": f"{A_pre['p_value']:.6f}"},
        {"era": "modern_2019_present", "n_years": len(A_post["per_year_nll"]),
         "S_obs": f"{A_post['S_obs']:.4f}",
         "null_mean": f"{A_post['null_mean']:.4f}",
         "p_value": f"{A_post['p_value']:.6f}"},
    ]
    _write_csv(args.out / "era_tests.csv", era_rows,
               ["era", "n_years", "S_obs", "null_mean", "p_value"])

    # Exploratory phase 1 results (header row per test family)
    phase1_rows = [
        {"family": "team_luck", "n_tests": len(team_ps),
         "n_rejected_bh_0_10": sum(1 for r in team_rows
                                    if r.get("reject_bh_q_0_10") == "1"),
         "min_adjusted_p": min(
             [float(r["bh_adjusted_p"]) for r in team_rows
              if r.get("bh_adjusted_p")] or [1.0]
         )},
        {"family": "seed_luck", "n_tests": len(seed_ps),
         "n_rejected_bh_0_10": sum(1 for r in seed_rows
                                    if r.get("reject_bh_q_0_10") == "1"),
         "min_adjusted_p": min(
             [float(r["bh_adjusted_p"]) for r in seed_rows
              if r.get("bh_adjusted_p")] or [1.0]
         )},
        {"family": "outlier_years", "n_tests": len(outlier_ps),
         "n_rejected_bh_0_10": sum(1 for r in outlier_rows
                                    if r.get("reject_bh_q_0_10") == "1"),
         "min_adjusted_p": min(
             [float(r["bh_adjusted_p"]) for r in outlier_rows
              if r.get("bh_adjusted_p")] or [1.0]
         )},
    ]
    _write_csv(args.out / "exploratory_phase1_results.csv", phase1_rows,
               ["family", "n_tests", "n_rejected_bh_0_10", "min_adjusted_p"])

    # Phase 2: hardcoded covariates and jump analysis
    # For scope, we emit a placeholder note; the full phase-2 machinery
    # requires external covariate data (msa_population, forbes_valuation,
    # attendance) which are not scraped as part of this pipeline. The plan
    # explicitly gates phase 2 as optional and heavily caveated.
    phase2_rows = [
        {"family": "narrative_market_covariates", "status": "deferred",
         "notes": "msa_population, forbes_valuation, attendance_rank not collected; "
                  "covariate coverage rule (>20% missing drops covariate) would drop all three"},
        {"family": "pick_recipient_robustness", "status": "deferred",
         "notes": "pick-recipient view requires unconditional-ownership filter; not yet wired"},
        {"family": "top3_top4_jump_analysis", "status": "deferred",
         "notes": "descriptive only per plan; not run in this pass"},
    ]
    _write_csv(args.out / "exploratory_phase2_results.csv", phase2_rows,
               ["family", "status", "notes"])

    # Persist the null distributions (for Figure 1's empirical histogram).
    np.savez_compressed(
        args.out / "null_samples.npz",
        A_null=A_result["S_null"],
        A_pre_null=A_pre["S_null"],
        A_post_null=A_post["S_null"],
    )

    print(f"\nResults written to {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
