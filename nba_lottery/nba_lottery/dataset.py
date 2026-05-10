"""Build processed datasets from parsed lottery tables.

Produces four canonical CSVs in data/processed/:
    - lottery_team_year.csv        (per year, per team observations)
    - lottery_probability_matrix.csv  (per year, per team, per pick position)
    - rule_regimes.csv              (era metadata)
    - source_audit.csv              (per-field provenance)

The pre-trade lottery slot owner is the team identified in the Wikipedia
lottery table (i.e., the team whose record generated the odds). Wikipedia
footnotes via {{Cnote}} / {{Cref}} or {{refn}} indicate traded picks; we
capture those markers into `has_trade_protection_note` so that phase-2
pick-recipient analysis can filter them.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from . import data as core_data
from .fetch import fetch_years
from .parse import parse_lottery, LotteryTable


# ---------------------------------------------------------------------------
# Year -> rule regime
# ---------------------------------------------------------------------------

def build_year_range() -> list[int]:
    """All years we attempt to parse."""
    return list(range(1985, 2026))


def pre_lottery_rank(wins: int | None, losses: int | None, rows: list) -> dict[str, int]:
    """Assign pre-lottery rank (1 = worst record) based on win pct.

    Returns a dict team -> rank. Tied records share the lowest rank group
    (we only use rank for labeling; odds are recorded directly from the
    source table).
    """
    scored = []
    for i, r in enumerate(rows):
        if r.record_wins is None or r.record_losses is None:
            scored.append((i, None))
        else:
            games = r.record_wins + r.record_losses
            pct = r.record_wins / games if games else 0.0
            scored.append((i, pct))
    # Worst record = smallest win pct; sort ascending by pct, Nones last
    def key(x):
        i, pct = x
        return (pct if pct is not None else 99.0, i)
    ordered = sorted(scored, key=key)
    ranks = {}
    prev_pct = None
    current_rank = 0
    for i, (idx, pct) in enumerate(ordered):
        if pct != prev_pct:
            current_rank = i + 1
            prev_pct = pct
        ranks[idx] = current_rank
    return ranks


# ---------------------------------------------------------------------------
# Probability matrix: long format (year, team, pick_position, probability)
# ---------------------------------------------------------------------------

def probability_rows(table: LotteryTable) -> list[dict]:
    """Flatten a parsed lottery table into probability-matrix rows."""
    out = []
    for r in table.rows:
        for pos, prob in r.probabilities.items():
            out.append({
                "year": table.year,
                "team": r.team,
                "team_wikilink": r.team_wikilink,
                "pick_position": pos,
                "probability": prob,
            })
    return out


# ---------------------------------------------------------------------------
# Core team-year table
# ---------------------------------------------------------------------------

def team_year_rows(table: LotteryTable) -> list[dict]:
    """One row per (year, team). Primary output of the data workstream."""
    era = core_data.era_for_year(table.year)
    ranks = pre_lottery_rank(None, None, table.rows)
    out = []
    for idx, r in enumerate(table.rows):
        out.append({
            "year": table.year,
            "era": era.name,
            "team": r.team,
            "team_wikilink": r.team_wikilink,
            "record_wins": r.record_wins if r.record_wins is not None else "",
            "record_losses": r.record_losses if r.record_losses is not None else "",
            "pre_lottery_rank": ranks[idx],
            "combinations": r.combinations if r.combinations is not None else "",
            "won_pick_position": r.won_position if r.won_position is not None else "",
            "has_trade_protection_note": "1" if r.pick_note_refs else "0",
            "pick_note_refs": ",".join(r.pick_note_refs),
            "data_quality_flag": "clean" if not r.pick_note_refs else "resolved_ambiguity",
            "confirmatory_eligible": "1",  # subject to gate check below
        })
    return out


# ---------------------------------------------------------------------------
# Confirmatory eligibility gate
# ---------------------------------------------------------------------------

def apply_confirmatory_gate(
    rows_by_year: dict[int, list[dict]],
    tables_by_year: dict[int, LotteryTable],
) -> dict[int, list[dict]]:
    """Mark confirmatory_eligible=0 for years failing the plan's gate."""
    # Known data-quality issues discovered during validate_probabilities.
    # Exclude these years from the confirmatory set. Reasons are documented
    # in docs/feasibility_report.md.
    KNOWN_INELIGIBLE: dict[int, str] = {
        2003: (
            "published probabilities on Wikipedia disagree with exact "
            "Monte Carlo marginals across multiple teams (up to 46 sigma); "
            "likely a source transcription issue for the 13-team era"
        ),
    }

    out = {}
    for year, rows in rows_by_year.items():
        t = tables_by_year[year]
        era = core_data.era_for_year(year)

        # Fail reasons
        reasons = []
        if year in KNOWN_INELIGIBLE:
            reasons.append(KNOWN_INELIGIBLE[year])
        # Check 1: integer combination sum matches era base (weighted eras only)
        if era.combination_base is not None:
            combo_sum = sum(int(r["combinations"]) for r in rows if r["combinations"] != "")
            if combo_sum != era.combination_base:
                reasons.append(f"combinations sum {combo_sum} != expected {era.combination_base}")
        else:
            # Envelope era: cannot model exact joint probabilities from these sources
            reasons.append("envelope era: exact official joint probabilities not sourced")
        # Check 2: At least era.drawn_picks winners identified
        n_winners = sum(1 for r in rows if r["won_pick_position"] != "")
        if n_winners < era.drawn_picks:
            reasons.append(f"only {n_winners} winners identified; expected >= {era.drawn_picks}")
        # Check 3: Any parse warnings
        if t.parse_warnings:
            reasons.append(f"parse_warnings={len(t.parse_warnings)}")

        eligible = "1" if not reasons else "0"
        reason_str = "; ".join(reasons) if reasons else "ok"
        new_rows = []
        for r in rows:
            new_r = dict(r)
            new_r["confirmatory_eligible"] = eligible
            new_r["eligibility_reason"] = reason_str
            new_rows.append(new_r)
        out[year] = new_rows
    return out


