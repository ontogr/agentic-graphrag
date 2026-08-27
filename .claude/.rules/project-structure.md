# Project Structure And Domain Map

`agrag` is an Agentic GraphRAG system. It builds a
knowledge graph from corpus text and answers medical/clinical questions with
multi-strategy retrieval and LLM reasoning.

## Commands

```bash
make sync                  # Install dependencies with uv sync --all-groups
make test                  # Run unit tests with coverage — tests/unit
make test-integration      # Run integration tests requiring external services
make lint-fmt              # Format and auto-fix with Ruff
make lint-check            # Check lint only, no modifications
make lint-typing           # Type check with ty
make lint-all              # Format + lint + type check + typos
make baml-gen              # Regenerate generated BAML client code
make clean                 # Remove build artifacts and caches
```

Run a single test file or class with `uv run pytest`, for example:

```bash
uv run pytest tests/unit/db/graph/test_client.py::TestNeo4jClient -v
uv run pytest tests/unit/db/vector/test_qdrant.py -k "test_search" -v
```

## Package layout

```text
agrag/
tests/
  unit/                # Unit tests mirroring agrag/
  integration/         # Integration tests with real external services
thoughts/shared/       # Shared plans and research notes
docs/                  # User-facing docs
```

## Data flow

## Agent docs

- Issues and PRDs live under `.scratch/<feature-slug>/`; see
  `docs/agents/issue-tracker.md`.
- Triage labels use the five canonical role labels; see
  `docs/agents/triage-labels.md`.
- Domain docs use one root `CONTEXT.md` plus `docs/adr/`; see
  `docs/agents/domain.md`.
