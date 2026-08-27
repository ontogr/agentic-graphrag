# Tooling And Configuration Rules

Use these rules when changing project tooling, dependency metadata, or CI-related
configuration.

## Package management

- Use `uv` for package management, virtual environments, and lockfiles.
- Use `uv run` for Python invocations.
- Keep dependency specs loose in `pyproject.toml` and rely on `uv.lock` for
  reproducibility.
- Add upper bounds only for known-breaking dependencies. Do not blanket-pin
  dependencies with upper bounds.
- Use `deptry` or an equivalent dependency check before removing dependencies,
  and account for dynamic imports or plugin entry points.

## Linting and formatting

- Use Ruff for linting and formatting.
- Line length is 88 characters, including docstrings.
- Python target is `>=3.11`; use modern Python 3.11-compatible syntax.
- When docstrings or comments exceed the line length, rewrite them concisely
  rather than truncating or wrapping awkwardly.
- Do not change Ruff, typing, or pytest configuration unless the user explicitly
  asks for a configuration change.

## Type checking

- Use the repository-configured type checker and commands. This repository uses
  `ty` via `make lint-typing`.
- See `.claude/.rules/ty-typing.md` for ty-specific error triage and fix
  patterns.
- Add type annotations to new and modified public APIs.
- Use gradual typing. Do not retrofit unrelated files only to satisfy a local
  change.
- For generated or unowned code, prefer configured tool ignores over manual
  edits.

## Generated and excluded files

- Do not manually edit `agrag/llm/baml_client/`.
- After editing BAML sources under `agrag/llm/baml_src/`, regenerate the
  client with `make baml-gen`.
- Ruff and ty ignore generated BAML directories by configuration; keep generated
  files out of manual cleanup and formatting work.

## Security and secrets

- Never commit `.env` or secrets.
- Never commit API keys or tokens, including `OPENAI_API_KEY`, `PRIME_API_KEY`,
  and `PRIME_TEAM_ID`.
- Store local secrets in `.env`; production secrets belong in environment
  variables or a secret manager.
- Do not put patient, customer, partner, or private organization names in code,
  docs, issues, PRs, commit messages, or tests unless they are already public
  fixture data approved for that use.
- In CI or installation scripts, never pipe a remote script into a shell, such
  as `curl ... | bash` or `wget ... | sh`.
- Pin every external CI tool download to a specific version and full URL. Do not
  use `latest` or `stable`.
- Download artifacts to files and verify SHA-256 checksums before installation,
  preferably using the provider's official `.sha256` or `.sha256sum` sidecar.
- Treat Bandit findings as review items unless project CI explicitly makes them
  blocking.
