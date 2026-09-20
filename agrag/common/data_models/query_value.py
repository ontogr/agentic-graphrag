"""A scalar value returned by a direct graph query."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class QueryValue(BaseModel):
    """One scalar row returned by a generated graph query."""

    id: UUID = Field(default_factory=uuid4)
    value: Any
