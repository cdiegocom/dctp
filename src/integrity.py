"""
Integrity Layer of the Data-Centric Trust Pipeline.

Implements the three classes of validation described in Section 5 of the paper:
  1. Structural validation (schema conformance, completeness)
  2. Semantic validation (ontology alignment, contextual consistency)
  3. Consistency validation (cross-field coherence)

Critically, it also computes demographic coverage parity — the metric that
detects when integrity-driven exclusions disproportionately affect protected
groups (the Integrity-Fairness conflict, Section 5.1 of paper).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .provenance import EventType, Layer, ProvenanceGraph


@dataclass
class IntegrityReport:
    """Output of the Integrity Layer: validated data + quality metadata."""

    validated_records: pd.DataFrame
    quarantined_records: pd.DataFrame
    flags: list[dict[str, Any]]
    demographic_coverage: dict[str, dict[str, float]]
    structural_completeness: float
    semantic_consistency: float
    provenance_node_ids: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "n_validated": len(self.validated_records),
            "n_quarantined": len(self.quarantined_records),
            "structural_completeness": round(self.structural_completeness, 4),
            "semantic_consistency": round(self.semantic_consistency, 4),
            "flag_counts": {
                flag_type: sum(1 for f in self.flags if f["type"] == flag_type)
                for flag_type in {f["type"] for f in self.flags}
            },
            "demographic_coverage": self.demographic_coverage,
        }


class IntegrityLayer:
    """
    Validates raw data through structural, semantic, and consistency checks.

    Key innovation vs. standard data quality tools: reports the demographic
    composition of the quarantine pool, which downstream Fairness Layer needs
    to detect the Integrity-Fairness conflict.
    """

    def __init__(
        self,
        schema: dict[str, str],
        protected_attributes: list[str],
        missing_value_sentinels: tuple[Any, ...] = ("?", "", None, "NA", "Unknown"),
        semantic_rules: dict[str, Any] | None = None,
        actor_id: str = "data_steward",
    ):
        """
        Args:
          schema: column_name -> expected dtype ('numeric', 'categorical', 'binary')
          protected_attributes: list of column names treated as protected
          missing_value_sentinels: values to treat as missing during structural check
          semantic_rules: optional dict of column -> validation function or rule
          actor_id: identity of the human/role running this layer (DP3)
        """
        self.schema = schema
        self.protected_attributes = protected_attributes
        self.missing_sentinels = missing_value_sentinels
        self.semantic_rules = semantic_rules or {}
        self.actor_id = actor_id

    def _normalize_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert sentinel values to NaN for uniform handling."""
        df = df.copy()
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.strip()
                df.loc[df[col].isin([str(s) for s in self.missing_sentinels]), col] = np.nan
        return df

    def _structural_validation(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, list[dict[str, Any]]]:
        """Identify records with missing required fields. Returns (mask, flags)."""
        flags = []
        # A record fails structural validation if any *required* field is missing.
        # We treat all schema columns as required.
        missing_mask = df[list(self.schema.keys())].isna().any(axis=1)

        per_column_missing = df[list(self.schema.keys())].isna().sum()
        for col, n_missing in per_column_missing.items():
            if n_missing > 0:
                flags.append({
                    "type": "STRUCTURAL_MISSING",
                    "field": col,
                    "n_records": int(n_missing),
                    "severity": "high" if col in self.protected_attributes else "medium",
                })
        return missing_mask, flags

    def _semantic_validation(
        self, df: pd.DataFrame
    ) -> tuple[pd.Series, list[dict[str, Any]]]:
        """Apply domain-specific consistency rules. Returns (mask, flags)."""
        flags = []
        inconsistent_mask = pd.Series([False] * len(df), index=df.index)

        for col, rule in self.semantic_rules.items():
            if col not in df.columns:
                continue
            if callable(rule):
                col_invalid = ~df[col].apply(rule)
            elif isinstance(rule, set):
                col_invalid = ~df[col].isin(rule) & df[col].notna()
            else:
                continue

            n_invalid = int(col_invalid.sum())
            if n_invalid > 0:
                flags.append({
                    "type": "SEMANTIC_INCONSISTENCY",
                    "field": col,
                    "n_records": n_invalid,
                    "severity": "medium",
                })
                inconsistent_mask = inconsistent_mask | col_invalid

        return inconsistent_mask, flags

    def _demographic_coverage(
        self,
        full_df: pd.DataFrame,
        quarantined_df: pd.DataFrame,
    ) -> dict[str, dict[str, float]]:
        """
        For each protected attribute, compute exclusion rate per group.
        This is the metric that triggers the Integrity-Fairness conflict
        protocol (Section 5.1 of paper).
        """
        coverage = {}
        for attr in self.protected_attributes:
            if attr not in full_df.columns:
                continue
            groups = full_df[attr].dropna().unique()
            group_stats = {}
            for g in groups:
                in_full = (full_df[attr] == g).sum()
                in_quarantine = (quarantined_df[attr] == g).sum() if attr in quarantined_df.columns else 0
                exclusion_rate = in_quarantine / in_full if in_full > 0 else 0.0
                group_stats[str(g)] = {
                    "n_full": int(in_full),
                    "n_quarantined": int(in_quarantine),
                    "exclusion_rate": round(float(exclusion_rate), 4),
                }
            coverage[attr] = group_stats
        return coverage

    def _detect_demographic_skew(
        self, coverage: dict[str, dict[str, float]], threshold_multiplier: float = 2.0
    ) -> list[dict[str, Any]]:
        """
        Flag protected groups whose exclusion rate exceeds threshold_multiplier
        times the majority group's exclusion rate (Integrity-Fairness conflict
        trigger, Table 4 of paper).
        """
        skew_flags = []
        for attr, groups in coverage.items():
            # Find the largest group (majority)
            sorted_groups = sorted(groups.items(), key=lambda x: -x[1]["n_full"])
            if len(sorted_groups) < 2:
                continue
            majority_rate = sorted_groups[0][1]["exclusion_rate"]
            for group_name, stats in groups.items():
                if group_name == sorted_groups[0][0]:
                    continue
                if majority_rate == 0 and stats["exclusion_rate"] > 0:
                    skew_flags.append({
                        "type": "DEMOGRAPHIC_SKEW",
                        "attribute": attr,
                        "group": group_name,
                        "exclusion_rate": stats["exclusion_rate"],
                        "majority_rate": majority_rate,
                        "severity": "high",
                    })
                elif majority_rate > 0 and stats["exclusion_rate"] >= threshold_multiplier * majority_rate:
                    skew_flags.append({
                        "type": "DEMOGRAPHIC_SKEW",
                        "attribute": attr,
                        "group": group_name,
                        "exclusion_rate": stats["exclusion_rate"],
                        "majority_rate": majority_rate,
                        "ratio": round(stats["exclusion_rate"] / majority_rate, 2),
                        "severity": "high",
                    })
        return skew_flags

    def validate(
        self,
        df: pd.DataFrame,
        provenance: ProvenanceGraph,
        ingestion_node_id: str | None = None,
    ) -> IntegrityReport:
        """Run the full Integrity Layer pipeline."""
        df_norm = self._normalize_missing(df)

        struct_mask, struct_flags = self._structural_validation(df_norm)
        sem_mask, sem_flags = self._semantic_validation(df_norm)

        quarantine_mask = struct_mask | sem_mask
        validated = df_norm[~quarantine_mask].reset_index(drop=True)
        quarantined = df_norm[quarantine_mask].reset_index(drop=True)

        structural_completeness = 1 - (struct_mask.sum() / len(df_norm))
        semantic_consistency = 1 - (sem_mask.sum() / len(df_norm))

        coverage = self._demographic_coverage(df_norm, quarantined)
        skew_flags = self._detect_demographic_skew(coverage)
        all_flags = struct_flags + sem_flags + skew_flags

        # Record events in provenance
        node_ids = []
        validation_node = provenance.record_event(
            event_type=EventType.VALIDATION,
            layer=Layer.INTEGRITY,
            actor_id=self.actor_id,
            input_refs=[ingestion_node_id] if ingestion_node_id else [],
            decision_rationale=(
                f"Structural+semantic validation on {len(df_norm)} records. "
                f"Quarantined {quarantine_mask.sum()} records "
                f"({quarantine_mask.sum() / len(df_norm):.1%})."
            ),
            flags=all_flags,
            metrics={
                "n_input": len(df_norm),
                "n_validated": len(validated),
                "n_quarantined": len(quarantined),
                "structural_completeness": round(float(structural_completeness), 4),
                "semantic_consistency": round(float(semantic_consistency), 4),
                "demographic_coverage": coverage,
            },
        )
        node_ids.append(validation_node)

        # If demographic skew detected, automatically log an ESCALATION node
        # (Integrity-Fairness conflict protocol, Section 5.1)
        if skew_flags:
            escalation_node = provenance.record_event(
                event_type=EventType.ESCALATION,
                layer=Layer.INTEGRITY,
                actor_id=self.actor_id,
                input_refs=[validation_node],
                decision_rationale=(
                    f"Integrity-Fairness conflict detected: "
                    f"{len(skew_flags)} protected groups exhibit exclusion rates "
                    f"exceeding 2x the majority group. "
                    f"Escalating to Fairness Analyst before any record removal."
                ),
                flags=skew_flags,
            )
            node_ids.append(escalation_node)

        return IntegrityReport(
            validated_records=validated,
            quarantined_records=quarantined,
            flags=all_flags,
            demographic_coverage=coverage,
            structural_completeness=float(structural_completeness),
            semantic_consistency=float(semantic_consistency),
            provenance_node_ids=node_ids,
        )
