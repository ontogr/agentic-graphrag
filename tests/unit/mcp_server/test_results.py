"""Unit tests for the size of task-history tool results as the SDK sends them.

The result of a record_event call with a full-size payload must fit the
default response limit once. Measuring it with the text block and structured
copy counted twice would reject a payload the store accepts.
"""

from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from pydantic_core import to_json

from agrag.common.data_models.task import Event, EventKind, RecordEventResult
from agrag.mcp_server.results import bounded_result


_DEFAULT_RESPONSE_CHARS = 60000
_T = TypeVar("_T")


def _recorded(payload: str) -> RecordEventResult:
    """Return a recorded event result that carries the payload."""
    event = Event(
        id=uuid4(),
        task_id=uuid4(),
        seq=1,
        kind=EventKind.TOOL_RESULT,
        role=None,
        name="search",
        payload=payload,
        payload_sha256="0" * 64,
        truncated=True,
        author="agent",
        at=datetime.now(UTC),
    )
    return RecordEventResult(recorded=True, event=event)


async def _awaited(value: _T) -> _T:
    """Return the value as an awaitable, like a completed history operation."""
    return value


class TestBoundedResult:
    """A task-history result is sent once and bounded by its serialized size."""

    async def test_full_size_payload_event_stays_under_the_default_limit(
        self,
    ) -> None:
        """A 32,000-character event is sent under 60,000 characters."""
        response = await bounded_result(
            5.0,
            _DEFAULT_RESPONSE_CHARS,
            _awaited(_recorded("x" * 32_000)),
        )

        assert len(to_json(response.structured_content)) > 32_000
        assert len(response.model_dump_json(by_alias=True)) < _DEFAULT_RESPONSE_CHARS

    async def test_result_over_the_limit_is_refused(self) -> None:
        """A result larger than the limit raises instead of being truncated."""
        with pytest.raises(
            ToolError, match="tool result exceeds the configured response limit"
        ):
            await bounded_result(5.0, 100, _awaited(_recorded("y" * 200)))
