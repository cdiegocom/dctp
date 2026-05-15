"""Run pipeline for a single (dataset, seed) pair and append to a CSV."""

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import FairnessLayer, IntegrityLayer, SynthesisLayer, TrustPipeline

RESULTS = Path("/home/claude/dctp/results")


def run(dataset, seed):
    if dataset == "adult":
        df = pd.read_csv("/home/claude/dctp/data/adult.csv")
        target, positive = "income-per-year", ">50K"
        rules = [
            lambda row: 17 <= float(row["age"]) <= 90,
            lambda row: 1 <= float(row["hours-per-week"]) <= 99,
            lambda row: 1 <= float(row["education-num"]) <= 16,
        ]
    elif dataset == "compas":
        df = pd.read_csv("/home/claude/dctp/data/compas.csv")
        df = df[df["days_b_screening_arrest"].between(-30, 30, inclusive="both")]
        df = df[df["is_recid"] != -1]
        df = df[df["c_charge_degree"] != "O"]
        df = df[df["score_text"] != "N/A"]
        df = df[df["race"].isin(["African-American", "Caucasian", "Hispanic", "Other"])]
        df = df[[
            "age", "age_cat", "race", "sex",
            "priors_count", "juv_fel_count", "juv_misd_count", "juv_other_count",
            "c_charge_degree", "decile_score", "two_year_recid",
        ]].reset_index(drop=True)
        target, positive = "two_year_recid", 1
        rules = [
            lambda row: row.get("age", 25) >= 17,
            lambda row: row.get("priors_count", 0) >= 0,
            lambda row: 1 <= row.get("decile_score", 5) <= 10,
        ]

    schema = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical")
              for c in df.columns}
    integrity = IntegrityLayer(
        schema=schema, protected_attributes=["race", "sex"],
        missing_value_sentinels=("?", "", "NA", "Unknown"),
    )
    fairness = FairnessLayer(
        target_column=target, protected_attributes=["race", "sex"],
        positive_label=positive, max_gap_threshold=0.10, random_state=seed,
    )
    synthesis = SynthesisLayer(
        js_divergence_threshold=0.10, p4_min_pass_rate=0.95, random_state=seed,
    )
    pipeline = TrustPipeline(integrity, fairness, synthesis)
    return pipeline.run(
        df, dataset_name=f"{dataset}_seed{seed}",
        plausibility_rules=rules,
        oversampling_ratio=0.5, max_synth_per_group=3000,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=["adult", "compas"])
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()

    r = run(args.dataset, args.seed)

    rows = []
    for attr in r.initial_fairness.equal_opportunity_gap:
        pre_rb = (r.pre_rollback_fairness or {}).get("pre_rollback_eo_gap", {}).get(attr)
        p2 = (r.pre_rollback_fairness or {}).get("p2_deltas_before_rollback", {}).get(attr)
        rows.append({
            "seed": args.seed,
            "dataset": args.dataset,
            "attribute": attr,
            "baseline_eo_gap": r.initial_fairness.equal_opportunity_gap[attr],
            "pre_rollback_eo_gap": pre_rb,
            "p2_delta_pre_rollback": p2,
            "final_eo_gap": r.final_fairness.equal_opportunity_gap[attr] if r.final_fairness else None,
            "rollback_executed": r.rollback_executed,
            "provenance_nodes": r.provenance.evaluate()["total_nodes"],
            "n_synthesis_accepted": sum(s.n_accepted for s in r.synthesis_reports),
        })

    csv_path = RESULTS / "tables" / "multi_seed_raw.csv"
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame(rows)
    if csv_path.exists():
        existing = pd.read_csv(csv_path)
        df_all = pd.concat([existing, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(subset=["seed", "dataset", "attribute"], keep="last")
    else:
        df_all = df_new
    df_all.to_csv(csv_path, index=False)
    print(f"\n=== {args.dataset.upper()} seed={args.seed} ===")
    for _, row in df_new.iterrows():
        p2_str = f"{row['p2_delta_pre_rollback']:+.4f}" if pd.notna(row['p2_delta_pre_rollback']) else "n/a"
        print(f"  {row['attribute']}: baseline_EO={row['baseline_eo_gap']:.4f}, "
              f"P2={p2_str}, rollback={row['rollback_executed']}")


if __name__ == "__main__":
    main()
