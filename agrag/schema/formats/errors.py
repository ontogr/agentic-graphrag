"""Errors and results for schema format importers."""

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from agrag.common.data_models.graph_schema import GraphSchema


@dataclass(frozen=True, slots=True)
class FormatWarning:
    """One lossy or unsupported construct found in an imported format."""

    code: str
    element: str
    message: str

    def __str__(self) -> str:
        """Format the warning for logs and command-line output."""
        return f"{self.code} [{self.element}]: {self.message}"


@dataclass(frozen=True, slots=True)
class ImportResult:
    """A validated schema and the warnings produced while importing it."""

    schema: GraphSchema
    warnings: list[FormatWarning] = dataclass_field(default_factory=list)


class SchemaFormatError(ValueError):
    """An input document cannot be imported as a supported schema format."""


class SchemaFormatMissingExtraError(SchemaFormatError):
    """An optional package required by a schema format is not installed."""

    def __init__(self, component: str, extra: str) -> None:
        """Build the error with installation guidance."""
        self.component = component
        self.extra = extra
        super().__init__(
            f"{component} requires the optional extra '{extra}'. "
            f"Install it with: pip install 'agentic-graphrag[{extra}]'."
        )
