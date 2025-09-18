.PHONY: help setup test test-cov lint format check clean run

help: ## Show this help message
	@echo "RenameWithLLM - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Setup & Environment
.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip pip-tools

setup: .venv/bin/python ## Complete project setup (first time)
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/pip-compile pyproject.toml -o requirements.txt
	.venv/bin/pip-compile --extra dev pyproject.toml -o requirements-dev.txt
	.venv/bin/pre-commit install
	@echo "Setup complete! Activate with: source .venv/bin/activate"

# Testing
test: setup ## Run all tests
	.venv/bin/python -m pytest tests/ -v

test-cov: setup ## Run tests with coverage
	.venv/bin/python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Code Quality
lint: setup ## Run linting and type checking
	.venv/bin/ruff check src/ main.py tests/
	.venv/bin/mypy src/ main.py tests/

format: setup ## Format code with ruff
	.venv/bin/ruff check --fix src/ main.py tests/

check: lint test ## Run all checks (lint + test)

# Utilities
clean: ## Clean up temporary files and virtual environment
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/ .coverage htmlcov/ dist/ build/ .venv/

run: setup ## Run the tool (example)
	.venv/bin/python main.py --help
