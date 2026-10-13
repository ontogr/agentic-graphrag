"""Result returned by document lifecycle operations."""

from pydantic import BaseModel

from agrag.common.data_models.update_decision import UpdateDecision
from agrag.ingestion.reports.add_result import AddResult


class UpdateResult(BaseModel):
    """Summary of an update or soft deletion.

    Attributes:
        document_key: Stable identity used for the document node.
        no_op: Whether no graph changes were needed.
        previous_content_hash: Hash stored before the operation, if present.
        new_content_hash: Hash written by an update, or ``None`` on deletion.
        parts_closed: Number of open HAS_PART edges closed.
        add_result: Ingestion details for changed content, if any.
        decision: The outcome selected for an update, or ``None`` on deletion.
    """

    document_key: str
    no_op: bool
    previous_content_hash: str | None = None
    new_content_hash: str | None = None
    parts_closed: int = 0
    add_result: AddResult | None = None
    decision: UpdateDecision | None = None
