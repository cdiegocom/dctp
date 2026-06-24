# Changelog

All notable changes to this repository are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-06-23

Round-1 major revision response submitted to *AI and Ethics* (Springer
Nature). All substantive code components remain stable from v1.0.0; the
changes in this release are concentrated in the manuscript, the
bibliography, and the supporting documentation.

### Added

- **Classifier ablation experiment** (`experiments/classifier_ablation.py`):
  re-runs seeds {13, 42, 137} on both datasets with a Logistic
  Regression classifier in place of the Random Forest, in response to
  Reviewer 2's robustness concern. Raw and aggregated outputs in
  `results/tables/classifier_ablation_*.csv`.
- **New manuscript subsection §1.1 Related work** (~400 words) covering
  AI governance and auditing, data-centric AI, dataset/model
  documentation standards, and MLOps deployment monitoring.
- **New manuscript subsection §3.8** analyzing the TVAE-on-COMPAS case
  in depth — the single configuration of the 32 where the
  conflict-resolution protocol accepted synthesis.
- **Threshold sensitivity paragraph** in §3.4 reporting what the
  rollback decision would have been at τ ∈ {0.02, 0.05} using existing
  multi-seed data.
- **Statistical scope paragraph** in §3.7 acknowledging the exploratory
  nature of the n=3 multi-generator panel, the +0.171 outlier in
  CTGAN-Adult-race, and the Adult-subsample confound.
- **`revision_round_1/`** directory containing:
  - `Response_to_Reviewers.pdf` — point-by-point response (9 pages)
  - `tracked_changes.pdf` — latexdiff vs the pre-revision version
- **8 new references** in `references.bib` (now 37 entries total):
  - Mitchell et al. 2019 (Model Cards)
  - Gebru et al. 2021 (Datasheets for Datasets)
  - Pushkarna, Zaldivar & Kjartansson 2022 (Data Cards)
  - Sambasivan et al. 2021 (Data Cascades)
  - Paleyes, Urma & Lawrence 2022 (Challenges in Deploying ML)
  - Mökander et al. 2024 (Auditing LLMs)
  - Falco et al. 2021 (Governing AI Safety through Independent Audits)
  - Calder et al. 2026 (Responsible AI in criminal justice)

### Changed

- **Abstract repositioned** to state the operational coupling as the
  contribution and the empirical finding (naive synthesis can preserve
  or worsen fairness) as corroborative of established literature, not
  as novel.
- **§2.1 expanded** with a paragraph distinguishing P1/P2 as
  batch-level discriminators from P3/P4 as record-level invariants;
  the distinction is propagated through the rest of the manuscript.
- **§2.2 rewritten and retitled** "Inter-layer dependencies and
  conflict-resolution protocols" (the count is no longer in the
  heading); each protocol is now labeled "exercised in this evaluation"
  (Fairness-Synthesis only) or "specified; not triggered in this
  evaluation" (Integrity-Fairness, Provenance-Integrity).
- **§3 introduction** expanded with a substantive caveat on the COMPAS
  label as a re-arrest indicator (not re-offense), encoding the
  institutional bias of patrol and enforcement patterns; the
  framework's role is to make the trade-off auditable rather than to
  legitimize the underlying prediction task.
- **§4 Discussion** reorganized to lead with regulatory implications;
  the "Implications for Regulation" paragraph rewritten to articulate
  a concrete normative position (shift from entity-level to
  decision-level accountability) and acknowledge the political
  question of standing as upstream of the technical work.
- **§4.1 Limitations** items 3 (rubber-stamp risk) and 4 (methodological
  choices) rewritten without the (a)(b)(c) enumeration that flagged
  the original as templated.
- **Statements and Declarations** consolidated into natural prose
  paragraphs (Funding/Competing/Ethics/Consent grouped); Code
  availability now references the canonical GitHub URL and the
  `v1.1.0` tag.
- **Makefile** target renamed from `main.tex` to `main_aie.tex`; new
  `ablation` target for the classifier ablation experiment.

### Fixed

- Cross-cutting audit pass to remove residual overstated phrasing.
  Five locations identified and fixed: §3.6 "four-protocol structure
  is the mechanism" line; §1 contributions "three conflict-resolution
  protocols" qualified; SMOTE paragraph First/Second/Third structure
  removed; "Comparison with related frameworks" paragraph reworked;
  Dammu comparison in §1 consolidated to remove redundancy with §4.

### Bibliography statistics

| Version | Entries | New since previous |
| ------- | ------- | ------------------ |
| v1.0.0  | 29      | (initial)          |
| v1.1.0  | 37      | +8                 |

### Manuscript statistics

| Metric        | v1.0.0 | v1.1.0 |
| ------------- | ------ | ------ |
| Pages         | 22     | 27     |
| Body words    | ~7,840 | ~9,560 |
| Abstract words| 248    | 280    |
| References    | 29     | 37     |

## [1.0.0] — 2026-05-15

Initial public release, accompanying the original *Patterns* (Cell
Press) submission. Subsequently adapted to *AI and Ethics* (Springer
Nature) format and submitted in May 2026.

### Released

- Complete reference implementation (~1,560 lines across five Python
  modules: integrity, fairness, synthesis, provenance, pipeline).
- Adult Census Income and ProPublica COMPAS datasets bundled in `data/`.
- Single-seed, multi-seed (10 seeds × 2 datasets), and multi-generator
  (Gaussian Copula, CTGAN, TVAE) experiment scripts.
- Aggregation scripts and per-run result tables.
- 22-page manuscript with 29-entry bibliography.
- MIT License.
