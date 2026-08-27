# Testing Rules

Use these rules for tests in this repository.

## Organization

- Use `pytest` and `pytest-asyncio` for tests, including async tests.
- Tests mirror the `agrag/` package structure under `tests/unit/` and
  `tests/integration/`.
- Use one `Test<Feature>` class per `test_<feature>.py` file.
- `pytest-asyncio` runs in auto mode. Do not add `@pytest.mark.asyncio` to async
  tests.
- `--strict-markers` and `--strict-config` are enabled. Marker typos and manual
  marker misuse are hard errors.
- Unit and integration tests run in parallel. Avoid shared mutable state between
  test classes.
- Use descriptive, behavior-oriented test names such as
  `test_returns_empty_when_no_results`.
- Test the public interface and documented behavior, not private implementation
  details. Avoid accessing private members in tests unless there is no public
  seam and adding one would be worse for the design.
- Follow nearby test patterns before introducing new fixtures or helpers.
- For bug fixes, extend the existing mapped test file when one already covers
  the affected module. Create a new test file only when no mapped test exists or
  a new feature/component needs one.
- One focused regression test that fails without the fix is better than many
  shallow tests that do not prove behavior.

## Isolation

- Unit tests must mock external dependencies such as Neo4j, Qdrant, Weaviate,
  Hugging Face, and LLM APIs.
- Unit tests must not enable sockets. If a unit test hits `SocketBlockedError`,
  fix the mock rather than enabling network access.
- `pytest-socket` disables network by default with
  `--disable-socket --allow-unix-socket`.
- Integration tests automatically receive `integration`, `enable_socket`, and
  `flaky(reruns=3, reruns_delay=30, rerun_except=[AssertionError])` markers from
  `tests/conftest.py` based on directory. Do not add these markers manually.
- Patch external drivers at the driver boundary used by production code.
- For Neo4j unit tests, patch `agrag.db.graph.neo4j.AsyncGraphDatabase.driver`.
- Avoid shared mutable state between test classes because tests run in parallel.

## Maintenance

- Tests must pass after every behavior change.
- Tests for changed behavior should fail when the behavior is broken. Do not add
  tests that merely exercise code without meaningful assertions.
- Refactoring internals should not require test changes. If it does, the tests
  may be too coupled to implementation details.
- When changing public APIs, update tests for the new public contract.
- When deleting behavior, delete or update the corresponding tests.
- Use `@pytest.mark.skip(reason="...")` or `@pytest.mark.xfail` for known-broken
  tests. Do not silently delete tests to hide failures.
- Do not write assertion-free tests only to increase coverage.
- Target 80-90% coverage for core/domain logic; do not chase 100% coverage.

## Commands

- Use `uv run` for Python commands.
- Use focused pytest commands while iterating, then run the narrowest broader
  check that proves the change.
- Example focused command:
  `uv run pytest tests/unit/db/graph/test_client.py -k client`.
