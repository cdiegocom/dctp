# Makefile for the Data-Centric Trust Pipeline manuscript

.PHONY: all paper clean experiments multiseed multibackend

all: paper

# Build the LaTeX manuscript (main.pdf)
paper: main.pdf

main.pdf: main.tex references.bib
	pdflatex -interaction=nonstopmode main.tex
	biber main
	pdflatex -interaction=nonstopmode main.tex
	pdflatex -interaction=nonstopmode main.tex

# Reproduce the primary empirical results
experiments:
	python3 experiments/run_adult.py
	python3 experiments/run_compas.py
	python3 experiments/cross_dataset.py

# Reproduce the multi-seed robustness analysis (10 seeds, ~25 min)
multiseed:
	@for seed in 7 13 23 42 71 101 137 211 313 911; do \
		echo "=== Adult seed=$$seed ==="; \
		python3 experiments/single_seed.py --dataset adult --seed $$seed; \
		echo "=== COMPAS seed=$$seed ==="; \
		python3 experiments/single_seed.py --dataset compas --seed $$seed; \
	done
	python3 experiments/aggregate_multi_seed.py

# Reproduce the multi-generator robustness analysis (3 seeds × 3 backends, ~45 min)
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

# Clean LaTeX build artifacts (keeps main.pdf)
clean:
	rm -f main.aux main.bbl main.bcf main.blg main.log main.out \
	      main.run.xml main.toc

# Full clean (also removes main.pdf and experiment outputs)
distclean: clean
	rm -f main.pdf
	rm -rf results/figures/*.png results/tables/* results/provenance_graphs/*
