# Makefile — local build pipeline for pytuiplayer
#
# Requires the `uv` package manager (https://github.com/astral-sh/uv).
# Tab-indented (do not convert to spaces).

.DEFAULT_GOAL := help

.PHONY: help install sync test lint format build build-wheel build-sdist \
        build-exe dist clean

help:  ## Show available targets
	@echo "pytuiplayer build pipeline"
	@echo "  make install      Install deps (uv sync --dev)"
	@echo "  make test         Run pytest (also refreshes testsuite.db)"
	@echo "  make lint         Run ruff check"
	@echo "  make format       Run ruff format"
	@echo "  make build        Build wheel + sdist into dist/"
	@echo "  make build-exe    Build one-file PyInstaller binary into dist/"
	@echo "  make dist         build + build-exe"
	@echo "  make clean        Remove build artifacts (dist/, build/, caches)"

install sync:  ## Install project + dev dependencies
	uv sync --dev

test:  ## Run the test suite (uv run pytest -q)
	uv run pytest -q

lint:  ## Run the ruff linter
	uv run ruff check .

format:  ## Auto-format with ruff
	uv run ruff format .

build build-wheel build-sdist:  ## Build wheel + sdist (uv build)
	uv build

build-exe:  ## Build a one-file PyInstaller executable
	uv run python scripts/build_pyinstaller.py

dist: build build-exe  ## Build wheel/sdist and the one-file binary

clean:  ## Remove generated build artifacts
	rm -rf dist build src/build
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
