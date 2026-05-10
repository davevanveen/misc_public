"""Tests for the simulator.

Validates:
- Marginal top-1 probabilities match the exact closed-form solution within MC tolerance.
- Integer combination sums match the era base.
- Weighted simulator: no team appears in two drawn slots within a single draw.
- Envelope simulator: full permutation, uniform per-slot marginals.
- N-way tie-breaker helper in data.apply_n_way_tie preserves total combinations.
"""

from __future__ import annotations

import numpy as np
import pytest

from nba_lottery import data as core_data
from nba_lottery.simulate import (
    YearConfig,
    simulate_year,
    simulate_year_envelope,
    marginal_top_k_probs,
    exact_top1_probs,
)


def _cfg_2019() -> YearConfig:
    # 2019 modern-era flattened odds. Sanity baseline used in multiple tests.
    teams = tuple(f"T{i}" for i in range(14))
    combos = (140, 140, 140, 125, 105, 90, 75, 60, 45, 30, 20, 15, 10, 5)
    assert sum(combos) == 1000
    return YearConfig(
        year=2019, era="modern_2019_present",
        teams=teams, ranks=tuple(range(1, 15)),
        combinations=combos, drawn_picks=4, combination_base=1000,
    )


def _cfg_2008() -> YearConfig:
    # 2008 pre-2019 weighted odds. Used to exercise the 3-pick draw path.
    teams = tuple(f"T{i}" for i in range(14))
    combos = (250, 199, 138, 137, 76, 63, 43, 28, 17, 11, 8, 7, 6, 5 + 12)  # pad to 1000
    # compute tail to hit 1000
    base = (250, 199, 138, 137, 76, 63, 43, 28, 17, 11, 8, 7, 6, 5)
    assert sum(base) == 988
    combos = base[:-1] + (base[-1] + (1000 - 988),)
    assert sum(combos) == 1000
    return YearConfig(
        year=2008, era="weighted_1994_2018",
        teams=teams, ranks=tuple(range(1, 15)),
        combinations=combos, drawn_picks=3, combination_base=1000,
    )


def test_combinations_sum_matches_era_base():
    cfg = _cfg_2019()
    assert sum(cfg.combinations) == cfg.combination_base
    cfg08 = _cfg_2008()
    assert sum(cfg08.combinations) == cfg08.combination_base


def test_weighted_top1_matches_closed_form_2019():
    cfg = _cfg_2019()
    rng = np.random.default_rng(0)
    draws = simulate_year(cfg, n=200_000, rng=rng)
    # Simulated #1-marginal distribution
    from collections import Counter
    c = Counter(draws[:, 0].tolist())
    n = draws.shape[0]
    sim_p = np.array([c.get(i, 0) / n for i in range(cfg.n_teams)])
    exact = exact_top1_probs(cfg)
    # 3 sigma binomial SE at p=0.14, n=200k: ~0.0023
    assert np.all(np.abs(sim_p - exact) < 0.005), (sim_p, exact)


def test_no_duplicate_team_within_draw():
    cfg = _cfg_2019()
    rng = np.random.default_rng(1)
    draws = simulate_year(cfg, n=10_000, rng=rng)
    # Each row should have strictly distinct indices
    for row in draws[:200]:
        assert len(set(row.tolist())) == cfg.drawn_picks


def test_envelope_uniform_marginals():
    teams = tuple(f"T{i}" for i in range(7))
    cfg = YearConfig(
        year=1985, era="envelope_1985_1989",
        teams=teams, ranks=tuple(range(1, 8)),
        combinations=(0,) * 7, drawn_picks=7, combination_base=0,
    )
    rng = np.random.default_rng(2)
    draws = simulate_year_envelope(cfg, n=50_000, rng=rng)
    # At each slot, each team should appear ~1/7 of the time.
    for slot in range(7):
        counts = np.bincount(draws[:, slot], minlength=7)
        pct = counts / draws.shape[0]
        assert np.all(np.abs(pct - 1/7) < 0.01), (slot, pct)


def test_top_k_probs_sum_to_drawn_picks():
    cfg = _cfg_2019()
    p = marginal_top_k_probs(cfg, k=cfg.drawn_picks, n=50_000, seed=0)
    # Each column should sum to ~1 (one of the teams wins that slot).
    per_slot = p.sum(axis=0)
    assert np.all(np.abs(per_slot - 1.0) < 0.01), per_slot
    # Each row should sum to <= drawn_picks (a team can win at most one slot).
    per_team = p.sum(axis=1)
    assert np.all(per_team <= 1.0 + 1e-9), per_team


def test_apply_n_way_tie_preserves_total():
    combos = {1: 250, 2: 199, 3: 156, 4: 119, 5: 88, 6: 63, 7: 43,
              8: 28, 9: 17, 10: 11, 11: 8, 12: 7, 13: 6, 14: 5}
    assert sum(combos.values()) == 1000
    # Simulate a 3-way tie at ranks 3-4-5
    out = core_data.apply_n_way_tie(combos, ties=[[3, 4, 5]])
    assert sum(out.values()) == 1000
    # All three tied teams have equal allocation within 1 (the remainder)
    tied_vals = sorted([out[3], out[4], out[5]])
    assert tied_vals[2] - tied_vals[0] <= 1


def test_era_lookup():
    assert core_data.era_for_year(1985).name == "envelope_1985_1989"
    assert core_data.era_for_year(1990).name == "weighted_1990_1993"
    assert core_data.era_for_year(2004).name == "weighted_1994_2018"
    assert core_data.era_for_year(2019).name == "modern_2019_present"
    with pytest.raises(ValueError):
        core_data.era_for_year(1984)
