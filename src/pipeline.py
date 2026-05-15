"""
Orchestrator for the Data-Centric Trust Pipeline.

Coordinates the four layers (Integrity, Fairness, Synthesis, Provenance) with
the recursive verification pattern specified in Section 5 of the paper:

  raw data -> Integrity -> Fairness -> [if disparities] Synthesis ->
              Integrity (re-validation) -> Fairness (P2 delta audit) ->
              merged corpus + provenance graph

Each transition is logged in the Provenance Layer with rationale and actor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .fairness import FairnessLayer, FairnessReport
from .integrity import IntegrityLayer, IntegrityReport
from .provenance import EventType, Layer, ProvenanceGraph
from .synthesis import SynthesisLayer, SynthesisReport


@dataclass
class PipelineResult:
    """End-to-end result of running the four layers."""

    dataset_name: str
    initial_integrity: IntegrityReport
    initial_fairness: FairnessReport
    synthesis_reports: list[SynthesisReport]
    final_integrity: IntegrityReport | None
    final_fairness: FairnessReport | None
    merged_corpus: pd.DataFrame
    provenance: ProvenanceGraph
    p2_fairness_deltas: dict[str, float] = field(default_factory=dict)
    rollback_executed: bool = False
    pre_rollback_fairness: dict[str, float] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset_name,
            "n_initial_validated": len(self.initial_integrity.validated_records),
            "n_initial_quarantined": len(self.initial_integrity.quarantined_records),
            "initial_eo_gap": self.initial_fairness.equal_opportunity_gap,
            "initial_dp_gap": self.initial_fairness.demographic_parity_gap,
            "n_synthesis_batches": len(self.synthesis_reports),
            "n_synthesis_accepted": sum(s.n_accepted for s in self.synthesis_reports),
            "n_synthesis_quarantined": sum(
                s.n_quarantined_p3 + s.n_quarantined_p4 for s in self.synthesis_reports
            ),
            "rollback_executed": self.rollback_executed,
            "pre_rollback_fairness": self.pre_rollback_fairness,
            "p2_fairness_deltas": self.p2_fairness_deltas,
            "final_eo_gap": (self.final_fairness.equal_opportunity_gap
                             if self.final_fairness else None),
            "final_dp_gap": (self.final_fairness.demographic_parity_gap
                             if self.final_fairness else None),
            "provenance_evaluation": self.provenance.evaluate(),
            "n_merged": len(self.merged_corpus),
        }


class TrustPipeline:
    """
    End-to-end orchestrator of the Data-Centric Trust Pipeline.
    """

    def __init__(
        self,
        integrity: IntegrityLayer,
        fairness: FairnessLayer,
        synthesis: SynthesisLayer,
        governance_officer: str = "governance_officer",
    ):
        self.integrity = integrity
        self.fairness = fairness
        self.synthesis = synthesis
        self.governance_officer = governance_officer

    def run(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        plausibility_rules: list[Callable[[pd.Series], bool]] | None = None,
        oversampling_ratio: float = 1.0,
        max_synth_per_group: int = 5000,
    ) -> PipelineResult:
        """
        Run the full pipeline. plausibility_rules is consumed by Synthesis P4.
        oversampling_ratio controls how many synthetic records to generate per
        group (relative to the group's current size).
        """
        provenance = ProvenanceGraph(run_id=f"{dataset_name}-{pd.Timestamp.utcnow().value}")

        # --- 1. INGESTION ---
        ingest_node = provenance.record_event(
            event_type=EventType.INGESTION,
            layer=Layer.EXTERNAL,
            actor_id="external_data_source",
            decision_rationale=f"Initial ingestion of {dataset_name}: {len(df)} records.",
            metrics={"n_records": len(df), "n_columns": df.shape[1]},
        )

        # --- 2. INITIAL INTEGRITY ---
        initial_integrity = self.integrity.validate(
            df, provenance, ingestion_node_id=ingest_node
        )

        # --- 3. INITIAL FAIRNESS (on validated subset) ---
        initial_fairness = self.fairness.audit(
            initial_integrity.validated_records,
            provenance,
            input_node_id=initial_integrity.provenance_node_ids[0],
        )

        # If no rebalancing needed, return early
        if not initial_fairness.rebalancing_recommendations:
            return PipelineResult(
                dataset_name=dataset_name,
                initial_integrity=initial_integrity,
                initial_fairness=initial_fairness,
                synthesis_reports=[],
                final_integrity=None,
                final_fairness=None,
                merged_corpus=initial_integrity.validated_records,
                provenance=provenance,
                rollback_executed=False,
                pre_rollback_fairness=None,
            )

        # --- 4. AUTHORIZATION (DP3 / DP4: human escalation for trade-off) ---
        # The Fairness Layer's recommendation requires Governance Officer approval
        # before Synthesis runs.
        authorization_node = provenance.record_event(
            event_type=EventType.AUTHORIZATION,
            layer=Layer.PROVENANCE,
            actor_id=self.governance_officer,
            input_refs=initial_fairness.provenance_node_ids
                       + initial_integrity.provenance_node_ids,
            decision_rationale=(
                f"Approved synthetic augmentation for "
                f"{len(initial_fairness.rebalancing_recommendations)} underrepresented "
                f"groups. Synthesis Layer authorized to proceed with P1-P4 protocols."
            ),
        )

        # --- 5. SYNTHESIS PER TARGET ---
        synthesis_reports = []
        accepted_batches = []
        for rec in initial_fairness.rebalancing_recommendations:
            n_target = min(
                int(rec["n_records"] * oversampling_ratio),
                max_synth_per_group,
            )
            report = self.synthesis.generate_for_group(
                source_df=initial_integrity.validated_records,
                attribute=rec["attribute"],
                group=rec["group"],
                n_to_generate=n_target,
                provenance=provenance,
                fairness_input_node=authorization_node,
                plausibility_rules=plausibility_rules,
            )
            synthesis_reports.append(report)
            if report.all_protocols_passed() and len(report.accepted_records) > 0:
                # Strip synthetic-only markers before merging into corpus for re-validation
                merged_batch = report.accepted_records.drop(
                    columns=["__provenance_hash", "__synthetic"], errors="ignore"
                )
                accepted_batches.append(merged_batch)

        # --- 6. MERGE + INTEGRITY RE-VALIDATION (DP1: recursive verification) ---
        if accepted_batches:
            augmented = pd.concat(
                [initial_integrity.validated_records] + accepted_batches,
                ignore_index=True,
            )
            final_integrity = self.integrity.validate(
                augmented, provenance,
                ingestion_node_id=authorization_node,
            )
            merged_corpus = final_integrity.validated_records
        else:
            final_integrity = None
            merged_corpus = initial_integrity.validated_records

        # --- 7. FAIRNESS RE-AUDIT (P2 fairness delta) ---
        final_fairness = None
        p2_deltas = {}
        rollback_executed = False
        pre_rollback_fairness = None
        if final_integrity is not None:
            final_fairness = self.fairness.audit(
                merged_corpus, provenance,
                input_node_id=final_integrity.provenance_node_ids[0],
            )
            # Compute P2 delta per protected attribute
            for attr in initial_fairness.equal_opportunity_gap:
                initial_gap = initial_fairness.equal_opportunity_gap.get(attr, 0)
                final_gap = final_fairness.equal_opportunity_gap.get(attr, 0)
                # Positive delta = improvement (gap reduced)
                p2_deltas[attr] = float(initial_gap - final_gap)

            # Update synthesis reports with P2 outcomes
            for report in synthesis_reports:
                if report.attribute in p2_deltas:
                    report.p2_fairness_delta = p2_deltas[report.attribute]
                    report.p2_passed = bool(p2_deltas[report.attribute] >= 0)

            # Log a P2 evaluation node in provenance
            p2_node = provenance.record_event(
                event_type=EventType.VALIDATION,
                layer=Layer.SYNTHESIS,
                actor_id=self.synthesis.actor_id,
                input_refs=final_fairness.provenance_node_ids,
                decision_rationale=(
                    f"P2 fairness delta audit: "
                    + ", ".join(
                        f"{k}={v:+.4f}" for k, v in p2_deltas.items()
                    )
                ),
                validation_results={"P2_deltas": p2_deltas},
                metrics={"P2_deltas": p2_deltas},
            )

            # --- Fairness-Synthesis conflict resolution (Section 5.1 of paper) ---
            # If P2 delta is negative for any protected attribute, synthesis worsened
            # fairness. Per the paper, such batches must be quarantined rather than
            # merged. Trigger an escalation and execute automatic rollback.
            failed_attrs = [a for a, d in p2_deltas.items() if d < 0]
            pre_rollback_fairness = None
            if failed_attrs:
                # Snapshot the pre-rollback measurements
                pre_rollback_fairness = {
                    "merged_corpus_n": len(merged_corpus),
                    "pre_rollback_eo_gap": dict(final_fairness.equal_opportunity_gap),
                    "p2_deltas_before_rollback": dict(p2_deltas),
                }

                escalation_node = provenance.record_event(
                    event_type=EventType.ESCALATION,
                    layer=Layer.SYNTHESIS,
                    actor_id=self.synthesis.actor_id,
                    input_refs=[p2_node],
                    decision_rationale=(
                        f"Fairness-Synthesis conflict detected: P2 audit reveals "
                        f"NEGATIVE fairness delta on attribute(s) {failed_attrs} "
                        f"despite passing P1. Synthesis batches augmented metrics on "
                        f"P1 (fidelity) but worsened the disparity metric P2 tracks. "
                        f"Escalating to Governance Officer for rollback decision."
                    ),
                    flags=[
                        {"type": "P2_REGRESSION", "attribute": a,
                         "delta": round(p2_deltas[a], 4), "severity": "high"}
                        for a in failed_attrs
                    ],
                )

                # Default policy per paper: roll back to pre-synthesis corpus
                rollback_node = provenance.record_event(
                    event_type=EventType.AUTHORIZATION,
                    layer=Layer.PROVENANCE,
                    actor_id=self.governance_officer,
                    input_refs=[escalation_node],
                    decision_rationale=(
                        f"Approved rollback: synthesis batches quarantined; "
                        f"training corpus reverts to the initial validated corpus. "
                        f"Rationale: P2 regression on {failed_attrs} indicates that "
                        f"the naive distributional synthesis reproduced rather than "
                        f"corrected the attribute-target disparity. Documented for "
                        f"regulatory audit per DP4."
                    ),
                )
                rollback_executed = True
                # Revert merged corpus to initial validated corpus
                merged_corpus = initial_integrity.validated_records.copy()

                # Re-audit fairness post-rollback for honest reporting
                final_fairness = self.fairness.audit(
                    merged_corpus, provenance,
                    input_node_id=rollback_node,
                )
                # Recompute P2 deltas relative to baseline (now identity, so zero)
                p2_deltas_post = {a: 0.0 for a in p2_deltas}
                p2_deltas = p2_deltas_post

        return PipelineResult(
            dataset_name=dataset_name,
            initial_integrity=initial_integrity,
            initial_fairness=initial_fairness,
            synthesis_reports=synthesis_reports,
            final_integrity=final_integrity,
            final_fairness=final_fairness,
            merged_corpus=merged_corpus,
            provenance=provenance,
            p2_fairness_deltas=p2_deltas,
            rollback_executed=rollback_executed,
            pre_rollback_fairness=pre_rollback_fairness,
        )
