.PHONY: test-cov-map test-cov-map-suites sync sync-docs-pins baml-gen lint-actions test test-integration test-e2e test-eval test-all dev-services-up dev-services-down cov-report cov lint-typing lint-style lint-fmt lint-check lint-typos lint-all security-bandit security-audit security build wheel-test clean help docs-api docs-install docs-dev docs-build

export UV_LOCKED = 1

help:
	@echo "Available make targets:"
	@echo "  make sync             - Sync project and install dependencies"
	@echo "  make test             - Run unit tests with coverage"
	@echo "  make test-integration - Run integration tests (requires network)"
	@echo "  make test-e2e         - Run end-to-end pipeline tests (requires Neo4j)"
	@echo "  make test-eval        - Run judged and real-agent evals (requires Neo4j and an LLM key)"
	@echo "  make test-all         - Run unit, integration, and e2e tests in order"
	@echo "  make test-cov-map     - Run all suites with JUnit files and per-test coverage contexts"
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
	@echo "  make docs-api         - Regenerate docs/docs/api/index.md from docstrings"
	@echo "  make docs-install     - Install the Docusaurus site's npm dependencies"
	@echo "  make docs-dev         - Run the Docusaurus dev server"
	@echo "  make docs-build       - Regenerate the API reference and build the docs site"
	@echo "  make clean            - Clean build artifacts and cache"
	@echo "  make sync-docs-pins   - Sync docs-api hook pins from uv.lock"

baml-gen:
	uv run baml-cli generate --from agrag/llm/baml_src

sync:
	uv sync --locked --all-groups --all-extras

sync-docs-pins:
	uv run python .github/scripts/update_precommit_docs_pins.py

COV_ARGS ?=
COV_MAP_DIR ?= reports

test:
	uv run pytest tests/unit \
		--cov=agrag \
		--cov-report=term-missing \
		--cov-report=xml \
		--junitxml=pytest-results.xml

# The suite's dist needs cannot share one pytest invocation, so this runs the two
# groups separately, mirroring the suite matrix in
# .github/workflows/integration.yml. Its cypher and retrieval community tests
# write and delete Community nodes against the same shared label and are tagged
# xdist_group(name="community_label"), which only --dist loadgroup keeps on one
# worker. The ingestion community detection tests instead rely on --dist
# loadscope to keep one class's methods on one worker, and they scan the whole
# entity graph, so they also cannot run alongside another suite's relation
# writes. The graph group runs second, so the scanning suite sees as few of
# those writes as the run can arrange. End-to-end tests are a separate target.
test-integration:
	uv run pytest tests/integration/agents tests/integration/ingestion tests/integration/embedding tests/integration/vectordb tests/integration/loaders -v -n auto --dist loadscope \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		$(COV_ARGS) --junitxml=pytest-integration-results-ingestion.xml
	uv run pytest tests/integration/retrieval tests/integration/graphdb tests/integration/cypher -v -n auto --dist loadgroup \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		$(COV_ARGS) --junitxml=pytest-integration-results-graph.xml

# E2E tests run serially, and never against a database that another suite uses:
# xdist workers would share one Neo4j database. The collection hook in
# tests/conftest.py skips them under xdist for the same reason. CI runs the same
# tests as parallel shards, each on its own runner (.github/workflows/integration.yml).
test-e2e:
	uv run pytest tests/integration/e2e -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		$(COV_ARGS) --junitxml=pytest-e2e-results.xml

# Judged evals call a real LLM, so they skip when no key is set. They run
# serially against one database, like the E2E tests. Telemetry is opted out
# because the DeepEval plugin would otherwise report each run.
test-eval:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest tests/integration/eval -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-results.xml

# Runs every suite in the safe order with one coverage data file, a JUnit file per
# suite, and per-test coverage contexts. The JSON report maps each line to the
# tests that ran it. The JUnit files record the outcome of each test.
test-cov-map:
	mkdir -p $(COV_MAP_DIR)
	rm -f $(COV_MAP_DIR)/.coverage
	COVERAGE_FILE=$(COV_MAP_DIR)/.coverage $(MAKE) test-cov-map-suites COV_ARGS="--cov=agrag --cov-append --cov-context=test"
	COVERAGE_FILE=$(COV_MAP_DIR)/.coverage uv run coverage json --show-contexts -o $(COV_MAP_DIR)/coverage-contexts.json

test-cov-map-suites:
	uv run pytest tests/unit -o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra -n auto --dist loadscope" $(COV_ARGS) --junitxml=$(COV_MAP_DIR)/junit-unit.xml
	$(MAKE) test-integration COV_ARGS="$(COV_ARGS)"
	$(MAKE) test-e2e COV_ARGS="$(COV_ARGS)"
	mv -f pytest-integration-results-ingestion.xml pytest-integration-results-graph.xml pytest-e2e-results.xml $(COV_MAP_DIR)/

test-all: test test-integration test-e2e

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
	rm -rf .coverage coverage.xml htmlcov dist build .wheelenv *.egg-info pytest-results.xml pytest-integration-results*.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .ty_cache -exec rm -rf {} +

# Overridable so the pre-commit hook can use its isolated docs environment.
DOCS_GRIPPE2MD ?= uv run --group docs griffe2md

docs-api:
	mkdir -p docs/docs/api
	{ printf '%s\n' '---' 'title: API Reference' 'sidebar_position: 2' '---' ''; \
	  $(DOCS_GRIPPE2MD) agrag -f; } > docs/docs/api/index.md.tmp
	mv docs/docs/api/index.md.tmp docs/docs/api/index.md

docs-install:
	cd docs && npm ci

docs-dev: docs-api
	cd docs && npm start

docs-build: docs-api
	cd docs && npm run build
