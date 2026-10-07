.PHONY: bench-lite bench bench-dry bench-clean test-cov-map test-cov-map-suites sync sync-docs-pins baml-gen lint-actions test test-integration test-e2e test-eval test-eval-answer test-eval-extraction test-eval-verifier test-eval-resolution test-eval-trajectory test-all dev-services-up dev-services-down cov-report cov lint-typing lint-style lint-fmt lint-check lint-typos lint-all security-bandit security-audit security build wheel-test clean help changelog docs-api docs-install docs-dev docs-build docs-test

export UV_LOCKED = 1

help:
	@echo "Available make targets:"
	@echo "  make sync             - Sync project and install dependencies"
	@echo "  make test             - Run unit tests with coverage"
	@echo "  make test-integration - Run integration tests (requires network)"
	@echo "  make test-e2e         - Run end-to-end pipeline tests (requires Neo4j)"
	@echo "  make test-eval        - Run judged and real-agent evals (requires Neo4j and an LLM key)"
	@echo "  make test-eval-answer - Score agrag answers on the FinQA fixture (requires Neo4j and an LLM key)"
	@echo "  make test-eval-extraction - Score the extractor on the KPI-EDGAR gold set (requires an LLM key)"
	@echo "  make test-eval-verifier - Score the verifier verdicts on the FinQA-derived set (requires an LLM key)"
	@echo "  make test-eval-resolution - Score entity resolution on the gold set (requires an LLM key)"
	@echo "  make test-eval-trajectory - Score agent trajectories on the tiny corpus (requires Neo4j and an LLM key)"
	@echo "  make test-all         - Run unit, integration, and e2e tests in order"
	@echo "  make bench-lite DOMAIN=<name> - Run a benchmark on its lite set (requires Docker, Neo4j and an LLM key)"
	@echo "  make bench DOMAIN=<name> - Run a benchmark on its full set; asks first (same requirements)"
	@echo "  make bench-dry DOMAIN=<name> MODE=lite|full - Bound calls and tokens without a model"
	@echo "  make bench-clean      - Delete the benchmark graphs and volumes"
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
	@echo "  make security-audit   - Audit the locked dependencies with uv audit"
	@echo "  make security         - Run all security scans"
	@echo "  make build            - Build sdist and wheel into dist/"
	@echo "  make wheel-test       - Install the built wheel in a clean env and import it"
	@echo "  make docs-api         - Regenerate the per-package API pages in docs/docs/api/ from docstrings"
	@echo "  make changelog        - Rebuild CHANGELOG.md from the git history"
	@echo "  make docs-install     - Install the Docusaurus site's npm dependencies"
	@echo "  make docs-dev         - Run the Docusaurus dev server"
	@echo "  make docs-build       - Regenerate the API reference and build the docs site"
	@echo "  make docs-test        - Run the Python code blocks in the docs"
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
	uv run pytest tests/integration/agents tests/integration/ingestion tests/integration/embedding tests/integration/vectordb tests/integration/loaders tests/integration/llm -v -n auto --dist loadscope \
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
		--ignore=tests/integration/eval/test_answer_quality_e2e.py \
		--ignore=tests/integration/eval/test_extraction_quality_e2e.py \
		--ignore=tests/integration/eval/test_verifier_calibration_e2e.py \
		--ignore=tests/integration/eval/test_resolution_quality_e2e.py \
		--ignore=tests/integration/eval/test_agent_trajectory_e2e.py \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-results.xml

# The answer quality gate ingests a small corpus, runs the real agent and calls
# the judge for each answer. It runs after merges and on a schedule, not on every
# pull request, and writes its scores to reports/eval/answer_quality.json.
test-eval-answer:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest \
		tests/integration/eval/test_answer_quality_e2e.py -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-answer-results.xml

# The extraction quality gate makes one LLM call per gold sentence and needs no
# database. It runs after merges and on a schedule, not on every pull request,
# and writes its scores to reports/eval/extraction_quality.json.
test-eval-extraction:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest \
		tests/integration/eval/test_extraction_quality_e2e.py -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-extraction-results.xml

# The verifier calibration gate makes about 60 short verifier calls and needs no
# database. It runs after merges and on a schedule, not on every pull request,
# and writes its scores to reports/eval/verifier_calibration.json.
test-eval-verifier:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest \
		tests/integration/eval/test_verifier_calibration_e2e.py -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-verifier-results.xml

# The resolution quality gate needs an LLM key and no database. It runs after
# merges and weekly, not on every pull request, and writes its scores to
# reports/eval/resolution_quality.json.
test-eval-resolution:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest \
		tests/integration/eval/test_resolution_quality_e2e.py -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-resolution-results.xml

# The agent trajectory gate traces 5 real agent runs and judges each one. It
# runs after merges and weekly, not on every pull request, and writes its
# scores to reports/eval/agent_trajectory.json.
test-eval-trajectory:
	DEEPEVAL_TELEMETRY_OPT_OUT=YES uv run pytest \
		tests/integration/eval/test_agent_trajectory_e2e.py -v \
		-o "addopts=--strict-markers --strict-config --disable-socket --allow-unix-socket -ra" \
		--junitxml=pytest-eval-trajectory-results.xml

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

# Benchmark runs are manual, cost real model calls, and never run in CI. See
# docs/docs/benchmarks/run-benchmarks.mdx.
MODE ?= lite

