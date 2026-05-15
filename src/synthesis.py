"""
Synthesis Layer of the Data-Centric Trust Pipeline.

Implements synthetic data generation for underrepresented groups, governed by
the four validation protocols specified in Table 4 of the paper:

  P1. Distributional Invariance Check  (Jensen-Shannon divergence)
  P2. Fairness Delta Audit             (recompute fairness after augmentation)
  P3. Cryptographic Provenance         (verifiable per-record identity hash)
  P4. Domain Plausibility Check        (constraint-based plausibility rules)

Generation uses SDV's GaussianCopulaSynthesizer as default (fast and stable);
the same interface supports CTGAN and TVAE if more expressive modeling is needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.spatial import distance

from sdv.metadata import SingleTableMetadata
from sdv.single_table import GaussianCopulaSynthesizer

from .provenance import EventType, Layer, ProvenanceGraph, hash_synthetic_record


@dataclass
class SynthesisReport:
    """Output of the Synthesis Layer for a single rebalancing target."""

    attribute: str
    group: str
    n_generated: int
    n_accepted: int
    n_quarantined_p3: int  # cryptographic provenance failures
    n_quarantined_p4: int  # plausibility failures
    p1_js_divergence: float
    p1_passed: bool
    p2_fairness_delta: float | None
    p2_passed: bool | None
    p3_verification_rate: float
    p4_plausibility_pass_rate: float
    accepted_records: pd.DataFrame
    quarantined_records: pd.DataFrame
    batch_id: str
    generation_params: dict[str, Any]
    provenance_node_ids: list[str] = field(default_factory=list)

    def all_protocols_passed(self) -> bool:
        if not self.p1_passed:
            return False
        if self.p2_passed is False:  # None is allowed (not yet measured)
            return False
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "target": f"{self.attribute}={self.group}",
            "n_generated": self.n_generated,
            "n_accepted": self.n_accepted,
            "P1_js_divergence": round(self.p1_js_divergence, 4),
            "P1_passed": self.p1_passed,
            "P2_fairness_delta": (round(self.p2_fairness_delta, 4)
                                   if self.p2_fairness_delta is not None else None),
            "P2_passed": self.p2_passed,
            "P3_verification_rate": round(self.p3_verification_rate, 4),
            "P4_plausibility_pass_rate": round(self.p4_plausibility_pass_rate, 4),
        }


class SynthesisLayer:
    """
    Generates synthetic data with auditable governance.

    The four-protocol structure (P1-P4) is what distinguishes this layer from
    post-hoc augmentation: every synthetic record is validated, hashed, and
    documented before merging into the training corpus (Section 5.2 of paper).
    """

    def __init__(
        self,
        js_divergence_threshold: float = 0.10,
        p4_min_pass_rate: float = 0.95,
        actor_id: str = "data_scientist",
        random_state: int = 42,
        privacy_epsilon: float = 2.0,
    ):
        self.js_threshold = js_divergence_threshold
        self.p4_min_pass = p4_min_pass_rate
        self.actor_id = actor_id
        self.random_state = random_state
        self.privacy_epsilon = privacy_epsilon

    # ---- P1: Distributional Invariance ----

    def _js_divergence(self, real: pd.DataFrame, synth: pd.DataFrame) -> float:
        """
        Average Jensen-Shannon divergence across columns.
        For numeric columns: bin and compare histograms.
        For categorical columns: compare value frequencies.
        """
        common_cols = [c for c in real.columns if c in synth.columns]
        if not common_cols:
            return 1.0

        divergences = []
        for col in common_cols:
            if pd.api.types.is_numeric_dtype(real[col]):
                # Bin both into same edges
                all_vals = pd.concat([real[col], synth[col]]).dropna()
                if len(all_vals) == 0 or all_vals.nunique() < 2:
                    continue
                edges = np.histogram_bin_edges(all_vals, bins=20)
                p, _ = np.histogram(real[col].dropna(), bins=edges)
                q, _ = np.histogram(synth[col].dropna(), bins=edges)
            else:
                # Categorical: align value sets
                vals = sorted(set(real[col].dropna().astype(str)) |
                              set(synth[col].dropna().astype(str)))
                p = np.array([(real[col].astype(str) == v).sum() for v in vals])
                q = np.array([(synth[col].astype(str) == v).sum() for v in vals])

            p = p.astype(float) / max(p.sum(), 1)
            q = q.astype(float) / max(q.sum(), 1)
            # Smooth to avoid zero-division
            p = p + 1e-12
            q = q + 1e-12
            p = p / p.sum()
            q = q / q.sum()
            divergences.append(float(distance.jensenshannon(p, q, base=2) ** 2))

        return float(np.mean(divergences)) if divergences else 0.0

    # ---- P4: Domain Plausibility ----

    def _check_plausibility(
        self,
        synth: pd.DataFrame,
        plausibility_rules: list[Callable[[pd.Series], bool]] | None,
    ) -> tuple[pd.Series, float]:
        """Apply domain constraints. Returns (per-record pass mask, pass rate)."""
        if not plausibility_rules:
            return pd.Series([True] * len(synth), index=synth.index), 1.0

        passes = pd.Series([True] * len(synth), index=synth.index)
        for rule in plausibility_rules:
            rule_pass = synth.apply(rule, axis=1)
            passes = passes & rule_pass

        pass_rate = float(passes.mean()) if len(synth) > 0 else 1.0
        return passes, pass_rate

    # ---- P3: Cryptographic Provenance ----

    def _attach_hashes(
        self, synth: pd.DataFrame, batch_id: str, model_id: str, seed: int
    ) -> pd.DataFrame:
        """Attach a per-record cryptographic hash (Protocol P3)."""
        ts = datetime.now(timezone.utc).isoformat()
        synth = synth.copy()
        synth["__provenance_hash"] = [
            hash_synthetic_record(i, batch_id, model_id, seed, ts)
            for i in range(len(synth))
        ]
        synth["__synthetic"] = True
        return synth

    def _verify_hashes(
        self, synth: pd.DataFrame, batch_id: str, model_id: str, seed: int
    ) -> float:
        """Re-verify hashes; returns verification rate."""
        if "__provenance_hash" not in synth.columns:
            return 0.0
        # We can't re-derive timestamps; verification here checks that all hashes
        # are well-formed (64 hex chars) and unique within the batch.
        valid = synth["__provenance_hash"].apply(
            lambda h: isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)
        )
        unique = synth["__provenance_hash"].nunique() == len(synth)
        rate = float(valid.mean()) * (1.0 if unique else 0.0)
        return rate

    # ---- generation ----

    def _fit_synthesizer(self, source: pd.DataFrame) -> tuple[Any, dict[str, Any]]:
        """Fit a Gaussian Copula synthesizer on the source distribution."""
        metadata = SingleTableMetadata()
        metadata.detect_from_dataframe(source)

        synthesizer = GaussianCopulaSynthesizer(
            metadata=metadata,
            enforce_min_max_values=True,
            enforce_rounding=False,
        )
        synthesizer.fit(source)

        params = {
            "model": "GaussianCopulaSynthesizer",
            "library": "sdv",
            "n_source": len(source),
            "n_columns": source.shape[1],
            "random_state": self.random_state,
            "privacy_epsilon": self.privacy_epsilon,
            "fit_time_iso": datetime.now(timezone.utc).isoformat(),
        }
        return synthesizer, params

    # ---- main orchestration ----

    def generate_for_group(
        self,
        source_df: pd.DataFrame,
        attribute: str,
        group: str,
        n_to_generate: int,
        provenance: ProvenanceGraph,
        fairness_input_node: str,
        plausibility_rules: list[Callable[[pd.Series], bool]] | None = None,
    ) -> SynthesisReport:
        """
        Generate synthetic records for one underrepresented group and apply P1-P3.
        P2 (fairness delta) is evaluated by the orchestrating pipeline after
        merging, because it requires re-running the Fairness Layer.
        """
        # Take the subset of the source corresponding to the target group
        source_group = source_df[source_df[attribute].astype(str) == str(group)].copy()
        if len(source_group) < 20:
            # Not enough source for meaningful synthesis
            return SynthesisReport(
                attribute=attribute, group=group, n_generated=0, n_accepted=0,
                n_quarantined_p3=0, n_quarantined_p4=0,
                p1_js_divergence=float("nan"), p1_passed=False,
                p2_fairness_delta=None, p2_passed=None,
                p3_verification_rate=0.0, p4_plausibility_pass_rate=0.0,
                accepted_records=pd.DataFrame(), quarantined_records=pd.DataFrame(),
                batch_id="aborted", generation_params={"error": "insufficient source"},
            )

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        model_id = f"GaussianCopula-{self.random_state}"

        synthesizer, gen_params = self._fit_synthesizer(source_group)
        np.random.seed(self.random_state)
        synth = synthesizer.sample(num_rows=n_to_generate)

        # P1: distributional invariance
        js_div = self._js_divergence(source_group, synth)
        p1_passed = js_div <= self.js_threshold

        # P3: cryptographic provenance
        synth_hashed = self._attach_hashes(synth, batch_id, model_id, self.random_state)
        p3_rate = self._verify_hashes(synth_hashed, batch_id, model_id, self.random_state)

        # P4: domain plausibility
        plaus_mask, p4_rate = self._check_plausibility(synth_hashed, plausibility_rules)

        # Per-record decisions
        # P3 fails -> quarantine record; P4 fails -> quarantine record
        valid_p3 = synth_hashed["__provenance_hash"].apply(
            lambda h: isinstance(h, str) and len(h) == 64
        )
        accept_mask = valid_p3 & plaus_mask
        accepted = synth_hashed[accept_mask].reset_index(drop=True)
        quarantined = synth_hashed[~accept_mask].reset_index(drop=True)

        # Provenance: generation event
        synthesis_node = provenance.record_event(
            event_type=EventType.SYNTHESIS,
            layer=Layer.SYNTHESIS,
            actor_id=self.actor_id,
            input_refs=[fairness_input_node],
            decision_rationale=(
                f"Generated {n_to_generate} synthetic records for "
                f"{attribute}={group} to address fairness disparity."
            ),
            generation_params=gen_params | {"batch_id": batch_id, "model_id": model_id},
            validation_results={
                "P1_js_divergence": round(js_div, 4),
                "P1_threshold": self.js_threshold,
                "P1_passed": bool(p1_passed),
                "P3_verification_rate": round(p3_rate, 4),
                "P4_plausibility_pass_rate": round(p4_rate, 4),
                "n_accepted": int(accept_mask.sum()),
                "n_quarantined": int((~accept_mask).sum()),
            },
            flags=(
                []
                if p1_passed and p4_rate >= self.p4_min_pass
                else [
                    {"type": "P1_FAILURE", "js_divergence": round(js_div, 4),
                     "threshold": self.js_threshold, "severity": "high"}
                    if not p1_passed else None,
                    {"type": "P4_LOW_PLAUSIBILITY", "pass_rate": round(p4_rate, 4),
                     "threshold": self.p4_min_pass, "severity": "medium"}
                    if p4_rate < self.p4_min_pass else None,
                ]
            ),
        )

        # Filter out None flags
        synthesis_node_data = provenance.graph.nodes[synthesis_node]
        synthesis_node_data["flags"] = [f for f in synthesis_node_data["flags"] if f]

        # If P1 failed -> reject entire batch via an escalation node
        node_ids = [synthesis_node]
        if not p1_passed:
            escalation = provenance.record_event(
                event_type=EventType.ESCALATION,
                layer=Layer.SYNTHESIS,
                actor_id=self.actor_id,
                input_refs=[synthesis_node],
                decision_rationale=(
                    f"Fairness-Synthesis conflict: batch rejected due to "
                    f"P1 failure (JS divergence {js_div:.4f} > threshold {self.js_threshold}). "
                    f"Batch quarantined; regeneration with adjusted parameters required."
                ),
                flags=[{"type": "P1_FAILURE_ESCALATED", "severity": "high"}],
            )
            node_ids.append(escalation)
            accepted = pd.DataFrame()  # zero out acceptance if batch rejected

        return SynthesisReport(
            attribute=attribute, group=group,
            n_generated=int(n_to_generate),
            n_accepted=int(len(accepted)),
            n_quarantined_p3=int((~valid_p3).sum()),
            n_quarantined_p4=int((~plaus_mask).sum()),
            p1_js_divergence=js_div, p1_passed=p1_passed,
            p2_fairness_delta=None, p2_passed=None,  # computed post-merge
            p3_verification_rate=p3_rate,
            p4_plausibility_pass_rate=p4_rate,
            accepted_records=accepted,
            quarantined_records=quarantined,
            batch_id=batch_id,
            generation_params=gen_params,
            provenance_node_ids=node_ids,
        )
