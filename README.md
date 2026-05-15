# Data-Centric Trust Pipeline

[![ci](https://github.com/cdiegocom/dctp/actions/workflows/ci.yml/badge.svg)](https://github.com/cdiegocom/dctp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Reference implementation and empirical validation for the four-layer
**Data-Centric Trust Pipeline** introduced in:

> Cavalcanti Pereira, C. D. (2026). *A Data-Centric Trust Pipeline: An
> Empirical Framework for Trustworthy AI in Sensitive Domains.*
> (Under submission to *Patterns*.)

The pipeline operationalizes four interdependent governance layers — Integrity,
Fairness, Synthesis, and Provenance — and three inter-layer conflict-resolution
protocols. It treats synthetic data as a governed layer with structured P1–P4
validation, and records decision-level provenance (why and by whom) rather than
only technical lineage.

## Repository structure

```
.
├── data/                              # source datasets (Adult, COMPAS)
├── src/
│   ├── integrity.py                   # Integrity Layer
│   ├── fairness.py                    # Fairness Layer (DP, EO, CF)
│   ├── synthesis.py                   # Synthesis Layer (protocols P1–P4)
│   ├── provenance.py                  # Provenance Layer (lineage graph)
│   └── pipeline.py                    # Orchestrator
├── experiments/
│   ├── run_adult.py                   # full Adult Census run
│   ├── run_compas.py                  # full COMPAS recidivism run
│   ├── cross_dataset.py               # aggregated comparison
│   ├── single_seed.py                 # one (dataset, seed) for multi-seed sweep
│   ├── aggregate_multi_seed.py        # multi-seed aggregation + figure
│   └── smoke_test.py                  # quick integration check (CI)
├── results/
│   ├── figures/                       # publication figures (.png, 200 dpi)
│   ├── tables/                        # per-run summaries + aggregated tables
│   └── provenance_graphs/             # full lineage graphs as JSON
├── paper1_draft.md                    # manuscript for Patterns
├── references.bib                     # bibliographic entries
├── requirements.txt                   # pinned dependencies
├── CITATION.cff                       # citable-software metadata
└── LICENSE                            # MIT
```

## Reproducing the empirical results

```bash
pip install -r requirements.txt

# Headline runs (Tables 2, 3, 4; Figures 1, 2)
python experiments/run_adult.py
python experiments/run_compas.py
python experiments/cross_dataset.py

# Multi-seed robustness (Table 5; Figure 3)
for seed in 13 42 137; do
    python experiments/single_seed.py --dataset adult --seed $seed
    python experiments/single_seed.py --dataset compas --seed $seed
done
python experiments/aggregate_multi_seed.py
```

All runs are deterministic (random_state controlled). Total wall-clock time is
approximately 8–12 minutes including the multi-seed sweep.

## Datasets

| Dataset | Source | Records (raw / validated) | Protected attributes | Outcome |
|---|---|---|---|---|
| Adult Census Income | algofairness/fairness-comparison (UCI mirror) | 32,561 / 30,162 | race, sex | `income > 50K` |
| COMPAS Recidivism | propublica/compas-analysis | 7,214 / 6,130 | race, sex | `two_year_recid` |

COMPAS preprocessing follows the standard ProPublica filter:
`days_b_screening_arrest ∈ [-30, 30]`, `is_recid ≠ -1`, `c_charge_degree ≠ "O"`,
`score_text ≠ "N/A"`, and races restricted to African-American, Caucasian,
Hispanic, Other.

## Headline results (seed = 42)

| | Adult | COMPAS |
|---|---|---|
| N validated / quarantined | 30,162 / 2,399 | 6,130 / 0 |
| Baseline EO gap (race) | 0.2254 | 0.3350 |
| Baseline EO gap (sex) | 0.0513 | 0.1003 |
| Synthesis batches generated | 4 | 4 |
| P1 passed (JS divergence ≤ 0.10) | 4 / 4 | 4 / 4 |
| P2 passed (fairness delta ≥ 0) | 0 / 4 | 3 / 4 |
| Rollback executed | Yes | Yes |
| Final EO gap (race / sex) | 0.225 / 0.051 | 0.335 / 0.100 |
| Provenance nodes | 15 | 14 |
| Lineage completeness | 1.0 | 1.0 |
| Decision coverage | 1.0 | 1.0 |
| Max traceability depth | 10 | 9 |

## Multi-seed robustness (seeds = 13, 42, 137)

| Dataset | Attribute | P2 delta (mean ± std) | Seeds with P2 < 0 | Rollback |
|---|---|---|---|---|
| Adult | race | −0.120 ± 0.023 | 3 / 3 | 3 / 3 |
| Adult | sex | −0.030 ± 0.010 | 3 / 3 | 3 / 3 |
| COMPAS | race | +0.016 ± 0.014 | 0 / 3 | 3 / 3 |
| COMPAS | sex | −0.034 ± 0.027 | 3 / 3 | 3 / 3 |

**Central empirical finding.** Across both datasets and three random seeds,
naive distributional synthesis passed P1 (Jensen–Shannon divergence
0.003–0.080, all under the 0.10 threshold) but failed P2 in every (dataset,
seed) configuration on at least one protected attribute. The pipeline detected
each regression, executed automatic rollback per the Fairness–Synthesis
conflict resolution protocol, and recorded the authorization in the provenance
graph. P1 alone is insufficient as a single check; the four-protocol structure
is what makes synthesis auditable.

## Layer evaluation criteria

| Layer | Primary metric | Acceptability |
|---|---|---|
| Integrity | structural completeness, semantic consistency, demographic coverage parity | no protected group's exclusion rate > 2× majority |
| Fairness | demographic parity gap, equal opportunity gap, counterfactual fairness | EO gap ≤ 0.10 per group |
| Synthesis | P1 (JS div), P2 (delta), P3 (hash verify), P4 (plausibility) | P1 ≤ 0.10; P2 ≥ 0 for all groups; P3 = 100 %; P4 ≥ 95 % |
| Provenance | lineage completeness, decision coverage, traceability depth | all transformations and all escalations documented |

## Provenance graph schema

Each node records: `node_id`, `event_type`, `timestamp`, `layer_origin`,
`actor_id`, `input_refs`, `output_refs`, `decision_rationale`, `flags`,
`schema_version`. SYNTHESIS nodes additionally carry `generation_params`
(model identifier, seed, privacy budget) and `validation_results` (P1–P4
outcomes). See `src/provenance.py::ProvenanceNode`.

## Citing this work

Please cite both the article and the software:

```bibtex
@article{CavalcantiPereira2026DCTP,
  author  = {Cavalcanti Pereira, Carlos Diego},
  title   = {A Data-Centric Trust Pipeline: An Empirical Framework for
             Trustworthy AI in Sensitive Domains},
  journal = {Patterns},
  year    = {2026},
  note    = {Under submission}
}

@software{CavalcantiPereira2026DCTPSoftware,
  author  = {Cavalcanti Pereira, Carlos Diego},
  title   = {Data-Centric Trust Pipeline: Reference Implementation},
  year    = {2026},
  url     = {https://github.com/cdiegocom/dctp},
  version = {1.0.0}
}
```

## License

Code is released under the MIT license. Bundled datasets are redistributed
under their original licenses (see LICENSE for details).

## Contact

Carlos Diego Cavalcanti Pereira — Visiting Fellow, Sloan School of Management,
Massachusetts Institute of Technology, and Professor at CESAR School (Recife
Center for Advanced Studies and Systems). cdiego@mit.edu