# ---------------------------------------------------------------------------
# Source audit
# ---------------------------------------------------------------------------

def source_audit_rows(year: int, meta: dict) -> list[dict]:
    """Per-(year, field) provenance for critical confirmatory fields."""
    src = f"Wikipedia:{meta['page_title']} rev={meta.get('revid','')}"
    fetched = meta["fetch_timestamp"]
    classification = "secondary"  # Wikipedia; primary sources cited via refs
    fields = [
        "pre_lottery_rank",
        "record_wins",
        "record_losses",
        "combinations",
        "won_pick_position",
    ]
    return [
        {
            "year": year,
            "field": f,
            "source": src,
            "classification": classification,
            "fetched": fetched,
            "sha256": meta["sha256"],
            "notes": (
                "Wikipedia {year}_NBA_draft 'Draft lottery' section. Wikipedia "
                "is a secondary compilation that cites primary sources "
                "(NBA.com press releases, ESPN reports) via inline refs; "
                "those citations are preserved in data/raw/wiki/*.wikitext."
            ),
        }
        for f in fields
    ]


# ---------------------------------------------------------------------------
# Top-level build entry point
# ---------------------------------------------------------------------------

def build(raw_dir: Path, processed_dir: Path, years: list[int] | None = None,
          throttle_s: float = 1.5) -> dict:
    """Fetch, parse, and emit all processed CSVs.

    Returns a summary dict with counts per year.
    """
    if years is None:
        years = build_year_range()
    processed_dir.mkdir(parents=True, exist_ok=True)

    fetch_years(years, raw_dir, throttle_s=throttle_s)

    tables: dict[int, LotteryTable] = {}
    team_year: dict[int, list[dict]] = {}
    prob_rows: list[dict] = []
    source_rows: list[dict] = []
    import json as _json
    for y in years:
        wikitext_path = raw_dir / "wiki" / f"{y}_NBA_draft.wikitext"
        meta_path = raw_dir / "wiki" / f"{y}_NBA_draft.wikitext.meta.json"
        if not wikitext_path.exists():
            continue
        meta = _json.loads(meta_path.read_text())
        t = parse_lottery(y, wikitext_path.read_text())
        tables[y] = t
        if t.rows:
            team_year[y] = team_year_rows(t)
            prob_rows.extend(probability_rows(t))
            source_rows.extend(source_audit_rows(y, meta))

    # Apply confirmatory eligibility gate
    team_year = apply_confirmatory_gate(team_year, tables)

    # Write CSVs
    def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    flat_team_year = [r for y in sorted(team_year.keys()) for r in team_year[y]]
    if flat_team_year:
        ty_fields = [
            "year", "era", "team", "team_wikilink",
            "record_wins", "record_losses", "pre_lottery_rank",
            "combinations", "won_pick_position",
            "has_trade_protection_note", "pick_note_refs",
            "data_quality_flag", "confirmatory_eligible", "eligibility_reason",
        ]
        write_csv(processed_dir / "lottery_team_year.csv", flat_team_year, ty_fields)

    if prob_rows:
        pm_fields = ["year", "team", "team_wikilink", "pick_position", "probability"]
        write_csv(processed_dir / "lottery_probability_matrix.csv", prob_rows, pm_fields)

    # Rule regimes
    rr_rows = core_data.rule_regimes_rows()
    rr_fields = ["era", "year_start", "year_end", "combination_base",
                 "drawn_picks", "description"]
    write_csv(processed_dir / "rule_regimes.csv", rr_rows, rr_fields)

    # Source audit
    if source_rows:
        sa_fields = ["year", "field", "source", "classification", "fetched",
                     "sha256", "notes"]
        write_csv(processed_dir / "source_audit.csv", source_rows, sa_fields)

    summary = {
        "years_attempted": len(years),
        "years_with_data": len(team_year),
        "confirmatory_eligible_years": sum(
            1 for y, rows in team_year.items()
            if rows and rows[0]["confirmatory_eligible"] == "1"
        ),
        "total_team_year_rows": len(flat_team_year),
        "total_probability_rows": len(prob_rows),
    }
    return summary
