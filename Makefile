# Makefile for the Data-Centric Trust Pipeline reproduction
#
# Targets:
#   make paper          — Build the compiled manuscript (main_aie.pdf)
#   make experiments    — Reproduce the primary single-seed empirical results
#   make multiseed      — Reproduce the multi-seed robustness sweep (10 seeds × 2 datasets)
#   make multibackend   — Reproduce the multi-generator robustness sweep (CTGAN, TVAE)
#   make ablation       — Reproduce the logistic regression classifier ablation
#   make all            — Manuscript + all experiments
#   make clean          — Remove LaTeX build artifacts
#   make distclean      — Also remove main_aie.pdf and experiment outputs

.PHONY: all paper clean distclean experiments multiseed multibackend ablation

all: paper experiments multiseed multibackend ablation

# ---------------------------------------------------------------------------
# Manuscript
# ---------------------------------------------------------------------------

paper: main_aie.pdf

main_aie.pdf: main_aie.tex references.bib
	pdflatex -interaction=nonstopmode main_aie.tex
	biber main_aie
	pdflatex -interaction=nonstopmode main_aie.tex
	pdflatex -interaction=nonstopmode main_aie.tex

# ---------------------------------------------------------------------------
# Primary experiments (single-seed)
# ---------------------------------------------------------------------------

experiments:
	python3 experiments/run_adult.py
	python3 experiments/run_compas.py
	python3 experiments/cross_dataset.py

# ---------------------------------------------------------------------------
# Multi-seed robustness — 10 seeds × 2 datasets, ~25 min on commodity hardware
# ---------------------------------------------------------------------------

multiseed:
	@for seed in 7 13 23 42 71 101 137 211 313 911; do \
		echo "=== Adult seed=$$seed ==="; \
		python3 experiments/single_seed.py --dataset adult --seed $$seed; \
		echo "=== COMPAS seed=$$seed ==="; \
		python3 experiments/single_seed.py --dataset compas --seed $$seed; \
	done
	python3 experiments/aggregate_multi_seed.py

# ---------------------------------------------------------------------------
# Multi-generator robustness — CTGAN and TVAE at 3 seeds × 2 datasets, ~45 min
# (Adult runs use a 5,000-record subsample; COMPAS uses full filtered dataset)
# ---------------------------------------------------------------------------

multibackend:
	@for seed in 13 42 137; do \
		for backend in ctgan tvae; do \
			echo "=== COMPAS $$backend seed=$$seed ==="; \
			python3 experiments/single_backend.py --dataset compas --seed $$seed --backend $$backend --epochs 150; \
			echo "=== Adult $$backend seed=$$seed ==="; \
			python3 experiments/single_backend.py --dataset adult --seed $$seed --backend $$backend --epochs 30 --adult-sample 5000; \
		done \
	done
	python3 experiments/aggregate_multi_backend.py

# ---------------------------------------------------------------------------
# Classifier ablation — logistic regression in place of random forest
# Added during the AIE round-1 revision in response to Reviewer 2's robustness concern
# ---------------------------------------------------------------------------

ablation:
	python3 experiments/classifier_ablation.py

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean:
	rm -f main_aie.aux main_aie.bbl main_aie.bcf main_aie.blg main_aie.log \
	      main_aie.out main_aie.run.xml main_aie.toc

distclean: clean
	rm -f main_aie.pdf
	rm -rf results/figures/*.png results/tables/* results/provenance_graphs/*
