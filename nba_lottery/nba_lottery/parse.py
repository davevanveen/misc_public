"""Parse the lottery table from a Wikipedia {year}_NBA_draft wikitext.

The pages follow a consistent format for the 2005-present era:

    ==Draft lottery==
    {| class="wikitable plainrowheaders" style="text-align:center"
    |-
    ! ... header ...
    |-
    ! scope="row" style="text-align:left;" | [[Team Name]]
    | record || chances || p1 || p2 || ...
    |-
    ...
    |}

Actual lottery winners are marked with `style="background:#ff9"` on the cell
that corresponds to the pick position they won.

Earlier years (1985-2004) use less uniform formatting; for those we parse
what we can and surface gaps to the feasibility report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class LotteryRow:
    """One team's row in a lottery table."""
    team: str
    team_wikilink: str  # raw wikilink target, preserves redirects
    record_wins: int | None
    record_losses: int | None
    combinations: int | None  # lottery chances (integer combos)
    probabilities: dict[int, float]  # pick position -> probability
    won_position: int | None  # which pick position they actually received (if drawn); None if fell through
    pick_note_refs: list[str]  # any {{Cref|N}} footnote markers attached to the team
    raw_row: str  # original wikitext of the row


@dataclass
class LotteryTable:
    year: int
    rows: list[LotteryRow]
    notes: list[str]  # {{Cnote|N|text}} footnote bodies
    raw_section: str
    parse_warnings: list[str]


def _extract_draft_lottery_section(wikitext: str) -> str | None:
    """Return the content of the ==Draft lottery== section, or None.

    Handles optional {{anchor|...}} template prefixes before the heading
    text, variable spacing, and both 'Draft lottery' and 'Draft Lottery'.
    """
    # Match an H2 header whose text contains "Draft lottery" (case-insensitive)
    # Allow optional {{anchor|...}} before the visible title.
    m = re.search(
        r"==\s*(?:\{\{anchor\|[^}]+\}\})?\s*Draft\s+[Ll]ottery\s*==",
        wikitext,
    )
    if not m:
        return None
    start = m.end()
    # End at the next H2 header of the same level
    m2 = re.search(r"\n==[^=]", wikitext[start:])
    end = start + (m2.start() if m2 else len(wikitext) - start)
    return wikitext[start:end]


