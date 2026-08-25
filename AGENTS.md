# Agent Guidelines

## Commands

- **Sync environment**: `make sync`
- **Run unit tests**: `make test`
- **Run a single test**: `uv run pytest tests/unit/test_version.py::TestVersion::test_exposes_a_pep440_version -vv`
- **Lint & format**: `make lint-all` (ruff format, ruff check --fix, ty)
- **Check without modifying**: `make lint-check`
- **Type check only**: `make lint-typing`
- **Verify packaging**: `make wheel-test`
- **Audit workflows**: `make lint-actions` (zizmor)

## Project

**`agrag`** — graph-based retrieval-augmented generation with agentic reasoning.
Published to PyPI as `agentic-graphrag`; imported as `agrag`. 
The repo is hosted at `ontogr/agentic-graphrag`.

**Layout**: flat. The package is `agrag/` at the repo root, configured with
`module-root = ""` and `module-name = "agrag"` under `[tool.uv.build-backend]`
— `module-name` is required whenever the distribution name doesn't normalize
to the module name. Everything outside `agrag/`
(tests, examples, benchmarks, docker, docs) is not part of the distribution.

## Conventions

- Python 3.11+. Ruff, 88 character lines, Google-style docstrings.
- `ty` for type checking, not mypy.
- Tests: one `Test<Feature>` class per `test_<feature>.py`, mirroring the package.
  Unit tests have sockets disabled; anything needing a real service goes in
  `tests/integration/` behind `@pytest.mark.integration`.
- Dependencies are added when code needs them, not in advance. Use loose lower
  bounds in `pyproject.toml`; the lockfile pins.
- Version lives only in `pyproject.toml`. `agrag.__version__` reads it from the
  installed distribution metadata — do not add a second copy.
- Releases are tag-driven: push `vX.Y.Z` and the Release workflow publishes.
- CI workflows pin every action to a commit SHA with a `# vX.Y.Z` comment.
  Dependabot bumps them. Never replace a SHA with a mutable tag — `make
  lint-actions` (zizmor) fails the build if you do, and so does CI.
- Releases publish over PyPI Trusted Publishing (OIDC); there is no API token.
  The release job needs `id-token: write`.
