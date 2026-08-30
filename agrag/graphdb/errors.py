"""Errors that the graph-store layer raises."""


class GraphStoreError(Exception):
    """The base class for every graph-store error."""


class GraphStoreMissingExtraError(GraphStoreError):
    """A graph store exists, but its package extra is not installed.

    Attributes:
        extra: The name of the package extra to install.
    """

    def __init__(self, extra: str) -> None:
        """Bind the missing extra's name to the error."""
        super().__init__(
            f"needs the {extra!r} extra: pip install 'agentic-graphrag[{extra}]'"
        )
        self.extra = extra


__all__ = ["GraphStoreError", "GraphStoreMissingExtraError"]