def _strip_wikitext_inline(s: str) -> str:
    """Lightly clean inline wikitext for human-readable team names."""
    # Strip references <ref>...</ref> (including self-closing)
    s = re.sub(r"<ref[^/]*?/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.DOTALL)
    # Strip templates like {{Cref|N}} but capture them separately
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    # Collapse [[Link|Display]] or [[Link]] to Display/Link
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    # Strip HTML tags
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def _extract_wikilink_target(s: str) -> str:
    """Extract the first [[Link|...]] target, or empty string."""
    m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", s)
    return m.group(1).strip() if m else ""


def _parse_record(s: str) -> tuple[int | None, int | None]:
    """Parse a record like '17–65' or '17-65' (with en-dash or hyphen)."""
    # en-dash U+2013 or hyphen
    m = re.search(r"(\d+)\s*[–\-]\s*(\d+)", s)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _parse_int(s: str) -> int | None:
    s = s.strip().replace(",", "")
    if not s or s == "—":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_prob_cell(s: str) -> tuple[float | None, bool]:
    """Parse a probability cell. Returns (prob, is_actual_winner).

    Values like '.140', '.006', '—', or with background highlight.
    The `background:#ff9` style marks the cell corresponding to the pick
    position the team actually received.
    """
    is_winner = "#ff9" in s or "#FFFF99" in s or "#ffff99" in s
    # Strip style attributes to get to the numeric content
    # Cell format examples:
    #   " .140 "
    #   'style="background:#ff9; width:2em; text-align:center;"| .127'
    #   " — "
    content = s
    if "|" in content:
        content = content.split("|", 1)[1]
    content = _strip_wikitext_inline(content).strip()
    if not content or content in ("—", "-", "0"):
        return (None, is_winner)
    try:
        return (float(content), is_winner)
    except ValueError:
        return (None, is_winner)


def _find_lottery_tables(section: str) -> list[str]:
    """Return all wikitable bodies within the section."""
    tables = []
    i = 0
    while True:
        start = section.find("{|", i)
        if start < 0:
            break
        # Find matching |} accounting for nesting (rare)
        depth = 1
        j = start + 2
        while j < len(section) and depth > 0:
            if section[j:j+2] == "{|":
                depth += 1
                j += 2
            elif section[j:j+2] == "|}":
                depth -= 1
                j += 2
            else:
                j += 1
        tables.append(section[start:j])
        i = j
    return tables


def _pick_main_lottery_table(tables: list[str]) -> str | None:
    """Pick the table that actually has lottery participants (record + chances).

    Heuristic: choose the largest table containing both a record pattern
    (like '17–65') and the string 'Lottery chances' or a column of mostly
    probabilities. Skip small legend/style-key tables.
    """
    candidates = []
    for t in tables:
        # Must look like a real data table, not a 2-row legend.
        row_count = t.count("\n|-")
        has_record = bool(re.search(r"\d+\s*[–\-]\s*\d+", t))
        has_chances = "chances" in t.lower() or "Chances" in t
        if row_count >= 5 and has_record and has_chances:
            candidates.append(t)
    if not candidates:
        # Fallback: largest table with at least 5 rows and a record pattern
        for t in tables:
            if t.count("\n|-") >= 5 and re.search(r"\d+\s*[–\-]\s*\d+", t):
                candidates.append(t)
    if not candidates:
        return None
    return max(candidates, key=len)


def _parse_cnotes(section: str) -> list[str]:
    """Extract {{Cnote|N|text}} bodies from the section."""
    notes = []
    for m in re.finditer(r"\{\{Cnote\|([^|]+)\|([^}]+)\}\}", section):
        notes.append(f"[{m.group(1)}] {m.group(2).strip()}")
    return notes


def _find_refs(cell: str) -> list[str]:
    """Find {{Cref|N}} markers in a cell."""
    return re.findall(r"\{\{Cref\|([^}]+)\}\}", cell)


def parse_lottery(year: int, wikitext: str) -> LotteryTable:
    """Parse a year's lottery table from its wikitext."""
    warnings: list[str] = []
    section = _extract_draft_lottery_section(wikitext)
    if section is None:
        return LotteryTable(year=year, rows=[], notes=[], raw_section="",
                            parse_warnings=[f"No '==Draft lottery==' section found for {year}"])

    tables = _find_lottery_tables(section)
    if not tables:
        return LotteryTable(year=year, rows=[], notes=[], raw_section=section,
                            parse_warnings=[f"No wikitable found in draft lottery section for {year}"])

    main_table = _pick_main_lottery_table(tables)
    if main_table is None:
        return LotteryTable(year=year, rows=[], notes=[], raw_section=section,
                            parse_warnings=[f"No lottery participant table identified for {year}"])

    notes = _parse_cnotes(section)

    # Split table into rows. Each row begins with a line starting with '|-'.
    # The first "row" is the header; subsequent are data rows.
    row_blocks = re.split(r"\n\|-\s*\n", main_table)
    # row_blocks[0] is "{| class=...\n" preamble possibly with header
    data_rows = []
    for block in row_blocks[1:]:
        block = block.strip()
        if not block or block.startswith("|}"):
            continue
        # Skip pure header rows.
        # Modern rows: `! scope="row"` + team wikilink; older rows:
        # `| align="left"` + team wikilink. A header row, by contrast, begins
        # with `!` at the block root and either has no data cells (`||` or
        # `\n|`), or its initial `!` cell contains column-header text rather
        # than a team wikilink. Heuristic: the block must contain a team
        # wikilink *in a data cell* (one that starts with `|` or `!` and
        # produces a cleanable team name). We require:
        #   - a wikilink exists
        #   - the wikilink does not reference a season page like
        #     '2006-07 NBA season' (these only appear in header rows)
        if "[[" not in block:
            continue
        if "||" not in block and "\n|" not in block:
            continue
        # If every wikilink in the block points to a season page ("NBA season"),
        # treat as header and skip.
        wikilinks = re.findall(r"\[\[([^\]|]+)", block)
        if wikilinks and all("NBA season" in wl for wl in wikilinks):
            continue
        data_rows.append(block)

    rows: list[LotteryRow] = []
    for block in data_rows:
        # Two schemas observed:
        #   modern: '! scope="row" ... | [[Team]]' then cells
        #   older:  '| align="left" | [[Team]] || cell || cell ...'
        # We split all cells (both `||` and `\n|`) and then pull the first
        # cell that contains a wikilink as the team.
        # Treat the very first character (! or |) as a cell prefix and
        # collapse it.
        text = block
        # Normalize: replace leading '!' with '|' so split rules are uniform
        if text.startswith("!"):
            text = "|" + text[1:]
        # Split on \n| or || (both are cell boundaries in wikitables)
        cells_raw = re.split(r"\s*\|\|\s*|\n\|\s*", text)
        # The first element is whatever was before the first | (usually empty)
        cells_raw = [c for c in cells_raw if c.strip()]

        if not cells_raw:
            warnings.append(f"Row has no cells: {block[:80]!r}")
            continue

        # Team is in the first cell. Strip any leading style attributes
        # (e.g. 'align="left" | [[Team]]' -> team name).
        team_cell = cells_raw[0]
        # Cell attribute syntax: 'attr="x" | value'. We want to split only on
        # the attribute-value separator, not on `|` inside templates or
        # wikilinks. Heuristic: attribute separator looks like `" | ` (quote,
        # pipe, space) or occurs before the first `[[`. Take the substring
        # from the last such separator to the end.
        attr_split = re.search(r'"\s*\|\s*', team_cell)
        if attr_split and attr_split.end() <= team_cell.find("[[") if "[[" in team_cell else True:
            if attr_split:
                team_cell = team_cell[attr_split.end():]
        if "[[" not in team_cell:
            if len(cells_raw) > 1 and "[[" in cells_raw[1]:
                team_cell = cells_raw[1]
                cells_raw = cells_raw[1:]
            else:
                warnings.append(f"No team wikilink found in first cell: {cells_raw[0]!r}")
                continue
        team_raw = team_cell.strip()
        team_wikilink = _extract_wikilink_target(team_raw)
        team_clean = _strip_wikitext_inline(team_raw)
        pick_refs = _find_refs(team_raw)
        cells_raw = cells_raw[1:]  # drop the team cell

        if len(cells_raw) < 3:
            # Often a multi-row header continuation (e.g. 'rowspan="2"|record').
            # Skip silently unless a team wikilink is present (which indicates
            # a real but malformed data row).
            if "[[" not in block:
                continue
            warnings.append(f"Row has too few cells ({len(cells_raw)}): {team_clean!r}")
            continue

        # Expected cell layout (2019-era, 14-team flattened):
        #   [record, chances, p1, p2, ..., p14]
        record_cell = _strip_wikitext_inline(cells_raw[0])
        wins, losses = _parse_record(record_cell)
        chances_cell = _strip_wikitext_inline(cells_raw[1])
        combinations = _parse_int(chances_cell)

        probabilities: dict[int, float] = {}
        won_position: int | None = None
        for i, cell in enumerate(cells_raw[2:], start=1):
            prob, is_winner = _parse_prob_cell(cell)
            if prob is not None:
                probabilities[i] = prob
            if is_winner:
                if won_position is not None:
                    warnings.append(
                        f"Multiple winning cells for {team_clean} ({year}): "
                        f"{won_position} and {i}"
                    )
                won_position = i

        rows.append(LotteryRow(
            team=team_clean,
            team_wikilink=team_wikilink,
            record_wins=wins,
            record_losses=losses,
            combinations=combinations,
            probabilities=probabilities,
            won_position=won_position,
            pick_note_refs=pick_refs,
            raw_row=block,
        ))

    return LotteryTable(
        year=year,
        rows=rows,
        notes=notes,
        raw_section=section,
        parse_warnings=warnings,
    )
