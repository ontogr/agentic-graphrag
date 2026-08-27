# Python Architecture Rules

Use these rules when writing, reviewing, or refactoring Python code in this
repository.

## Structure

- Default to functions and modules. Use classes only when there is genuine
  stateful behavior, shared `self` state, or a data container with behavior.
- Use `snake_case` for functions and variables, `PascalCase` for classes, and
  `test_*.py` for test files.
- Do not use classes only for namespacing, single-method wrappers, or grouping
  pure functions. Use modules for namespacing.
- Do not add abstractions for single-use code or hypothetical future needs.
- Prefer composition over inheritance for new code unless an existing framework
  or local interface expects inheritance.
- Prefer early returns and guard clauses over deeply nested control flow.
- Keep public APIs minimal and well-defined. Do not expose internals to make
  tests or one caller easier.
- Do not access private members (`_`-prefixed attributes or methods) of other
  classes. Use the public API, or add a deliberate interface when the public API
  is missing required behavior.
- Put module-level helper functions near the top of the file after imports and
  before classes. Put private/helper methods near the end of a class after the
  public methods when doing so matches the surrounding file.
- Keep changes surgical. Touch only files and lines required by the requested
  behavior.

## Library boundaries

- Do not wrap third-party library APIs unless there is a concrete reason:
  implementation swapping, domain-native interface, or I/O isolation for tests.
- Wrap databases, external services, network I/O, and message queues when a
  boundary is needed.
- Do not wrap stable utility libraries or ML libraries merely to hide imports.
- When wrapping is justified, keep the wrapper thin and expose only behavior the
  project actually uses.

## Dependencies and public API

- Prefer explicit dependency injection through constructors or function
  parameters for production code.
- Use monkeypatching/mocking for OS calls, time, third-party SDKs, and test-only
  seams. If tests need to monkeypatch project internals, prefer adding an
  explicit injection seam.
- Avoid monkeypatching project class attributes in tests when dependency
  injection can provide the seam. Patching third-party SDK or driver boundaries
  is acceptable when it is the narrowest reliable isolation point.
- Do not use dependency-injection frameworks.
- Public APIs are contracts. Do not break them during refactors without explicit
  approval and a deprecation path.
- Define `__all__` only in package `__init__.py` files that intentionally
  re-export public symbols. Do not put `__all__` in implementation modules where
  classes or functions are defined.
- Prefix internal helpers with `_` when they carry no stability guarantee.

## Project-specific constraints

- This repository uses a flat layout with `am_diag/` at the root. Do not add a
  `src/` package layout.
- All public API is async unless an existing interface requires otherwise.
- Use `pydantic-settings` for environment-backed settings classes.
- Keep author attribution comments or module-docstring attribution if present.
  Do not remove attribution during cleanup or refactoring.
