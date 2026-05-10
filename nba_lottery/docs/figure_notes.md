# Figure notes

All figures in this report use consistent color conventions:

- **Red / crimson**: observed values, winner cells, anomalies of interest.
- **Blue / steelblue**: null-distribution reference or non-anomalous observations.
- **Gray**: null mean / baseline references.

All figures include family labels in captions:

- **Confirmatory**: part of the pre-registered 4-test family. Holm-Bonferroni FWE control.
- **Exploratory phase 1**: team, seed, outlier-year analyses under BH-FDR at q = 0.10.
- **Exploratory phase 2**: deferred (covariates not collected).

All confirmatory figures use N = 1,000,000 Monte Carlo simulations per year.
MC standard errors are shown as error bars where applicable.

Figures are generated from the CSVs in `outputs/tables/` via `scripts/export_results.py`.
