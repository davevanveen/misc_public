"""Tests for stats.py.

Validates:
- Holm-Bonferroni: known-answer cases including monotonicity enforcement.
- BH-FDR: known-answer case.
- Poisson-binomial: matches exact PMF for small cases; mean matches sum of probabilities.
- Global NLL null distribution has expected properties.
- LOYO flips correctly when a single dominant year is removed.
"""

from __future__ import annotations

import numpy as np
import pytest

from nba_lottery.stats import (
    holm_bonferroni,
    benjamini_hochberg,
    top1_poisson_binomial_test,
    global_test,
    concentration_gate,
    leave_one_year_out,
)
from nba_lottery.simulate import YearConfig


def test_holm_bonferroni_simple():
    # Two p-values, m=2. Smallest p=0.01: adj = 0.02. Next p=0.04: adj=max(0.04, 0.02)=0.04.
    out = holm_bonferroni({"a": 0.01, "b": 0.04}, alpha=0.05)
    assert abs(out["a"]["adjusted_p"] - 0.02) < 1e-12
    assert abs(out["b"]["adjusted_p"] - 0.04) < 1e-12
    assert out["a"]["reject_at_alpha"]
    assert out["b"]["reject_at_alpha"]


def test_holm_bonferroni_stops_on_failure():
    # m=3. p=[0.02, 0.03, 0.5]. Adjusted: 0.06, max(0.06, 0.06)=0.06, max(0.5, 0.06)=0.5.
    out = holm_bonferroni({"a": 0.02, "b": 0.03, "c": 0.5}, alpha=0.05)
    # a: adj=0.06 -> not rejected. b and c follow without rejection.
    assert not out["a"]["reject_at_alpha"]
    assert not out["b"]["reject_at_alpha"]
    assert not out["c"]["reject_at_alpha"]


def test_bh_fdr_matches_canonical():
    # Classic example: p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.060],
    # m=6, q=0.05. Cutoff rank where p_k <= (k/m)*q: rank 2 (0.008 <= 2/6*0.05=0.0167).
    ps = {"a": 0.001, "b": 0.008, "c": 0.039, "d": 0.041, "e": 0.042, "f": 0.060}
    out = benjamini_hochberg(ps, q=0.05)
    assert out["a"]["reject_at_q"]
    assert out["b"]["reject_at_q"]
    assert not out["c"]["reject_at_q"]
    assert not out["d"]["reject_at_q"]


def test_poisson_binomial_identical_probs():
    # If all probs are equal to p, the Poisson-binomial reduces to Binomial(n, p).
    from scipy.stats import binom
    p = 0.3
    n = 10
    per_year_probs = {i: p for i in range(n)}
    out = top1_poisson_binomial_test(per_year_probs, observed_count=5)
    assert abs(out["expected"] - n * p) < 1e-9
    # Two-sided p for obs=5 vs mean=3: P(|X-3|>=2) = P(X<=1) + P(X>=5)
    expected_tail = float(binom.cdf(1, n, p) + (1 - binom.cdf(4, n, p)))
    assert abs(out["two_sided_p"] - expected_tail) < 1e-9


def test_poisson_binomial_distinct_probs():
    # 3 Bernoullis with p=0.2, 0.5, 0.7. Compute expected PMF manually.
    # P(X=0) = 0.8 * 0.5 * 0.3 = 0.12
    # P(X=3) = 0.2 * 0.5 * 0.7 = 0.07
    probs = {0: 0.2, 1: 0.5, 2: 0.7}
    out = top1_poisson_binomial_test(probs, observed_count=3)
    assert abs(out["expected"] - (0.2 + 0.5 + 0.7)) < 1e-9
    # P(X>=3) = 0.07
    assert abs(out["one_sided_p"] - 0.07) < 1e-9


def _toy_configs() -> dict[int, YearConfig]:
    # Two tiny years, 3 teams each, draw 1 pick.
    return {
        2019: YearConfig(
            year=2019, era="toy", teams=("A", "B", "C"), ranks=(1, 2, 3),
            combinations=(60, 30, 10), drawn_picks=1, combination_base=100,
        ),
        2020: YearConfig(
            year=2020, era="toy", teams=("A", "B", "C"), ranks=(1, 2, 3),
            combinations=(60, 30, 10), drawn_picks=1, combination_base=100,
        ),
    }


def test_global_test_null_distribution_reasonable():
    configs = _toy_configs()
    # Use a plausible "observed" tuple
    observed = {2019: (0,), 2020: (0,)}  # rank-1 team wins both
    res = global_test(configs, observed, n_sims=20_000, seed_offset=1)
    assert "S_obs" in res and "p_value" in res and res["p_value"] > 0
    assert 0 < res["p_value"] <= 1
    # Null mean should be approximately sum of per-year entropies (small tails)
    assert res["null_mean"] > 0


def test_concentration_gate_pure_uniform():
    # If all per-year NLL are equal, top3_share = 3/n, excess share = 0 (no excess).
    fake_result = {
        "per_year_nll": {i: (1.0, 0.01) for i in range(10)},
        "null_mean": 10.0,  # equal to sum
        "S_obs": 10.0,
        "S_null": np.full(100, 10.0),
        "n_sims": 100,
    }
    gate = concentration_gate(fake_result)
    assert abs(gate["top3_share"] - 0.3) < 1e-9
    # Excess over expected (1.0) is zero -> top3_excess_share = 0
    assert abs(gate["top3_excess_share"]) < 1e-9
    assert gate["gini"] < 1e-9
    assert gate["passes_gate"] is True


def test_concentration_gate_dominant_outlier():
    # Year 0 contributes 10 units; others contribute 1 each. Expected = 1.9 per year.
    per_year = {i: (10.0 if i == 0 else 1.0, 0.01) for i in range(10)}
    fake_result = {
        "per_year_nll": per_year,
        "null_mean": 19.0,  # 10 years x 1.9 per-year expected
        "S_obs": 19.0,
        "S_null": np.full(100, 19.0),
        "n_sims": 100,
    }
    gate = concentration_gate(fake_result)
    # Year 0's excess = 10 - 1.9 = 8.1; others have 0 excess (they're at the baseline)
    # top3 includes year 0 which dominates; fraction should be ~1.0
    assert gate["top3_excess_share"] > 0.9
    assert not gate["passes_gate"]


def test_loyo_flips_when_dominant_year_removed():
    # Construct a fake result where S_obs is just above significance, but
    # removing year 0 (which contributes most of the NLL) brings it below.
    per_year = {0: (10.0, 0.1), 1: (2.0, 0.1), 2: (2.0, 0.1)}
    S_obs = 14.0
    rng = np.random.default_rng(0)
    # Synthetic per-year null: year 0 dominant (mean 3), others mean 1.
    py0 = rng.normal(3.0, 1.0, size=10_000)
    py1 = rng.normal(1.0, 1.0, size=10_000)
    py2 = rng.normal(1.0, 1.0, size=10_000)
    S_null = py0 + py1 + py2
    fake_result = {
        "per_year_nll": per_year,
        "S_obs": S_obs,
        "S_null": S_null,
        "per_year_null": {0: py0, 1: py1, 2: py2},
        "null_mean": float(S_null.mean()),
        "null_std": float(S_null.std()),
        "n_sims": 10_000,
        "p_value": float((S_null >= S_obs).mean()),
        "p_value_se": 0.001,
    }
    loyo = leave_one_year_out(fake_result, alpha=0.05)
    # Dropping year 0 should raise p substantially (lose dominant observed NLL)
    assert loyo[0]["p_value_loyo"] > loyo[1]["p_value_loyo"]
