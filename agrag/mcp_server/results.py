"""Bound tool results and shape them for MCP responses."""

import asyncio
from collections.abc import Awaitable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent
from pydantic_core import to_json, to_jsonable_python


# The SDK sends a text block beside every structured result. This wrapper keeps
# that block short, so structured data is sent once.
RESULT_TEXT = "The result is in structuredContent."


async def bounded_result(
    deadline: float,
    response_limit: int,
    operation: Awaitable[Any],
) -> CallToolResult:
    """Apply the deadline and the size cap, then build the tool result.

    Args:
        deadline: The most seconds the operation may take.
        response_limit: The most characters the sent result may take: the
            structured JSON plus the text block.
        operation: The history, decision, or evidence operation to await.

    Returns:
        The result with the value as structured content.

    Raises:
        ToolError: The operation missed the deadline or the result is too large.
    """
    try:
        async with asyncio.timeout(deadline):
            value = await operation
    except TimeoutError:
        raise ToolError("tool operation deadline exceeded") from None
    structured = to_jsonable_python(value, by_alias=True)
    if not isinstance(structured, dict):
        # Match the wrapped output schema that the SDK advertises for lists.
        structured = {"result": structured}
    if len(to_json(structured)) + len(RESULT_TEXT) > response_limit:
        raise ToolError("tool result exceeds the configured response limit")
    return CallToolResult(
        content=[TextContent(type="text", text=RESULT_TEXT)],
        structured_content=structured,
    )
