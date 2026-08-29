.PHONY: sync lint-actions test test-integration dev-services-up dev-services-down cov-report cov lint-typing lint-style lint-fmt lint-check lint-typos lint-all security-bandit security-audit security build wheel-test clean help docs-api docs-install docs-dev docs-build

help:
	@echo "Available make targets:"
	@echo "  make sync             - Sync project and install dependencies"
	@echo "  make test             - Run unit tests with coverage"
	@echo "  make test-integration - Run integration tests (requires network)"
	@echo "  make dev-services-up  - Start local Neo4j/Qdrant/Weaviate/Milvus for integration tests"
	@echo "  make dev-services-down - Stop and remove local backend services and their data"
	@echo "  make cov-report       - Generate coverage reports (xml, html)"
	@echo "  make cov              - Run tests and generate coverage reports"
	@echo "  make lint-typing      - Type check with ty"
	@echo "  make lint-style       - Lint with ruff (check only)"
	@echo "  make lint-fmt         - Format code and lint with auto-fixes"
	@echo "  make lint-check       - Check formatting and lint without modifying files"
	@echo "  make lint-typos       - Check for typos"
	@echo "  make lint-actions     - Audit GitHub Actions workflows with zizmor"
	@echo "  make lint-all         - Run formatting, linting, and type checking"
	@echo "  make security-bandit  - Run Bandit security scan"
	@echo "  make security-audit   - Run pip-audit dependency vulnerability scan"
	@echo "  make security         - Run all security scans"
	@echo "  make build            - Build sdist and wheel into dist/"
	@echo "  make wheel-test       - Install the built wheel in a clean env and import it"
	@echo "  make clean            - Clean build artifacts and cache"
	@echo "  make docs-api         - Regenerate docs/docs/api/index.md from docstrings"
	@echo "  make docs-install     - Install the Docusaurus site's npm dependencies"
	@echo "  make docs-dev         - Run the Docusaurus dev server"
	@echo "  make docs-build       - Regenerate the API reference and build the docs site"

sync:
	uv sync --all-groups --all-extras

test:
	uv run pytest tests/unit \
		--cov=agrag \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=pytest-results.xml

test-integration:
	uv run pytest tests/integration -v -n auto --dist loadscope \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-integration-results.xml

dev-services-up:
	docker compose -f docker/docker-compose.ci.yml up -d --wait --wait-timeout 420

dev-services-down:
	docker compose -f docker/docker-compose.ci.yml down -v

cov-report:
	uv run coverage html

cov: test cov-report

lint-typing:
	uv run ty check agrag/ tests

lint-style:
	uv run ruff check .

lint-fmt:
	uv run ruff format .
	uv run ruff check --fix --unsafe-fixes .

lint-check:
	uv run ruff format --check .
	uv run ruff check .

lint-typos:
	uv run typos

lint-actions:
	uvx zizmor .github/workflows/

lint-all: lint-fmt lint-typing lint-typos lint-actions

security-bandit:
	uv run bandit -c pyproject.toml -r agrag/ --severity-level high --confidence-level high

security-audit:
	uv run pip-audit --desc

security: security-bandit security-audit

build:
	rm -rf dist
	uv build

wheel-test: build
	rm -rf .wheelenv
	uv venv .wheelenv
	uv pip install --python .wheelenv/bin/python dist/*.whl
	cd /tmp && "$(CURDIR)/.wheelenv/bin/python" -c "import agrag; print(agrag.__version__)"

clean:
	rm -rf .coverage coverage.xml htmlcov dist build .wheelenv *.egg-info pytest-results.xml pytest-integration-results.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .ty_cache -exec rm -rf {} +

docs-api:
	mkdir -p docs/docs/api
	{ printf '%s\n' '---' 'title: API Reference' 'sidebar_position: 2' '---' ''; \
	  uv run --group docs griffe2md agrag -f; } > docs/docs/api/index.md.tmp
	mv docs/docs/api/index.md.tmp docs/docs/api/index.md

docs-install:
	cd docs && npm ci

docs-dev: docs-api
	cd docs && npm start

docs-build: docs-api
	cd docs && npm run build
