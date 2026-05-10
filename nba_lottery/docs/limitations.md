# Limitations

## Sample size

- 20 confirmatory-eligible years (2006-2025 excluding 2003). Only ~3-4 drawn picks per year. This is a genuinely small sample. Statistical power against subtle non-randomness is limited; see `docs/power_validation.md` for specific detectable effect sizes.

## Data sources

- **Primary source used:** Wikipedia `{year}_NBA_draft` pages, "Draft lottery" sections. These are secondary compilations that cite primary sources (NBA.com press releases, ESPN reports) inline. The raw wikitext plus SHA-256 and fetch timestamp are preserved in `data/raw/wiki/` with `.meta.json` sidecars.
- **Source classification:** secondary-compilation. Field-level provenance for confirmatory fields is recorded in `data/processed/source_audit.csv`.
- **Years excluded from confirmatory analysis (source limitation):** 1985-2002, 2004-2005. Wikipedia's draft pages for these years either do not contain a lottery participant/odds table or use a format incompatible with the parser. These years are preserved in `data/raw/` for audit but are not simulated or tested.
- **2003 excluded (data-quality):** Wikipedia's published probabilities for the 2003 draft lottery disagree with exact Monte Carlo marginals by up to 46σ across multiple teams. This appears to be a transcription issue in the source; the year is excluded from confirmatory analysis. The raw source is preserved.

## Modeling limitations

- **1985-1989 envelope era** is not modeled. Published joint probabilities for intermediate picks are coarser than for later eras, and we do not have primary-source integer mechanics.
- **1990-1993 (66-combination era)** is not parsed by our Wikipedia pipeline; no data is available in this workstream. Not in the confirmatory family.
- **Expansion teams:** any expansion-era mechanical exceptions (e.g., guaranteed slots in a team's first year) are flagged in `data/processed/rule_regimes.csv`.
- **Traded picks with conditional protections:** captured as footnote markers in `has_trade_protection_note`; treated as robustness-only in phase 2. The pre-trade slot-owner view (primary) is insulated from this complexity.

## LLM training-data contamination / hindsight bias

This analysis is implemented by an LLM (Claude Code). Its training data includes the complete historical record of every NBA draft lottery, including widely discussed anomalies (2008 Bulls, 2014 Cavaliers, 2019 Pelicans, etc.). **True preregistration-style blinding is not possible.**

The "analysis-plan freeze" described in the plan is an **audit trail**, not a blinding mechanism. Its value is (a) preventing post-execution test-tuning, (b) letting a human reviewer detect post-freeze drift via SHA-256 comparison, (c) forcing explicit commitment to statistics before computing them on real data. It does not make the LLM blind to the historical record.

Phase-2 narrative/market covariates are especially vulnerable to this: even with a hardcoded covariate list, the LLM may (consciously or not) select analysis framings that align with publicly known anomalies. Phase-2 results should be read as hypothesis-generating only.

## Statistical interpretation

- **"Statistical anomaly" ≠ "evidence of manipulation."** A rejection of the null means the observed outcomes are unlikely under the published probability model; it does not imply intent. A failure to reject does not prove fairness, only that this sample cannot distinguish the observed outcomes from the null.
- **Dependence within a year** (one team's lottery win implies another's loss) is handled by the Monte Carlo null, which simulates the full joint distribution.

## Known weaknesses of this implementation

- **Rounding in published probabilities.** Wikipedia publishes probabilities rounded to 3 decimals. The validator absorbs a 0.002 absolute tolerance before applying MC-SE-based comparison.
- **2024 draft forfeited pick.** The 2024 lottery included a Philadelphia 76ers pick forfeited due to tampering sanctions; the pre-trade slot owner is unambiguous but the deterministic tail ordering is complicated. Captured but not specifically modeled; falls within the 3σ tolerance.
