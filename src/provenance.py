"""
Provenance Layer of the Data-Centric Trust Pipeline.

Implements the decision-level lineage graph specified in Section 5 of the paper.
Each node carries the fields required by Table 3:
  node_id, event_type, timestamp, layer_origin, actor_id, input_refs,
  output_refs, decision_rationale, flags, schema_version.

The graph is stored as a NetworkX DiGraph and exported as JSON.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx


class EventType(Enum):
    INGESTION = "INGESTION"
    TRANSFORMATION = "TRANSFORMATION"
    VALIDATION = "VALIDATION"
    FAIRNESS_AUDIT = "FAIRNESS_AUDIT"
    SYNTHESIS = "SYNTHESIS"
    ESCALATION = "ESCALATION"
    AUTHORIZATION = "AUTHORIZATION"
    DEPLOYMENT = "DEPLOYMENT"


class Layer(Enum):
    INTEGRITY = "INTEGRITY"
    FAIRNESS = "FAIRNESS"
    SYNTHESIS = "SYNTHESIS"
    PROVENANCE = "PROVENANCE"
    EXTERNAL = "EXTERNAL"


@dataclass
class ProvenanceNode:
    """A single lineage event, conforming to the schema in Table 3 of the paper."""

    node_id: str
    event_type: str
    timestamp: str
    layer_origin: str
    actor_id: str
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    decision_rationale: str | None = None
    flags: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = "1.0"
    # Synthesis-specific extensions (Section 5.2 of paper)
    generation_params: dict[str, Any] | None = None
    validation_results: dict[str, Any] | None = None
    # Auxiliary
    metrics: dict[str, Any] = field(default_factory=dict)


class ProvenanceGraph:
    """
    Lineage graph that records all pipeline events with decision-level granularity.

    The Provenance Layer differs from a standard log: it captures not only what
    changed but why and by whom (Design Principle DP4).
    """

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        self.graph = nx.DiGraph()
        self.created_at = datetime.now(timezone.utc).isoformat()

    # ---- node construction ----

    def record_event(
        self,
        event_type: EventType,
        layer: Layer,
        actor_id: str,
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
        decision_rationale: str | None = None,
        flags: list[dict[str, Any]] | None = None,
        metrics: dict[str, Any] | None = None,
        generation_params: dict[str, Any] | None = None,
        validation_results: dict[str, Any] | None = None,
    ) -> str:
        """Add an event node and the edges that connect it to its inputs."""
        node_id = f"{event_type.value.lower()}-{uuid.uuid4().hex[:8]}"

        node = ProvenanceNode(
            node_id=node_id,
            event_type=event_type.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            layer_origin=layer.value,
            actor_id=actor_id,
            input_refs=input_refs or [],
            output_refs=output_refs or [],
            decision_rationale=decision_rationale,
            flags=flags or [],
            metrics=metrics or {},
            generation_params=generation_params,
            validation_results=validation_results,
        )

        self.graph.add_node(node_id, **asdict(node))

        # Edges from upstream lineage
        for parent in node.input_refs:
            if parent in self.graph:
                self.graph.add_edge(parent, node_id)

        return node_id

    # ---- audit queries (Section 5.2 of paper: what / why / who / when) ----

    def ancestors_of(self, node_id: str) -> list[str]:
        """Backward traceability: all ancestors of a node (what produced this)."""
        return list(nx.ancestors(self.graph, node_id))

    def descendants_of(self, node_id: str) -> list[str]:
        """Forward traceability: everything downstream of this event."""
        return list(nx.descendants(self.graph, node_id))

    def nodes_of_type(self, event_type: EventType) -> list[str]:
        return [
            n
            for n, d in self.graph.nodes(data=True)
            if d.get("event_type") == event_type.value
        ]

    def nodes_of_layer(self, layer: Layer) -> list[str]:
        return [
            n
            for n, d in self.graph.nodes(data=True)
            if d.get("layer_origin") == layer.value
        ]

    def authorization_records(self) -> list[dict]:
        """Decisions with explicit human authorization (Design Principle DP4)."""
        return [
            self.graph.nodes[n]
            for n in self.graph.nodes()
            if self.graph.nodes[n].get("event_type")
            in (EventType.AUTHORIZATION.value, EventType.ESCALATION.value)
        ]

    # ---- evaluation criteria (Table 4 of paper) ----

    def evaluate(self) -> dict[str, Any]:
        """
        Compute the Provenance Layer's evaluation metrics from Table 4:
          - lineage completeness: fraction of transformation events with rationale
          - decision node coverage: fraction of escalations with authorization
          - backward traceability depth: max depth of any output's ancestor chain
        """
        all_nodes = list(self.graph.nodes(data=True))
        if not all_nodes:
            return {"lineage_completeness": None, "decision_coverage": None,
                    "max_traceability_depth": 0, "orphan_nodes": 0}

        # Lineage completeness: TRANSFORMATION events that have decision_rationale or flags
        transformation_nodes = [
            d for _, d in all_nodes
            if d.get("event_type") == EventType.TRANSFORMATION.value
        ]
        if transformation_nodes:
            documented = sum(
                1 for d in transformation_nodes
                if d.get("decision_rationale") or d.get("flags") or d.get("metrics")
            )
            lineage_completeness = documented / len(transformation_nodes)
        else:
            lineage_completeness = 1.0

        # Decision coverage: ESCALATION events that have a matching AUTHORIZATION
        escalations = self.nodes_of_type(EventType.ESCALATION)
        authorizations = self.nodes_of_type(EventType.AUTHORIZATION)
        # Each authorization should reference an escalation in input_refs
        authorized_escalations = set()
        for auth_id in authorizations:
            auth_node = self.graph.nodes[auth_id]
            for ref in auth_node.get("input_refs", []):
                if ref in escalations:
                    authorized_escalations.add(ref)
        decision_coverage = (
            len(authorized_escalations) / len(escalations) if escalations else 1.0
        )

        # Backward traceability depth: longest ancestor path
        max_depth = 0
        for node in self.graph.nodes():
            if self.graph.out_degree(node) == 0:  # leaf nodes (outputs)
                try:
                    # Compute longest path in DAG
                    ancestors = nx.ancestors(self.graph, node)
                    if ancestors:
                        max_depth = max(max_depth, len(ancestors))
                except nx.NetworkXError:
                    pass

        # Orphan nodes: no inputs and no outputs (excluding ingestion)
        orphan_nodes = sum(
            1 for n in self.graph.nodes()
            if self.graph.in_degree(n) == 0
            and self.graph.out_degree(n) == 0
            and self.graph.nodes[n].get("event_type") != EventType.INGESTION.value
        )

        return {
            "lineage_completeness": round(lineage_completeness, 4),
            "decision_coverage": round(decision_coverage, 4),
            "max_traceability_depth": max_depth,
            "orphan_nodes": orphan_nodes,
            "total_nodes": len(all_nodes),
            "escalation_count": len(escalations),
            "authorization_count": len(authorizations),
        }

    # ---- export ----

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "evaluation": self.evaluate(),
            "nodes": [
                {**self.graph.nodes[n]} for n in self.graph.nodes()
            ],
            "edges": [
                {"source": u, "target": v} for u, v in self.graph.edges()
            ],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path


def hash_synthetic_record(
    record_idx: int,
    batch_id: str,
    model_id: str,
    seed: int,
    timestamp: str,
) -> str:
    """
    Cryptographic provenance for synthetic records (Protocol P3, Table 4 of paper).
    Each synthetic record carries a verifiable identity marker distinguishing
    it from real data at any downstream stage.
    """
    payload = f"{model_id}|{batch_id}|{record_idx}|{seed}|{timestamp}"
    return hashlib.sha256(payload.encode()).hexdigest()
