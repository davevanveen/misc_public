# Power Validation: Sensitivity to Specified Alternatives

This report is NOT a general power analysis. It is a sensitivity probe: we inject known anomalies into the data and check whether the primary test statistics detect them at the pre-specified correction level.

- MC size for each injection run: N = 30,000
- Confirmatory-eligible years (A-family tests): 20 (2006-2025).

## Baseline (no injection)

- Observed S (sum per-year NLL): **138.60** (MC SE ≈ 1.725)
- Null S mean ± std: 137.48 ± 5.71
- p-value of A: **0.4131** (MC SE ≈ 0.0028)

## Sparse / outlier injection

For a randomly chosen year, we force the #1 pick to the team with the LOWEST pre-lottery probability. This simulates a single-year outlier anomaly (the alternative hypothesis F in the plan).

| Injected year | Forced to team | Original #1 | Δ p-value |
|---|---|---|---|
| 2008 | Golden State Warriors | Chicago Bulls | 0.4131 → 0.3418 (↓ 0.0714) |
| 2014 | Phoenix Suns | Cleveland Cavaliers | 0.4131 → 0.5077 (↑ 0.0946) |
| 2019 | Charlotte Hornets | New Orleans Pelicans | 0.4131 → 0.4834 (↑ 0.0703) |

**Interpretation:** if a single-year outlier noticeably lowers the global p-value, the test is sensitive to sparse alternatives.

## Diffuse injection

We multiply one team's combinations by a factor (1.05, 1.10, 1.20) in every year they appear, then re-normalize to the era total. We then recompute the per-year NLL **under this altered null** and the global S. This simulates a persistent bias (alternative hypothesis B).

- Target team: **Sacramento Kings** (18 years of appearances)

| Multiplier | Baseline p-value | Perturbed p-value | Δ |
|---|---|---|---|
| ×1.05 | 0.4131 | 0.4859 | -0.0728 |
| ×1.10 | 0.4131 | 0.4950 | -0.0818 |
| ×1.20 | 0.4131 | 0.5156 | -0.1025 |

## T1 detection thresholds

For the Poisson-binomial Top-1 test over all 41 years, how many deviations from the expected top-seed-wins-#1 count are required to reject at α = 0.05? Using the actual per-year probabilities from `lottery_winners_all_years.csv`.

- n_years = 41
- Σ p_y (expected #1 wins by top-seed) = 5.59

| Observed top-seed #1 wins | One-sided p | Detected at α=0.05 |
|---|---|---|
| 5 | 0.5045 | — |
| 7 | 0.3199 | — |
| 9 | 0.0916 | — |
| 11 | 0.0160 | ✓ |
| 13 | 0.0017 | ✓ |