bench-lite:
	uv run python -m benchmarks run $(DOMAIN) --mode lite

bench:
	uv run python -m benchmarks run $(DOMAIN) --mode full

bench-dry:
	uv run python -m benchmarks dry-run $(DOMAIN) --mode $(MODE)

bench-clean:
	uv run python -m benchmarks clean

dev-services-up:
	docker compose -f docker/docker-compose.ci.yml up -d --wait --wait-timeout 420

dev-services-down:
	docker compose -f docker/docker-compose.ci.yml down -v

cov-report:
	uv run coverage html

cov: test cov-report

lint-typing:
	uv run ty check agrag/ benchmarks/ tests

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
	uv audit --preview-features audit-command

security: security-bandit security-audit

build:
	rm -rf dist
	uv build

wheel-test: build
	rm -rf .wheelenv
	uv venv .wheelenv
	uv pip install --python .wheelenv/bin/python dist/*.whl
	cd /tmp && "$(CURDIR)/.wheelenv/bin/python" -c "import agrag, agrag.agents, agrag.chunking, agrag.common.data_models, agrag.embedding, agrag.graphdb, agrag.ingestion, agrag.loaders, agrag.retrieval, agrag.vectordb; print(agrag.__version__)"

clean:
	rm -rf .coverage coverage.xml htmlcov dist build .wheelenv *.egg-info pytest-results.xml pytest-integration-results*.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .ty_cache -exec rm -rf {} +

# Overridable so the pre-commit hook can use its isolated docs environment.
DOCS_GRIPPE2MD ?= uv run --group docs griffe2md
DOCS_PYTHON ?= uv run python
# Community APIs live in agrag.ingestion.community, not agrag.communities.
DOCS_API_PKGS ?= agents chunking common embedding eval graphdb ingestion loaders observability retrieval vectordb

docs-api:
	mkdir -p docs/docs/api
	rm -f $(filter-out docs/docs/api/index.md,$(wildcard docs/docs/api/*.md))
	i=2; for p in $(DOCS_API_PKGS); do \
	  { printf '%s\n' '---' "title: agrag.$$p" "sidebar_position: $$i" '---' ''; \
	    PYTHONPATH=. $(DOCS_GRIPPE2MD) agrag.$$p -f; } > docs/docs/api/$$p.md.tmp \
	    && mv docs/docs/api/$$p.md.tmp docs/docs/api/$$p.md || exit 1; \
	  i=$$((i+1)); done
	$(DOCS_PYTHON) .github/scripts/docs_api_links.py docs/docs/api

changelog:
	uvx git-cliff@2.14.2 --output CHANGELOG.md
	@# git-cliff ends the file with a blank line, which the end-of-file hook removes.
	@printf '%s\n' "$$(cat CHANGELOG.md)" > CHANGELOG.md.tmp && mv CHANGELOG.md.tmp CHANGELOG.md

docs-install:
	cd docs && npm ci

docs-dev: docs-api
	cd docs && npm start

docs-build: docs-api
	cd docs && npm run build 2>&1 | tee build.log
	@# Docusaurus reports many problems as warnings and still exits with success.
	@grep -q '^\[SUCCESS\]' docs/build.log && ! grep -qE '^\[(WARNING|ERROR)\]' docs/build.log \
	  || { echo "The docs build did not finish cleanly. Read docs/build.log."; exit 1; }

# The docs tests need a Neo4j reachable through NEO4J_* (see docker/docker-compose.ci.yml).
# Some blocks empty that database. They run only when DOCS_TEST_ALLOW_NEO4J_RESET=1,
# so point NEO4J_URI at a throwaway database before you set it.
# The generated API pages hold docstring examples that are not self-contained, so they never run.
#
# CI runs the pages in three shards, each on its own runner with its own Neo4j and
# Qdrant. Set DOCS_SHARD=1, 2 or 3 to run one shard. Shards hold whole pages, because
# blocks of one page run in file order and can read what an earlier block wrote.
# Shards 1 and 2 list their pages. Shard 3 runs both docs folders except those pages,
# so a new page always runs somewhere. The lists balance measured run time (about 45
# seconds each) and spread the pages that need an LLM key.
DOCS_SHARD_1 := docs/docs/guides/ingest-documents.mdx \
	docs/docs/guides/update-and-delete-documents.mdx \
	docs/docs/guides/retrieve-and-answer.mdx
DOCS_SHARD_2 := docs/docs/guides/configure-chunking.mdx \
	docs/docs/guides/configure-storage-backends.mdx \
	docs/docs/get-started/quickstart.mdx
DOCS_SHARD_3 := docs/docs/get-started docs/docs/guides \
	$(addprefix --ignore=,$(DOCS_SHARD_1) $(DOCS_SHARD_2))
DOCS_TEST_PATHS ?= $(if $(DOCS_SHARD),$(DOCS_SHARD_$(DOCS_SHARD)),docs/docs/get-started docs/docs/guides)

docs-test:
	@test -n "$(strip $(DOCS_TEST_PATHS))" || { echo "No docs pages selected. DOCS_SHARD must be 1, 2 or 3."; exit 1; }
	uv run --group docs pytest --markdown-docs $(DOCS_TEST_PATHS) \
		--ignore=docs/docs/api -p no:deepeval -p no:cacheprovider -o addopts="" --forked -q
