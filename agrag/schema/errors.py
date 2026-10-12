"""Errors that the schema loader raises."""

from collections.abc import Sequence
from dataclasses import dataclass


class SchemaError(Exception):
    """The base class for every schema-loader error."""


@dataclass(frozen=True)
class SchemaIssue:
    """One problem found in a schema source.

    Attributes:
        path: Where the problem is, for example ``entities[2].parents``. The
            value ``schema`` means the whole schema.
        message: What is wrong and how to fix it.
    """

    path: str
    message: str


class SchemaLoadError(SchemaError, ValueError):
    """A schema source is invalid.

    The message lists every problem found, one per line, each with the path to
    the offending key.

    Attributes:
        issues: Every problem found.
        source: The file path that was read, or ``None`` for in-memory input.
    """

    def __init__(
        self, issues: Sequence[SchemaIssue], *, source: str | None = None
    ) -> None:
        """Build the message from the issues."""
        count = len(issues)
        where = f" in {source}" if source else ""
        noun = "error" if count == 1 else "errors"
        lines = [f"invalid schema{where} ({count} {noun}):"]
        lines.extend(f"  {issue.path}: {issue.message}" for issue in issues)
        super().__init__("\n".join(lines))
        self.issues = tuple(issues)
        self.source = source


class Issues:
    """Collects issues so that one load reports every problem."""

    def __init__(self) -> None:
        """Start with no issues."""
        self.items: list[SchemaIssue] = []

    def add(self, path: str, message: str) -> None:
        """Record one issue."""
        self.items.append(SchemaIssue(path, message))

    def __bool__(self) -> bool:
        """Return ``True`` when at least one issue exists."""
        return bool(self.items)

    def error(self, source: str | None = None) -> SchemaLoadError:
        """Return the error that reports every collected issue."""
        return SchemaLoadError(self.items, source=source)
