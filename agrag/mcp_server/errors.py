"""Errors raised by the MCP server package."""


class McpServerMissingExtraError(Exception):
    """The MCP server needs a package extra that is not installed.

    Attributes:
        extra: The name of the package extra to install.
    """

    def __init__(self, extra: str) -> None:
        """Bind the missing package extra to the error."""
        super().__init__(
            f"needs the {extra!r} extra: pip install 'agentic-graphrag[{extra}]'"
        )
        self.extra = extra
