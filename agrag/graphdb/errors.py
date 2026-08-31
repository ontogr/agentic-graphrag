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


class GraphStoreConstraintViolationError(GraphStoreError):
    """A write violated a uniqueness constraint the backend enforces.

    Raised instead of letting the backend's own driver exception propagate,
    so callers can recognize this specific case -- for example, two
    concurrent writers both missing an exact-match lookup and racing to
    create the same ``merge_key`` -- and recover by re-resolving to
    whichever write landed first, rather than treating it as a fatal error.
    """


__all__ = [
    "GraphStoreConstraintViolationError",
    "GraphStoreError",
    "GraphStoreMissingExtraError",
]
