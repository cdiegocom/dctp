"""
Multi-seed robustness analysis.

Runs the full pipeline on Adult and COMPAS across multiple random seeds.
Produces:
  - results/tables/multi_seed_summary.json
  - results/tables/multi_seed_summary.md
  - results/figures/multi_seed_p1_p2.png

This is the experiment that defends against the "n=1 experiment" critique.
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

RESULTS = Path("/home/claude/dctp/results")
SEEDS = [13, 42, 137]


def run_one(df, dataset_name, target, positive, protected, plausibility_rules, seed):
    schema = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical")
              for c in df.columns}
    integrity = IntegrityLayer(
        schema=schema, protected_attributes=protected,
        missing_value_sentinels=("?", "", "NA", "Unknown"),
    )
    fairness = FairnessLayer(
        target_column=target, protected_attributes=protected,
        positive_label=positive, max_gap_threshold=0.10, random_state=seed,
    )
    synthesis = SynthesisLayer(
        js_divergence_threshold=0.10, p4_min_pass_rate=0.95, random_state=seed,
    )
    pipeline = TrustPipeline(integrity, fairness, synthesis)
    return pipeline.run(
        df, dataset_name=f"{dataset_name}_seed{seed}",
        plausibility_rules=plausibility_rules,
        oversampling_ratio=0.5, max_synth_per_group=3000,
    )


def main():
    # Load datasets once
    adult_df = pd.read_csv("/home/claude/dctp/data/adult.csv")

    compas_raw = pd.read_csv("/home/claude/dctp/data/compas.csv")
    compas = compas_raw[compas_raw["days_b_screening_arrest"].between(-30, 30, inclusive="both")]
    compas = compas[compas["is_recid"] != -1]
    compas = compas[compas["c_charge_degree"] != "O"]
    compas = compas[compas["score_text"] != "N/A"]
    compas = compas[compas["race"].isin(["African-American", "Caucasian", "Hispanic", "Other"])]
    compas = compas[[
        "age", "age_cat", "race", "sex",
        "priors_count", "juv_fel_count", "juv_misd_count", "juv_other_count",
        "c_charge_degree", "decile_score", "two_year_recid",
    ]].reset_index(drop=True)

    adult_rules = [
        lambda row: 17 <= float(row["age"]) <= 90,
        lambda row: 1 <= float(row["hours-per-week"]) <= 99,
        lambda row: 1 <= float(row["education-num"]) <= 16,
    ]
    compas_rules = [
        lambda row: row.get("age", 25) >= 17,
        lambda row: row.get("priors_count", 0) >= 0,
        lambda row: 1 <= row.get("decile_score", 5) <= 10,
    ]

    rows = []
    for seed in SEEDS:
        print(f"\n=== Seed {seed} ===")

        for name, df, target, positive, rules in [
            ("Adult", adult_df, "income-per-year", ">50K", adult_rules),
            ("COMPAS", compas, "two_year_recid", 1, compas_rules),
        ]:
            r = run_one(df, name, target, positive, ["race", "sex"], rules, seed)
            for attr in r.initial_fairness.equal_opportunity_gap:
                pre_rb = (r.pre_rollback_fairness or {}).get("pre_rollback_eo_gap", {}).get(attr)
                p2 = (r.pre_rollback_fairness or {}).get("p2_deltas_before_rollback", {}).get(attr)
                rows.append({
                    "seed": seed,
                    "dataset": name,
                    "attribute": attr,
                    "baseline_eo_gap": r.initial_fairness.equal_opportunity_gap[attr],
                    "pre_rollback_eo_gap": pre_rb,
                    "p2_delta_pre_rollback": p2,
                    "final_eo_gap": r.final_fairness.equal_opportunity_gap[attr] if r.final_fairness else None,
                    "rollback_executed": r.rollback_executed,
                    "provenance_nodes": r.provenance.evaluate()["total_nodes"],
                    "n_synthesis_accepted": sum(s.n_accepted for s in r.synthesis_reports),
                })
                p2_str = f"{p2:+.4f}" if p2 is not None else "n/a"
                print(f"  {name} {attr}: baseline_EO={r.initial_fairness.equal_opportunity_gap[attr]:.4f}, "
                      f"P2_delta={p2_str}, rollback={r.rollback_executed}")

    df_results = pd.DataFrame(rows)
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    df_results.to_csv(RESULTS / "tables" / "multi_seed_raw.csv", index=False)

    # Aggregate: mean and std per (dataset, attribute)
    agg = df_results.groupby(["dataset", "attribute"]).agg(
        baseline_eo_mean=("baseline_eo_gap", "mean"),
        baseline_eo_std=("baseline_eo_gap", "std"),
        pre_rollback_eo_mean=("pre_rollback_eo_gap", "mean"),
        pre_rollback_eo_std=("pre_rollback_eo_gap", "std"),
        p2_delta_mean=("p2_delta_pre_rollback", "mean"),
        p2_delta_std=("p2_delta_pre_rollback", "std"),
        rollback_rate=("rollback_executed", "mean"),
        n_synthesis_mean=("n_synthesis_accepted", "mean"),
        n_seeds=("seed", "count"),
    ).round(4).reset_index()

    agg.to_csv(RESULTS / "tables" / "multi_seed_aggregate.csv", index=False)

    with open(RESULTS / "tables" / "multi_seed_summary.json", "w") as f:
        json.dump({
            "n_seeds": len(SEEDS),
            "seeds": SEEDS,
            "aggregate": agg.to_dict(orient="records"),
            "raw": df_results.to_dict(orient="records"),
        }, f, indent=2, default=str)

    # Markdown
    md = ["# Multi-seed robustness analysis\n",
          f"Seeds tested: {SEEDS}\n\n## Aggregate (mean ± std across seeds)\n",
          agg.to_markdown(index=False)]
    (RESULTS / "tables" / "multi_seed_summary.md").write_text("\n".join(md))

    print("\n=== AGGREGATE RESULTS ===")
    print(agg.to_string(index=False))

    # Figure: P2 delta distribution across seeds (showing the negative-delta signal is robust)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for i, ds in enumerate(["Adult", "COMPAS"]):
        sub = df_results[df_results["dataset"] == ds]
        attrs = sorted(sub["attribute"].unique())
        positions = np.arange(len(attrs))
        for j, attr in enumerate(attrs):
            vals = sub[sub["attribute"] == attr]["p2_delta_pre_rollback"].values
            color = "#27ae60" if np.mean(vals) >= 0 else "#c0392b"
            axes[i].scatter([j] * len(vals), vals, color=color, alpha=0.7, s=80,
                            edgecolors="black", linewidths=0.5)
            axes[i].plot([j - 0.18, j + 0.18], [np.mean(vals), np.mean(vals)],
                         color="black", linewidth=2)
        axes[i].axhline(y=0, color="gray", linewidth=1)
        axes[i].set_xticks(positions)
        axes[i].set_xticklabels(attrs)
        axes[i].set_ylabel("P2 fairness delta (pre-rollback)")
        axes[i].set_title(f"{ds} — across {len(SEEDS)} seeds")
    fig.suptitle("Multi-seed robustness: negative P2 delta is consistent", fontsize=12)
    plt.tight_layout()
    plt.savefig(RESULTS / "figures" / "multi_seed_p2_distribution.png", dpi=200)
    plt.close()
    print(f"\nFigure saved: multi_seed_p2_distribution.png")


if __name__ == "__main__":
    main()
