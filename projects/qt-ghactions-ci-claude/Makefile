.PHONY: lint test typecheck install

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install ruff pytest pytest-cov mypy

lint:
	ruff check .
	ruff format --check .

test:
	pytest testing/ \
		-m "not integration" \
		--cov=core --cov=analytics \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		-v

typecheck:
	mypy core/ analytics/ \
		--ignore-missing-imports \
		--no-error-summary || true
