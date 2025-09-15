.PHONY: help install install-dev sync sync-dev compile compile-dev clean test lint format check

help: ## Show this help message
	@echo "RenameWithLLM - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip pip-tools

install: .venv/bin/python ## Install production dependencies
	.venv/bin/pip install -e .

install-dev: .venv/bin/python ## Install development dependencies
	.venv/bin/pip install -e ".[dev]"

compile: .venv/bin/python ## Compile production requirements
	.venv/bin/pip-compile pyproject.toml -o requirements.txt

compile-dev: .venv/bin/python ## Compile development requirements
	.venv/bin/pip-compile --extra dev pyproject.toml -o requirements-dev.txt

compile-all: compile compile-dev ## Compile all requirements

sync: requirements.txt .venv/bin/python ## Sync production dependencies
	.venv/bin/pip-sync requirements.txt

sync-dev: requirements-dev.txt .venv/bin/python ## Sync development dependencies
	.venv/bin/pip-sync requirements-dev.txt

test: install-dev ## Run tests
	.venv/bin/python -m pytest tests/ -v

test-cov: install-dev ## Run tests with coverage
	.venv/bin/python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

test-basic: install-dev ## Run basic tests
	.venv/bin/python tests/test_basic.py

lint: install-dev ## Run linting
	.venv/bin/ruff check src/ main.py tests/
	.venv/bin/mypy src/ main.py tests/

format: install-dev ## Format code
	.venv/bin/ruff check --fix src/ main.py tests/

check: lint test ## Run all checks (lint + test)

pre-commit: install-dev ## Run pre-commit hooks on all files
	.venv/bin/pre-commit run --all-files

pre-commit-install: install-dev ## Install pre-commit hooks
	.venv/bin/pre-commit install

setup: .venv/bin/python compile-all sync-dev pre-commit-install ## Initial setup
	@echo "Setup complete! Activate with: source .venv/bin/activate"

update: compile-all sync-dev ## Update all dependencies

run: install-dev ## Run the tool (example)
	.venv/bin/python main.py --help

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf .venv/
