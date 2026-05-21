.PHONY: help install dev test scrape assets videos videos-480 all smoke list-videos link-videos wizard clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install package into venv
	python -m venv .venv
	.venv/bin/pip install -e .

dev: ## Install with dev deps (pytest, responses)
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test: ## Run 32 tests (0.3s, no network)
	.venv/bin/pytest -v

wizard: ## Interactive wizard (guided setup)
	.venv/bin/mifisec

scrape: ## Stage 1: scrape lectures → markdown (~20 min, ~20 MB)
	.venv/bin/mifisec --stage 1

assets: ## Stage 2: download images/PDF + rewrite links (~3 min, ~500 MB)
	.venv/bin/mifisec --stage 2

videos: ## Stage 3: download video recordings + link to notes (~3 hrs, ~10 GB)
	.venv/bin/mifisec --stage 3

videos-480: ## Stage 3: videos in 480p (smaller, ~5 GB)
	.venv/bin/mifisec --stage 3 --quality 480

all: ## Run all stages non-interactively (1→2→3)
	.venv/bin/mifisec --all

smoke: ## Quick test: scrape 5 units only
	.venv/bin/mifisec --stage 1 --limit 5

list-videos: ## List 208 available recordings without downloading
	.venv/bin/mifisec --list-videos

link-videos: ## Re-link downloaded videos to vault notes
	.venv/bin/python -c "from pathlib import Path; from mifisec.videos import link_videos_to_vault; v=Path('vault'); print(f'Linked: {link_videos_to_vault(v, v/\"_videos\")}')"

fix-graph: ## Reapply Graph View colors (fixes blank graph)
	.venv/bin/mifisec --fix-graph

retry-videos: ## Retry failed video downloads (skips existing)
	.venv/bin/mifisec --stage 3

retry-assets: ## Retry failed asset downloads (skips existing)
	.venv/bin/mifisec --stage 2

clean: ## Remove vault, venv, caches
	rm -rf vault/ .venv/ *.egg-info/ __pycache__/ .pytest_cache/
