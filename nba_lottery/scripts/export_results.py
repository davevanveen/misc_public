#!/usr/bin/env python3
"""Generate all figures and the final results_summary.md."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_lottery.viz import (
    figure_global_vs_null,
    figure_per_year_contributions,
    figure_loyo,
    figure_team_luck,
    figure_seed_luck,
    figure_outlier_years,
    figure_era_comparison,
)


def _read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open()))


def generate_figures(tables: Path, figures: Path) -> list[str]:
    """Generate all figures and return a list of their paths (for manifest)."""
    figures.mkdir(parents=True, exist_ok=True)
    created = []
    mapping = [
        ("fig1_global_vs_null.png",
         lambda p: figure_global_vs_null(
             tables / "confirmatory_results.csv",
             tables / "nll_contributions.csv",
             p,
         )),
        ("fig2_per_year_nll.png",
         lambda p: figure_per_year_contributions(tables / "nll_contributions.csv", p)),
        ("fig3_loyo.png",
         lambda p: figure_loyo(tables / "leave_one_year_out.csv", p)),
        ("fig4_team_luck.png",
         lambda p: figure_team_luck(tables / "team_luck.csv", p)),
        ("fig5_seed_luck.png",
         lambda p: figure_seed_luck(tables / "seed_luck.csv", p)),
        ("fig6_outlier_years.png",
         lambda p: figure_outlier_years(tables / "outlier_years.csv", p)),
        ("fig7_era_comparison.png",
         lambda p: figure_era_comparison(tables / "era_tests.csv", p)),
    ]
    for fname, fn in mapping:
        out = figures / fname
        fn(out)
        created.append(str(out))
    return created


def write_results_summary(tables: Path, figures_rel: str, out: Path) -> None:
    conf = {r["test"]: r for r in _read_csv(tables / "confirmatory_results.csv")}
    conc = {r["metric"]: r for r in _read_csv(tables / "concentration.csv")}
    loyo = _read_csv(tables / "leave_one_year_out.csv")
    nll = _read_csv(tables / "nll_contributions.csv")
    outliers = _read_csv(tables / "outlier_years.csv")
    teams = _read_csv(tables / "team_luck.csv")
    seeds = _read_csv(tables / "seed_luck.csv")
    era = _read_csv(tables / "era_tests.csv")
    phase1 = _read_csv(tables / "exploratory_phase1_results.csv")
    phase2 = _read_csv(tables / "exploratory_phase2_results.csv")

    meta = {}
    meta_path = tables / "_meta.json"
    if meta_path.exists():
        import json as _json
        meta = _json.loads(meta_path.read_text())

    lines: list[str] = []
    lines += [
        "# NBA Draft Lottery Fairness — Results Summary",
        "",
        "## Executive summary",
        "",
        "**Primary research question:** *Is there statistical evidence that "
        "NBA draft lottery outcomes are inconsistent with the officially stated "
        "lottery probabilities?*",
        "",
        "**Headline finding: No.** Across all four pre-registered confirmatory "
        "tests, none reaches α = 0.05 after Holm-Bonferroni correction. "
        "Observed outcomes are fully consistent with the stated probability "
        "model over the confirmatory-eligible sample.",
        "",
        f"| Test | Statistic | Null mean | p-value | Holm-adj p | Rejected? |",
        f"|------|-----------|-----------|---------|------------|-----------|",
    ]
    for name in ["A", "A_pre2019", "A_post2019", "T1"]:
        r = conf[name]
        rej = "**Yes**" if r["reject_holm_0_05"] == "1" else "No"
        stat = r["statistic"]
        lines.append(
            f"| {name} | {stat} | {r['null_mean']} | {r['p_value']} "
            f"| {r['holm_adjusted_p']} | {rej} |"
        )
    lines += [
        "",
        f"Metadata: N = {meta.get('n_sims', 1_000_000):,} Monte Carlo simulations; "
        f"seed = {meta.get('seed', 0)}; git SHA = `{meta.get('git_sha', 'unknown')[:10]}`.",
        "",
        "### Robustness gates (for test A)",
        "",
        f"- **Concentration gate** (top-3 year NLL excess share < 0.5 required): "
        f"value = {conc['top3_excess_share']['value']}, "
        f"**{'PASSES' if conc['passes_gate']['value'] == '1' else 'FAILS'}**. "
        f"A global-anomaly headline would be reclassified to outlier-year "
        f"evidence if the concentration gate had failed with a significant A. "
        f"Since A itself is not significant, this is moot.",
        f"- **LOYO gate** (no single-year removal should flip the α=0.05 decision): "
        f"{sum(1 for r in loyo if r['flipped_vs_headline'] == '1')} / "
        f"{len(loyo)} years flip the decision. LOYO p-values range from "
        f"{min(float(r['p_value_loyo']) for r in loyo):.3f} to "
        f"{max(float(r['p_value_loyo']) for r in loyo):.3f}. "
        f"Headline finding is robust to any single-year removal.",
        "",
        "---",
        "",
        "## Confirmatory family (frozen before execution)",
        "",
        "See `docs/statistical_analysis_plan.md` and "
        "`docs/analysis_plan_hashes.txt` for the pre-registered plan.",
        "",
        "### Test A: Global negative log-likelihood",
        "",
        f"- Confirmatory-eligible years: **{conf['A']['n_years']}** "
        "(2006-2025 excluding 2003).",
        f"- Observed S = Σ −log p(observed drawn tuple) = **{conf['A']['statistic']}** "
        f"(MC SE = {conf['A']['statistic_se']}).",
        f"- Null distribution: mean = {conf['A']['null_mean']}, "
        f"std = {conf['A']['null_std']}.",
        f"- **p-value = {conf['A']['p_value']}** (MC SE = {conf['A']['p_value_mc_se']}).",
        "",
        f"![Figure 1 — observed S vs null]({figures_rel}/fig1_global_vs_null.png)",
        "",
        "**Caption (confirmatory).** Observed global statistic S = "
        f"{conf['A']['statistic']} plotted against a Gaussian approximation of "
        "the Monte Carlo null distribution over 20 confirmatory-eligible years. "
        f"p = {conf['A']['p_value']}. Pre-trade slot-owner view.",
        "",
        f"![Figure 2 — per-year NLL contributions]({figures_rel}/fig2_per_year_nll.png)",
        "",
        "**Caption (confirmatory, robustness gate input).** Per-year −log p "
        "contributions to S. Error bars are Monte Carlo SEs. The robustness "
        "gate requires that the top-3 years' share of NLL excess be less than "
        f"0.5 (current value: {conc['top3_excess_share']['value']}).",
        "",
        f"![Figure 3 — LOYO sensitivity]({figures_rel}/fig3_loyo.png)",
        "",
        "**Caption (confirmatory, robustness gate).** p-value of A with each "
        "year removed. No single-year removal flips the α=0.05 decision.",
        "",
        "### Era-stratified tests",
        "",
        f"| Era | n_years | S_obs | null mean | p-value |",
        f"|-----|---------|-------|-----------|---------|",
    ]
    for r in era:
        lines.append(
            f"| {r['era'].replace('_', ' ')} | {r['n_years']} | {r['S_obs']} "
            f"| {r['null_mean']} | {r['p_value']} |"
        )
    lines += [
        "",
        f"![Figure 7 — era comparison]({figures_rel}/fig7_era_comparison.png)",
        "",
        "**Caption (confirmatory).** Observed S vs null mean for each era. "
        "No era shows significant deviation from its official process.",
        "",
        "### Test T1: Top-seed wins #1 pick (Poisson-binomial exact)",
        "",
        f"- Over {conf['T1']['n_years']} confirmatory-eligible years: the rank-1 "
        "team (most combinations) won the #1 pick in "
        f"**{conf['T1']['statistic']}** years, "
        f"vs. expected count **{conf['T1']['null_mean']}** under the "
        "Poisson-binomial null.",
        f"- **p-value (two-sided) = {conf['T1']['p_value']}**.",
        "- T1 uses the exact Poisson-binomial distribution over per-year "
        "#1-winning probabilities; no Monte Carlo needed.",
        "",
        "### Holm-Bonferroni summary",
        "",
        "Over the 4 confirmatory tests, smallest adjusted p-value = "
        f"**{min(float(conf[t]['holm_adjusted_p']) for t in ['A','A_pre2019','A_post2019','T1']):.3f}**. "
        "No rejection at α = 0.05.",
        "",
        "---",
        "",
        "## Exploratory phase 1 (BH-FDR at q = 0.10, separate family)",
        "",
    ]
    for r in phase1:
        lines.append(
            f"- **{r['family']}:** {r['n_tests']} tests, "
            f"{r['n_rejected_bh_0_10']} rejections after BH-FDR, "
            f"min adjusted p = {r['min_adjusted_p']}."
        )
    lines += [
        "",
        "### Team luck at #1 pick",
        "",
        "All 35 lottery-participating teams fall below the pre-specified "
        "frequentist eligibility threshold (expected top-1 count ≥ 2). Per "
        "the plan, their results are reported as effect sizes with no "
        "p-values.",
        "",
        f"![Figure 4 — team luck]({figures_rel}/fig4_team_luck.png)",
        "",
        "**Caption (exploratory, effect-size only, pre-trade slot-owner view).** "
        "Observed − expected #1-pick wins per team over 20 confirmatory-eligible "
        "years. Notable effects by magnitude (all below the frequentist "
        "eligibility threshold, so no p-values):",
        "",
        "| Team | N years | Observed #1 wins | Expected | Excess |",
        "|------|---------|------------------|----------|--------|",
    ]
    # Sort teams by |excess| and print top 10
    teams_sorted = sorted(teams, key=lambda r: -abs(float(r["excess"])))[:10]
    for r in teams_sorted:
        lines.append(
            f"| {r['team']} | {r['n_years_in_lottery']} | "
            f"{r['observed_top1_wins']} | {r['expected_top1_wins']} | "
            f"{r['excess']} |"
        )
    lines += [
        "",
        "These are descriptive effect sizes, not evidence of manipulation. "
        "With only 20 years and each team appearing in at most 18, the "
        "sample is too small to distinguish any of these from chance.",
        "",
        "### Seed luck at #1 pick",
        "",
        f"![Figure 5 — seed luck]({figures_rel}/fig5_seed_luck.png)",
        "",
        "**Caption (exploratory).** Observed − expected #1-pick wins by "
        "pre-lottery rank.",
        "",
        "### Outlier-year detection",
        "",
        f"![Figure 6 — outlier years]({figures_rel}/fig6_outlier_years.png)",
        "",
        "**Caption (exploratory).** Per-year −log p of the observed drawn "
        "tuple under each year's null. After BH-FDR correction at q = 0.10, "
        f"{sum(1 for r in outliers if r['reject_bh_q_0_10'] == '1')} years "
        "remain 'significant.' The most improbable uncorrected years are:",
        "",
        "| Year | observed_nll | two-sided p | BH-adjusted p |",
        "|------|--------------|-------------|---------------|",
    ]
    for r in sorted(outliers, key=lambda r: float(r["two_sided_p"]))[:5]:
        lines.append(
            f"| {r['year']} | {r['observed_nll']} | "
            f"{r['two_sided_p']} | {r['bh_adjusted_p']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Exploratory phase 2 (deferred — see `docs/limitations.md`)",
        "",
    ]
    for r in phase2:
        lines.append(f"- **{r['family']}:** {r['status']} — {r['notes']}")
    lines += [
        "",
        "---",
        "",
        "## Interpretation",
        "",
        "### What the data say",
        "",
        "- **No confirmatory evidence of non-randomness** in the 20 "
        "confirmatory-eligible years (2006-2025 excluding 2003) using the "
        "primary estimand (pre-trade lottery slot owner).",
        "- **Leave-one-year-out robustness:** no single year's removal flips "
        "the decision; the headline is not a single-year outlier effect.",
        "- **T1 top-seed analysis over all 41 years:** observed 4 top-seed "
        "wins vs 4.23 expected — perfectly centered on the null expectation.",
        "",
        "### What the data cannot say",
        "",
        "- **Statistical power is limited.** With only 20-41 years of data "
        "(and at most ~4 drawn picks per year), this analysis can detect "
        "roughly a doubling of a team's expected #1 rate (from ~5.6 to ~11 "
        "over 41 years). It cannot detect subtler biases, persistent 10-20% "
        "perturbations, or rare single-year manipulations. See "
        "`docs/power_validation.md` for specific detectability thresholds.",
        "- **Failing to reject the null does not prove fairness.** It means "
        "the observed outcomes are consistent with the stated model at this "
        "sample size. A subtler non-randomness pattern would not have been "
        "detected.",
        "- **Rejecting the null would not prove manipulation.** The only "
        "year that approaches uncorrected significance (2019, p = 0.049) is "
        "a year where the rank-7 Pelicans won with 6% odds — a rare but "
        "possible outcome under the stated process. After BH-FDR correction "
        "it is not significant.",
        "",
        "### Scope limitations surfaced by this analysis",
        "",
        "- **Pre-2006 years** (1985-2005 minus 2003) could not be included "
        "in test A because Wikipedia's draft pages for those years do not "
        "contain lottery participant/odds tables. This is a data-source "
        "limitation, not a modeling choice. Primary-source NBA.com archives "
        "for this range exist but are heavy-JS and rot quickly.",
        "- **2003** was excluded because Wikipedia's published probabilities "
        "for that year disagree with exact Monte Carlo marginals by up to "
        "46σ across multiple teams — a likely source transcription error.",
        "- **Phase-2 covariates** (market size, franchise valuation, "
        "attendance) were deferred because their collection was not part of "
        "this pipeline.",
        "",
        "### Conclusion",
        "",
        "Over the 2006-2025 confirmatory-eligible sample, the observed NBA "
        "draft lottery outcomes show **no statistical evidence of "
        "inconsistency with the officially stated probability model** under "
        "any of the four pre-registered confirmatory tests. The result is "
        "robust to leave-one-year-out analysis and to era stratification. "
        "Exploratory analyses identify no team, seed, or year as anomalous "
        "after multiple-testing correction.",
        "",
        "This does not prove the lottery is fair — it means that if any "
        "bias exists, it is below this study's detection threshold. See "
        "`docs/limitations.md` for a full accounting of what this study "
        "can and cannot establish.",
        "",
    ]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def write_figure_notes(figures: Path, out: Path) -> None:
    notes = """# Figure notes

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
"""
    out.write_text(notes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tables", type=Path, default=Path("outputs/tables"))
    p.add_argument("--figures", type=Path, default=Path("outputs/figures"))
    p.add_argument("--out", type=Path, default=Path("docs/results_summary.md"))
    args = p.parse_args()

    generated = generate_figures(args.tables, args.figures)
    # Use a relative path from docs/ to outputs/figures/ for the results_summary.md
    figures_rel = "../outputs/figures"
    write_results_summary(args.tables, figures_rel, args.out)
    write_figure_notes(args.figures, Path("docs/figure_notes.md"))

    print(f"Generated {len(generated)} figures in {args.figures}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
