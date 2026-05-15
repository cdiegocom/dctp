# A Data-Centric Trust Pipeline: An Empirical Framework for Trustworthy AI in Sensitive Domains

**Carlos Diego Cavalcanti Pereira**¹

¹ Sloan School of Management, Massachusetts Institute of Technology, Cambridge, MA, USA — and CESAR School (Recife Center for Advanced Studies and Systems), Recife, Brazil. Correspondence: cdiego@mit.edu

---

## Highlights

- Treating data integrity, fairness, synthetic data, and provenance as **independent controls is the root cause** of accountability failures in deployed AI systems.
- The Data-Centric Trust Pipeline integrates these four dimensions through **explicit inter-layer handoffs and three conflict-resolution protocols**.
- A reference implementation tested on **Adult Census Income (n = 30,162) and COMPAS recidivism (n = 6,130)** demonstrates that naive synthesis passes distributional fidelity (Jensen–Shannon divergence 0.003–0.080, all under the 0.10 threshold) **yet fails the fairness delta audit (P2)** on 5 of 8 batches across the two datasets, with the pattern replicating across three random seeds.
- In every (dataset, seed) configuration the pipeline **detects the regression, executes automatic rollback, and records the authorization decision in the lineage graph** with full decision coverage (1.0) and full lineage completeness (1.0) — empirically showing that P1 distributional fidelity is insufficient and that the four-protocol structure is what makes synthesis auditable.

## Bigger Picture

Trust in artificial intelligence is usually framed as a model-level problem: improve accuracy, increase interpretability, reduce overfitting. Documented failures in deployed AI systems — in healthcare, public administration, and criminal justice — point elsewhere. The systems fail because the data sustaining them are incomplete, demographically skewed, or transformed without traceable accountability. Four dimensions are central to this upstream failure pattern: integrity, fairness, synthetic data, and provenance. Each has an established technical literature; each is typically managed in isolation; and that isolation is the source of failure, because the interactions between the four dimensions are precisely where accountability breaks down. This work proposes a Data-Centric Trust Pipeline that connects the four dimensions through explicit inter-layer handoffs, formal conflict-resolution protocols, and decision-level provenance. We provide a reference implementation and an empirical evaluation on two canonical fairness benchmarks. The pipeline does not aim to eliminate errors but to make them detectable, locatable, and correctable — converting accountability from a documentary requirement into a structural property of the data lifecycle.

## Summary

Documented failures in deployed AI systems consistently trace to data infrastructure rather than model design, yet the four dimensions most central to data-level accountability — integrity, fairness, synthetic data, and provenance — are typically managed as independent controls. We argue this fragmentation is itself a structural source of failure, since the dimensions interact in ways that no single control monitors. We introduce the Data-Centric Trust Pipeline, a four-layer governance framework that specifies inter-layer dependencies, conflict-resolution protocols, and a minimum provenance record structure that captures *why* and *by whom* a decision was made rather than only *what* changed. We implement the framework as open-source Python and evaluate it on two canonical fairness benchmarks (Adult Census Income, n = 30,162; COMPAS recidivism, n = 6,130). Naive synthetic augmentation passed the distributional fidelity protocol (P1) on every batch across both datasets but produced a negative fairness delta (P2 failure) in 5 of 8 batches in our primary run, with the qualitative pattern replicating across three random seeds. The pipeline detected each regression, executed automatic rollback per the Fairness–Synthesis conflict protocol, and recorded the authorization decision in the provenance graph (lineage completeness 1.0, decision coverage 1.0) across all six (dataset, seed) configurations. The empirical results demonstrate that distributional fidelity alone is insufficient and that the four-protocol structure is what makes synthetic augmentation governable.

**Keywords:** trustworthy AI, data governance, algorithmic fairness, synthetic data, data provenance, accountability.

---

## Introduction

Trust in artificial intelligence is frequently framed as a model-level problem: improve accuracy, increase interpretability, reduce overfitting. Documented failures in deployed systems point elsewhere. AI deployed in healthcare, public administration, financial services, and criminal justice produces unreliable or discriminatory outputs not primarily because models are poorly designed but because the data feeding them are incomplete, inconsistently documented, or demographically unrepresentative.[^1][^2] The problem is upstream, not downstream.

Four dimensions are central to this upstream failure pattern: *data integrity*, *bias and fairness*, *synthetic data*, and *provenance*.[^3] Each has an established technical literature. Integrity frameworks specify how datasets should be validated and annotated.[^4] Fairness criteria formalize what representational equity requires.[^5][^6][^7] Synthetic generation methods address demographic underrepresentation and privacy constraints.[^8] Provenance systems record data origins and transformations.[^9] The problem is that these solutions are developed and deployed in isolation. An organization can pass integrity checks at ingestion, satisfy fairness audits at deployment, and still produce biased predictions — because the integrity check did not assess demographic completeness, and the fairness audit cannot trace back to which records were excluded during validation.

Empirical evidence confirms this gap. Studies of clinical AI systems show that 40–60% of training datasets lack standardized metadata or licensing documentation.[^4][^10] More than half of AI publications in clinical settings report fairness outcomes without specifying the metrics used or the audit procedures applied.[^11][^12] Synthetic datasets generated to correct demographic imbalances frequently reproduce the structural inequalities present in their source distributions.[^8][^13] These are not isolated failures; they reflect a consistent pattern in which each dimension is handled competently but none interoperates with the others.

