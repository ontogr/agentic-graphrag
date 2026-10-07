# Contributing to Agentic GraphRAG

Thanks for taking the time to contribute.

## Getting started

You need [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone git@github.com:ontogr/agentic-graphrag.git
cd agentic-graphrag
make sync
uv run pre-commit install
```

## Making a change

1. Fork the repository. Branch off `main`.
2. Make your change, with tests. Tests live in `tests/unit/` and mirror the
   package structure, one `Test<Feature>` class per `test_<feature>.py`.
3. Run the checks:

   ```bash
   make lint-all   # format, lint, type check
   make test       # unit tests with coverage
   ```

4. Open a pull request. Use a [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) prefix in the title: `fix:`, `feat:`, `build:`, `chore:`, `ci:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`.

## Tests

- Unit tests must not touch the network. Sockets are disabled by default.
- Tests that need external services (databases, APIs) go in `tests/integration/` and are marked `@pytest.mark.integration`. Run them with `make test-integration`.
- Aim for 80-90% coverage on new code. Do not write assertion-free tests to hit a number.

## Style

- Ruff handles formatting and linting.
- Write Google-style docstrings on public functions and classes.
- Add type annotations on public signatures.

## Docs

- The docs website is at `docs/`, served at `ontogr.github.io/agentic-graphrag`. Guides live as Markdown/MDX under `docs/docs/`.
- The API reference has two parts. `docs/docs/api/index.md` is the hand-written Core API page. The other pages in `docs/docs/api/` are generated from the docstrings of Agentic GraphRAG with `griffe2md`. Run `make docs-api` to regenerate them. Do not edit them by hand. `make docs-dev` and `make docs-build` regenerate them automatically.

```bash
make docs-install  # once, or after docs/package.json changes
make docs-dev      # dev server with live reload, http://localhost:3000/agentic-graphrag/
make docs-build    # regenerate the API reference and build the static site into docs/build/
```

To check the production build itself rather than the dev server:

```bash
make docs-build
cd docs && npm run serve   # serves docs/build/ at http://localhost:3000/agentic-graphrag/
```

If you push to `main` with changes under `docs/`, `agrag/`, or `pyproject.toml`, the site builds and deploys automatically via `.github/workflows/docs.yml`.

- Every Python block in the docs must run. `make docs-test` runs them (it needs Neo4j, see the Makefile). Mark a block that cannot run with `notest`.
- Blocks that need an LLM endpoint use a `python fixture:llm_env` fence and run only when `LLM_BASE_URL` and `LLM_API_KEY` are set.
- The landing page is `docs/src/pages/index.js`.

## Setup Commands

| Command | Description |
| --- | --- |
| `make sync` | Install all dependencies |
| `make test` | Run unit tests with coverage |
| `make test-eval` | Run judged and real-agent evals (needs Neo4j and an LLM key) |
| `make test-eval-extraction` | Score the extractor on the KPI-EDGAR gold set (needs an LLM key) |
| `make test-eval-verifier` | Score the verifier verdicts on the FinQA-derived set (needs an LLM key) |
| `make test-eval-resolution` | Score entity resolution on the gold set (needs an LLM key) |
| `make test-eval-answer` | Score Agentic GraphRAG answers on the FinQA fixture (needs Neo4j and an LLM key) |
| `make test-eval-trajectory` | Score agent trajectories on the tiny corpus (needs Neo4j and an LLM key) |
| `make lint-all` | Format, lint, and type check |
| `make lint-check` | Check formatting and lint without modifying files |
| `make security` | Run Bandit and uv audit |
| `make changelog` | Rebuild `CHANGELOG.md` from the git history with git-cliff. It needs the full history and the release tags, and stops if they are missing |
| `make wheel-test` | Build the wheel and import it from a clean environment |
| `make docs-dev` | Run the docs site locally with live reload. Restart it to see edits to `CHANGELOG.md` |
| `make docs-build` | Regenerate the API reference and build the docs site |
| `make help` | List all targets |

Run `uv run pre-commit install` once to enable the commit hooks.

## Releasing

To publish a release, push a tag:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

## Reporting bugs and requesting features

Open an [issue](https://github.com/ontogr/agentic-graphrag/issues). For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
