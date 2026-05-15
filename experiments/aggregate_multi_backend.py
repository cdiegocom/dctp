"""Aggregate the multi-backend CSV into manuscript-ready table and figure.

Produces:
  - results/tables/multi_backend_aggregate.csv
  - results/tables/multi_backend_summary.md
  - results/figures/multi_backend_comparison.png
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS = Path("/home/claude/dctp/results")
RAW = RESULTS / "tables" / "multi_backend_raw.csv"


def main():
    df = pd.read_csv(RAW)
    print(f"Raw rows: {len(df)}\n")

    # Aggregate per (dataset, backend, attribute)
    agg = df.groupby(["dataset", "backend", "attribute"]).agg(
        n_seeds=("seed", "count"),
        baseline_eo_mean=("baseline_eo_gap", "mean"),
        p2_delta_mean=("p2_delta_pre_rollback", "mean"),
        p2_delta_std=("p2_delta_pre_rollback", "std"),
        p1_pass_rate=("p1_pass_count", lambda s: s.sum() / df.loc[s.index, "p1_total"].sum()),
        rollback_rate=("rollback_executed", "mean"),
        n_p2_valid=("p2_delta_pre_rollback", lambda s: s.notna().sum()),
    ).round(4).reset_index()

    agg.to_csv(RESULTS / "tables" / "multi_backend_aggregate.csv", index=False)

    # Robustness signal per (dataset, backend, attribute)
    print("=== Per (dataset, backend, attribute) signal ===")
    for (ds, be, attr), sub in df.groupby(["dataset", "backend", "attribute"]):
        valid = sub["p2_delta_pre_rollback"].dropna()
        n_neg = (valid < 0).sum()
        n_pos = (valid >= 0).sum()
        rb = sub["rollback_executed"].sum()
        p1_pass = sub["p1_pass_count"].sum()
        p1_total = sub["p1_total"].sum()
        print(f"  {ds.upper():6} {be:16} {attr:4}: "
              f"P1 pass {p1_pass}/{p1_total} ({100*p1_pass/p1_total:.0f}%), "
              f"P2< 0 in {n_neg}/{len(valid)} valid seeds, "
              f"rollback {rb}/{len(sub)}")

    # Markdown summary
    md = ["# Multi-backend robustness analysis\n",
          f"**Backends tested:** Gaussian Copula, CTGAN, TVAE",
          f"**Seeds tested:** {sorted(df['seed'].unique().tolist())}",
          f"**Note:** Adult runs used a 5,000-record subsample (with seed-specific subsampling) "
          f"to make CTGAN and TVAE tractable within typical compute budgets; "
          f"the COMPAS runs used the full filtered dataset (6,130 records).\n",
          "## Aggregate per (dataset, backend, attribute)\n",
          agg.to_markdown(index=False)]
    (RESULTS / "tables" / "multi_backend_summary.md").write_text("\n".join(md))

    # JSON
    with open(RESULTS / "tables" / "multi_backend_summary.json", "w") as f:
        json.dump({
            "backends": sorted(df["backend"].unique().tolist()),
            "seeds": sorted(df["seed"].unique().tolist()),
            "aggregate": agg.to_dict(orient="records"),
            "raw": df.to_dict(orient="records"),
        }, f, indent=2, default=str)

    # ---- Figure: side-by-side P2 deltas across three backends ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=False)
    backends = ["gaussian_copula", "ctgan", "tvae"]
    backend_labels = ["Gaussian Copula", "CTGAN", "TVAE"]
    attrs = ["race", "sex"]
    palette = {"gaussian_copula": "#3498db", "ctgan": "#e67e22", "tvae": "#9b59b6"}

    # For each dataset, plot grouped P2 deltas by backend, separated by attribute
    for i, ds in enumerate(["adult", "compas"]):
        ax = axes[i]
        positions = []
        labels = []
        all_vals = []
        x = 0
        for attr in attrs:
            for backend in backends:
                sub = df[(df["dataset"] == ds) &
                         (df["backend"] == backend) &
                         (df["attribute"] == attr)]
                valid = sub["p2_delta_pre_rollback"].dropna()
                if len(valid) == 0:
                    # All batches failed P1 — annotate
                    ax.text(x, 0, "P1\nrejected", ha="center", va="center",
                            fontsize=8, color="#7f8c8d",
                            bbox=dict(boxstyle="round,pad=0.2",
                                      facecolor="white", edgecolor="#7f8c8d",
                                      alpha=0.85))
                else:
                    point_colors = ["#c0392b" if v < 0 else "#27ae60" for v in valid]
                    ax.scatter([x] * len(valid), valid, color=point_colors, alpha=0.8,
                               s=100, edgecolors="black", linewidths=0.5, zorder=3)
                    mean_val = float(valid.mean())
                    ax.plot([x - 0.18, x + 0.18], [mean_val, mean_val],
                            color="black", linewidth=2, zorder=2)
                positions.append(x)
                labels.append(backend_labels[backends.index(backend)] + f"\n({attr})")
                x += 1
            x += 0.6  # gap between attributes

        ax.axhline(y=0, color="gray", linewidth=1, zorder=1)
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=8.5, rotation=0)
        ax.set_ylabel("P2 fairness delta (pre-rollback)")
        ax.set_title(f"{ds.upper()} — 3 seeds × 3 backends")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Multi-backend robustness: P2 outcomes depend on the generator, not just the data",
        fontsize=12, y=1.01,
    )
    plt.tight_layout()
    plt.savefig(RESULTS / "figures" / "multi_backend_comparison.png", dpi=300,
                bbox_inches="tight")
    plt.close()
    print(f"\nFigure saved: multi_backend_comparison.png")

    print("\n=== Aggregate table ===")
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
