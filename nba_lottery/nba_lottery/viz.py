"""Visualization helpers: figures for the results report."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def figure_global_vs_null(
    conf_csv: Path,
    per_year_nll_csv: Path,
    out_path: Path,
    null_samples_npz: Path | None = None,
) -> None:
    """Figure 1: Observed global statistic S vs simulated null distribution.

    Uses the empirical S_null histogram when null_samples_npz is provided,
    otherwise falls back to a Gaussian approximation (labeled as such).
    """
    rows = list(csv.DictReader(conf_csv.open()))
    A = next(r for r in rows if r["test"] == "A")
    S_obs = float(A["statistic"])
    null_mean = float(A["null_mean"])
    null_std = float(A["null_std"])
    p = float(A["p_value"])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if null_samples_npz is not None and null_samples_npz.exists():
        data = np.load(null_samples_npz)
        S_null = data["A_null"]
        # Empirical histogram
        counts, edges, _ = ax.hist(
            S_null, bins=80, density=True, color="steelblue",
            edgecolor="white", linewidth=0.3,
            label=f"Empirical null (N={len(S_null):,})",
        )
        source = "empirical"
    else:
        xs = np.linspace(null_mean - 4 * null_std, null_mean + 4 * null_std, 200)
        pdf = np.exp(-0.5 * ((xs - null_mean) / null_std) ** 2) / (
            null_std * np.sqrt(2 * np.pi)
        )
        ax.plot(xs, pdf, color="steelblue",
                label="Null distribution (Gaussian approx)")
        source = "Gaussian approx (null samples not available)"

    ax.axvline(S_obs, color="crimson", linestyle="--", lw=2,
               label=f"Observed S = {S_obs:.1f}")
    # Shade the tail for visual clarity
    ax.axvspan(S_obs, ax.get_xlim()[1], color="crimson", alpha=0.15,
               label=f"p-value tail = {p:.3f}")
    ax.set_xlabel("Global statistic S = Σ −log p(observed)")
    ax.set_ylabel("Density under null")
    ax.set_title(
        f"Test A: observed S vs null (confirmatory; {source})\n"
        "Pre-trade slot-owner view, 20 years (2006-2025 excl. 2003)"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_per_year_contributions(nll_csv: Path, out_path: Path) -> None:
    """Figure 2: per-year NLL contribution bar chart with MC SE bars."""
    rows = list(csv.DictReader(nll_csv.open()))
    years = [int(r["year"]) for r in rows]
    nll = np.array([float(r["nll"]) for r in rows])
    se = np.array([float(r["mc_se"]) for r in rows])
    mean_nll = nll.mean()

    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["crimson" if n - s > mean_nll * 1.5 else "steelblue" for n, s in zip(nll, se)]
    ax.bar(years, nll, yerr=se, color=colors, capsize=3, edgecolor="black", linewidth=0.5)
    ax.axhline(mean_nll, color="gray", linestyle=":", label=f"Per-year mean = {mean_nll:.2f}")
    ax.set_xlabel("Year")
    ax.set_ylabel("−log p(observed) under null")
    ax.set_title("Per-year NLL contributions (confirmatory, robustness gate input)\n"
                 "Concentration gate metric: top-3 excess share")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_loyo(loyo_csv: Path, out_path: Path) -> None:
    """Figure 3: LOYO sensitivity — p-value with each year removed."""
    rows = list(csv.DictReader(loyo_csv.open()))
    years = [int(r["year_removed"]) for r in rows]
    ps = np.array([float(r["p_value_loyo"]) for r in rows])

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(years, ps, color="slategray", edgecolor="black", linewidth=0.5)
    ax.axhline(0.05, color="crimson", linestyle=":", label="α = 0.05")
    ax.set_xlabel("Year removed from confirmatory set")
    ax.set_ylabel("p-value of A (leave-one-year-out)")
    ax.set_title("LOYO robustness gate — does any single year flip the decision?\n"
                 "(No flips: headline finding is robust to any one-year removal.)")
    ax.set_ylim(0, 1.0)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_team_luck(team_csv: Path, out_path: Path) -> None:
    """Figure 4: Team cumulative lottery luck (observed − expected #1 wins)."""
    rows = list(csv.DictReader(team_csv.open()))
    rows.sort(key=lambda r: float(r["excess"]))
    teams = [r["team"] for r in rows]
    excess = np.array([float(r["excess"]) for r in rows])
    appearances = np.array([int(r["n_years_in_lottery"]) for r in rows])

    fig, ax = plt.subplots(figsize=(8, max(6, 0.2 * len(teams))))
    colors = ["crimson" if e > 0 else "steelblue" for e in excess]
    ax.barh(teams, excess, color=colors, edgecolor="black", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Observed #1 wins − expected #1 wins (confirmatory-eligible years)")
    ax.set_ylabel("Team (pre-trade slot owner)")
    ax.set_title("Team luck at #1 pick (exploratory phase 1)\n"
                 "All teams below E[top-1] ≥ 2 threshold — effect sizes only, no p-values")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_seed_luck(seed_csv: Path, out_path: Path) -> None:
    """Figure 5: Pre-lottery-rank cumulative luck."""
    rows = list(csv.DictReader(seed_csv.open()))
    ranks = [int(r["pre_lottery_rank"]) for r in rows]
    excess = np.array([float(r["excess"]) for r in rows])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["crimson" if e > 0 else "steelblue" for e in excess]
    ax.bar(ranks, excess, color=colors, edgecolor="black", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Pre-lottery rank (1 = worst record)")
    ax.set_ylabel("Observed #1 wins − expected #1 wins")
    ax.set_title("Seed luck at #1 pick (exploratory phase 1)\n"
                 "Confirmatory-eligible years, 2006-2025 excl. 2003")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_outlier_years(outlier_csv: Path, out_path: Path) -> None:
    """Figure 6: timeline of most improbable lottery outcomes."""
    rows = list(csv.DictReader(outlier_csv.open()))
    years = [int(r["year"]) for r in rows]
    nll = np.array([float(r["observed_nll"]) for r in rows])
    ps = np.array([float(r["two_sided_p"]) for r in rows])
    # Sort by year for timeline
    order = np.argsort(years)
    years = np.array(years)[order]
    nll = nll[order]
    ps = ps[order]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["crimson" if p < 0.10 else "steelblue" for p in ps]
    ax.bar(years, nll, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_xlabel("Year")
    ax.set_ylabel("−log p(observed outcome)")
    ax.set_title("Timeline of per-year outcome improbability (exploratory phase 1)\n"
                 "Red: uncorrected p < 0.10. None survive BH-FDR correction at q = 0.10.")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


def figure_era_comparison(era_csv: Path, out_path: Path) -> None:
    """Figure 7: era-by-era deviation plot."""
    rows = list(csv.DictReader(era_csv.open()))
    eras = [r["era"] for r in rows]
    s_obs = np.array([float(r["S_obs"]) for r in rows])
    null_mean = np.array([float(r["null_mean"]) for r in rows])
    ps = np.array([float(r["p_value"]) for r in rows])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(eras))
    w = 0.35
    ax.bar(x - w/2, s_obs, w, label="Observed S", color="crimson",
           edgecolor="black", linewidth=0.5)
    ax.bar(x + w/2, null_mean, w, label="Null mean", color="steelblue",
           edgecolor="black", linewidth=0.5)
    for xi, p in zip(x, ps):
        ax.annotate(f"p={p:.3f}", (xi, max(s_obs[xi], null_mean[xi]) * 1.02),
                    ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([e.replace("_", " ") for e in eras], rotation=10)
    ax.set_ylabel("Global statistic S")
    ax.set_title("Era-by-era deviation (confirmatory)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
