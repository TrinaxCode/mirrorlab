# MirrorLab — developer tasks.
#
# Everything here works on macOS, Linux and Windows (Git Bash / WSL).
# Run `make` or `make help` to list the targets.

.DEFAULT_GOAL := help
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	BIN := $(VENV)/Scripts
endif

.PHONY: help install dev test test-fast lint format typecheck check \
        run demo doctor filters gestures benchmark gallery models \
        web-install web-dev web-build web-test build clean distclean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #
$(VENV):
	$(PY) -m venv $(VENV)

install: $(VENV) ## Create the venv and install MirrorLab with dev extras
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev]"

dev: install ## Alias for `install`

# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
test: ## Run the full test suite (headless, no camera required)
	PYTEST_HEADLESS=1 $(BIN)/python -m pytest

test-fast: ## Run the tests, skipping the slow end-to-end cases
	PYTEST_HEADLESS=1 $(BIN)/python -m pytest -m "not slow" -x -q

lint: ## Lint with ruff
	$(BIN)/python -m ruff check src tests

format: ## Auto-format with black and fix what ruff can
	$(BIN)/python -m black src tests
	$(BIN)/python -m ruff check --fix src tests

typecheck: ## Static type check with mypy
	$(BIN)/python -m mypy

check: lint format typecheck test ## Everything CI runs, locally

# --------------------------------------------------------------------------- #
# Running
# --------------------------------------------------------------------------- #
run: ## Start MirrorLab with defaults
	$(BIN)/mirrorlab run

demo: ## Run offline on a synthetic source (no camera needed)
	$(BIN)/mirrorlab demo --frames 120

doctor: ## Diagnose camera, backends and models
	$(BIN)/mirrorlab doctor

filters: ## List every filter
	$(BIN)/mirrorlab filters

gestures: ## List every gesture and its action
	$(BIN)/mirrorlab gestures

benchmark: ## Measure per-filter performance
	$(BIN)/mirrorlab benchmark --all --frames 20

gallery: ## Render a contact sheet of every filter
	$(BIN)/mirrorlab gallery --output assets/filter-gallery.png

models: ## Download every model bundle into the cache
	$(BIN)/mirrorlab models --download

# --------------------------------------------------------------------------- #
# Web demo
# --------------------------------------------------------------------------- #
web-install: ## Install the web demo's dependencies
	cd web && npm install

web-dev: ## Run the web demo against a local dev server
	cd web && npm run dev

web-build: ## Production build of the web demo
	cd web && npm run build

web-test: ## Unit tests for the web demo
	cd web && npm test -- --run

# --------------------------------------------------------------------------- #
# Packaging
# --------------------------------------------------------------------------- #
build: ## Build the sdist and wheel
	$(BIN)/python -m build

clean: ## Remove caches and build artefacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

distclean: clean ## `clean` plus the virtualenv and the web build
	rm -rf $(VENV) web/dist web/node_modules
