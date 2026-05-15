"""Quick smoke test: verify the pipeline runs end-to-end on a small Adult sample."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import FairnessLayer, IntegrityLayer, SynthesisLayer, TrustPipeline

# Load a small sample of Adult for fast iteration
df = pd.read_csv("/home/claude/dctp/data/adult.csv")
print(f"Loaded Adult: {df.shape}")
print(f"Columns: {df.columns.tolist()}")

# Use a small stratified sample for the smoke test
df_sample = df.sample(n=3000, random_state=42).reset_index(drop=True)
print(f"Sample: {df_sample.shape}")
print(f"Target distribution:\n{df_sample['income-per-year'].value_counts()}")
print(f"\nRace distribution:\n{df_sample['race'].value_counts()}")
print(f"\nSex distribution:\n{df_sample['sex'].value_counts()}")

# Define schema (all columns expected)
schema = {c: ("numeric" if pd.api.types.is_numeric_dtype(df_sample[c]) else "categorical")
          for c in df_sample.columns}

# Configure layers
integrity = IntegrityLayer(
    schema=schema,
    protected_attributes=["race", "sex"],
    missing_value_sentinels=("?", "", "NA", "Unknown"),
)
fairness = FairnessLayer(
    target_column="income-per-year",
    protected_attributes=["race", "sex"],
    positive_label=">50K",
    max_gap_threshold=0.10,
    random_state=42,
)
synthesis = SynthesisLayer(
    js_divergence_threshold=0.20,  # relaxed for smoke test
    random_state=42,
)

pipeline = TrustPipeline(integrity, fairness, synthesis)

# Run
result = pipeline.run(df_sample, dataset_name="adult_smoke", oversampling_ratio=0.5)

print("\n=== Pipeline Result Summary ===")
import json
print(json.dumps(result.summary(), indent=2, default=str))

print("\n=== Provenance Graph Evaluation ===")
print(json.dumps(result.provenance.evaluate(), indent=2))

# Persist provenance graph
prov_path = result.provenance.save("/home/claude/dctp/results/provenance_graphs/adult_smoke.json")
print(f"\nProvenance saved to: {prov_path}")
print(f"Total nodes: {len(result.provenance.graph.nodes())}")
print(f"Total edges: {len(result.provenance.graph.edges())}")
