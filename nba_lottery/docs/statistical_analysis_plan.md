# Statistical Analysis Plan

**Status:** pre-freeze draft. The freeze commit will attach a SHA-256 digest of this file to `docs/analysis_plan_hashes.txt`.

## Primary estimand

For each confirmatory-eligible year `y`, the observed outcome is the tuple of pre-trade lottery slot owners receiving the drawn picks (positions 1 through `drawn_picks[y]`). The null hypothesis is that this tuple is a draw from the official distribution `P_y` defined by the published integer ping-pong-ball combinations.

## Confirmatory family (4 tests, Holm-Bonferroni FWE at α = 0.05)

| Test | Hypothesis | Inference method | Justification |
|------|-----------|------------------|---------------|
| **A** | Global NLL is inconsistent with null over all confirmatory-eligible weighted-era years | Monte Carlo, N = 1,000,000 | Exact joint-outcome enumeration would require ≈ Π(n_k) evaluations per year; MC is simpler and sufficient. |
| **A_pre2019** | Era-stratified A for 1994-2018 weighted era | Monte Carlo, N = 1,000,000 | Same as A restricted to this era. |
| **A_post2019** | Era-stratified A for 2019-present modern era | Monte Carlo, N = 1,000,000 | Same as A restricted to this era. |
| **T1** | Aggregate #1-pick observed outcome is inconsistent with per-year pre-lottery probabilities, over 1985-2025 | Exact Poisson-binomial (closed-form), cross-checked by Monte Carlo N = 1,000,000 | Only per-year #1-pick probabilities are needed; exact Poisson-binomial tail gives p-values directly. Data source: `data/processed/lottery_winners_all_years.csv` (41 rows, 1985-present). |

1985-1989 is NOT in the A/A_pre2019/A_post2019 confirmatory tests. Full participant lists for that era are not sourced (Wikipedia's pre-2006 draft pages do not carry lottery tables), so the joint-outcome NLL is not computable. **T1 uses all 41 years (1985-2025)** because only per-year #1-pick probabilities are required, and those are sourced from the main NBA_draft_lottery Wikipedia article for every year.

## Primary test statistic: global negative log-likelihood (NLL)

For year `y`, let `p_y` = P(observed drawn outcome in y | null). The per-year NLL contribution is `-log p_y`. The global statistic is `S = Σ_y -log p_y`.

- p_y is estimated by Monte Carlo: simulate N draws, count exact matches to the observed tuple. If the count is below a minimum of 5, we report an exact closed-form calculation for that year's top-k tuple as a cross-check.
- Reference distribution: simulate each year independently N times, aggregate to form the null distribution of S. The observed S is compared against this null.
- Reported: p-value with MC standard error.

## Robustness gates on A (both required for a "global anomaly" headline)

1. **Concentration gate.** Compute `top3_share = sum of the 3 largest per-year NLL contributions / total NLL excess over expected`. If `top3_share ≥ 0.5`, the claim is reclassified to outlier-year evidence.
2. **LOYO (leave-one-year-out) gate.** Recompute S with each year removed. If the significance decision flips for any single-year removal, the headline is downgraded to descriptive.

Concentration and LOYO are reported in `outputs/tables/concentration.csv` and `outputs/tables/leave_one_year_out.csv` regardless of whether A is significant.

## Exploratory phase 1 (BH-FDR, separate output file)

- **Team luck.** Per team T, compute observed vs expected cumulative top-1 and top-4 win counts across confirmatory-eligible years. Inference eligibility: **E[top-1 count under null] ≥ 2** OR **E[top-4 count under null] ≥ 5**. Teams below both thresholds: report shrinkage/effect-size with 95% bootstrap CI from the MC null, no p-values.
- **Seed luck.** Same framework as team luck but keyed by pre-lottery rank.
- **Outlier year detection.** Per-year p-values corrected by BH-FDR at q = 0.10. Minimum MC count 1,000,000 for this family.

## Exploratory phase 2 (BH-FDR, separate output file, heaviest caveats)

Three hardcoded covariates (see `docs/estimand_choice.md` for rationale):
1. `msa_population`
2. `forbes_franchise_valuation_rank` (covariate coverage rule: dropped if >20% of eligible years lack data)
3. `prior_season_attendance_rank`

Method: linear regression of per-team "luck" (observed − expected top-4 count over eligible years) on standardized covariates, with permutation-based p-values (permute team labels within each year's null distribution). BH-FDR at q = 0.10.

**Pick-recipient robustness:** restricted to unconditional-ownership year-picks (flagged by `has_trade_protection_note=0`). Report whether primary conclusions change.

**Top-3 / top-4 jump analysis:** distribution of pick-position deltas vs pre-lottery rank. Descriptive only.

## Sensitivity analyses

- Excluding 1985-2005 (data not sourced → already done).
- Excluding any year with `has_trade_protection_note=1` in the drawn region.
- 1,000,000 vs 100,000 MC simulations (MC-stability check).
- Bootstrap CI at MC-null for all reported effect sizes.

## Reporting requirements

- Every reported p-value ships with its MC standard error.
- Flag per-year NLL contributions where SE > 10% of the value.
- Per-team effect-size confidence intervals: 95% bootstrap from the MC null.
- Headline narrative in `docs/results_summary.md` distinguishes "statistical anomaly" from "evidence of manipulation."
