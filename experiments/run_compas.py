"""
Full experiment on the COMPAS recidivism dataset (Propublica analysis).

A second canonical fairness benchmark to demonstrate cross-domain applicability.
Produces:
  - results/tables/compas_summary.json
  - results/provenance_graphs/compas_full.json
  - results/figures/compas_*.png
"""

import json
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import FairnessLayer, IntegrityLayer, SynthesisLayer, TrustPipeline

DATA_PATH = Path("/home/claude/dctp/data/compas.csv")
RESULTS = Path("/home/claude/dctp/results")
SEED = 42

# Plausibility rules for COMPAS:
#  - age >= 17
#  - priors_count >= 0
#  - decile_score in [1, 10]
PLAUSIBILITY_RULES = [
    lambda row: row.get("age", 25) >= 17,
    lambda row: row.get("priors_count", 0) >= 0,
    lambda row: 1 <= row.get("decile_score", 5) <= 10,
]


def prepare_compas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standard ProPublica COMPAS preprocessing:
      - Filter to cases where days_b_screening_arrest is in [-30, 30]
      - Drop missing essentials
      - Keep predictive features + protected attributes + target
    """
    df = df[df["days_b_screening_arrest"].between(-30, 30, inclusive="both")].copy()
    df = df[df["is_recid"] != -1]  # exclude -1 sentinel
    df = df[df["c_charge_degree"] != "O"]  # exclude ordinance violations
    df = df[df["score_text"] != "N/A"]

    # Filter to two main racial groups for cleaner per-group analysis
    df = df[df["race"].isin(["African-American", "Caucasian", "Hispanic", "Other"])]

    cols = [
        "age", "age_cat", "race", "sex",
        "priors_count", "juv_fel_count", "juv_misd_count", "juv_other_count",
        "c_charge_degree", "decile_score", "two_year_recid",
    ]
    return df[cols].reset_index(drop=True)


def main():
    print(f"Loading COMPAS from {DATA_PATH}")
    df_raw = pd.read_csv(DATA_PATH)
    print(f"Raw shape: {df_raw.shape}")

    df = prepare_compas(df_raw)
    print(f"Filtered shape: {df.shape}")
    print(f"Target distribution:\n{df['two_year_recid'].value_counts()}")
    print(f"\nRace distribution:\n{df['race'].value_counts()}")

    schema = {
        c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical")
        for c in df.columns
    }

    integrity = IntegrityLayer(
        schema=schema,
        protected_attributes=["race", "sex"],
        missing_value_sentinels=("?", "", "NA", "Unknown"),
    )
    fairness = FairnessLayer(
        target_column="two_year_recid",
        protected_attributes=["race", "sex"],
        positive_label=1,
        max_gap_threshold=0.10,
        random_state=SEED,
    )
    synthesis = SynthesisLayer(
        js_divergence_threshold=0.10,
        p4_min_pass_rate=0.95,
        random_state=SEED,
    )

    pipeline = TrustPipeline(integrity, fairness, synthesis)
    print("\nRunning pipeline on COMPAS...")
    result = pipeline.run(
        df,
        dataset_name="compas_full",
        plausibility_rules=PLAUSIBILITY_RULES,
        oversampling_ratio=0.5,
        max_synth_per_group=3000,
    )

    summary = result.summary()
    summary["per_synthesis_batch"] = [r.summary() for r in result.synthesis_reports]
    summary["initial_demographic_coverage"] = result.initial_integrity.demographic_coverage
    summary["initial_per_group_metrics"] = result.initial_fairness.per_group_metrics
    summary["rollback_executed"] = result.rollback_executed
    if result.pre_rollback_fairness:
        summary["pre_rollback_fairness"] = result.pre_rollback_fairness
    if result.final_fairness:
        summary["final_per_group_metrics"] = result.final_fairness.per_group_metrics

    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "tables" / "compas_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSummary saved.")

    result.provenance.save(RESULTS / "provenance_graphs" / "compas_full.json")
    print("Provenance saved.")

    # ---------- figures ----------

    figdir = RESULTS / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 11, "figure.dpi": 120})

    # EO gap before/after
    fig, ax = plt.subplots(figsize=(7, 4.5))
    attrs = list(result.initial_fairness.equal_opportunity_gap.keys())
    initial_gaps = [result.initial_fairness.equal_opportunity_gap[a] for a in attrs]
    final_gaps = ([result.final_fairness.equal_opportunity_gap[a] for a in attrs]
                  if result.final_fairness else [0] * len(attrs))
    x = np.arange(len(attrs))
    w = 0.35
    ax.bar(x - w / 2, initial_gaps, w, label="Baseline (before pipeline)", color="#c0392b")
    ax.bar(x + w / 2, final_gaps, w, label="After pipeline", color="#27ae60")
    ax.axhline(y=0.10, color="gray", linestyle="--", linewidth=1, label="Threshold (0.10)")
    ax.set_xticks(x)
    ax.set_xticklabels([a.capitalize() for a in attrs])
    ax.set_ylabel("Equal Opportunity Gap")
    ax.set_title("COMPAS Recidivism — Disparity outcomes under pipeline governance")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figdir / "compas_eo_gap.png", dpi=300)
    plt.close()
    print("Figure saved: compas_eo_gap.png")

    # Per-group TPR
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for i, attr in enumerate(attrs):
        before = result.initial_fairness.per_group_metrics[attr]["equal_opportunity"]
        after = (result.final_fairness.per_group_metrics[attr]["equal_opportunity"]
                 if result.final_fairness else before)
        groups = list(before.keys())
        before_vals = [before[g] if before[g] is not None else 0 for g in groups]
        after_vals = [after.get(g, 0) if after.get(g) is not None else 0 for g in groups]
        x = np.arange(len(groups))
        axes[i].bar(x - 0.2, before_vals, 0.4, label="Before", color="#c0392b", alpha=0.8)
        axes[i].bar(x + 0.2, after_vals, 0.4, label="After", color="#27ae60", alpha=0.8)
        axes[i].set_xticks(x)
        axes[i].set_xticklabels(groups, rotation=30, ha="right")
        axes[i].set_ylabel("True Positive Rate")
        axes[i].set_title(f"By {attr}")
        axes[i].legend()
    fig.suptitle("COMPAS — Per-group equal opportunity")
    plt.tight_layout()
    plt.savefig(figdir / "compas_per_group_tpr.png", dpi=300)
    plt.close()
    print("Figure saved: compas_per_group_tpr.png")

    # P1 divergences
    p1_vals = [r.p1_js_divergence for r in result.synthesis_reports
               if not np.isnan(r.p1_js_divergence)]
    labels = [f"{r.attribute}={r.group}" for r in result.synthesis_reports
              if not np.isnan(r.p1_js_divergence)]
    if p1_vals:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.barh(labels, p1_vals, color=["#27ae60" if v <= 0.10 else "#c0392b"
                                         for v in p1_vals])
        ax.axvline(x=0.10, color="black", linestyle="--", linewidth=1, label="P1 threshold (0.10)")
        ax.set_xlabel("Jensen-Shannon divergence")
        ax.set_title("COMPAS — Protocol P1 outcomes per synthesis batch")
        ax.legend()
        plt.tight_layout()
        plt.savefig(figdir / "compas_p1_divergence.png", dpi=300)
        plt.close()
        print("Figure saved: compas_p1_divergence.png")

    print("\n=== COMPAS experiment complete ===")
    print(json.dumps({k: v for k, v in summary.items()
                      if k in ("dataset", "n_initial_validated", "initial_eo_gap",
                               "final_eo_gap", "p2_fairness_deltas",
                               "n_synthesis_accepted", "rollback_executed",
                               "provenance_evaluation")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
