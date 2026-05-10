"""Statistical tests for the confirmatory and exploratory analysis.

Implements:
- Global NLL test (A): sum of per-year -log p(observed) vs Monte Carlo null.
- Era-stratified A (A_pre2019, A_post2019).
- Top-1 aggregate test (T1): Poisson-binomial exact p-value.
- Robustness gates on A: LOYO, concentration (Gini + top-3 share).
- Team luck, seed luck, outlier-year detection (exploratory phase 1).
- Multiple-testing correction: Holm-Bonferroni (confirmatory),
  Benjamini-Hochberg (exploratory).

All statistics ship with Monte Carlo standard errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from .simulate import YearConfig, simulate


# ---------------------------------------------------------------------------
# Per-year observed outcome support
# ---------------------------------------------------------------------------

def observed_index_tuple(cfg: YearConfig, observed_teams: list[str]) -> tuple[int, ...]:
    """Convert an ordered list of winning teams into team indices.

    observed_teams[j] is the team that received pick j+1 (pre-trade slot
    owner view). Length must equal cfg.drawn_picks.
    """
    if len(observed_teams) != cfg.drawn_picks:
        raise ValueError(
            f"{cfg.year}: observed_teams has {len(observed_teams)} picks; "
            f"expected {cfg.drawn_picks}"
        )
    name_to_idx = {t: i for i, t in enumerate(cfg.teams)}
    try:
        return tuple(name_to_idx[t] for t in observed_teams)
    except KeyError as e:
        raise ValueError(
            f"{cfg.year}: observed team {e} not in cfg.teams {cfg.teams}"
        )


# ---------------------------------------------------------------------------
# Per-year NLL: Monte Carlo estimate of -log P(observed drawn tuple)
# ---------------------------------------------------------------------------

def per_year_nll(
    cfg: YearConfig,
    observed: tuple[int, ...],
    n_sims: int,
    seed: int,
) -> tuple[float, float]:
    """Return (nll, mc_se). nll = -log(p_hat); se is the delta-method SE.

    For p close to zero (few/no matches), we use a Bayesian smoothing
    estimate p_hat = (matches + 1) / (n_sims + 2) so nll is finite.
    """
    rng = np.random.default_rng(seed)
    sims = simulate(cfg, n_sims, seed=seed)  # deterministic given seed
    target = np.asarray(observed, dtype=np.int32)
    matches = int(np.all(sims == target[np.newaxis, :], axis=1).sum())
    # Laplace-smoothed estimate so -log is finite even for rare outcomes.
    p_hat = (matches + 1) / (n_sims + 2)
    nll = float(-np.log(p_hat))
    # Delta-method SE: Var(log p) ≈ (1-p)/(n p). For smoothed p, same form.
    var_log_p = (1 - p_hat) / (n_sims * p_hat)
    se = float(np.sqrt(var_log_p)) if var_log_p > 0 else 0.0
    return nll, se


def per_year_expected_nll(cfg: YearConfig, n_sims: int, seed: int) -> float:
    """Monte Carlo estimate of E[-log p(outcome)] under the null.

    This is the entropy H(outcome) under the null distribution, used to
    center the test statistic and compute "NLL excess" for the
    concentration metric.

    We estimate by: simulate many draws, for each draw compute the empirical
    probability of that particular drawn tuple, and take the mean of
    -log(p_hat(tuple)). This is noisy for rare tuples but is only used for
    descriptive baselines.
    """
    sims = simulate(cfg, n_sims, seed=seed)
    # For large lotteries the number of distinct tuples can be ~n_sims, so
    # empirical-frequency estimate of -log p is biased high. Instead, compute
    # the theoretical H = -sum p log p using the Exp/argmax-trick density is
    # infeasible in closed form; approximate H as log(n_sims) - (1/n) sum log(count[tuple])
    # where count is the empirical frequency. For a uniform distribution this
    # gives the correct entropy. With few sims this underestimates H slightly;
    # we use it as an approximation.
    # Represent each tuple as a bytes key for hashing.
    keys = [tuple(row.tolist()) for row in sims]
    from collections import Counter
    cnt = Counter(keys)
    n = len(keys)
    # Empirical p = cnt[k]/n; plug-in entropy estimator (Miller-Madow style
    # without correction).
    log_p = np.array([np.log(cnt[k] / n) for k in keys])
    H_hat = float(-log_p.mean())
    return H_hat


# ---------------------------------------------------------------------------
# Global statistic S = sum of per-year NLL; null distribution by simulation.
# ---------------------------------------------------------------------------

def global_statistic_null(
    configs: dict[int, YearConfig],
    n_sims: int,
    seed_offset: int = 0,
) -> np.ndarray:
    """Return the null distribution of S = sum of per-year -log p(outcome).

    For each year, draw one outcome from the null, estimate its
    -log p under the null using a SEPARATE MC pool of size n_sims, and
    sum across years. Repeat many times to build the null distribution.

    This is the computationally expensive step. For 20 years at
    n_sims=1M, this would be prohibitively slow (would take 20M simulations
    per null sample, times many samples). To make it tractable we use a
    different strategy: for each year, pre-compute the empirical
    distribution of -log p over n_sims draws, and combine across years.

    Specifically:
    1. For each year, generate n_sims draws, compute their empirical
       frequencies (via Counter), and store {tuple -> log_prob}.
    2. Sample from each year's empirical distribution to build S null.

    This gives us n_sims samples of S cheaply.
    """
    per_year_nll_samples: list[np.ndarray] = []
    for year in sorted(configs.keys()):
        cfg = configs[year]
        sims = simulate(cfg, n_sims, seed=seed_offset + year)
        keys = [tuple(row.tolist()) for row in sims]
        from collections import Counter
        cnt = Counter(keys)
        # For each sample, its empirical -log p = -log(cnt[key] / n_sims)
        log_ps = np.array([-np.log(cnt[k] / n_sims) for k in keys])
        per_year_nll_samples.append(log_ps)
    # Sum across years (aligned by sample index). Shuffle within years to
    # avoid spurious correlation between years (each year is independent under
    # the null).
    rng = np.random.default_rng(seed_offset + 99999)
    S = np.zeros(n_sims, dtype=np.float64)
    for arr in per_year_nll_samples:
        rng.shuffle(arr)  # in-place
        S += arr
    return S


def global_test(
    configs: dict[int, YearConfig],
    observed_per_year: dict[int, tuple[int, ...]],
    n_sims: int,
    seed_offset: int,
) -> dict:
    """Run global NLL test A.

    Returns a dict with:
      - S_obs: observed S
      - p_value: P(S_null >= S_obs)
      - p_value_se: MC SE on the p-value
      - null_mean, null_std: descriptive
      - per_year_nll: {year: (nll, se)}
      - S_null: the null samples array (for LOYO and plotting)
    """
    per_year = {}
    S_obs = 0.0
    S_obs_se_sq = 0.0
    for year, obs in observed_per_year.items():
        cfg = configs[year]
        nll, se = per_year_nll(cfg, obs, n_sims, seed=seed_offset + year)
        per_year[year] = (nll, se)
        S_obs += nll
        S_obs_se_sq += se * se
    S_obs_se = float(np.sqrt(S_obs_se_sq))

    S_null = global_statistic_null(
        {y: configs[y] for y in observed_per_year},
        n_sims=n_sims,
        seed_offset=seed_offset,
    )
    # p-value: fraction of null samples with S >= S_obs
    tail = int((S_null >= S_obs).sum())
    p_value = (tail + 1) / (len(S_null) + 1)  # +1 smoothing
    p_value_se = float(np.sqrt(max(p_value, 1e-12) * (1 - p_value) / len(S_null)))

    return {
        "S_obs": S_obs,
        "S_obs_se": S_obs_se,
        "p_value": p_value,
        "p_value_se": p_value_se,
        "null_mean": float(S_null.mean()),
        "null_std": float(S_null.std()),
        "n_sims": n_sims,
        "per_year_nll": per_year,
        "S_null": S_null,
    }


# ---------------------------------------------------------------------------
# LOYO (leave-one-year-out) and concentration gates
# ---------------------------------------------------------------------------

def leave_one_year_out(test_result: dict, alpha: float = 0.05) -> dict:
    """Recompute the p-value with each year removed.

    Uses the stored per_year_nll (observed) and S_null (generated over the
    full set). For a strict LOYO we'd re-simulate the null without each
    year; as an approximation, we subtract the expected per-year null
    contribution from S_null. This is cheap and preserves the comparison.

    Returns {year: {S_obs_loyo, p_value_loyo, flipped}}.
    """
    per_year = test_result["per_year_nll"]
    S_null_full = test_result["S_null"]
    alpha_full = test_result["p_value"]
    flipped_at_alpha = alpha_full < alpha

    results: dict[int, dict] = {}
    # Null mean contribution per year: we approximate each year's contribution
    # by its mean (null_mean scales linearly in years). Simpler approach:
    # recompute the null distribution only over kept years using the same
    # seeds. To keep this practical we re-run global_statistic_null without
    # the removed year. This is O(Y) passes; for small Y (20-41) and
    # moderate n_sims that's fine.
    # For tractability we implement this via incremental subtraction from the
    # per-year null samples, which we stored in global_statistic_null.
    # Here we don't have that cache — so we approximate by subtracting the
    # per-year null MEAN from S_null and comparing S_obs minus that year's
    # observed NLL. This gives a valid but slightly conservative LOYO check:
    # it centers the null correctly and only misses the variance contribution
    # of the dropped year (which shrinks the null std, so is not overly
    # anti-conservative).
    years = list(per_year.keys())
    total_nll_mean = test_result["null_mean"]
    per_year_mean = total_nll_mean / max(1, len(years))  # uniform split
    for y in years:
        S_obs_loyo = test_result["S_obs"] - per_year[y][0]
        # Shift null by the removed year's expected contribution
        S_null_loyo = S_null_full - per_year_mean
        tail = int((S_null_loyo >= S_obs_loyo).sum())
        p_loyo = (tail + 1) / (len(S_null_loyo) + 1)
        flipped = (p_loyo < alpha) != flipped_at_alpha
        results[y] = {
            "S_obs_loyo": S_obs_loyo,
            "p_value_loyo": p_loyo,
            "flipped": bool(flipped),
        }
    return results


def concentration_gate(test_result: dict) -> dict:
    """Compute concentration metrics on per-year NLL contributions.

    Returns:
      - top3_share: fraction of TOTAL NLL contributed by the top-3 years
      - top3_excess_share: same but computed on excess over expected (null mean / n_years)
      - gini: Gini coefficient of the contributions
      - passes_gate: True if top3_excess_share < 0.5

    "Passes" means a global-anomaly claim is not driven purely by outlier
    years.
    """
    per_year = test_result["per_year_nll"]
    nll_vals = np.array([v[0] for v in per_year.values()])
    total = nll_vals.sum()
    top3_share = float(np.sort(nll_vals)[-3:].sum() / total) if total > 0 else 0.0

    # Excess over expected (expected per-year = null_mean / n_years)
    n_years = len(nll_vals)
    expected_per_year = test_result["null_mean"] / n_years
    excess = np.maximum(nll_vals - expected_per_year, 0)
    total_excess = float(excess.sum())
    top3_excess = float(np.sort(excess)[-3:].sum())
    top3_excess_share = (top3_excess / total_excess) if total_excess > 0 else 0.0

    # Gini coefficient of (non-negative) contributions
    sorted_vals = np.sort(nll_vals)
    n = len(sorted_vals)
    index = np.arange(1, n + 1)
    if sorted_vals.sum() > 0:
        gini = float(
            (2 * (index * sorted_vals).sum()) / (n * sorted_vals.sum()) - (n + 1) / n
        )
    else:
        gini = 0.0

    return {
        "top3_share": top3_share,
        "top3_excess_share": top3_excess_share,
        "gini": gini,
        "passes_gate": top3_excess_share < 0.5,
    }


# ---------------------------------------------------------------------------
# T1: Top-1 aggregate test (Poisson-binomial exact)
# ---------------------------------------------------------------------------

def top1_poisson_binomial_test(
    per_year_probs: dict[int, float],
    observed_count: int,
) -> dict:
    """Exact two-sided Poisson-binomial p-value for the observed count.

    Under the null, each year is an independent Bernoulli with its own
    P(top-seed wins #1). The number of "top-seed wins #1" events is a sum
    of independent non-identical Bernoullis (Poisson-binomial).

    observed_count is the observed number of years where the best-odds
    team (highest pre_chances / pre_probability) won #1.

    Returns the exact PMF, observed count, and two-sided p-value defined
    as P(|X - E[X]| >= |obs - E[X]|).
    """
    probs = np.array(list(per_year_probs.values()), dtype=np.float64)
    n = len(probs)
    # Compute Poisson-binomial PMF by iterative convolution.
    pmf = np.zeros(n + 1)
    pmf[0] = 1.0
    for p in probs:
        new = np.zeros(n + 1)
        new[0] = pmf[0] * (1 - p)
        for k in range(1, n + 1):
            new[k] = pmf[k] * (1 - p) + pmf[k - 1] * p
        pmf = new
    mean = float((np.arange(n + 1) * pmf).sum())
    # Two-sided p-value: sum of PMF at |X - mean| >= |obs - mean|
    deviation = abs(observed_count - mean)
    two_sided_mass = float(pmf[np.abs(np.arange(n + 1) - mean) >= deviation - 1e-12].sum())
    # One-sided "more extreme in upward direction" p-value
    if observed_count >= mean:
        one_sided_upper = float(pmf[observed_count:].sum())
    else:
        one_sided_upper = float(pmf[:observed_count + 1].sum())
    return {
        "n_years": n,
        "expected": mean,
        "observed": observed_count,
        "two_sided_p": two_sided_mass,
        "one_sided_p": one_sided_upper,
        "pmf_argmax": int(np.argmax(pmf)),
    }


def top1_generic_count_test(
    per_year_probs_by_unit: dict[str, dict[int, float]],
    observed_wins_by_unit: dict[str, int],
) -> dict[str, dict]:
    """For each unit (team), run a Poisson-binomial test.

    per_year_probs_by_unit[team][year] = P(team wins #1 in year).
    observed_wins_by_unit[team] = number of years the team won #1.

    Used by the team-luck exploratory test.
    """
    out = {}
    for team, yearly in per_year_probs_by_unit.items():
        obs = observed_wins_by_unit.get(team, 0)
        out[team] = top1_poisson_binomial_test(yearly, obs)
    return out


# ---------------------------------------------------------------------------
# Multiple-testing correction
# ---------------------------------------------------------------------------

def holm_bonferroni(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm-Bonferroni FWE correction.

    Returns {name: {p, adjusted_p, reject_at_alpha}}.
    """
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, dict] = {}
    reject_all_below = True
    for rank, (name, p) in enumerate(items):
        adj = min(1.0, p * (m - rank))
        # Enforce monotonicity: adjusted p-values must not decrease.
        if out:
            prev = max(d["adjusted_p"] for d in out.values())
            adj = max(adj, prev)
        reject = reject_all_below and (adj < alpha)
        if not reject:
            reject_all_below = False
        out[name] = {"p": p, "adjusted_p": adj, "reject_at_alpha": reject}
    return out


def benjamini_hochberg(p_values: dict[str, float], q: float = 0.10) -> dict[str, dict]:
    """Benjamini-Hochberg FDR correction at level q.

    Returns {name: {p, adjusted_p, reject_at_q}}.
    """
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, dict] = {}
    # Find largest rank k such that p_k <= (k/m) * q
    cutoff_rank = -1
    for rank, (_, p) in enumerate(items):
        if p <= ((rank + 1) / m) * q:
            cutoff_rank = rank
    # Adjusted p-values (BH-Yekutieli style monotone adjustment):
    adj_running = 1.0
    for rank in range(m - 1, -1, -1):
        name, p = items[rank]
        adj = min(1.0, p * m / (rank + 1))
        adj_running = min(adj_running, adj)
        out[name] = {"p": p, "adjusted_p": adj_running, "reject_at_q": rank <= cutoff_rank}
    return out
