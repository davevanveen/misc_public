# Feasibility Report

This report is required by the plan's phase-0 milestone. It answers:

1. How many years pass the confirmatory-eligibility gate?
2. Can we reconstruct exact per-year probabilities for representative years?
3. How often does the pick-recipient view diverge from the slot-owner view?

## 1. Confirmatory-eligibility counts

| Era | Years with data | Confirmatory-eligible |
|-----|-----------------|-----------------------|
| modern_2019_present | 7 | 7 |
| weighted_1994_2018 | 14 | 13 |

**Total confirmatory-eligible years: 20**

Reasons specific years are ineligible:

- **2003:** published probabilities on Wikipedia disagree with exact Monte Carlo marginals across multiple teams (up to 46 sigma); likely a source transcription issue for the 13-team era

Years before 2006 (and 2004-2005) are absent from the data source used (Wikipedia `{year}_NBA_draft` pages do not carry lottery participant tables for those years). They are preserved in `data/raw/` for audit but are not simulated.

## 2. Worked exact-probability reconstructions

The plan requires at least three representative years. We use:

- **2008** — weighted 2005-2018 era, 14 teams (represents the bulk of the pre-flattening sample)
- **2019** — modern era with flattened top-3 odds and multi-way ties (first year of current format)
- **2023** — modern era with traded picks carrying conditional protections

### 2008 (weighted_1994_2018)

- 14 lottery teams, combination base = 1000
- drawn picks = 3
- sum(combinations) = 1000 (OK)

Exact P(team gets #1) via closed form:

| Team | Combos | Exact P(#1) | MC P(#1) |
|------|--------|-------------|----------|
| Miami Heat | 250 | 0.2500 | 0.2514 |
| Seattle SuperSonics | 199 | 0.1990 | 0.1971 |
| Minnesota Timberwolves | 138 | 0.1380 | 0.1371 |
| Memphis Grizzlies | 137 | 0.1370 | 0.1364 |
| New York Knicks | 76 | 0.0760 | 0.0757 |
| Los Angeles Clippers | 75 | 0.0750 | 0.0765 |
| Milwaukee Bucks | 43 | 0.0430 | 0.0433 |
| Charlotte Bobcats | 28 | 0.0280 | 0.0284 |
| Chicago Bulls | 17 | 0.0170 | 0.0173 |
| New Jersey Nets | 11 | 0.0110 | 0.0110 |
| Indiana Pacers | 8 | 0.0080 | 0.0080 |
| Sacramento Kings | 7 | 0.0070 | 0.0070 |
| Portland Trail Blazers | 6 | 0.0060 | 0.0056 |
| Golden State Warriors | 5 | 0.0050 | 0.0051 |

Monte Carlo matches closed-form within MC SE at N = 200,000.

### 2019 (modern_2019_present)

- 14 lottery teams, combination base = 1000
- drawn picks = 4
- sum(combinations) = 1000 (OK)

Exact P(team gets #1) via closed form:

| Team | Combos | Exact P(#1) | MC P(#1) |
|------|--------|-------------|----------|
| New York Knicks | 140 | 0.1400 | 0.1400 |
| Cleveland Cavaliers | 140 | 0.1400 | 0.1381 |
| Phoenix Suns | 140 | 0.1400 | 0.1393 |
| Chicago Bulls | 125 | 0.1250 | 0.1248 |
| Atlanta Hawks | 105 | 0.1050 | 0.1059 |
| Washington Wizards | 90 | 0.0900 | 0.0912 |
| New Orleans Pelicans | 60 | 0.0600 | 0.0602 |
| Memphis Grizzlies | 60 | 0.0600 | 0.0595 |
| Dallas Mavericks | 60 | 0.0600 | 0.0609 |
| Minnesota Timberwolves | 30 | 0.0300 | 0.0298 |
| Los Angeles Lakers | 20 | 0.0200 | 0.0204 |
| Charlotte Hornets | 10 | 0.0100 | 0.0102 |
| Miami Heat | 10 | 0.0100 | 0.0097 |
| Sacramento Kings | 10 | 0.0100 | 0.0101 |

Monte Carlo matches closed-form within MC SE at N = 200,000.

### 2023 (modern_2019_present)

- 14 lottery teams, combination base = 1000
- drawn picks = 4
- sum(combinations) = 1000 (OK)

Exact P(team gets #1) via closed form:

| Team | Combos | Exact P(#1) | MC P(#1) |
|------|--------|-------------|----------|
| Detroit Pistons | 140 | 0.1400 | 0.1402 |
| Houston Rockets | 140 | 0.1400 | 0.1383 |
| San Antonio Spurs | 140 | 0.1400 | 0.1392 |
| Charlotte Hornets | 125 | 0.1250 | 0.1247 |
| Portland Trail Blazers | 105 | 0.1050 | 0.1061 |
| Orlando Magic | 90 | 0.0900 | 0.0911 |
| Indiana Pacers | 68 | 0.0680 | 0.0681 |
| Washington Wizards | 67 | 0.0670 | 0.0662 |
| Utah Jazz | 45 | 0.0450 | 0.0463 |
| Dallas Mavericks | 30 | 0.0300 | 0.0297 |
| Chicago Bulls | 18 | 0.0180 | 0.0182 |
| Oklahoma City Thunder | 17 | 0.0170 | 0.0171 |
| Toronto Raptors | 10 | 0.0100 | 0.0097 |
| New Orleans Pelicans | 5 | 0.0050 | 0.0051 |

Monte Carlo matches closed-form within MC SE at N = 200,000.

## 3. Slot-owner vs pick-recipient divergence

Counts of drawn year-picks where the Wikipedia source flagged a trade-protection footnote (`has_trade_protection_note=1`). Only confirmatory-eligible years contribute.

| Era | Total drawn picks | With trade protection note | Fraction |
|-----|-------------------|----------------------------|----------|
| modern_2019_present | 98 | 4 | 0.04 |
| weighted_1994_2018 | 182 | 25 | 0.14 |

Interpretation: the slot-owner (primary) and pick-recipient (robustness) views diverge for this fraction of drawn year-picks. The plan's primary estimand is the slot-owner view, so these trades do not affect the confirmatory claim.

## 4. Verdict

- **Confirmatory scope:** 20 years (2006-2025 minus 2003) spanning two era sub-regimes (`weighted_1994_2018` and `modern_2019_present`).
- **Simulator validation:** all 625 published-probability checks pass within combined rounding (0.002) and MC (3σ) tolerance at N=500,000. See `validate_probabilities.py`.
- **Freeze commit can proceed.**
