"""Result returned by document lifecycle operations."""

from pydantic import BaseModel

from agrag.ingestion.reports.add_result import AddResult


class UpdateResult(BaseModel):
    """Summary of an update or soft deletion.

    Attributes:
        document_key: Stable identity used for the document node.
        no_op: Whether no graph changes were needed.
        previous_content_hash: Hash stored before the operation, if present.
        new_content_hash: Hash written by an update, or ``None`` on deletion.
        chunks_closed: Number of open PART_OF edges closed.
        add_result: Ingestion details for changed content, if any.
    """

    document_key: str
    no_op: bool
    previous_content_hash: str | None = None
    new_content_hash: str | None = None
    chunks_closed: int = 0
    add_result: AddResult | None = None