Regulatory responses — the EU AI Act,[^14] ISO/IEC 42001,[^15] and the NIST AI Risk Management Framework[^3] — have shifted the framing from technical compliance to organizational accountability.[^16][^10] This shift is necessary but insufficient. Current frameworks remain prescriptive at the category level: they specify what must be documented without specifying how integrity checks should connect to fairness audits, or how synthetic generation events should be anchored in provenance records. An organization can satisfy the letter of these requirements while operating a data pipeline in which the four dimensions never communicate.

Several existing frameworks share the lifecycle orientation that motivates this work, including the NIST AI RMF,[^3] ISO/IEC 42001,[^15] and the data-centric framework of Dammu et al.[^17] The most directly related is Dammu et al., who propose a data-centric perspective integrating governance, fairness, validation, and lifecycle accountability within a layered structure. The contribution of the present work extends this line in three specific dimensions. First, we formalize inter-layer dependencies through a taxonomy specifying inputs, outputs, and conflict-resolution protocols for each layer transition. Second, we treat synthetic data as a first-class governance layer with four auditable validation protocols, rather than as a bias-mitigation technique appended to model development. Third, we distinguish decision-level provenance from entity-level logging: the provenance layer records not only what changed but who authorized it and why, which is the information that post-deployment audits and regulatory reviews actually require.

This article makes three contributions. (i) We introduce the *Data-Centric Trust Pipeline*, a four-layer framework that connects integrity, fairness, synthesis, and provenance through explicit handoffs and three conflict-resolution protocols. (ii) We provide an open-source reference implementation of the framework in Python and release the full empirical run logs. (iii) We evaluate the framework on two canonical fairness benchmarks — Adult Census Income (n = 30,162) and the ProPublica COMPAS recidivism dataset (n = 6,130) — and show that naive distributional synthesis, even when it passes the standard fidelity protocol, can introduce fairness regressions that the pipeline detects and rolls back automatically. The empirical finding is consequential: distributional fidelity (P1) is insufficient as a single check, and the four-protocol structure (P1–P4) is what makes synthesis auditable. We position the framework as a substrate for the regulatory requirements established by the EU AI Act, NIST AI RMF, and ISO/IEC 42001, rather than as a replacement for them.

The remainder of this article proceeds as follows. The Framework section formalizes the four layers, their inter-layer dependencies, and the conflict-resolution protocols. The Results section presents the empirical evaluation on Adult and COMPAS, with cross-dataset synthesis. The Discussion engages with limitations, scope conditions, and implications for regulatory frameworks. The Experimental Procedures section documents the reference implementation. The Resource Availability section provides full reproduction instructions.

---

## The Data-Centric Trust Pipeline

The pipeline comprises four interdependent governance layers — *Integrity*, *Fairness*, *Synthesis*, *Provenance* — that form a recursive cycle rather than a linear sequence. Each layer produces structured metadata that the subsequent layers consume as inputs. Failures in any one layer propagate into the others, which is why the dependencies are formalized rather than left to convention.

### Layer definitions and evaluation criteria

**Integrity Layer.** Validates structural, semantic, and contextual consistency. Beyond standard schema validation, it computes *demographic coverage parity* — the exclusion rate per protected group — which is the metric that detects when missing-value patterns are themselves demographically skewed. Outputs include validated and quarantined record sets, a quality report with per-flag severity, and a demographic coverage matrix. The Integrity Layer triggers an escalation whenever a protected group's exclusion rate exceeds twice the majority group's exclusion rate (the Integrity–Fairness conflict, below).

**Fairness Layer.** Operationalizes three formal criteria: demographic parity (Calders and Verwer),[^5] equal opportunity (Hardt, Price, and Srebro),[^6] and counterfactual fairness (Kusner et al.).[^7] In our implementation, counterfactual fairness is approximated through matching: for a stratified random sample of records, we find each record's nearest neighbor in the opposite protected-attribute group and compare the classifier's predictions; the mean absolute divergence is reported. Outputs include per-group metrics, disparity reports, and rebalancing recommendations forwarded to the Synthesis Layer. The default acceptability threshold for the equal opportunity gap is 0.10; any disparity above this triggers a rebalancing target and a fairness audit record.

**Synthesis Layer.** Receives the rebalancing recommendation and generates synthetic records for the underrepresented groups under four validation protocols (Table 1). Generation uses a Gaussian Copula synthesizer; CTGAN and TVAE backends are supported through the same interface. Each synthetic record is hashed at generation time with a SHA-256 cryptographic signature incorporating the model identifier, batch ID, record index, random seed, and timestamp — distinguishing it from real data at any downstream stage.

**Table 1. The four synthetic-data validation protocols.**

| Protocol | Objective | Operationalization | Rejection criterion |
|---|---|---|---|
| **P1.** Distributional invariance | Verify that synthetic records preserve the source statistical structure | Jensen–Shannon divergence between the marginal distributions of the synthetic batch and the source group, averaged over key variables | JS divergence > 0.10 → batch quarantined, regeneration triggered |
| **P2.** Fairness delta audit | Confirm that augmentation reduces measured disparity rather than only shifting metric values | Recompute the equal opportunity gap on the augmented corpus and compare to baseline | Negative delta on any protected attribute → batch quarantined, conflict escalated |
| **P3.** Cryptographic provenance | Ensure every synthetic record carries a verifiable identity marker | SHA-256 hash incorporating model_id, batch_id, record_idx, seed, timestamp; registered in the Provenance Layer before release | Unverifiable hash → record quarantined as integrity violation |
| **P4.** Domain plausibility | Detect contextually implausible feature combinations | Domain-specific co-occurrence rules validated by a domain expert | Record fails any constraint → quarantined; batch proceeds with remainder |

