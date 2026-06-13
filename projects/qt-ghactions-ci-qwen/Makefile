.PHONY: lint test typecheck help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

lint: ## Run ruff linter and format check
	ruff check .
	ruff format --check .

test: ## Run pytest with coverage (skips PG integration tests)
	pytest --cov=. --cov-report=html --cov-report=term -m "not integration"

typecheck: ## Run mypy on core/ and analytics/ (warnings only)
	-mypy core/ analytics/
