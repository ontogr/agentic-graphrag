# Contributing to Agentic GraphRAG

Thanks for taking the time to contribute.

## Getting started

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:ontogr/agentic-graphrag.git
cd agentic-graphrag
make sync
uv run pre-commit install
```

`make sync` installs the project dependencies, including optional dependencies and development tools. Unit tests do not need external services. Integration, end-to-end, and documentation tests may need services or credentials. Do not put credentials in Git. Use a local `.env` file for settings that read one.

## Make and test a change

1. Fork the repository and create a branch from `main`.
2. Make the change and add or update tests where needed. Unit tests live under `tests/unit/`; integration tests live under `tests/integration/`.
3. While you work, run a focused test by passing a test file or test name to pytest. For example:

   ```bash
   uv run pytest tests/unit/graphdb/test_neo4j.py -q
   ```

   Replace the path with the test file for the behavior you changed. A focused test gives faster feedback; it does not replace the full unit suite.
4. Before you open a pull request, run the unit suite and non-mutating lint and type checks:

   ```bash
   make test
   make lint-check
   make lint-typing
   ```

   `make test` runs unit tests with coverage. `make lint-check` checks Ruff formatting and lint without changing files. `make lint-typing` runs `ty`. `make lint-all` runs auto-formatting and unsafe lint fixes, so it can change files. Use it only when you want those changes.
5. Open a pull request. Use a [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) prefix in the title: `fix:`, `feat:`, `build:`, `chore:`, `ci:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`.

## Tests

- Unit tests must not touch the network. Sockets are disabled by default.
- Tests that need external services go in `tests/integration/`. `tests/conftest.py` applies the `integration`, `enable_socket`, and flaky rerun markers to tests in that directory. Do not add those markers by hand.
- Run integration tests with `make test-integration`. They need the relevant external services and configuration. `make dev-services-up` starts the local Neo4j, Qdrant, Weaviate, and Milvus services used by integration tests. `make dev-services-down` stops them and removes their data.
- Run serial end-to-end tests with `make test-e2e`. They need a reachable Neo4j database. Do not run them against a database used by another test suite.
- `make test-all` runs the unit, integration, and end-to-end suites. These broader suites need the services described above.
- Aim for 80-90% coverage on new code. Do not write assertion-free tests to hit a number.

## Style

- Ruff handles formatting and linting.
- Write Google-style docstrings on public functions and classes.
- Add type annotations on public signatures.

## Third-party code

Do not copy code from another project unless its licence allows it and the licence is compatible with Apache-2.0. When you copy code, or adapt it with small changes:

- Keep the original copyright line and licence notice in the file header. Name the source project, the file and the commit that you copied from, and list what you changed.
- Add a comment above a copied function that says where it came from.
- Put the full text of the licence in a file under `licenses/` and list that file in `license-files` in `pyproject.toml`, so the wheel and the source distribution carry it.
- Mention the code in the pull request.

Code that you write from an idea in another project needs no notice. Name the project in a comment when it helps a reader.

## Docs

- The docs website is at `docs/`, served at `ontogr.github.io/agentic-graphrag`. Guides live as Markdown/MDX under `docs/docs/`. Link to other pages with relative file paths such as `../concepts/chunking.mdx`, so a link in a versioned copy of the docs stays in that version. `make docs-build` fails on Markdown links and `href` attributes that start with `/`.
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

- `make docs-test` runs Python blocks in the getting-started and guide pages. The tests need a reachable Neo4j database through `NEO4J_*`. Some blocks clear that database, so use a throwaway database and set `DOCS_TEST_ALLOW_NEO4J_RESET=1` to confirm the reset. Blocks that need an LLM endpoint skip unless `LLM_BASE_URL` and `LLM_API_KEY` are set.
- Label the opening fence `python fixture:llm_env` to attach the LLM fixture to a code block. Add `notest` to the opening fence for code that cannot run as a docs test. Both forms match the syntax used by the documentation test tooling and existing guides.
- The landing page is `docs/src/pages/index.js`.

## Setup Commands

| Command | Description |
| --- | --- |
| `make sync` | Install all dependencies |
| `make test` | Run unit tests with coverage |
| `make test-integration` | Run integration tests with external services |
| `make test-e2e` | Run serial end-to-end tests with Neo4j |
| `make test-all` | Run unit, integration, and end-to-end tests |
| `make dev-services-up` | Start local Neo4j, Qdrant, Weaviate, and Milvus services |
| `make dev-services-down` | Stop local services and remove their data |
| `make test-eval` | Run judged and real-agent evals (needs Neo4j and an LLM key) |
| `make test-eval-extraction` | Score the extractor on the KPI-EDGAR gold set (needs an LLM key) |
| `make test-eval-verifier` | Score the verifier verdicts on the FinQA-derived set (needs an LLM key) |
| `make test-eval-resolution` | Score entity resolution on the gold set (needs an LLM key) |
| `make test-eval-answer` | Score Agentic GraphRAG answers on the FinQA fixture (needs Neo4j and an LLM key) |
| `make test-eval-trajectory` | Score agent trajectories on the tiny corpus (needs Neo4j and an LLM key) |
| `make lint-check` | Check formatting and lint without modifying files |
| `make lint-typing` | Type check with `ty` |
| `make lint-all` | Format, apply lint fixes, type check, check typos, and audit GitHub Actions |
| `make security` | Run Bandit and uv audit |
| `make changelog` | Rebuild `CHANGELOG.md` from the git history with git-cliff. It needs the full history and the release tags, and stops if they are missing |
| `make wheel-test` | Build the wheel and import it from a clean environment |
| `make docs-dev` | Run the docs site locally with live reload. Restart it to see edits to `CHANGELOG.md` |
| `make docs-build` | Regenerate the API reference and build the docs site |
| `make help` | List all targets |

Run `uv run pre-commit install` once to enable the commit hooks.

## Releasing

1. In a pull request, raise `version` in `pyproject.toml` and run `uv lock` to update the package version in `uv.lock`.
2. Update `CHANGELOG.md` before freezing the docs. Run `uvx git-cliff@2.14.2 --tag v<VERSION> --output CHANGELOG.md`, replacing `<VERSION>` with the package version. The command generates a release section without creating a Git tag. Check the release date and entries, preserve any manually recorded changes, and keep an empty `Unreleased` section with a comparison link from the new tag to `HEAD`.
3. Run `make docs-version` to freeze the docs and API reference as the new version of the docs site. Include the new files in `docs/versioned_docs/`, `docs/versioned_sidebars/` and `docs/versions.json`. The newest version is served at `/stable/`, and main-branch docs remain at `/latest/`. Point website entry links at `/stable/` when the new snapshot includes their target pages.
4. Run `make docs-build` and `make wheel-test`. The docs build fails if the package version has no frozen docs or if links are broken. The wheel check builds the package and checks imports in a clean environment.
5. After the pull request is merged, create a GitHub release targeting the merged commit with a tag that matches the package version, such as `v0.0.5` for `0.0.5`. Copy the version's changelog entries into the release notes. Creating the tag starts the PyPI publish workflow. Check that the workflow succeeds and that PyPI lists the new version. The docs site deploys separately when the release preparation is pushed to `main`.

## Reporting bugs and requesting features

Open an [issue](https://github.com/ontogr/agentic-graphrag/issues). For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
