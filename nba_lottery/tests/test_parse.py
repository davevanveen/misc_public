"""Regression tests for the wikitext probability-cell parser.

Covers the winner-cell formats that previously caused 237/293 winner-cell
probabilities to be dropped (fixed in 3b96c58):

1. Footnote-dagger format: 'style="background:#ff9"|.225^'
2. Percent-with-sign: '14.0%'
3. Percent with highlight and broken style attribute: 'style="background:#ff9;| 13.4%'
4. Plain decimal: '.140'
5. Uppercase highlight color variants
6. Em-dash placeholder: '—'
"""

from __future__ import annotations

from nba_lottery.parse import _parse_prob_cell


def test_plain_decimal():
    val, winner = _parse_prob_cell(".140")
    assert abs(val - 0.140) < 1e-9
    assert not winner


def test_footnote_dagger_winner():
    val, winner = _parse_prob_cell('style="background:#ff9"|.225^')
    assert abs(val - 0.225) < 1e-9
    assert winner


def test_percent_with_sign():
    val, winner = _parse_prob_cell("14.0%")
    assert abs(val - 0.14) < 1e-9
    assert not winner


def test_percent_with_highlight_broken_style():
    # The 2021+ format: broken closing-quote means `|` inside style attribute
    # gets consumed by the cell splitter. We handle it because the value
    # '13.4%' follows the last `|`.
    val, winner = _parse_prob_cell('style="background:#ff9;| 13.4%')
    assert abs(val - 0.134) < 1e-9
    assert winner


def test_uppercase_highlight():
    val, winner = _parse_prob_cell('style="background-color:#FFFF99"|.215^')
    assert abs(val - 0.215) < 1e-9
    assert winner


def test_em_dash_is_missing():
    val, winner = _parse_prob_cell("—")
    assert val is None


def test_hyphen_is_missing():
    val, winner = _parse_prob_cell("-")
    assert val is None


def test_empty_is_missing():
    val, winner = _parse_prob_cell("")
    assert val is None


def test_cell_with_trailing_footnote_mark():
    val, winner = _parse_prob_cell(".140*")
    assert abs(val - 0.140) < 1e-9


def test_styled_em_dash_winner_cell_still_registers_winner():
    # Degenerate case: a cell that's highlighted as winner but has no numeric
    # value. is_winner should still be True; value should be None.
    val, winner = _parse_prob_cell('style="background:#ff9"|—')
    assert val is None
    assert winner
