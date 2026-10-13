"""Outcomes for updating a stored document."""

from enum import StrEnum


class UpdateDecision(StrEnum):
    """What an update does with a document already in the graph.

    Attributes:
        NO_OP: The stored input matches and no refresh was requested.
        IN_PLACE: Extraction runs again while chunks and embeddings stay.
        NEW_VERSION: Changed content, chunking or schema requires new chunks.
        METADATA_ONLY: Only the document dates are written.
    """

    NO_OP = "no_op"
    IN_PLACE = "in_place"
    NEW_VERSION = "new_version"
    METADATA_ONLY = "metadata_only"