The distinction between batch-level (P1, P2) and record-level (P3, P4) rejection is intentional: it preserves the usable portion of a generation run while ensuring that specific anomalies are not silently incorporated into training data.

**Provenance Layer.** Records every decision point across all layers. Unlike standard lineage systems that log what changed, this layer captures why and by whom. Each node carries: `node_id`, `event_type` (one of INGESTION, TRANSFORMATION, VALIDATION, FAIRNESS_AUDIT, SYNTHESIS, ESCALATION, AUTHORIZATION, DEPLOYMENT), `timestamp`, `layer_origin`, `actor_id`, `input_refs`, `output_refs`, `decision_rationale`, `flags`, and `schema_version`. SYNTHESIS nodes additionally carry `generation_params` and `validation_results`. The evaluation criteria are *lineage completeness* (fraction of transformations with rationale), *decision coverage* (fraction of escalations with matching authorization), *backward traceability depth* (longest ancestor chain), and *orphan nodes* (events with no inputs or outputs). The minimum target on all criteria is 1.0 (lineage completeness, decision coverage) with zero orphan nodes.

### Inter-layer dependencies and three conflict types

The conflicts between layer requirements are structural, not edge cases. Three categories arise consistently and each has an explicit resolution protocol:

**Integrity–Fairness conflict.** Arises when enforcing data completeness disproportionately removes underrepresented groups. The protocol logs the exclusion rule with a demographic impact assessment before enforcement; if any protected group's exclusion rate exceeds twice the majority's, the decision is escalated to a human reviewer rather than applied automatically.

**Fairness–Synthesis conflict.** Arises when synthetic augmentation improves aggregate fairness metrics while either degrading distributional fidelity or shifting disparity to a different protected attribute. The protocol requires that every batch pass both P1 (fidelity) and P2 (fairness delta). Batches that improve P1 but fail P2 are quarantined, and the merged corpus reverts to the pre-synthesis state with an authorization record documenting the decision.

**Provenance–Integrity conflict.** Arises when schema migrations applied to improve integrity invalidate earlier provenance records. The protocol requires versioned provenance: each schema migration generates a new lineage node rather than overwriting the prior state, preserving backward traceability across structural changes.

These protocols do not resolve conflicts algorithmically; they ensure conflicts are documented and escalated to a human decision-maker whose identity and rationale are recorded in the provenance graph. The distinction is substantive: an automated system that silently resolves an Integrity–Fairness conflict by dropping records is compliant but not accountable.

### Five design principles

The framework rests on five principles that constrain both implementation and evaluation.

**DP1. Recursive verification over sequential checkpoints.** Each layer reassesses outputs from prior layers rather than accepting them as given. After synthesis, the augmented corpus returns to the Integrity Layer for re-validation; after re-validation, the Fairness Layer recomputes disparity metrics. The cycle is explicit, not implicit.

**DP2. Explicit inter-layer handoffs.** Every transition produces a documented artifact — a quality report, a fairness audit record, a synthesis log, a provenance node — that serves simultaneously as the input to the next layer and as the audit evidence for retrospective review. No transformation is implicit.

**DP3. Human escalation for irreducible trade-offs.** Decisions involving conflicts that cannot be resolved algorithmically — demographic exclusion thresholds, synthetic batch authorization, schema migration approvals — must be escalated to a designated human reviewer whose identity and rationale enter the provenance record.

**DP4. Decision-level provenance over entity-level logging.** The provenance graph records not only *what* changed and *when*, but *why* and *by whom*. This shifts accountability from organizational entities to specific decisions, enabling regulatory audits to trace harm to its origin.

**DP5. Failure visibility over failure prevention.** The pipeline does not aim to eliminate errors; it aims to make errors detectable, locatable, and correctable. A system that surfaces and documents failures provides more durable accountability than a system designed to prevent them through opacity.

[^1]: Afroogh, P. et al. (2024). *Trust in AI: Progress, challenges, and future directions.* Artif. Intell. Rev. doi:10.1007/s10462-024-10648-2.
[^2]: Alzubaidi, L. et al. (2023). *Towards Risk-Free Trustworthy Artificial Intelligence.* Inf. Fusion. doi:10.1016/j.inffus.2023.102180.
[^3]: NIST. (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0).*
[^4]: Schwabe, D. et al. (2024). *The METRIC-framework for assessing data quality for trustworthy AI in medicine.* npj Digit. Med. 7:11. doi:10.1038/s41746-024-01196-4.
[^5]: Calders, T., Verwer, S. (2010). *Three naive Bayes approaches for discrimination-free classification.* Data Min. Knowl. Discov. 21:277–292.
[^6]: Hardt, M., Price, E., Srebro, N. (2016). *Equality of Opportunity in Supervised Learning.* NeurIPS 29.
[^7]: Kusner, M.J. et al. (2017). *Counterfactual Fairness.* NeurIPS 30.
[^8]: Shahul Hameed, M.A., Qureshi, A.M., Kaushik, A. (2024). *Bias Mitigation via Synthetic Data Generation.* Electronics 13:3909.
[^9]: Ahmed, M. et al. (2023). *Data Provenance in Healthcare.* Sensors 23:6495.
[^10]: Nastoska, A. et al. (2025). *Evaluating Trustworthiness in AI.* Electronics 14:2717.
[^11]: Cross, M. et al. (2024). *Bias in medical AI.* Lancet Digit. Health 6:2.
[^12]: Hanna, N. et al. (2025). *Ethical and Bias Considerations in AI/ML.* IEEE Trans. Technol. Soc.
[^13]: Kapania, N. et al. (2025). *Examining the Expanding Role of Synthetic Data Throughout the AI Development Pipeline.* Patterns 6:1.
[^14]: European Union. (2024). *Artificial Intelligence Act.*
[^15]: ISO/IEC. (2023). *ISO/IEC 42001: Artificial Intelligence Management System (AIMS).*
[^16]: van Bekkum, M., Borgesius, F.Z. (2023). *Using sensitive data to prevent discrimination by AI.* Comput. Law Secur. Rev. 49.
[^17]: Dammu, I. et al. (2026). *Toward a Data-Centric Framework for Trustworthy AI.* Curr. Opin. Biomed. Eng. 37:100649.

