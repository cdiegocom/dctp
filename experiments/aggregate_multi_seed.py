"""Aggregate the multi-seed raw CSV produced by single_seed.py runs."""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS = Path("/home/claude/dctp/results")
RAW = RESULTS / "tables" / "multi_seed_raw.csv"


def main():
    df = pd.read_csv(RAW)
    print(f"Raw rows: {len(df)}")
    print(df.to_string(index=False))

    # Aggregate per (dataset, attribute)
    agg = df.groupby(["dataset", "attribute"]).agg(
        n_seeds=("seed", "count"),
        baseline_eo_mean=("baseline_eo_gap", "mean"),
        baseline_eo_std=("baseline_eo_gap", "std"),
        pre_rollback_eo_mean=("pre_rollback_eo_gap", "mean"),
        pre_rollback_eo_std=("pre_rollback_eo_gap", "std"),
        p2_delta_mean=("p2_delta_pre_rollback", "mean"),
        p2_delta_std=("p2_delta_pre_rollback", "std"),
        p2_delta_min=("p2_delta_pre_rollback", "min"),
        p2_delta_max=("p2_delta_pre_rollback", "max"),
        rollback_rate=("rollback_executed", "mean"),
        n_synthesis_mean=("n_synthesis_accepted", "mean"),
        provenance_nodes_mean=("provenance_nodes", "mean"),
    ).round(4).reset_index()

    agg.to_csv(RESULTS / "tables" / "multi_seed_aggregate.csv", index=False)

    # Robustness signal: count seeds with negative P2 delta per (dataset, attribute)
    print("\n=== Robustness signal ===")
    for (ds, attr), sub in df.groupby(["dataset", "attribute"]):
        n_neg = (sub["p2_delta_pre_rollback"] < 0).sum()
        n_total = len(sub)
        rb = sub["rollback_executed"].sum()
        print(f"  {ds.upper()} {attr}: P2<0 in {n_neg}/{n_total} seeds; rollback in {rb}/{n_total}")

    # JSON summary
    summary = {
        "seeds": sorted(df["seed"].unique().tolist()),
        "n_seeds": int(df["seed"].nunique()),
        "aggregate": agg.to_dict(orient="records"),
        "robustness": {},
    }
    for (ds, attr), sub in df.groupby(["dataset", "attribute"]):
        key = f"{ds}_{attr}"
        summary["robustness"][key] = {
            "n_seeds": int(len(sub)),
            "p2_delta_negative_count": int((sub["p2_delta_pre_rollback"] < 0).sum()),
            "p2_delta_values": [float(v) for v in sub["p2_delta_pre_rollback"].tolist()],
            "rollback_count": int(sub["rollback_executed"].sum()),
        }
    with open(RESULTS / "tables" / "multi_seed_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Markdown
    md_lines = [
        "# Multi-seed robustness analysis\n",
        f"**Seeds tested:** {sorted(df['seed'].unique().tolist())}",
        f"**Configurations:** {len(df)} per-attribute outcomes ({df['dataset'].nunique()} datasets × {df['attribute'].nunique()} attributes × {df['seed'].nunique()} seeds)\n",
        "## Aggregate per (dataset, attribute)\n",
        agg.to_markdown(index=False),
        "\n## Robustness pattern\n",
        "| Dataset | Attribute | P2 < 0 (seeds) | Rollback executed | Signal |",
        "|---|---|---|---|---|",
    ]
    for (ds, attr), sub in df.groupby(["dataset", "attribute"]):
        n_neg = int((sub["p2_delta_pre_rollback"] < 0).sum())
        rb = int(sub["rollback_executed"].sum())
        signal = ("**P2 fails consistently**" if n_neg == len(sub)
                  else "**P2 passes consistently**" if n_neg == 0
                  else "P2 mixed")
        md_lines.append(f"| {ds.upper()} | {attr} | {n_neg}/{len(sub)} | {rb}/{len(sub)} | {signal} |")
    (RESULTS / "tables" / "multi_seed_summary.md").write_text("\n".join(md_lines))
    print(f"\nMarkdown saved.")

    # Figure 1: P2 delta scatter across seeds (per-point color reflects per-seed sign)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for i, ds in enumerate(["adult", "compas"]):
        sub = df[df["dataset"] == ds]
        attrs = sorted(sub["attribute"].unique())
        for j, attr in enumerate(attrs):
            vals = sub[sub["attribute"] == attr]["p2_delta_pre_rollback"].values
            mean_val = float(np.mean(vals))
            point_colors = ["#c0392b" if v < 0 else "#27ae60" for v in vals]
            axes[i].scatter([j] * len(vals), vals, color=point_colors, alpha=0.75, s=110,
                            edgecolors="black", linewidths=0.6, zorder=3)
            axes[i].plot([j - 0.22, j + 0.22], [mean_val, mean_val],
                         color="black", linewidth=2.2, zorder=2)
        axes[i].axhline(y=0, color="gray", linewidth=1, linestyle="-", zorder=1)
        axes[i].set_xticks(range(len(attrs)))
        axes[i].set_xticklabels([a.capitalize() for a in attrs])
        axes[i].set_ylabel("P2 fairness delta (pre-rollback)")
        axes[i].set_title(f"{ds.upper()} — {df['seed'].nunique()} seeds")
        axes[i].grid(axis="y", alpha=0.3)
    fig.suptitle(
        "Multi-seed robustness: P2 deltas are negative or near-zero, never reliably positive",
        fontsize=12, y=1.02,
    )
    plt.tight_layout()
    plt.savefig(RESULTS / "figures" / "multi_seed_p2_distribution.png", dpi=300,
                bbox_inches="tight")
    plt.close()
    print("Figure saved: multi_seed_p2_distribution.png")

    print("\n=== Aggregate ===")
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
