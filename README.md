# Data-Centric Trust Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![DOI: data](https://img.shields.io/badge/Adult-10.24432%2FC5XW20-blue)](https://doi.org/10.24432/C5XW20)

Reference implementation and empirical validation for the four-layer
**Data-Centric Trust Pipeline**, introduced in:

> Cavalcanti Pereira, C. D. (2026). *A Data-Centric Trust Pipeline: An
> Empirical Framework for Trustworthy AI in Sensitive Domains.*
> Under revision at *AI and Ethics* (Springer Nature) — round-1 major
> revision response submitted.

The pipeline operationalizes four interdependent governance layers —
Integrity, Fairness, Synthesis, and Provenance — coupled through three
specified inter-layer conflict-resolution protocols. It treats synthetic
data as a governed layer with structured P1–P4 validation, and records
decision-level provenance (why and by whom) rather than only technical
lineage. The framework is evaluated on the Adult Census Income and
ProPublica COMPAS benchmarks across 32 dataset–generator–seed
configurations covering 26 independent pipeline executions.

## Status

The article was originally adapted from a *Patterns* (Cell Press)
submission and is currently under revision at *AI and Ethics* following
a major-revision invitation. Round-1 reviewer responses and the revised
manuscript are in [`revision_round_1/`](./revision_round_1/).

## Repository structure

```
.
├── data/                              # source datasets (Adult, COMPAS)
│   ├── adult.csv
│   └── compas.csv
├── src/
│   ├── integrity.py                   # Integrity Layer
│   ├── fairness.py                    # Fairness Layer (DP, EO, CF)
│   ├── synthesis.py                   # Synthesis Layer (protocols P1–P4)
│   ├── provenance.py                  # Provenance Layer (lineage graph)
│   └── pipeline.py                    # Orchestrator
├── experiments/
│   ├── run_adult.py                   # Primary Adult pipeline
│   ├── run_compas.py                  # Primary COMPAS pipeline
│   ├── cross_dataset.py               # Cross-dataset comparison
│   ├── single_seed.py                 # Single (dataset, seed) run
│   ├── single_backend.py              # Single (dataset, backend, seed) run
│   ├── aggregate_multi_seed.py        # Aggregate the 20-run multi-seed sweep
│   ├── aggregate_multi_backend.py     # Aggregate the 12-run multi-generator sweep
│   ├── classifier_ablation.py         # Random Forest vs Logistic Regression
│   └── smoke_test.py                  # Minimal smoke test
├── results/
│   ├── figures/                       # Generated PNGs cited in the manuscript
│   ├── tables/                        # CSV/MD aggregates and per-run summaries
│   └── provenance_graphs/             # Lineage graphs (per-run JSON)
├── revision_round_1/
│   ├── Response_to_Reviewers.pdf      # Point-by-point response
│   └── tracked_changes.pdf            # latexdiff vs pre-revision version
├── main_aie.tex                       # Manuscript (LaTeX source)
├── main_aie.pdf                       # Manuscript (compiled)
├── references.bib                     # Bibliography (37 entries)
├── requirements.txt                   # Pinned dependencies
├── Makefile                           # Reproduction targets
├── CITATION.cff                       # Software citation metadata
├── MANUSCRIPT_NOTES.md                # Compact structural summary
└── LICENSE                            # MIT
```

## Quickstart

```bash
# Clone and set up
git clone https://github.com/cdiegocom/dctp.git
cd dctp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Smoke test (~30 s)
python3 experiments/smoke_test.py

# Primary single-seed experiments (~3 min)
make experiments

# Build the manuscript
make paper
```

## Reproduction targets

| Target              | What it does                                                        | Time   |
| ------------------- | ------------------------------------------------------------------- | ------ |
| `make paper`        | Compile `main_aie.pdf` from LaTeX                                   | ~30 s  |
| `make experiments`  | Run the primary Adult + COMPAS single-seed pipelines                | ~3 min |
| `make multiseed`    | 10 seeds × 2 datasets with Gaussian Copula (20 independent runs)    | ~25 min|
| `make multibackend` | CTGAN + TVAE at 3 seeds × 2 datasets (12 additional runs)           | ~45 min|
| `make ablation`     | Logistic Regression classifier ablation (added in R1 revision)      | ~5 min |
| `make all`          | Manuscript + all experiments                                        | ~1.5 h |
| `make clean`        | Remove LaTeX build artifacts (keeps `main_aie.pdf`)                 | < 1 s  |
| `make distclean`    | Also remove `main_aie.pdf` and all experiment outputs               | < 1 s  |

Wall-clock times are for commodity hardware (8-core x86_64, no GPU).
CTGAN and TVAE training is the dominant cost; the Gaussian Copula sweep
is fast.

## The four layers, in brief

| Layer        | Function                                          | Key outputs                                    |
| ------------ | ------------------------------------------------- | ---------------------------------------------- |
| Integrity    | Structural and demographic validation             | Validated records, coverage matrix, exclusions |
| Fairness    | Demographic parity, equal opportunity, counter-factual fairness | Per-group metrics, rebalancing targets |
| Synthesis    | Generate underrepresented records under P1–P4     | Synthetic batches, per-batch protocol audit    |
| Provenance   | Decision-level lineage with rationale             | Lineage graph, AUTHORIZATION nodes             |

