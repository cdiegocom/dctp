"""
Fairness Layer of the Data-Centric Trust Pipeline.

Implements the three formal fairness criteria specified in Section 5 of the paper:
  1. Demographic Parity (Calders & Verwer 2010)
  2. Equal Opportunity (Hardt, Price, Srebro 2016)
  3. Counterfactual Fairness (Kusner et al. 2017) — approximated via matching

Reports per-group disparity metrics that the Synthesis Layer consumes to
target rebalancing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder

from .provenance import EventType, Layer, ProvenanceGraph


@dataclass
class FairnessReport:
    """Output of the Fairness Layer."""

    demographic_parity_gap: dict[str, float]
    equal_opportunity_gap: dict[str, float]
    counterfactual_fairness_score: dict[str, float]
    per_group_metrics: dict[str, dict[str, dict[str, float]]]
    rebalancing_recommendations: list[dict[str, Any]]
    flags: list[dict[str, Any]]
    overall_accuracy: float
    provenance_node_ids: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "demographic_parity_gap": self.demographic_parity_gap,
            "equal_opportunity_gap": self.equal_opportunity_gap,
            "counterfactual_fairness": self.counterfactual_fairness_score,
            "overall_accuracy": round(self.overall_accuracy, 4),
            "rebalancing_targets": [
                f"{r['attribute']}={r['group']}: gap={r['gap']:.3f}"
                for r in self.rebalancing_recommendations
            ],
            "n_flags": len(self.flags),
        }


class FairnessLayer:
    """
    Performs continuous disparity analysis. Unlike a pre-deployment audit, this
    layer is invoked whenever data changes (e.g., after synthesis augmentation)
    to support the recursive verification design principle (DP1).
    """

    def __init__(
        self,
        target_column: str,
        protected_attributes: list[str],
        positive_label: Any = 1,
        max_gap_threshold: float = 0.10,
        actor_id: str = "fairness_analyst",
        random_state: int = 42,
    ):
        """
        Args:
          target_column: the binary outcome to predict
          protected_attributes: columns to evaluate for disparities
          positive_label: which value of the target is the "positive" outcome
          max_gap_threshold: disparities above this trigger rebalancing recommendation
          actor_id: role identity for provenance
        """
        self.target_column = target_column
        self.protected_attributes = protected_attributes
        self.positive_label = positive_label
        self.max_gap = max_gap_threshold
        self.actor_id = actor_id
        self.random_state = random_state
        self._encoders: dict[str, LabelEncoder] = {}

    def _prepare_features(
        self, df: pd.DataFrame, drop_protected: bool = True
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Encode categoricals and return X, y, feature_names."""
        work = df.copy()

        # Encode target
        y = (work[self.target_column].astype(str) == str(self.positive_label)).astype(int).values

        # Choose features
        feature_cols = [
            c for c in work.columns
            if c != self.target_column
            and (c not in self.protected_attributes if drop_protected else True)
        ]

        # Encode categoricals consistently across calls (so synthetic data uses same encoders)
        X_parts = []
        for c in feature_cols:
            if pd.api.types.is_numeric_dtype(work[c]):
                col_vals = pd.to_numeric(work[c], errors="coerce").fillna(0).values
            else:
                col_str = work[c].astype(str).fillna("MISSING")
                if c not in self._encoders:
                    enc = LabelEncoder()
                    enc.fit(list(col_str.unique()) + ["MISSING", "UNSEEN"])
                    self._encoders[c] = enc
                else:
                    enc = self._encoders[c]
                # Map unseen labels to UNSEEN
                col_str = col_str.apply(lambda v: v if v in enc.classes_ else "UNSEEN")
                col_vals = enc.transform(col_str)
            X_parts.append(col_vals.reshape(-1, 1))

        X = np.hstack(X_parts).astype(float)
        return X, y, feature_cols

    def _train_predictor(self, X: np.ndarray, y: np.ndarray):
        """Train a classifier that we'll evaluate for fairness."""
        clf = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=self.random_state, n_jobs=1
        )
        clf.fit(X, y)
        return clf

    def _demographic_parity(
        self, df: pd.DataFrame, y_pred: np.ndarray, attr: str
    ) -> dict[str, float]:
        """P(Y_hat = 1 | A = a) for each group a. Gap = max - min."""
        groups = df[attr].astype(str).values
        rates = {}
        for g in np.unique(groups):
            mask = groups == g
            if mask.sum() > 0:
                rates[g] = float(y_pred[mask].mean())
        return rates

    def _equal_opportunity(
        self, df: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray, attr: str
    ) -> dict[str, float]:
        """TPR = P(Y_hat = 1 | Y = 1, A = a) for each group."""
        groups = df[attr].astype(str).values
        tprs = {}
        for g in np.unique(groups):
            mask = (groups == g) & (y_true == 1)
            if mask.sum() > 0:
                tprs[g] = float(y_pred[mask].mean())
            else:
                tprs[g] = float("nan")
        return tprs

    def _counterfactual_fairness(
        self,
        df: pd.DataFrame,
        X: np.ndarray,
        clf,
        attr: str,
        n_samples: int = 500,
    ) -> float:
        """
        Approximated counterfactual fairness: for a random sample, find nearest
        neighbor of opposite protected-attribute value and compare predictions.

        Returns mean prediction divergence (lower = more counterfactually fair).
        Approximation rationale: matching-based CF (Russell et al. 2017 line of
        work) avoids requiring an explicit causal model, which we don't have
        for the datasets used here.
        """
        groups = df[attr].astype(str).values
        unique_groups = list(np.unique(groups))
        if len(unique_groups) < 2:
            return 0.0

        rng = np.random.default_rng(self.random_state)
        sample_idx = rng.choice(len(df), size=min(n_samples, len(df)), replace=False)

        divergences = []
        for idx in sample_idx:
            current_group = groups[idx]
            other_groups = [g for g in unique_groups if g != current_group]
            for other_group in other_groups:
                other_mask = groups == other_group
                if other_mask.sum() == 0:
                    continue
                # Find nearest neighbor in other group based on features
                nn = NearestNeighbors(n_neighbors=1)
                nn.fit(X[other_mask])
                _, nn_idx = nn.kneighbors(X[idx].reshape(1, -1))
                cf_idx = np.where(other_mask)[0][nn_idx[0, 0]]
                # Compare predictions
                pred_current = clf.predict_proba(X[idx].reshape(1, -1))[0, 1]
                pred_cf = clf.predict_proba(X[cf_idx].reshape(1, -1))[0, 1]
                divergences.append(abs(pred_current - pred_cf))

        return float(np.mean(divergences)) if divergences else 0.0

    def audit(
        self,
        df: pd.DataFrame,
        provenance: ProvenanceGraph,
        input_node_id: str | None = None,
        precomputed_predictor=None,
    ) -> FairnessReport:
        """Run the full fairness audit."""
        X, y, _ = self._prepare_features(df)
        clf = precomputed_predictor or self._train_predictor(X, y)
        y_pred = clf.predict(X)
        accuracy = float(accuracy_score(y, y_pred))

        dp_gaps = {}
        eo_gaps = {}
        cf_scores = {}
        per_group = {}
        rebalancing = []
        flags = []

        for attr in self.protected_attributes:
            if attr not in df.columns:
                continue
            dp_rates = self._demographic_parity(df, y_pred, attr)
            eo_tprs = self._equal_opportunity(df, y, y_pred, attr)
            cf_score = self._counterfactual_fairness(df, X, clf, attr)

            # Filter out NaN TPRs (groups with no positives)
            valid_tprs = {g: v for g, v in eo_tprs.items() if not np.isnan(v)}

            dp_gap = max(dp_rates.values()) - min(dp_rates.values()) if dp_rates else 0
            eo_gap = (max(valid_tprs.values()) - min(valid_tprs.values())) if valid_tprs else 0

            dp_gaps[attr] = float(dp_gap)
            eo_gaps[attr] = float(eo_gap)
            cf_scores[attr] = float(cf_score)

            per_group[attr] = {
                "demographic_parity": {g: round(r, 4) for g, r in dp_rates.items()},
                "equal_opportunity": {g: (round(v, 4) if not np.isnan(v) else None)
                                       for g, v in eo_tprs.items()},
            }

            # Identify groups that need rebalancing (TPR below highest by > threshold)
            if valid_tprs:
                max_tpr_group = max(valid_tprs, key=valid_tprs.get)
                max_tpr = valid_tprs[max_tpr_group]
                for g, tpr in valid_tprs.items():
                    if g == max_tpr_group:
                        continue
                    gap = max_tpr - tpr
                    if gap > self.max_gap:
                        rebalancing.append({
                            "attribute": attr,
                            "group": g,
                            "current_tpr": round(tpr, 4),
                            "reference_tpr": round(max_tpr, 4),
                            "gap": round(gap, 4),
                            "n_records": int((df[attr].astype(str) == g).sum()),
                        })
                        flags.append({
                            "type": "FAIRNESS_DISPARITY",
                            "attribute": attr,
                            "group": g,
                            "metric": "equal_opportunity",
                            "gap": round(gap, 4),
                            "severity": "high",
                        })

        audit_node = provenance.record_event(
            event_type=EventType.FAIRNESS_AUDIT,
            layer=Layer.FAIRNESS,
            actor_id=self.actor_id,
            input_refs=[input_node_id] if input_node_id else [],
            decision_rationale=(
                f"Fairness audit on {len(df)} records. "
                f"Identified {len(rebalancing)} groups requiring rebalancing "
                f"(EO gap > {self.max_gap})."
            ),
            flags=flags,
            metrics={
                "demographic_parity_gap": {k: round(v, 4) for k, v in dp_gaps.items()},
                "equal_opportunity_gap": {k: round(v, 4) for k, v in eo_gaps.items()},
                "counterfactual_fairness": {k: round(v, 4) for k, v in cf_scores.items()},
                "overall_accuracy": round(accuracy, 4),
                "per_group_metrics": per_group,
                "rebalancing_targets": rebalancing,
            },
        )

        return FairnessReport(
            demographic_parity_gap=dp_gaps,
            equal_opportunity_gap=eo_gaps,
            counterfactual_fairness_score=cf_scores,
            per_group_metrics=per_group,
            rebalancing_recommendations=rebalancing,
            flags=flags,
            overall_accuracy=accuracy,
            provenance_node_ids=[audit_node],
        )
