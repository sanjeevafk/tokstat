# TokStat — AI Engineering Telemetry Observatory & Token Tracker
#
# Common developer workflows. Run `make help` to list targets.
# The default flow is `make run` -> gather usage from every local source,
# generate the dashboard and open it in your browser.

PYTHON ?= python3
PIP := $(PYTHON) -m pip

.PHONY: help install dev test lint format check run watch collect migrate \
        daemon-start daemon-stop daemon-status proxy proxy-start proxy-stop proxy-status \
        build release-check publish clean

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install the package (editable)
	$(PIP) install -e .

dev: ## Install the package with dev/test dependencies
	$(PIP) install -e ".[dev]"

test: ## Run the test suite
	pytest

lint: ## Lint with ruff
	ruff check src tests

format: ## Auto-fix lint issues and format the code
	ruff check --fix src tests
	ruff format src tests

check: lint test ## Lint + test (CI gate)

run: ## Gather all usage, generate the dashboard and open it in the browser
	$(PYTHON) -m tokstat.cli

watch: ## Live watch mode with browser updates
	$(PYTHON) -m tokstat.cli --watch

collect: ## Gather usage once from all local sources
	$(PYTHON) -m tokstat.cli collect --once

migrate: ## Import legacy OpenUsage/Tokentop history (read-only)
	$(PYTHON) -m tokstat.cli migrate

daemon-start: ## Start the background daemon (collectors + ingestion server)
	$(PYTHON) -m tokstat.cli daemon start

daemon-stop: ## Stop the background daemon
	$(PYTHON) -m tokstat.cli daemon stop

daemon-status: ## Show daemon + collector status
	$(PYTHON) -m tokstat.cli daemon status

proxy: proxy-start ## Alias for proxy-start (local-model proxy)

proxy-start: ## Start the local-model proxy (default upstream http://localhost:11434)
	$(PYTHON) -m tokstat.cli proxy start

proxy-stop: ## Stop the local-model proxy
	$(PYTHON) -m tokstat.cli proxy stop

proxy-status: ## Show proxy status
	$(PYTHON) -m tokstat.cli proxy status

build: ## Build sdist + wheel into dist/
	rm -rf build dist
	find . -maxdepth 3 -name '*.egg-info' -prune -exec rm -rf {} +
	$(PIP) install -q build
	$(PYTHON) -m build

release-check: build ## Build and verify the release artifacts
	$(PIP) install -q twine
	twine check dist/*

publish: release-check ## Upload the release to PyPI (needs TWINE_USERNAME/PASSWORD or a token)
	twine upload dist/*

clean: ## Remove build artifacts, caches and generated dashboards
	rm -rf build dist .pytest_cache .ruff_cache
	find . -maxdepth 3 -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f tokstat_dashboard.html openusage_dashboard.html
