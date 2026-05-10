"""Data workstream: ingest, build probability matrix, provenance tracking.

This module encodes the canonical NBA draft lottery history in structured form.
Values are transcribed from well-documented public sources (NBA.com historical
archives, Basketball-Reference, RealGM); per-row source citations live in
`data/processed/source_audit.csv`.

Design notes:
- We operate at the (year, team) granularity. Each year has a lottery with
  N teams, each assigned an integer number of ping-pong-ball combinations
  (weighted era) or uniform probability (envelope era 1985-89).
- The "pre-trade slot owner" is the team whose regular-season record generated
  the odds. This is what we model, not pick-recipient-after-trades.
- Era-specific combination bases: 1990-1993 used 66 combinations; 1994-present
  uses 1,000 combinations (the 14-ball system).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Era:
    name: str
    year_start: int
    year_end: int
    combination_base: int | None  # None for envelope era (no integer combos)
    drawn_picks: int  # number of picks determined by the drawing
    description: str


ERAS: tuple[Era, ...] = (
    Era(
        name="envelope_1985_1989",
        year_start=1985,
        year_end=1989,
        combination_base=None,
        drawn_picks=7,  # all lottery positions were drawn; no weighted odds
        description=(
            "Envelope-draw era. Equal odds among lottery teams for their full "
            "draft order. Exact official joint probabilities for intermediate "
            "picks are coarser than in later eras."
        ),
    ),
    Era(
        name="weighted_1990_1993",
        year_start=1990,
        year_end=1993,
        combination_base=66,
        drawn_picks=3,
        description=(
            "Weighted-ball era using 66 combinations. Top 3 picks drawn; "
            "remainder fall by inverse record order."
        ),
    ),
    Era(
        name="weighted_1994_2018",
        year_start=1994,
        year_end=2018,
        combination_base=1000,
        drawn_picks=3,
        description=(
            "Weighted 14-ball system with 1,000 combinations. Top 3 picks "
            "drawn; remainder fall by inverse record order."
        ),
    ),
    Era(
        name="modern_2019_present",
        year_start=2019,
        year_end=9999,
        combination_base=1000,
        drawn_picks=4,
        description=(
            "Modern weighted system with flattened top-3 odds (14.0/14.0/14.0). "
            "Top 4 picks drawn; remainder fall by inverse record order."
        ),
    ),
)


def era_for_year(year: int) -> Era:
    for era in ERAS:
        if era.year_start <= year <= era.year_end:
            return era
    raise ValueError(f"No era for year {year}")


# ---------------------------------------------------------------------------
# Canonical odds tables (pre-lottery-rank -> combinations, by era)
# ---------------------------------------------------------------------------
# Source: NBA.com historical lottery archives cross-checked with
# Basketball-Reference. These are the *published* combinations per
# pre-lottery rank (seed 1 = worst record). Per-year ties modify these
# via the N-way tie-breaker procedure; ties are applied in `build_year_odds`.
#
# 1990-1993: 66 combinations total, allocated by record rank.
# 1994-2018: 1,000 combinations total; schedule changed in 1994, 1995, 2005.
# 2019+: 1,000 combinations with flattened top-3 (14/14/14/12.5/10.5/9/7.5/6/4.5/3/2/1.5/1/0.5).

# Combinations by pre-lottery rank for each sub-regime.
# Rank 1 is the worst team (most combinations).

ODDS_1990_1993 = {
    # 66 combinations total; 1990-1993 "weighted" era.
    # Per NBA records: rank 1 gets 11 combos, rank 2 gets 10, ... rank 11 gets 1.
    # Sum: 11+10+9+8+7+6+5+4+3+2+1 = 66.
    1: 11, 2: 10, 3: 9, 4: 8, 5: 7, 6: 6, 7: 5, 8: 4, 9: 3, 10: 2, 11: 1,
}

# NOTE: 1994-2004 used a 13-team lottery with a different combination schedule
# than 2005-2018. The exact integer allocation for that sub-regime is not
# encoded here pending primary-source verification and is marked
# confirmatory-ineligible by the feasibility report.
ODDS_1994_2004: dict[int, int] = {}  # intentionally empty; see feasibility_report.md

ODDS_2005_2018 = {
    # 1,000 combinations; 14 lottery teams from 2004-05 onward.
    # Standard schedule.
    1: 250, 2: 199, 3: 156, 4: 119, 5: 88, 6: 63, 7: 43, 8: 28,
    9: 17, 10: 11, 11: 8, 12: 7, 13: 6, 14: 5,
}

ODDS_2019_PRESENT = {
    # 2019+ flattened odds.
    1: 140, 2: 140, 3: 140, 4: 125, 5: 105, 6: 90, 7: 75, 8: 60,
    9: 45, 10: 30, 11: 20, 12: 15, 13: 10, 14: 5,
}


def canonical_odds_for_year(year: int) -> dict[int, int]:
    """Return {pre-lottery rank: combinations} for the given year.

    For the envelope era, raises ValueError (no combinations).
    """
    era = era_for_year(year)
    if era.name == "envelope_1985_1989":
        raise ValueError(
            f"Year {year} is envelope-era; use uniform odds over participants."
        )
    if era.name == "weighted_1990_1993":
        return dict(ODDS_1990_1993)
    if era.name == "weighted_1994_2018":
        if year <= 2004:
            raise ValueError(
                f"Year {year} (13-team lottery, 1994-2004) is not "
                "confirmatory-eligible: exact integer combination schedule "
                "pending primary-source verification. See feasibility_report.md."
            )
        return dict(ODDS_2005_2018)
    if era.name == "modern_2019_present":
        return dict(ODDS_2019_PRESENT)
    raise ValueError(f"Unknown era {era.name}")


def odds_sum(year: int) -> int:
    return sum(canonical_odds_for_year(year).values())


# ---------------------------------------------------------------------------
# Rule regimes frame
# ---------------------------------------------------------------------------

def rule_regimes_rows() -> list[dict]:
    """Return rows for data/processed/rule_regimes.csv."""
    return [
        {
            "era": era.name,
            "year_start": era.year_start,
            "year_end": era.year_end,
            "combination_base": era.combination_base if era.combination_base else "",
            "drawn_picks": era.drawn_picks,
            "description": era.description,
        }
        for era in ERAS
    ]


# ---------------------------------------------------------------------------
# Helpers used by the dataset builder and simulators
# ---------------------------------------------------------------------------

def apply_n_way_tie(combinations: dict[int, int], ties: list[list[int]]) -> dict[int, int]:
    """Redistribute combinations across tied pre-lottery ranks.

    When teams tie in standings, their combined combination count is split
    evenly. Any remainder (due to indivisibility) is allocated by a pre-lottery
    N-way tie-breaker drawing; this helper returns the *deterministic* split
    (floor share to each tied team) and puts any remainder into the highest
    pre-lottery rank among the tied teams. For post-draw analysis, the
    remainder-resolution mode (documented vs simulated) is tracked separately
    by the caller.

    `ties` is a list of groups; each group is a list of pre-lottery ranks that
    share a record. Untied ranks are not modified.

    Example: two teams tied at ranks {3, 4} with canonical combos 156+119=275
    -> both get 137, and the remainder 1 goes to one via tie-breaker drawing.
    """
    out = dict(combinations)
    for group in ties:
        if len(group) < 2:
            continue
        pooled = sum(combinations[r] for r in group)
        floor = pooled // len(group)
        remainder = pooled - floor * len(group)
        # Deterministic fallback: remainder to the lowest numerical rank
        # (worst team among tied). Callers that know the documented tie-breaker
        # outcome should overwrite this or re-distribute.
        sorted_group = sorted(group)
        for r in group:
            out[r] = floor
        for i in range(remainder):
            out[sorted_group[i]] += 1
    return out


def data_dir(repo_root: Path | None = None) -> Path:
    """Return data/processed/ as a Path, relative to the repo root."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "data" / "processed"
