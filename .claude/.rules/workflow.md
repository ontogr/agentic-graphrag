# Coding Workflow Rules

Use these rules for day-to-day implementation, refactoring, and documentation
work.

## Before changing code

- State assumptions when the request is ambiguous. Ask a narrow clarifying
  question when multiple valid interpretations exist.
- Do not hide confusion. If the task has multiple plausible interpretations,
  name them and ask or state the assumption you will use.
- Surface tradeoffs when they matter. Push back when a simpler or safer approach
  exists.
- Do not assume existing code is always the right pattern. Follow good local
  patterns, but call out code smells or risky patterns when they affect the
  requested change.
- Prefer the simplest approach that satisfies the request.
- Do not add features, configuration, abstractions, or error handling for
  scenarios outside the request.
- If the solution becomes much larger than the problem requires, stop and
  simplify before continuing.

## During edits

- Make surgical changes. Every changed line should trace to the user request.
- Match existing style even when a different style would be preferable.
- Do not refactor, reformat, or clean up adjacent code unless required by the
  change.
- Remove imports, variables, functions, or docs that your change makes obsolete.
  Do not remove pre-existing dead code unless asked.
- If you notice unrelated issues, mention them separately instead of fixing them
  opportunistically.

## Commits and pull requests

- Commit messages should be a single short imperative sentence with no trailing
  period.
- Prefix commit messages with a conventional commit type: `fix:`, `feat:`,
  `build:`, `chore:`, `ci:`, `docs:`, `style:`, `refactor:`, `perf:`, or
  `test:`.
- PRs should have short, scoped subjects and clear descriptions following
  `.github/pull_request_template.md`. PR titles should be prefixed with the conventional commit type.
- Do not add AI-agent attribution such as `Co-Authored-By: Claude`, `Generated
  with Claude Code`, or similar text to commits, PR descriptions, comments, or
  issues.
- For public-facing PR descriptions, issues, comments, and commit messages,
  avoid emojis, hype, AI-sounding phrasing, and unnecessary bullet lists. Prefer
  concise human prose.

## Documentation and research

- When asked to document or explain the codebase, describe what exists. Do not
  propose improvements unless explicitly asked.
- Use `.claude/.rules/diataxis-docs.md` when writing docs. This repository's
  docs may not be organized exactly as four Diátaxis quadrants, but Diátaxis
  practices still apply to every docs page: keep reader needs clear, separate
  learning/task/reference/explanation content where practical, and link between
  modes instead of blending them.
- Update relevant docstrings, READMEs, and docs when code behavior changes.
- User-facing documentation belongs under `docs/` and should be updated after
  code behavior changes.
- Check `thoughts/shared/plans/` before starting non-trivial implementation work.
- Include paper and repository links when documenting research-based
  implementations.

## Verification

- Define a narrow verification check for each change.
- For bug fixes, prefer a reproducing test first, then make it pass.
- For refactors, verify behavior before and after with existing tests when
  practical.
- Stop when the requested outcome is implemented and the narrowest useful check
  passes, or report the concrete blocker.

## Project commands

- Prefer non-mutating Makefile targets for standard checks: `make test`,
  `make lint-check`, and `make lint-typing`. Reserve `make lint-all` for explicit
  autofix runs; it formats and applies unsafe Ruff fixes that change the checkout.
- Use focused `uv run pytest ...` commands while developing.
