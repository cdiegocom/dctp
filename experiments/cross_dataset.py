"""
Cross-dataset comparison: synthesizes results from Adult + COMPAS into a single
table and figure suitable for Paper 1.

Outputs:
  - results/tables/cross_dataset_comparison.csv (and .md for paper insertion)
  - results/figures/cross_dataset_summary.png
  - results/figures/provenance_graph_compas.png
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS = Path("/home/claude/dctp/results")


def load_summary(name: str) -> dict:
    with open(RESULTS / "tables" / f"{name}_summary.json") as f:
        return json.load(f)


def build_comparison_table() -> pd.DataFrame:
    rows = []
    for name in ("adult", "compas"):
        s = load_summary(name)
        prov = s["provenance_evaluation"]
        prf = s.get("pre_rollback_fairness", {}) or {}
        pre_rb_eo = prf.get("pre_rollback_eo_gap", {})
        p2_before = prf.get("p2_deltas_before_rollback", {})

        for attr in s["initial_eo_gap"]:
            rows.append({
                "Dataset": name.upper(),
                "Protected Attribute": attr,
                "N records (validated)": s["n_initial_validated"],
                "N records (quarantined)": s["n_initial_quarantined"],
                "Baseline EO gap": round(s["initial_eo_gap"][attr], 4),
                "Baseline DP gap": round(s["initial_dp_gap"][attr], 4),
                "N synthesis batches": s["n_synthesis_batches"],
                "N synthetic accepted": s["n_synthesis_accepted"],
                "Pre-rollback EO gap": round(pre_rb_eo.get(attr, 0), 4) if pre_rb_eo else "—",
                "P2 delta (pre-rollback)": (f"{p2_before.get(attr, 0):+.4f}"
                                              if p2_before else "—"),
                "Rollback executed": s.get("rollback_executed", False),
                "Final EO gap": round(s["final_eo_gap"][attr], 4),
                "Provenance nodes": prov["total_nodes"],
                "Lineage completeness": prov["lineage_completeness"],
                "Decision coverage": prov["decision_coverage"],
            })
    return pd.DataFrame(rows)


def build_per_batch_table() -> pd.DataFrame:
    rows = []
    for name in ("adult", "compas"):
        s = load_summary(name)
        for b in s["per_synthesis_batch"]:
            rows.append({
                "Dataset": name.upper(),
                "Target": b["target"],
                "N generated": b["n_generated"],
                "N accepted": b["n_accepted"],
                "P1 JS divergence": round(b["P1_js_divergence"], 4),
                "P1 passed": b["P1_passed"],
                "P2 delta": (f"{b['P2_fairness_delta']:+.4f}"
                              if b["P2_fairness_delta"] is not None else "—"),
                "P2 passed": b["P2_passed"],
                "P3 verification rate": b["P3_verification_rate"],
                "P4 plausibility rate": b["P4_plausibility_pass_rate"],
            })
    return pd.DataFrame(rows)


def cross_dataset_figure(df_summary: pd.DataFrame):
    """Bar chart comparing baseline vs pre-rollback vs final EO gaps."""
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(df_summary))
    w = 0.27

    baseline = df_summary["Baseline EO gap"].values
    pre_rb = [v if v != "—" else 0 for v in df_summary["Pre-rollback EO gap"].values]
    final = df_summary["Final EO gap"].values

    ax.bar(x - w, baseline, w, label="Baseline (Integrity-validated)", color="#2c3e50")
    ax.bar(x, pre_rb, w, label="After naive synthesis (pre-rollback)", color="#c0392b")
    ax.bar(x + w, final, w, label="After pipeline (post-rollback)", color="#27ae60")
    ax.axhline(y=0.10, color="gray", linestyle="--", linewidth=1, alpha=0.7,
               label="P2 threshold (0.10)")

    labels = [f"{r['Dataset']}\n{r['Protected Attribute']}" for _, r in df_summary.iterrows()]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Equal Opportunity Gap")
    ax.set_title("Cross-dataset: P2 audit detects regression that P1 alone misses",
                 fontsize=12, pad=12)
    ax.legend(loc="upper right", fontsize=9)
    plt.tight_layout()
    out = RESULTS / "figures" / "cross_dataset_summary.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Saved {out}")


def provenance_graph_figure(name: str):
    """Render a provenance graph as a layered DAG."""
    with open(RESULTS / "provenance_graphs" / f"{name}_full.json") as f:
        g_data = json.load(f)

    G = nx.DiGraph()
    color_map = {
        "INGESTION": "#95a5a6",
        "VALIDATION": "#3498db",
        "FAIRNESS_AUDIT": "#9b59b6",
        "SYNTHESIS": "#e67e22",
        "ESCALATION": "#e74c3c",
        "AUTHORIZATION": "#27ae60",
        "TRANSFORMATION": "#16a085",
        "DEPLOYMENT": "#34495e",
    }
    labels = {}
    colors = []
    for n in g_data["nodes"]:
        nid = n["node_id"]
        G.add_node(nid)
        labels[nid] = f"{n['event_type']}\n[{n['layer_origin']}]"
        colors.append(color_map.get(n["event_type"], "#bdc3c7"))
    for e in g_data["edges"]:
        G.add_edge(e["source"], e["target"])

    # Layered layout using topological generations
    layers = list(nx.topological_generations(G))
    pos = {}
    for layer_idx, layer in enumerate(layers):
        for node_idx, n in enumerate(sorted(layer)):
            pos[n] = (layer_idx, -node_idx)

    fig, ax = plt.subplots(figsize=(13, 6))
    nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=1700,
                            edgecolors="black", linewidths=1.0)
    nx.draw_networkx_edges(G, pos, arrows=True, edge_color="#555555",
                            arrowsize=14, width=1.2)
    nx.draw_networkx_labels(G, pos, labels, font_size=7.5)

    # Legend
    legend_handles = [plt.Line2D([0], [0], marker="o", color="w", label=k,
                                  markerfacecolor=v, markersize=10)
                      for k, v in color_map.items() if k in {n["event_type"] for n in g_data["nodes"]}]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, ncol=2)
    ax.set_title(f"Provenance graph — {name.upper()} pipeline run\n"
                 f"({len(g_data['nodes'])} nodes, "
                 f"lineage_completeness={g_data['evaluation']['lineage_completeness']}, "
                 f"decision_coverage={g_data['evaluation']['decision_coverage']})")
    ax.axis("off")
    plt.tight_layout()
    out = RESULTS / "figures" / f"provenance_graph_{name}.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Saved {out}")


def main():
    df_summary = build_comparison_table()
    df_batches = build_per_batch_table()

    # CSV outputs
    df_summary.to_csv(RESULTS / "tables" / "cross_dataset_comparison.csv", index=False)
    df_batches.to_csv(RESULTS / "tables" / "synthesis_batches_outcomes.csv", index=False)
    print("CSVs saved")

    # Markdown for the paper
    md_lines = ["# Cross-dataset results\n\n## Pipeline summary\n",
                df_summary.to_markdown(index=False),
                "\n\n## Per-batch synthesis outcomes (P1-P4)\n",
                df_batches.to_markdown(index=False)]
    (RESULTS / "tables" / "cross_dataset_comparison.md").write_text("\n".join(md_lines))
    print("Markdown saved")

    cross_dataset_figure(df_summary)
    for name in ("adult", "compas"):
        provenance_graph_figure(name)

    print("\n=== Summary preview ===")
    print(df_summary.to_string(index=False))
    print("\n=== Per-batch preview ===")
    print(df_batches.to_string(index=False))


if __name__ == "__main__":
    main()
