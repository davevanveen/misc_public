# Estimand Choice: Pre-trade Lottery Slot Owner

## What we model

The primary unit of analysis is the **pre-trade lottery slot owner**: the team whose regular-season record **generated** the odds for a given lottery slot in year `y`. This is well-defined from final regular-season standings and is independent of (a) which logo appeared on the ball during the lottery broadcast and (b) which team received the drawn pick after trades.

## What we do not model as primary

The **pick-recipient view** (who actually ended up with the drawn pick) is retained as an exploratory robustness check only. NBA draft picks are frequently traded with lottery-outcome-dependent conditional protections (e.g., "top-3 protected"), so the pick-recipient distribution is a **function of the lottery realization itself**. Modeling it correctly would require a high-fidelity database of the trade conditions in effect at the time of each lottery, which public sources do not reliably provide.

## Why this matters

The research question is "Is the random drawing mechanism producing outcomes consistent with the published distribution?" The drawing mechanism operates on teams' records (through their assigned ping-pong-ball combinations), not on their trade status. The pre-trade slot-owner view is the correct estimand for that question.

The pick-recipient view answers a different question: "Do teams that end up with picks under complex conditional-protection trades deviate from expected?" We report a restricted version of this (unconditional-ownership year-picks only) in phase 2 as a robustness check, not a headline claim.

## Quantitative divergence

Of the 20 confirmatory-eligible years (2006-2025 excluding 2003), the Wikipedia source uses `{{Cref|n}}` / `{{refn}}` footnote markers to tag teams whose pick had trade protections. We capture those markers in `data/processed/lottery_team_year.csv` as `has_trade_protection_note`.

Divergence summary across the confirmatory-eligible set:

| Era | Total drawn year-picks | With trade protection note | Fraction |
|-----|-----------------------|-----------------------------|----------|
| 2006-2018 (pre-flattening) | 39 (3 per year × 13 years) | computed by script | ≈0.15 |
| 2019-2025 (modern) | 28 (4 per year × 7 years) | computed by script | ≈0.30 |

Exact values are produced by `scripts/run_feasibility_report.py` and reported in `docs/feasibility_report.md`.

## Sensitivity note

If the conclusions from phase-2 pick-recipient robustness diverge substantively from the primary slot-owner results, that divergence is reported in `docs/results_summary.md` as a scope-sensitive finding, not a headline claim.
