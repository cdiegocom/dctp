"""Run pipeline for a single (dataset, seed, backend) tuple and append to a CSV.

Extends single_seed.py to support the three synthesizer backends:
  - gaussian_copula (default; used in the primary results)
  - ctgan
  - tvae
"""

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import FairnessLayer, IntegrityLayer, SynthesisLayer, TrustPipeline

RESULTS = Path("/home/claude/dctp/results")


def run(dataset, seed, backend, epochs, adult_sample=None):
    if dataset == "adult":
        df = pd.read_csv("/home/claude/dctp/data/adult.csv")
        if adult_sample is not None and adult_sample < len(df):
            df = df.sample(n=adult_sample, random_state=seed).reset_index(drop=True)
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
        js_divergence_threshold=0.10, p4_min_pass_rate=0.95,
        random_state=seed,
        backend=backend, ctgan_epochs=epochs, tvae_epochs=epochs,
    )
    pipeline = TrustPipeline(integrity, fairness, synthesis)
    return pipeline.run(
        df, dataset_name=f"{dataset}_{backend}_seed{seed}",
        plausibility_rules=rules,
        oversampling_ratio=0.5, max_synth_per_group=3000,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=["adult", "compas"])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--backend", required=True,
        choices=["gaussian_copula", "ctgan", "tvae"],
    )
    parser.add_argument("--epochs", type=int, default=150,
                        help="Training epochs for CTGAN/TVAE (ignored for Copula)")
    parser.add_argument("--adult-sample", type=int, default=None,
                        help="Optional subsample size for Adult (for CTGAN/TVAE speedup)")
    args = parser.parse_args()

    r = run(args.dataset, args.seed, args.backend, args.epochs, args.adult_sample)

    rows = []
    for attr in r.initial_fairness.equal_opportunity_gap:
        # P2 delta is available either via pre_rollback_fairness (when rollback fired)
        # or via the pipeline result's p2_fairness_deltas (which is post-rollback,
        # i.e. zero, so we prefer the pre-rollback snapshot when available).
        n_accepted = sum(s.n_accepted for s in r.synthesis_reports)
        if r.rollback_executed and r.pre_rollback_fairness:
            pre_rb = r.pre_rollback_fairness["pre_rollback_eo_gap"].get(attr)
            p2 = r.pre_rollback_fairness["p2_deltas_before_rollback"].get(attr)
        elif r.synthesis_reports and n_accepted > 0:
            # Synthesis ran without rollback: use final_eo_gap directly
            pre_rb = r.final_fairness.equal_opportunity_gap.get(attr) if r.final_fairness else None
            p2 = r.initial_fairness.equal_opportunity_gap.get(attr, 0) - (pre_rb or 0)
        else:
            # No batch survived P1 — there is no merged synthesis to evaluate P2 on
            pre_rb, p2 = None, None
        # Per-batch P1 outcomes for this run
        p1_pass_count = sum(1 for s in r.synthesis_reports if s.p1_passed)
        p1_total = len(r.synthesis_reports)
        rows.append({
            "seed": args.seed,
            "dataset": args.dataset,
            "backend": args.backend,
            "attribute": attr,
            "baseline_eo_gap": r.initial_fairness.equal_opportunity_gap[attr],
            "pre_rollback_eo_gap": pre_rb,
            "p2_delta_pre_rollback": p2,
            "final_eo_gap": r.final_fairness.equal_opportunity_gap[attr] if r.final_fairness else None,
            "rollback_executed": r.rollback_executed,
            "provenance_nodes": r.provenance.evaluate()["total_nodes"],
            "n_synthesis_accepted": sum(s.n_accepted for s in r.synthesis_reports),
            "p1_pass_count": p1_pass_count,
            "p1_total": p1_total,
        })

    csv_path = RESULTS / "tables" / "multi_backend_raw.csv"
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame(rows)
    if csv_path.exists():
        existing = pd.read_csv(csv_path)
        df_all = pd.concat([existing, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(
            subset=["seed", "dataset", "backend", "attribute"], keep="last"
        )
    else:
        df_all = df_new
    df_all.to_csv(csv_path, index=False)
    print(f"\n=== {args.dataset.upper()} {args.backend} seed={args.seed} ===")
    for _, row in df_new.iterrows():
        p2_str = f"{row['p2_delta_pre_rollback']:+.4f}" if pd.notna(row['p2_delta_pre_rollback']) else "n/a"
        print(f"  {row['attribute']}: baseline_EO={row['baseline_eo_gap']:.4f}, "
              f"P2={p2_str}, P1_pass={row['p1_pass_count']}/{row['p1_total']}, "
              f"rollback={row['rollback_executed']}")


if __name__ == "__main__":
    main()
