"""Chat reader: JSON Lines or JSON messages as one document with turns."""

import json
import unicodedata
from collections.abc import Iterator
from typing import Any, BinaryIO

from agrag.common.data_models.document import SourceFormat, TurnRef
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.decode import decode_text
from agrag.loaders.corpus.errors import MalformedRecordError
from agrag.loaders.corpus.readers._common import (
    build_prose_document,
    read_within_limit,
    source_title,
)
from agrag.loaders.corpus.types import ReadOptions, SourceRef


_TURN_SEPARATOR = "\n\n"


def _messages(text: str, source: SourceRef) -> list[dict[str, Any]]:
    """Parse the messages of a JSON array or of JSON Lines text."""
    if source.extension == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedRecordError(f"Failed to parse {source.uri}: {exc}") from exc
        if not isinstance(parsed, list):
            raise MalformedRecordError(f"{source.uri} must hold an array of messages")
        return parsed
    messages: list[Any] = []
    for line_no, raw_line in enumerate(text.split("\n")):
        line = raw_line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise MalformedRecordError(
                f"Failed to parse line {line_no} of {source.uri}: {exc}"
            ) from exc
    return messages


class ChatLoader(ProseLoader):
    """Reads a file of chat messages as one document with a turn for each message.

    Each message is a JSON object with a ``role`` and a ``content`` string, and an
    optional ``id``. A ``.jsonl`` or ``.ndjson`` file has one message per line. A
    ``.json`` file holds an array of messages. The document text is one
    ``[role] content`` block per message, separated by a blank line, and
    ``Document.turns`` records the span of each block.

    The loader is not registered for any extension, because ``.jsonl`` belongs to the
    record loader. Pass ``loader=ChatLoader()`` with a single-file source.

    Attributes:
        extensions: The ``.jsonl``, ``.ndjson`` and ``.json`` extensions.
    """

    extensions = frozenset({".jsonl", ".ndjson", ".json"})

    def load(
        self,
        source: SourceRef,
        stream: BinaryIO,
        opts: ReadOptions,
        *,
        start_at: int = 0,
    ) -> Iterator:
        """Yield one prose Document that holds every message.

        Args:
            source: The source to read.
            stream: The open binary stream for the source.
            opts: The read options.
            start_at: Ignored by prose loaders.

        Yields:
            One Document, or none when the source has no messages.

        Raises:
            MalformedRecordError: A message is not a JSON object with a non-empty
                string ``role``, a string ``content`` and a unique ``id``, or the
                source is not valid JSON of the expected shape.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        messages = _messages(decoded.text, source)
        if not messages:
            return
        blocks: list[str] = []
        turns: list[TurnRef] = []
        seen_ids: set[str] = set()
        position = 0
        for index, message in enumerate(messages):
            role, content, turn_id = self._fields(message, index, source)
            # JSON escapes such as \\ufb01 reach the text only after parsing, so the
            # Unicode form of the decode step has not seen them yet.
            form = opts.normalization.unicode_form
            if form != "none":
                role = unicodedata.normalize(form, role)
                content = unicodedata.normalize(form, content)
            if turn_id is not None:
                if turn_id in seen_ids:
                    raise MalformedRecordError(
                        f"Message {index} of {source.uri} repeats the id {turn_id!r}"
                    )
                seen_ids.add(turn_id)
            block = f"[{role}] {content}"
            turns.append(
                TurnRef(
                    role=role,
                    turn_id=turn_id,
                    char_start=position,
                    char_end=position + len(block),
                )
            )
            blocks.append(block)
            position += len(block) + len(_TURN_SEPARATOR)
        yield build_prose_document(
            source=source,
            text=_TURN_SEPARATOR.join(blocks),
            encoding=decoded.encoding,
            source_format=(
                SourceFormat.JSON if source.extension == ".json" else SourceFormat.JSONL
            ),
            loader_name="chat",
            opts=opts,
            title=source_title(source),
            turns=turns,
        )

    @staticmethod
    def _fields(
        message: Any, index: int, source: SourceRef
    ) -> tuple[str, str, str | None]:
        """Return the role, content and id of one message, or raise."""
        if not isinstance(message, dict):
            raise MalformedRecordError(
                f"Message {index} of {source.uri} is not a JSON object"
            )
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise MalformedRecordError(
                f"Message {index} of {source.uri} needs a non-empty string role"
            )
        if not isinstance(content, str):
            raise MalformedRecordError(
                f"Message {index} of {source.uri} needs a string content"
            )
        turn_id = message.get("id")
        return role, content, None if turn_id is None else str(turn_id)
