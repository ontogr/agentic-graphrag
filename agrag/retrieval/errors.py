"""Errors that the retrieval layer raises."""


class RetrievalError(Exception):
    """The base class for every retrieval error."""


class AllRetrievalMethodsFailedError(RetrievalError):
    """Every retrieval method a Recipe named failed.

    Raised instead of returning an empty result list so a total
    retrieval outage is not mistaken for a query with no matches.

    Attributes:
        failures: Each failed method name mapped to the exception it
            raised.
    """

    def __init__(self, failures: dict[str, BaseException]) -> None:
        """Bind the failed method names and their causes to the error."""
        self.failures = failures
        details = "; ".join(f"{name}: {error!r}" for name, error in failures.items())
        super().__init__(f"every retrieval method failed: {details}")


__all__ = [
    "AllRetrievalMethodsFailedError",
    "RetrievalError",
]