---

## Results

We evaluated the Data-Centric Trust Pipeline on two canonical fairness benchmarks: the Adult Census Income dataset (UCI; n = 32,561 raw, 30,162 after Integrity validation) and the ProPublica COMPAS recidivism dataset (n = 7,214 raw, 6,130 after standard preprocessing[^18] and Integrity validation). The two datasets cover distinct sensitive domains (employment/income discrimination and criminal-justice recidivism) and exhibit substantially different baseline characteristics. Both expose `race` and `sex` as protected attributes and a binary outcome (`income > 50K` and `two_year_recid` respectively). All runs use `random_state = 42`; the full reference implementation is open-source (see Resource Availability).

### Integrity Layer outcomes

The Integrity Layer normalizes sentinel values (`"?"`, `"NA"`, `"Unknown"`) to NaN, then runs structural and semantic checks. On Adult, 2,399 records (7.4%) were quarantined for structural missingness, almost entirely concentrated in the `workclass`, `occupation`, and `native-country` fields. Crucially, the demographic coverage analysis revealed that the exclusion rate was distributed approximately uniformly across protected groups; the Integrity–Fairness conflict trigger (exclusion rate > 2× the majority's) did not fire. On COMPAS, the dataset arrived pre-cleaned through the standard ProPublica filter, and no records required quarantine.

These results are unspectacular but consequential: the Integrity Layer's most important output here is not the validated corpus but the *demographic coverage matrix*, which the Fairness Layer consumes as evidence that subsequent disparity findings cannot be attributed to skewed integrity-driven exclusions.

### Fairness Layer: baseline disparities

We measured the equal opportunity gap (Hardt, Price, Srebro)[^6] and the demographic parity gap (Calders and Verwer)[^5] on the Integrity-validated corpus. A random forest classifier (`n_estimators=100`, `max_depth=10`) trained on the validated corpus served as the audit target. Counterfactual fairness was approximated through a matching procedure detailed in Experimental Procedures.

**Table 2. Baseline fairness metrics on the Integrity-validated corpus.** Demographic parity and equal opportunity gaps are reported as the maximum minus minimum across protected-group strata. Counterfactual fairness is the mean absolute prediction divergence under nearest-neighbor matching across the protected-attribute groups (500 sampled records); higher values indicate stronger dependence of the prediction on the protected attribute conditional on observed covariates.

| Dataset | Attribute | Demographic parity gap | Equal opportunity gap | Counterfactual fairness score |
|---|---|---|---|---|
| Adult | race | 0.1813 | 0.2254 | 0.2316 |
| Adult | sex   | 0.1562 | 0.0513 | 0.2170 |
| COMPAS | race | 0.3180 | 0.3350 | 0.0622 |
| COMPAS | sex   | 0.1264 | 0.1003 | 0.0513 |

The counterfactual fairness scores reveal a pattern that the parity and opportunity gaps obscure. On Adult, prediction divergence under matched counterfactuals is substantial for both race (0.232) and sex (0.217) — the classifier is making materially different predictions for otherwise-similar records that differ only in the protected attribute. On COMPAS the same metric is smaller (0.062 and 0.051), suggesting that the recidivism prediction depends less on the protected attribute conditional on the available covariates than the demographic parity gap (0.318) alone would imply. Both datasets exceed the 0.10 equal opportunity threshold on at least one attribute, which is the trigger the Fairness Layer uses to forward rebalancing recommendations to Synthesis.

The equal opportunity gap exceeded the 0.10 threshold for race on both datasets and for sex on COMPAS, triggering rebalancing recommendations. The Fairness Layer's rebalancing logic measures each group's true positive rate against the highest-performing group; any group with a gap above 0.10 enters the rebalancing target list. On Adult, the highest-TPR race group is Asian-Pac-Islander (TPR 0.702); all four remaining race categories — White (0.588), Amer-Indian-Eskimo (0.529), Black (0.511), and Other (0.476) — exceed the 0.10 threshold against this reference and become Synthesis targets. On COMPAS, the highest-TPR race group is African-American (TPR 0.754); Caucasian (0.534), Hispanic (0.482), and Other (0.419) each exceed the threshold and enter the target list, alongside Female on the sex attribute.

### Synthesis Layer: P1 passes, P2 fails

For each rebalancing target, the Synthesis Layer fitted a Gaussian Copula synthesizer on the source-group subset and generated 50% additional records (capped at 3,000 per group). Every record was hashed (P3) and run through the domain plausibility check (P4, with rules constraining age ≥ 17, valid hours-per-week and education range for Adult; age ≥ 17, valid priors_count and decile_score for COMPAS).

**Table 3. Per-batch synthesis outcomes across both datasets (8 batches total).** P1, P3, and P4 are evaluated per batch. P2 is evaluated at corpus level after all accepted batches are merged, so the P2 delta column shows the per-attribute corpus-level delta as inherited by each batch in that attribute group; this is intentional, since the Fairness–Synthesis conflict is defined at the corpus level and individual batches cannot pass P2 unless the corpus as a whole improves.

| Dataset | Target | N generated | P1 JS divergence | P1 passed | P2 delta | P2 passed | P3 verify | P4 plausibility |
|---|---|---|---|---|---|---|---|---|
| ADULT | race = Amer-Indian-Eskimo | 143 | 0.0795 | ✓ | −0.1066 | ✗ | 1.00 | 1.00 |
| ADULT | race = Black | 1,408 | 0.0499 | ✓ | −0.1066 | ✗ | 1.00 | 1.00 |
| ADULT | race = Other | 115 | 0.0476 | ✓ | −0.1066 | ✗ | 1.00 | 1.00 |
| ADULT | race = White | 3,000 | 0.0245 | ✓ | −0.1066 | ✗ | 1.00 | 1.00 |
| COMPAS | race = Caucasian | 1,051 | 0.0031 | ✓ | +0.0177 | ✓ | 1.00 | 1.00 |
| COMPAS | race = Hispanic | 254 | 0.0174 | ✓ | +0.0177 | ✓ | 1.00 | 1.00 |
| COMPAS | race = Other | 171 | 0.0117 | ✓ | +0.0177 | ✓ | 1.00 | 1.00 |
| COMPAS | sex = Female | 585 | 0.0035 | ✓ | −0.0658 | ✗ | 1.00 | 1.00 |

P1, P3, and P4 passed for all 8 batches: JS divergences ranged from 0.003 to 0.080 (all below the 0.10 threshold), every record's cryptographic hash verified, and every record satisfied the domain plausibility rules. **P2 failed for 5 of 8 batches.** On Adult, all four batches produced a negative fairness delta on the race attribute (−0.107); the augmented corpus's equal opportunity gap on race rose from 0.225 to 0.332, with a corresponding rise on sex from 0.051 to 0.080. On COMPAS, three of four batches passed P2 on the race attribute (delta +0.018), but the sex = Female batch failed (delta −0.066) — synthesis improved race fairness slightly while worsening sex fairness substantially.

These findings have a specific interpretation. The synthesizer faithfully reproduced the source distribution of each underrepresented group (this is what high P1 confirms). But reproducing the source distribution of a group whose attribute-target relationship is already biased *amplifies* that bias rather than correcting it: more records of an underrepresented group whose positive-outcome rate is lower than the majority's reinforces the classifier's existing pattern. This is consistent with the theoretical analyses of Pasculli et al.[^19] and Capasso,[^20] who argue that synthetic records are not neutral substitutes for real data but epistemic artifacts shaped by the source distribution's existing asymmetries.

### Fairness–Synthesis conflict resolution

Per the conflict protocol specified in the framework, any negative P2 delta triggers escalation to a human reviewer. The Synthesis Layer records an ESCALATION node in the Provenance Layer with the affected attribute(s) and measured delta; the Governance Officer role then issues an AUTHORIZATION node documenting the resolution. Our reference implementation's default policy is conservative rollback: the merged corpus reverts to the Integrity-validated baseline, the synthetic batches are quarantined, and the authorization decision is permanently recorded.

The rollback was executed in both runs. On Adult, the post-rollback equal opportunity gap returned to the baseline values (race 0.225, sex 0.051). On COMPAS, the same restoration occurred (race 0.335, sex 0.100). The cross-dataset comparison is summarized in Figure 1.

**Figure 1.** *Cross-dataset comparison of equal opportunity gap across three states.* Baseline (Integrity-validated corpus, navy), after naive synthesis pre-rollback (red), and after pipeline post-rollback (green). The horizontal dashed line marks the P2 threshold (0.10). Naive synthesis worsened the gap on Adult (race: 0.225 → 0.332; sex: 0.051 → 0.080), partially improved race on COMPAS (0.335 → 0.317) but substantially worsened sex (0.100 → 0.166), and the pipeline's automatic rollback restored the baseline in both cases.

`[INSERT cross_dataset_summary.png]`

The conservative rollback policy is a deliberate choice: in both runs the Synthesis Layer generated batches that *individually* would have improved the targeted attribute (race on Adult and COMPAS) but jointly worsened fairness on a different protected attribute (sex on COMPAS, race itself on Adult through the recursive interaction). The pipeline's design — operating at the corpus level rather than the per-batch level — surfaces these inter-batch interactions that a batch-by-batch evaluation would miss.

### Provenance Layer: decision-level traceability

The provenance graph for each run captured the full pipeline lineage as a directed acyclic graph with rich decision rationales attached to each node.

**Table 4. Provenance Layer evaluation criteria across both runs.**

| Metric | Adult | COMPAS | Target |
|---|---|---|---|
| Total nodes | 15 | 14 | — |
| Lineage completeness | 1.00 | 1.00 | 1.00 |
| Decision coverage | 1.00 | 1.00 | 1.00 |
| Max traceability depth | 10 | 9 | — |
| Orphan nodes | 0 | 0 | 0 |
| Escalation count | 2 | 1 | — |
| Authorization count | 2 | 2 | — |

Both runs achieved full lineage completeness (every transformation event carries an explicit rationale, flags, or metrics) and full decision coverage (every escalation has a matching authorization with the role, identity, and rationale of the human authorizer). The traceability depth of 9–10 indicates that any leaf node in the graph — for instance, the final post-rollback fairness audit — can be traced back through every prior decision. The full COMPAS provenance graph is shown in Figure 2.

**Figure 2.** *Provenance graph for the COMPAS pipeline run.* Nodes are color-coded by event type. The flow proceeds from the data source (left) through Integrity validation, initial Fairness audit, Authorization for synthesis, four parallel Synthesis events, Integrity re-validation of the augmented corpus, Fairness re-audit, an Escalation when P2 regression on sex was detected, the Governance Officer's Authorization for rollback, and the final Fairness audit on the rolled-back corpus.

`[INSERT provenance_graph_compas.png]`

This is what decision-level provenance means in practice. A regulatory audit of either run can answer not only what changes were made to the training data but who authorized each decision, on what evidence, and with what stated rationale. Specifically, in the COMPAS run, an auditor inspecting the final corpus would find: (i) why 585 synthetic Female records were generated (rebalancing recommendation, gap 0.166), (ii) why those records were ultimately not used (P2 regression of −0.066 on the sex attribute), (iii) who made the rollback decision (the Governance Officer role), and (iv) on what stated grounds (the documented rationale in the AUTHORIZATION node). This is the information that post-deployment audits and regulatory reviews actually require, and which standard provenance systems do not capture.

### Multi-seed robustness

To assess whether the P1-passes-but-P2-fails pattern is an artifact of a single seed or a robust property of the synthesizer-data combination, we ran the full pipeline three times on each dataset with seeds {13, 42, 137}, holding all other configuration identical. Table 5 reports the aggregate outcomes.

**Table 5. Multi-seed aggregate outcomes (mean ± standard deviation across three seeds).**

| Dataset | Attribute | Baseline EO gap | Pre-rollback EO gap | P2 delta | Seeds with P2 < 0 | Rollback executed |
|---|---|---|---|---|---|---|
| Adult | race | 0.199 ± 0.024 | 0.319 ± 0.018 | −0.120 ± 0.023 | 3/3 | 3/3 |
| Adult | sex | 0.052 ± 0.005 | 0.082 ± 0.015 | −0.030 ± 0.010 | 3/3 | 3/3 |
| COMPAS | race | 0.330 ± 0.020 | 0.314 ± 0.006 | +0.016 ± 0.014 | 0/3 | 3/3 |
| COMPAS | sex | 0.099 ± 0.001 | 0.133 ± 0.029 | −0.034 ± 0.027 | 3/3 | 3/3 |

The P2 regression pattern is robust across seeds. On Adult, every seed produced a negative P2 delta on both race (range −0.108 to −0.147) and sex (range −0.021 to −0.041). On COMPAS, the race attribute exhibited a small positive P2 delta in all three seeds (range +0.001 to +0.030), but the sex attribute exhibited a consistently negative delta (range −0.017 to −0.066). Critically, the rollback protocol fired in every one of the six (dataset, seed) combinations — because rollback is triggered by *any* protected attribute failing P2, and at least one attribute failed in every run. Figure 3 displays the per-seed distribution.

**Figure 3.** *Multi-seed robustness of the P2 fairness delta.* Each dot is one seed's P2 delta outcome for a given (dataset, attribute) cell; the horizontal black line is the mean across the three seeds. Red = mean P2 < 0 (regression); green = mean P2 ≥ 0 (improvement). Adult exhibits negative deltas on both attributes across all seeds; COMPAS exhibits positive race deltas and negative sex deltas across all seeds. The rollback protocol was executed in all six runs, since any single negative attribute triggers corpus-level reversion.

`[INSERT multi_seed_p2_distribution.png]`

These results address the most predictable critique of the original n = 1 experiment: that the negative P2 deltas might have been a single-seed artifact of the random forest's tree-splitting variance or of the Gaussian Copula's sampling. They are not. The qualitative finding — naive distributional synthesis passes P1 but fails P2 in a way that requires the pipeline's rollback protocol to surface — replicates across seeds without exception. The quantitative magnitudes are stable within roughly 15–25% of their means, with the largest variance on the COMPAS sex attribute, which is also the smallest absolute effect.

### Cross-dataset synthesis

The two evaluations converge on three claims. First, distributional fidelity is insufficient as a single check: across 8 synthesis batches with mean JS divergence 0.025 (max 0.080), 5 batches produced negative fairness deltas. Second, the four-protocol structure (P1 fidelity, P2 fairness, P3 provenance, P4 plausibility) is what makes synthesis governable, since the failure mode is detected only by P2. Third, full decision-level provenance is achievable with modest engineering overhead: the entire eight-step COMPAS pipeline produces a 14-node graph with full lineage and decision coverage, which adds well under one second to total execution time.

[^18]: ProPublica preprocessing applied: `days_b_screening_arrest ∈ [-30, 30]`, `is_recid ≠ -1`, `c_charge_degree ≠ "O"`, `score_text ≠ "N/A"`, races restricted to African-American, Caucasian, Hispanic, Other.
[^19]: Pasculli, G. et al. (2025). *Synthetic Data in Healthcare and Drug Development.* CPT: Pharmacomet. Syst. Pharmacol. 14:840–852.
[^20]: Capasso, M. (2025). *Synthetic data as meaningful data: On responsibility in data ecosystems.* Philos. Technol.

---

## Discussion

The empirical findings have a counterintuitive structure: the synthetic batches that passed every standard fidelity check produced fairness regressions in 5 of 8 cases, and the pipeline's value lies in detecting and rolling back precisely those statistically faithful but substantively harmful augmentations. This vindicates the framework's central claim — that the four-protocol structure exists because no single protocol is sufficient — but it also raises three issues worth engaging directly.

**Why naive synthesis fails fairness.** The mechanism is not subtle. Generating additional records from the source distribution of an underrepresented group preserves whatever attribute-target relationship that group already exhibits, including the bias that motivated rebalancing in the first place. If the underrepresented group's positive-outcome rate is depressed by structural factors (sampling, coding practice, historical exclusion patterns) rather than by mere undersampling, then sampling more from that distribution amplifies the bias. This is the mechanism Capasso[^20] frames philosophically as synthetic data being "not neutral substitutes for real data but epistemic artefacts shaped by generative model design," and which Pasculli et al.[^19] frame regulatorily. The pipeline's contribution is making this mechanism *operationally diagnosable*: the P2 audit detects in a single test what would otherwise require theoretical analysis of the generation process.

**Implications for regulation.** The EU AI Act, ISO/IEC 42001, and the NIST AI RMF specify documentation requirements at the category level — datasets must be characterized, training procedures documented, post-deployment monitoring established. They do not specify the inter-layer mechanics by which fidelity, fairness, and provenance must communicate. The empirical results suggest that this granularity matters: an organization could satisfy every category-level requirement of the EU AI Act with a static data card describing the synthetic batches we generated, yet operate a pipeline in which the P2 regression we measured would never have been detected. We propose that data-governance regulation move from entity-level accountability (which organization is responsible?) to *decision-level accountability* (which decision, made by whom, under what evidence, produced this outcome?). The minimum lineage record structure in the framework specifies what this would require operationally.

**Scope conditions and what the pipeline does not do.** The pipeline is designed for AI systems where demographic disparities in outcomes carry significant ethical, legal, or clinical weight — the four sensitive domains motivating the framework. It is less directly applicable to settings where training data does not involve person-level records or where the primary risk is not distributional bias but model robustness or adversarial vulnerability. The framework governs the data layer; it presupposes but does not replace model governance. The Fairness Layer's threshold of 0.10 for the equal opportunity gap and the Synthesis Layer's JS divergence threshold of 0.10 are not universal constants but illustrative defaults that should be domain-justified; what the pipeline standardizes is the *process* of setting and documenting such thresholds, not the values themselves.

**Relationship to class-balancing methods.** Methods such as SMOTE and its variants[^22] also generate synthetic records to address imbalance, and a natural question is whether the present results merely repeat what SMOTE-style oversampling already establishes. They do not, for two related reasons. First, the unit of imbalance differs: SMOTE oversamples the minority *class* (the positive label) conditional on the full feature distribution; the Synthesis Layer oversamples the underrepresented protected *group* — its generation prior is the source distribution of the group itself, not the minority class. Second, and more consequentially, the contribution of the present framework is not the generator but the validation structure surrounding it. The same P1–P4 protocol applied to SMOTE-generated records would yield the same conclusion: high distributional fidelity, potential failure on the fairness delta audit (P2) when the underlying attribute-target relationship is itself biased. The pipeline's value is the four-protocol audit, the cryptographic per-record provenance, the corpus-level P2 evaluation, and the conflict-resolution rollback — components that are absent from SMOTE-style methods regardless of the generator used. Any tabular synthesizer (Gaussian Copula, SMOTE, CTGAN, TVAE) can serve as the Synthesis Layer's backend; what makes the synthesis governable is the protocol structure, not the choice of generator.

**Comparison with related frameworks.** The Data-Centric Trust Pipeline is positioned alongside but distinct from the data-centric perspective of Dammu et al.,[^17] who propose a layered structure integrating governance, fairness, validation, and lifecycle accountability. The differences are specific. First, the present framework formalizes inter-layer dependencies through a taxonomy of inputs, outputs, and conflict-resolution protocols — a structural specification absent from prior data-centric frameworks. Second, synthetic data is treated as a first-class governance layer with the four-protocol validation structure rather than as a bias-mitigation technique appended to model development. Third, the empirical demonstration grounds the framework in measurable artifacts — the per-batch P1–P4 outcomes, the provenance graph evaluation metrics — rather than in conceptual claims alone. Relative to the NIST AI RMF and ISO/IEC 42001, the pipeline is more granular at the data layer but compatible with their organizational scope; we expect the framework to constitute a concrete technical architecture for the data-governance categories these standards specify.

### Limitations

Three limitations bound the empirical claims.

First, the synthesizer used (Gaussian Copula via SDV) is one of several available generative families. CTGAN, TVAE, and diffusion-based tabular synthesizers may produce different P1–P2 profiles on the same datasets. The pipeline's design is synthesizer-agnostic, but the specific quantitative outcomes reported here are tied to the Gaussian Copula's behavior on Adult and COMPAS; the qualitative finding (P1 passes, P2 fails) replicates across the three random seeds we tested but should be confirmed with additional generators in future work. The multi-seed analysis (n = 3 seeds) is sufficient to rule out single-seed artifact but does not establish formal confidence intervals; a larger seed sweep (n ≥ 20) would tighten the variance estimates reported in Table 5.

Second, the evaluation uses Adult and COMPAS — canonical but small fairness benchmarks with documented limitations.[^21] The framework's behavior on larger-scale industrial pipelines, particularly with many more protected attributes or with intersectional groupings, remains to be tested. We expect the inter-layer protocols to scale (their cost is constant per transformation event), but the human-escalation paths require organizational infrastructure that not all settings provide.

Third, the framework presupposes organizational conditions that not all institutions possess: defined roles (Data Steward, Fairness Analyst, Governance Officer), a shared data ontology for cross-source semantic validation, and provenance records treated as institutional artifacts with defined retention and access controls. The technical components alone, implemented without this organizational substrate, produce documentation that is technically present but interpretively empty.

[^21]: Bao, M. et al. (2021). It's COMPASlicated: The Messy Relationship between RAI Datasets and Algorithmic Fairness Benchmarks. NeurIPS Datasets and Benchmarks.
[^22]: Chawla, N.V., Bowyer, K.W., Hall, L.O., Kegelmeyer, W.P. (2002). SMOTE: Synthetic Minority Over-sampling Technique. J. Artif. Intell. Res. 16:321–357.

---

## Experimental Procedures

### Implementation

The pipeline is implemented in Python 3.12 across five modules: `integrity.py` (404 lines), `fairness.py` (309 lines), `synthesis.py` (327 lines), `provenance.py` (242 lines), and `pipeline.py` (303 lines). Dependencies include `pandas`, `numpy`, `scipy`, `scikit-learn`, `fairlearn`, `sdv` (Gaussian Copula synthesizer), and `networkx` (lineage graph). The full implementation is open-source under the MIT license; the public release contains pinned versions and a single-command reproduction script.

### Datasets

Adult Census Income was obtained from the algofairness/fairness-comparison GitHub mirror of the UCI repository (32,561 records, 15 columns). COMPAS Recidivism was obtained from the ProPublica compas-analysis GitHub repository (7,214 records, 53 columns; reduced to 6,130 after standard filtering). Both are publicly available; neither contains personally identifiable information beyond what the original sources released.

### Configuration

For both runs: `random_state=42`, equal-opportunity threshold = 0.10, JS divergence threshold (P1) = 0.10, P4 minimum plausibility pass rate = 0.95, oversampling ratio = 0.5 (capped at 3,000 records per group). The Fairness Layer's random forest classifier uses `n_estimators=100, max_depth=10`. The Synthesis Layer's Gaussian Copula synthesizer uses `enforce_min_max_values=True, enforce_rounding=False`. Counterfactual fairness sampling uses 500 records with 1-nearest neighbor matching in the opposite protected-attribute group.

### Per-record cryptographic provenance (P3)

Each synthetic record's identity hash is computed as `SHA256("{model_id}|{batch_id}|{record_idx}|{seed}|{timestamp_iso}")`, attached as the `__provenance_hash` column at generation time, and the batch hash set is registered as a SYNTHESIS node in the Provenance Layer before the batch is released. Verification at integration time checks both hash well-formedness (64 hex characters) and within-batch uniqueness.

### Plausibility rules (P4)

Domain rules are passed as callables that evaluate a single record. For Adult: `age ∈ [17, 90]`, `hours-per-week ∈ [1, 99]`, `education-num ∈ [1, 16]`. For COMPAS: `age ≥ 17`, `priors_count ≥ 0`, `decile_score ∈ [1, 10]`. These are illustrative defaults; production deployments should derive rules from domain expert validation as specified in the framework.

### Reproducibility

The complete reproduction sequence is:

```
pip install -r requirements.txt
python experiments/run_adult.py
python experiments/run_compas.py
python experiments/cross_dataset.py
# Multi-seed robustness (Table 5, Figure 3):
for seed in 13 42 137; do
    python experiments/single_seed.py --dataset adult --seed $seed
    python experiments/single_seed.py --dataset compas --seed $seed
done
python experiments/aggregate_multi_seed.py
```

All artifacts (per-run JSON summaries, provenance graphs, figures, comparison tables) regenerate deterministically. Total wall-clock time on commodity hardware is approximately 8–12 minutes including the multi-seed sweep.

---

## Resource Availability

**Lead contact.** Carlos Diego Cavalcanti Pereira (cdiego@mit.edu).

**Materials availability.** No physical materials were generated.

**Data and code availability.** The full source code, configuration, run logs, provenance graphs, and figures are released under the MIT license at `https://github.com/cdiegocom/dctp` and archived on Zenodo (DOI to be assigned upon submission). Source datasets (Adult Census Income, ProPublica COMPAS) are publicly available; redistributed copies are included for reproducibility under their original licenses. This study analyzes only public, secondary data; no new data were collected.

---

## Acknowledgments

This research was conducted as part of the author's extended research and residency activities at the Sloan School of Management within the Visiting Fellows Program at the Massachusetts Institute of Technology. The author, a professor and researcher at CESAR School (Recife Center for Advanced Studies and Systems), gratefully acknowledges the intellectual environment that supported this work. No external funding was received.

## Declaration of Interests

The author declares no competing interests.

## References

(Citations are numbered above as footnotes for drafting purposes; final submission will use the Patterns numbered-reference style. Full bibliographic entries are available in the project repository's `references.bib`.)
