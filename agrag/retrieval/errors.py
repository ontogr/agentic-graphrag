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


class UnknownRecipeMethodError(RetrievalError):
    """A Recipe named a method SearchEngine does not know how to run.

    A misspelled method name is a configuration error and must be
    raised at search time so an empty successful search cannot
    silently hide a typo.

    Attributes:
        unknown: The method names the recipe listed that are not in
            the retriever registry.
        known: The method names this SearchEngine can run.
    """

    def __init__(self, unknown: list[str], known: list[str]) -> None:
        """Bind the unknown and known method lists to the error."""
        self.unknown = list(unknown)
        self.known = list(known)
        super().__init__(
            f"recipe methods {self.unknown!r} are not registered; "
            f"known methods: {self.known!r}"
        )


__all__ = [
    "AllRetrievalMethodsFailedError",
    "RetrievalError",
    "UnknownRecipeMethodError",
]
