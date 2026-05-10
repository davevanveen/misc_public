# Multiple Testing Plan

## Confirmatory family (4 tests)

**Correction:** Holm-Bonferroni FWE at α = 0.05.

Tests: A, A_pre2019, A_post2019, T1.

Adjustment is computed across these four p-values only. No pooling with exploratory families.

**Interpretation gate:** a "global anomaly" headline claim requires (a) Holm-adjusted significance of A, AND (b) top-3-year NLL-contribution share < 0.5, AND (c) LOYO robustness.

## Exploratory phase 1

Three sub-families, each corrected independently by Benjamini-Hochberg FDR at q = 0.10:

1. Team luck: one p-value per eligible team.
2. Seed luck: one p-value per eligible pre-lottery rank.
3. Outlier years: one p-value per confirmatory-eligible year.

Teams/seeds below their eligibility threshold are reported as shrinkage/effect-size summaries only; they do not enter any p-value family.

## Exploratory phase 2

Two sub-families, each corrected independently by BH-FDR at q = 0.10:

1. Narrative/market covariates: three covariates → three p-values.
2. Pick-position jump analysis: up to 3 p-values (top-1 jump, top-3 jump, top-4 jump, per era).

**Phase 2 is never reported in the headline.** Phase 2 claims must be stated as "hypothesis-generating, not hypothesis-testing."

## Rationale for the family split

Confirmatory and exploratory families answer different questions:
- Confirmatory asks "do aggregated observations across years violate the official model?" Holm-Bonferroni is appropriate for a small, pre-specified test battery where each rejection is a substantive claim.
- Exploratory surveys a larger space of team/seed/year effects; BH-FDR allows a controlled false-discovery rate appropriate for ranking interesting effects, not for making confirmatory rejections.
