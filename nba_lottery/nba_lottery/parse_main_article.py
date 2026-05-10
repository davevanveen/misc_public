"""Parse the main NBA_draft_lottery Wikipedia article's 'Lottery winners' table.

This table lists the #1 pick winner for every year since the lottery began
(1985-present), with their pre-lottery record, number of combinations (or
envelope count), probability of winning #1, and the player selected.

It is the authoritative source for the `T1` aggregate-top-1 confirmatory
test over the full historical sample. The test requires only the per-year
winner's pre-lottery probability of winning #1, which this table provides.

Output rows:
    year            - int, the lottery year
    winner_team     - canonical team name (no trade annotations)
    winner_record   - "W-L"
    pre_chances     - int, ping-pong-ball combinations OR envelope count
    pre_probability - float, pre-lottery probability of winning #1
    player_selected - string
    had_trade_note  - 1 if the winner's pick had a trade-conveyance note

Trade annotations (e.g. "conveyed to the Cleveland Cavaliers") are captured
into `had_trade_note` for phase-2 pick-recipient robustness but the primary
estimand (pre-trade slot owner) is the winner_team field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WinnerRow:
    year: int
    winner_team: str
    winner_record_wins: int | None
    winner_record_losses: int | None
    pre_chances: int | None  # total combinations (or envelope count for 1985-89)
    pre_probability: float | None
    player_selected: str
    had_trade_note: bool


def _clean(s: str) -> str:
    """Strip refs, templates, HTML, and flatten wikilinks."""
    s = re.sub(r"<ref[^/]*?/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.DOTALL)
    # Recursively strip templates (flat, not nested-nested)
    while "{{" in s:
        new = re.sub(r"\{\{[^{}]*\}\}", "", s)
        if new == s:
            break
        s = new
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def parse_lottery_winners(wikitext: str) -> list[WinnerRow]:
    """Parse the 'Lottery winners' table from NBA_draft_lottery main article."""
    m = re.search(r"==\s*Lottery winners\s*==", wikitext)
    if not m:
        return []
    section = wikitext[m.end():]
    # Find first sortable wikitable in the section
    tstart = section.find('{|class="wikitable sortable"')
    if tstart < 0:
        tstart = section.find('{| class="wikitable sortable"')
    if tstart < 0:
        return []
    tend = section.find("\n|}", tstart)
    if tend < 0:
        return []
    table = section[tstart:tend + 3]

    rows: list[WinnerRow] = []
    blocks = re.split(r"\n\|-\n", table)
    for block in blocks[1:]:  # skip header/preamble
        cells = re.split(r"\n\|", block)
        cells = [c.lstrip("|").strip() for c in cells if c.strip()]
        if len(cells) < 5:
            continue

        year_s = _clean(cells[0])
        team_s = cells[1]  # raw; we want to detect trade note and link target
        record_s = _clean(cells[2])
        chances_s = _clean(cells[3])
        prob_s = _clean(cells[4])
        player_s = _clean(cells[5]) if len(cells) > 5 else ""

        ym = re.search(r"\d{4}", year_s)
        if not ym:
            continue
        year = int(ym.group(0))

        # Clean team cell: strip cell-attribute prefix, wikilinks, trade annotation
        team_clean = team_s
        # Remove 'align="x" | ' or 'style=... | ' attribute prefix
        if re.search(r'"\s*\|\s*', team_clean):
            team_clean = re.sub(r'^[^|]*"\s*\|\s*', "", team_clean)
        # Drop trailing |<whatever> if it leaked through
        team_clean = team_clean.split("|")[-1] if team_clean.startswith("|") else team_clean
        had_trade = bool(
            re.search(r"convey|trade|traded", team_clean, re.IGNORECASE)
            or "<small>" in team_clean
        )
        # Truncate at first <br>, <small>, or newline — that separates the
        # primary team from trade annotations
        team_primary = re.split(r"<br\s*/?>|<small>|\n", team_clean)[0]
        team = _clean(team_primary)
        # Handle leftover 'align="left"|' not caught above
        if team.startswith('align="') or 'align="' in team:
            m2 = re.search(r'"\s*\|\s*(.+)', team)
            if m2:
                team = m2.group(1).strip()
        team = team.strip()

        # Record
        rm = re.search(r"(\d+)\s*[–\-]\s*(\d+)", record_s)
        wins, losses = (int(rm.group(1)), int(rm.group(2))) if rm else (None, None)

        # Chances: first integer in the cell
        cm = re.search(r"(\d+)", chances_s)
        chances = int(cm.group(1)) if cm else None

        # Probability: percentage value
        pm = re.search(r"(\d+(?:\.\d+)?)\s*%", prob_s)
        probability = float(pm.group(1)) / 100.0 if pm else None

        rows.append(WinnerRow(
            year=year,
            winner_team=team,
            winner_record_wins=wins,
            winner_record_losses=losses,
            pre_chances=chances,
            pre_probability=probability,
            player_selected=player_s,
            had_trade_note=had_trade,
        ))
    return rows


def write_lottery_winners_csv(wikitext_path: Path, out_path: Path) -> int:
    """Parse and write to CSV. Returns row count."""
    import csv
    rows = parse_lottery_winners(wikitext_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "year", "winner_team", "winner_record_wins", "winner_record_losses",
        "pre_chances", "pre_probability", "player_selected", "had_trade_note",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "year": r.year,
                "winner_team": r.winner_team,
                "winner_record_wins": r.winner_record_wins or "",
                "winner_record_losses": r.winner_record_losses or "",
                "pre_chances": r.pre_chances or "",
                "pre_probability": r.pre_probability if r.pre_probability is not None else "",
                "player_selected": r.player_selected,
                "had_trade_note": "1" if r.had_trade_note else "0",
            })
    return len(rows)
