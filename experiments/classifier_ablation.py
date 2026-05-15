"""
Logistic Regression ablation for the Fairness Layer's audit classifier.

Re-runs the multi-seed analysis with Logistic Regression in place of the default
Random Forest to verify the empirical claim that the P2 sign pattern is driven by
the underlying attribute-target relationship, not by the classifier's hypothesis
class. Addresses a reviewer concern about classifier ablation.

Usage:
    python experiments/classifier_ablation.py

Output:
    results/tables/classifier_ablation_raw.csv
    results/tables/classifier_ablation_aggregate.csv
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src import FairnessLayer, IntegrityLayer, SynthesisLayer, TrustPipeline

_ORIG = FairnessLayer._train_predictor


def _train_predictor_lr(self, X: np.ndarray, y: np.ndarray):
    # Edge case: empty input or single-class — return a dummy that always predicts majority
    if len(X) < 10 or len(np.unique(y)) < 2:
        majority = int(np.bincount(y.astype(int)).argmax()) if len(y) > 0 else 0

        class _Dummy:
            def predict(self, X):
                return np.full(len(X), majority, dtype=int)

            def predict_proba(self, X):
                out = np.zeros((len(X), 2))
                out[:, majority] = 1.0
                return out

        return _Dummy()
    scaler = StandardScaler(with_mean=False)
    Xs = scaler.fit_transform(X)
    clf = LogisticRegression(max_iter=2000, random_state=self.random_state, n_jobs=1)
    clf.fit(Xs, y)

    class _Wrap:
        def __init__(self, scaler, clf):
            self._s = scaler
            self._c = clf

        def predict(self, X):
            return self._c.predict(self._s.transform(X))

        def predict_proba(self, X):
            return self._c.predict_proba(self._s.transform(X))

    return _Wrap(scaler, clf)


FairnessLayer._train_predictor = _train_predictor_lr


SEEDS = [13, 42, 137]
DATA = Path(__file__).resolve().parents[1] / "data"
TABLES = Path(__file__).resolve().parents[1] / "results" / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

ADULT_PLAUSIBILITY = [
    lambda row: 17 <= float(row["age"]) <= 90,
    lambda row: 1 <= float(row["hours-per-week"]) <= 99,
    lambda row: 1 <= float(row["education-num"]) <= 16,
]
COMPAS_PLAUSIBILITY = [
    lambda row: 17 <= float(row["age"]),
    lambda row: 0 <= float(row["priors_count"]),
    lambda row: 1 <= float(row["decile_score"]) <= 10,
]


def run_one(dataset, seed):
    print(f"  {dataset} seed={seed} ...", end=" ", flush=True)
    if dataset == "adult":
        df = pd.read_csv(DATA / "adult.csv")
        target = "income-per-year"
        pos = ">50K"
        plaus = ADULT_PLAUSIBILITY
    else:
        df = pd.read_csv(DATA / "compas.csv")
        # Apply ProPublica's standard filter, same as single_seed.py
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
        target = "two_year_recid"
        pos = 1
        plaus = COMPAS_PLAUSIBILITY

    schema = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical") for c in df.columns}
    integrity = IntegrityLayer(
        schema=schema, protected_attributes=["race", "sex"],
        missing_value_sentinels=("?", "", "NA", "Unknown", " ?"),
    )
    fairness = FairnessLayer(
        target_column=target, protected_attributes=["race", "sex"],
        positive_label=pos, max_gap_threshold=0.10, random_state=seed,
    )
    synthesis = SynthesisLayer(
        js_divergence_threshold=0.10, p4_min_pass_rate=0.95, random_state=seed,
    )
    pipeline = TrustPipeline(integrity, fairness, synthesis)
    result = pipeline.run(
        df, dataset_name=f"{dataset}_lr_{seed}", plausibility_rules=plaus,
        oversampling_ratio=0.5, max_synth_per_group=3000,
    )

    rows = []
    baseline = result.initial_fairness.equal_opportunity_gap
    # pre_rollback_fairness is a nested dict: {merged_corpus_n, pre_rollback_eo_gap, p2_deltas_before_rollback}
    pre = (
        result.pre_rollback_fairness.get("pre_rollback_eo_gap", baseline)
        if result.pre_rollback_fairness else baseline
    )
    final = result.final_fairness.equal_opportunity_gap if result.final_fairness else baseline
    for attr in ("race", "sex"):
        b = baseline.get(attr, 0.0)
        p = pre.get(attr, b) if isinstance(pre, dict) else b
        f = final.get(attr, b)
        rows.append({
            "dataset": dataset, "seed": seed, "classifier": "logistic_regression",
            "attribute": attr, "baseline_eo_gap": b, "pre_rollback_eo_gap": p,
            "p2_delta_pre_rollback": b - p, "final_eo_gap": f,
            "rollback_executed": result.rollback_executed,
        })
    print("done")
    return rows


def main():
    print("=== Logistic Regression classifier ablation ===")
    rows = []
    for ds in ("adult", "compas"):
        for s in SEEDS:
            rows.extend(run_one(ds, s))
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "classifier_ablation_raw.csv", index=False)
    agg = (
        df.groupby(["dataset", "attribute"])
        .agg(
            baseline_mean=("baseline_eo_gap", "mean"),
            pre_rollback_mean=("pre_rollback_eo_gap", "mean"),
            p2_mean=("p2_delta_pre_rollback", "mean"),
            p2_std=("p2_delta_pre_rollback", "std"),
            seeds_negative=("p2_delta_pre_rollback", lambda x: int((x < 0).sum())),
            n=("p2_delta_pre_rollback", "count"),
        )
        .reset_index()
    )
    agg.to_csv(TABLES / "classifier_ablation_aggregate.csv", index=False)
    print("\n--- AGGREGATE ---")
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