### The four synthesis protocols (calibrated in the AIE revision)

Discriminators that did empirical work in this evaluation:

- **P1 — Distributional invariance** (Jensen–Shannon divergence per
  attribute; aggregate threshold 0.10). Rejects out-of-distribution
  batches.
- **P2 — Fairness delta audit** (equal opportunity gap pre- vs post-
  synthesis on every protected attribute). Rejects batches that worsen
  any protected attribute.

Record-level integrity invariants that held trivially across these runs:

- **P3 — Cryptographic provenance** (SHA-256 over `model_id || batch_id
  || record_idx || seed || timestamp`). Guards against undetectable
  injection of synthetic records.
- **P4 — Domain plausibility** (callable predicates per dataset).
  Guards against impossible records (age = −3, education-num = 99).

P3 and P4 passed at 100% across every run in this evaluation, which is
the expected behaviour for well-behaved generators on benchmark data.
Their role is to surface pathologies that did not occur here; the
empirical signal in the multi-seed and multi-generator sweeps is carried
by P1 and P2.

### The three conflict-resolution protocols

- **Fairness–Synthesis** (exercised in this evaluation). Triggered when
  P2 fails: corpus reverts to the Integrity-validated baseline and the
  rollback decision is logged with role + rationale. Fires in all 20
  (dataset, seed) configurations of the multi-seed sweep.
- **Integrity–Fairness** (specified; not triggered in this evaluation).
  Triggered when integrity exclusions disproportionately remove an
  underrepresented group. Adult and COMPAS happened to have uniform
  exclusion rates across protected groups, so this protocol's escalation
  path is specified but was not exercised in our runs.
- **Provenance–Integrity** (specified; not triggered in this evaluation).
  Triggered when schema migrations would invalidate earlier lineage.
  No schema migration occurred during these runs.

## Headline empirical results

### Multi-seed Gaussian Copula sweep (10 seeds × 2 datasets)

| Dataset | Attribute | P2 Δ (mean ± std)     | Seeds with P2 Δ < 0 |
| ------- | --------- | ---------------------- | ------------------- |
| Adult   | race      | −0.1273 ± 0.0191       | 10/10               |
| Adult   | sex       | −0.0330 ± 0.0135       | 10/10               |
| COMPAS  | race      | −0.0014 ± 0.0162       | 6/10                |
| COMPAS  | sex       | −0.0290 ± 0.0159       | 10/10               |

Rollback fired in 20/20 configurations. Detailed per-run logs are in
`results/tables/multi_seed_*.csv`.

### Multi-generator panel (CTGAN + TVAE at 3 seeds × 2 datasets)

| Dataset | Generator | P1 pass rate | Rollback |
| ------- | --------- | ------------ | -------- |
| Adult   | CTGAN     | 75%          | 3/3      |
| Adult   | TVAE      | 0%           | 0/3 (P1 blocked) |
| COMPAS  | CTGAN     | 100%         | 2/3      |
| COMPAS  | TVAE      | 70%          | **0/3 (synthesis accepted)** |

TVAE on COMPAS is the only configuration of the 32 where the
conflict-resolution protocol *accepted* synthesis. The new §3.8 of the
manuscript discusses this case in detail.

### Classifier ablation (added in R1)

Random Forest replaced with Logistic Regression on seeds {13, 42, 137}:
the sign pattern of P2 deltas survives the swap on all four (dataset,
attribute) cells. Magnitudes differ, qualitative pattern is unchanged.
Raw data in `results/tables/classifier_ablation_raw.csv`.

## Citation

If you use this code or the manuscript, please cite both. The article
metadata (currently under revision at *AI and Ethics*) and the software
metadata are in [`CITATION.cff`](./CITATION.cff). GitHub renders that
file as a copy-to-clipboard citation widget in the sidebar.

In plain BibTeX, for the software:

```bibtex
@software{CavalcantiPereira2026DCTP,
  author  = {Cavalcanti Pereira, Carlos Diego},
  title   = {Data-Centric Trust Pipeline: Reference Implementation},
  year    = {2026},
  url     = {https://github.com/cdiegocom/dctp},
  version = {1.1.0},
  license = {MIT}
}
```

For the manuscript itself, please cite the eventual journal version
once accepted. In the meantime, the working reference is the preprint
inside this repository (`main_aie.pdf`).

## License

MIT — see [LICENSE](./LICENSE).

## Author

**Carlos Diego Cavalcanti Pereira**
Sloan School of Management, MIT (Visiting Fellows Program)
CESAR School, Recife, Brazil
ORCID: [0009-0005-2003-8713](https://orcid.org/0009-0005-2003-8713)
Email: [cdiego@mit.edu](mailto:cdiego@mit.edu)

## Acknowledgments

This research was conducted as part of the author's extended research
and residency activities at the Sloan School of Management within the
Visiting Fellows Program at MIT, with the support of the CESAR School
research environment. Thanks to the two anonymous reviewers and the
editors of *AI and Ethics* for the constructive feedback that materially
improved this work.
