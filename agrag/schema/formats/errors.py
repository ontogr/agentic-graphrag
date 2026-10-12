"""Errors raised by schema format importers."""


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
