"""The base class for a graph node."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DataPoint(BaseModel):
    """A graph node with a fixed id and free metadata.

    Attributes:
        id: The node id. Each subclass defines its own rule to compute this id.
        created_at: The time the system created this node. Defaults to the current time.
        metadata: Extra data about the node. Add an ``index_fields`` key to list which
        fields
            the store must index for filters.
    """

    id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
