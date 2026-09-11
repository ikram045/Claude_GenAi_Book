.PHONY: help install fmt lint type test check clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync the environment and install git hooks
	uv sync
	uv run pre-commit install

fmt:  ## Format the code
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Lint without changing anything
	uv run ruff check .
	uv run ruff format --check .

type:  ## Type check
	uv run mypy src tests

test:  ## Run the tests
	uv run pytest

check: lint type test  ## Everything CI runs

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist
	find . -type d -name __pycache__ -exec rm -rf {} +
