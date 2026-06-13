.PHONY: test test-cov cov-report cov-html cov-detail clean

# Run tests without coverage
test:
	python -m pytest testing/ -v

# Run tests with coverage (one-click)
test-cov:
	python -m pytest testing/ \
		--cov=core --cov=analytics --cov=live --cov=factor_engine --cov=ml \
		--cov-report=term --cov-report=html \
		--cov-fail-under=40 \
		-v

# Open HTML coverage report (Windows)
cov-report:
	start htmlcov/index.html

# Generate detailed coverage report per module (with missing lines)
cov-detail:
	python -m pytest testing/ \
		--cov=core --cov=analytics --cov=live --cov=factor_engine --cov=ml \
		--cov-report=term-missing \
		--cov-fail-under=40 \
		-v

clean:
	rm -rf htmlcov .coverage .coverage.*
