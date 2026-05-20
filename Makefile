.PHONY: help install dev test scrape assets videos all clean lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install package into venv
	python -m venv .venv
	.venv/bin/pip install -e .

dev: ## Install with dev deps (pytest)
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test: ## Run tests
	.venv/bin/pytest -v

scrape: ## Stage 1: scrape lectures (~20 min)
	.venv/bin/mifisec --stage 1

assets: ## Stage 2: download images/PDF (~3 min)
	.venv/bin/mifisec --stage 2

videos: ## Stage 3: download video recordings (~3 hrs)
	.venv/bin/mifisec --stage 3

videos-480: ## Stage 3: videos in 480p (smaller)
	.venv/bin/mifisec --stage 3 --quality 480

all: ## Run all stages (1→2→3)
	.venv/bin/mifisec --all

smoke: ## Quick test: scrape 5 units only
	.venv/bin/mifisec --stage 1 --limit 5

list-videos: ## List available recordings
	.venv/bin/mifisec --list-videos

clean: ## Remove vault and venv
	rm -rf vault/ .venv/ *.egg-info/ __pycache__/ .pytest_cache/
