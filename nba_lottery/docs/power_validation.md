# Power Validation: Sensitivity to Specified Alternatives

This report is NOT a general power analysis. It is a sensitivity probe: we inject known anomalies into the data and check whether the primary test statistics detect them at the pre-specified correction level.

- MC size for each injection run: N = 50,000
- Confirmatory-eligible years (A-family tests): 20 (2006-2025).

## Baseline (no injection)

- Observed S (sum per-year NLL): **138.95** (MC SE ≈ 1.487)
- Null S mean ± std: 138.31 ± 5.93
- p-value of A: **0.4454** (MC SE ≈ 0.0022)

## Sparse / outlier injection

For a randomly chosen year, we force the #1 pick to the team with the LOWEST pre-lottery probability. This simulates a single-year outlier anomaly (the alternative hypothesis F in the plan).

| Injected year | Forced to team | Original #1 | Δ p-value |
|---|---|---|---|
| 2008 | Golden State Warriors | Chicago Bulls | 0.4454 → 0.3809 (↓ 0.0646) |
| 2014 | Phoenix Suns | Cleveland Cavaliers | 0.4454 → 0.4745 (↑ 0.0290) |
| 2019 | Charlotte Hornets | New Orleans Pelicans | 0.4454 → 0.4246 (↓ 0.0209) |

**Interpretation:** if a single-year outlier noticeably lowers the global p-value, the test is sensitive to sparse alternatives.

## Diffuse injection

We multiply one team's combinations by a factor (1.05, 1.10, 1.20) in every year they appear, then re-normalize to the era total. We then recompute the per-year NLL **under this altered null** and the global S. This simulates a persistent bias (alternative hypothesis B).

- Target team: **Sacramento Kings** (18 years of appearances)

| Multiplier | Baseline p-value | Perturbed p-value | Δ |
|---|---|---|---|
| ×1.05 | 0.4454 | 0.4836 | -0.0382 |
| ×1.10 | 0.4454 | 0.4956 | -0.0501 |
| ×1.20 | 0.4454 | 0.5028 | -0.0574 |

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

