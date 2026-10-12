"""The value that every schema import returns."""

from dataclasses import dataclass, field

from agrag.common.data_models.graph_schema import GraphSchema


@dataclass(frozen=True, slots=True)
class FormatWarning:
    """One thing an import dropped, changed or could not map.

    Attributes:
        code: A stable machine-readable name, such as ``unknown_parent``.
        element: The source element the warning is about.
        message: A sentence that says what happened and how to fix it.
    """

    code: str
    element: str
    message: str

    def __str__(self) -> str:
        """Render as ``code: element: message``."""
        return f"{self.code}: {self.element}: {self.message}"


@dataclass(frozen=True, slots=True)
class ImportResult:
    """A schema read from another format, with everything the read lost.

    Attributes:
        schema: The imported schema.
        warnings: One entry for each dropped or changed element, in the
            order the importer found them. Empty when the import lost nothing.
    """

    schema: GraphSchema
    warnings: list[FormatWarning] = field(default_factory=list)
