"""Errors raised by candidate review operations."""


class PatchNotAppliedError(ValueError):
    """The active schema does not contain every change in a patch."""

    def __init__(self, missing: list[str]) -> None:
        """Store missing patch entries and describe how to resolve them."""
        self.missing = missing
        super().__init__(
            "The schema does not contain these patch items: " + "; ".join(missing)
        )
