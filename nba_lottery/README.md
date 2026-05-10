# nba_lottery

A reproducible, pre-registered statistical test of whether historical NBA draft lottery outcomes are consistent with the officially stated ping-pong-ball probabilities. Implements four confirmatory tests (global negative log-likelihood + era-stratified + Poisson-binomial top-seed) under Holm-Bonferroni correction, plus exploratory team/seed/outlier-year analyses under BH-FDR. **Headline finding: no confirmatory rejection — observed outcomes are statistically consistent with the official probability model.**

## Table of contents

- [Repository architecture](#repository-architecture)
- [Methods](#methods)
- [Results](#results)
- [Reproducing](#reproducing)

## Repository architecture

```
nba_lottery/
├── nba_lottery/          # single Python package, 4 workstream modules
│   ├── data.py           # era / rule-regime definitions, tie-breaker helpers
│   ├── fetch.py          # Wikipedia parse-API fetcher (idempotent, rate-limit-aware)
│   ├── parse.py          # wikitext lottery-table parser (handles 2006-2025 formats)
│   ├── parse_main_article.py  # parses the all-years #1-pick winners table
│   ├── dataset.py        # builds data/processed/ CSVs + eligibility gate
│   ├── simulate.py       # weighted + envelope simulators, Monte Carlo
│   ├── stats.py          # NLL, LOYO, concentration, Poisson-binomial, corrections
│   ├── viz.py            # figures
│   └── cli.py            # CLI entry points (placeholder; scripts/ are primary)
├── scripts/              # pipeline stages, each a thin wrapper
│   ├── build_dataset.py
│   ├── validate_probabilities.py
│   ├── run_feasibility_report.py
│   ├── run_power_validation.py
│   ├── freeze_plan.py
│   ├── run_stat_tests.py
│   └── export_results.py
├── data/
│   ├── raw/wiki/         # 41 {year}_NBA_draft.wikitext + meta.json sidecars
│   ├── interim/
│   └── processed/        # 5 canonical CSVs (team-year, prob matrix, rule regimes, source audit, all-years winners)
├── outputs/
│   ├── tables/           # 10 result CSVs + null_samples.npz + _meta.json
│   └── figures/          # 7 PNG figures
├── docs/                 # analysis plan, hypotheses, multiple-testing plan, estimand choice,
│                         # limitations, feasibility report, power validation, results summary,
│                         # figure notes, analysis_plan_hashes.txt (freeze artifact)
├── tests/                # pytest suite (7 simulator + 9 stats + 10 parser = 26 tests)
├── Makefile              # `make all` runs the full pipeline from locally-cached raw data
└── pyproject.toml
```

The four workstreams (data / stats / simulate / viz) correspond to distinct concerns with file-contract handoffs. The pipeline runs sequentially via the Makefile:

```
build_dataset → validate_probabilities → run_feasibility_report
             → run_power_validation → freeze_plan → run_stat_tests
             → export_results
```

## Methods

- **Primary estimand:** the pre-trade lottery slot owner (the team whose regular-season record *generated* the odds). Independent of logo displayed, independent of pick recipient after trades. See [`docs/estimand_choice.md`](docs/estimand_choice.md).
- **Null hypothesis:** for each year, the observed mapping of pre-trade slot owners to drawn pick positions is a sample from the official distribution defined by the year's integer ping-pong-ball combinations (post-tie-breaker).
- **Data source:** Wikipedia `{year}_NBA_draft` pages, "Draft lottery" sections (for full participant + odds tables, 2006-2025) and the main `NBA_draft_lottery` article's "Lottery winners" table (for #1-pick data, 1985-2025). Raw wikitext snapshots + SHA-256 sidecars preserved in `data/raw/wiki/`.
- **Confirmatory scope (A, A_pre2019, A_post2019):** 20 years (2006-2025 excluding 2003). Pre-2006 Wikipedia draft pages do not carry lottery participant tables; 2003's published probabilities disagree with exact Monte Carlo by up to 46σ (source transcription issue).
- **Confirmatory scope (T1):** 41 years (1985-2025). T1 needs only per-year #1-pick probabilities, available for all years.
- **Inference:** Monte Carlo at N = 1,000,000 for the NLL family; exact Poisson-binomial for T1. MC standard errors reported alongside every p-value.
- **Multiple-testing correction:** Holm-Bonferroni FWE over the 4 confirmatory tests; BH-FDR at q = 0.10 within each exploratory family (team, seed, outlier-year).
- **Robustness gates on test A:** concentration (top-3 year NLL-excess share < 0.5) and LOYO (no single-year removal flips the α=0.05 decision).
- **Freeze mechanism:** `scripts/freeze_plan.py` writes SHA-256 of the analysis-plan docs into `docs/analysis_plan_hashes.txt`. The freeze commit is the authoritative audit trail. This is *not* a blinding device — the LLM implementing this analysis has training-data knowledge of every historical lottery outcome. See [`docs/limitations.md`](docs/limitations.md).
- **Reproducibility:** `make all` runs from locally-cached raw data by default (no network required). All stages are deterministic given a seed.

See [`docs/statistical_analysis_plan.md`](docs/statistical_analysis_plan.md), [`docs/hypotheses.md`](docs/hypotheses.md), and [`docs/multiple_testing_plan.md`](docs/multiple_testing_plan.md) for the full pre-registered plan.

## Results

**No confirmatory rejection.** All four pre-registered tests have Holm-adjusted p = 1.000; the observed #1-pick count over 41 lotteries (4) essentially equals the expected count under the null (4.23), with no gap to explain. The result is robust to leave-one-year-out and to era stratification, and no exploratory team/seed/year effect survives BH-FDR correction. This does not prove the lottery is fair — with only 20-41 years of data the study cannot detect subtler biases — but observed outcomes are statistically consistent with the officially stated ping-pong-ball probabilities.

See [`docs/results_summary.md`](docs/results_summary.md) for the full narrative with tables, figures, and per-year detail.

## Reproducing

```bash
cd nba_lottery/
make all            # runs the full pipeline (≈ 2m30s at N=1,000,000)
make test           # runs the pytest suite (26 tests)
```

`make all` uses the committed raw Wikipedia snapshots in `data/raw/wiki/` — no network required. To refresh a specific year from upstream, delete its `.wikitext` + `.meta.json` and re-run `make dataset`.
