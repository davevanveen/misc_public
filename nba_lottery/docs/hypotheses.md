# Hypotheses

## Null

For each lottery year `y`, the observed outcome (mapping of pre-trade lottery slot owners to drawn pick positions) is a draw from the official probability distribution `P_y` defined by the published integer combinations.

## Alternatives

- **A.** Global: aggregated outcomes over confirmatory-eligible weighted-era years are less likely under `P_y` than expected by chance. **Confirmatory.**
- **A_pre2019.** Era-stratified A for 1994-2018. **Confirmatory.**
- **A_post2019.** Era-stratified A for 2019-present. **Confirmatory.**
- **T1.** Aggregate #1-pick observed outcome is inconsistent with per-year pre-lottery probabilities, over all 41 lotteries (1985-2025). **Confirmatory.**
- **B.** Team-specific luck. **Exploratory phase 1.**
- **C.** Pre-lottery-rank-specific luck. **Exploratory phase 1.**
- **F.** Outlier-year detection. **Exploratory phase 1.**
- **E.** Narrative/market covariate association (3 hardcoded variables). **Exploratory phase 2.**
- Pick-recipient robustness. **Exploratory phase 2.**
- Top-3 / top-4 jump analysis. **Exploratory phase 2.**

1985-1989 (envelope era) and 1990-2002, 2004-2005 weighted era are **not** covered by any confirmatory claim in this analysis: their exact integer combinations and pre-lottery tie-breaker outcomes are not reconstructable from the Wikipedia source used here. Those years are carried only for reference in `data/raw/` and are not simulated.

## Pre-registration caveat

This analysis is implemented by an LLM (Claude Code) whose training data includes the historical record of every NBA draft lottery. Genuine preregistration-style blinding is impossible. The freeze commit is an audit-trail device, not a blinding mechanism. See `docs/limitations.md`.
