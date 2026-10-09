"""Chat reader: JSON Lines or JSON messages, one section for each message."""

import json
import unicodedata
from collections.abc import Iterator
from typing import Any, BinaryIO

from agrag.common.data_models.document import Document, DocumentSection, SourceFormat
from agrag.loaders.base import ProseLoader
from agrag.loaders.common import (
    build_prose_document,
    paragraph_units,
    read_within_limit,
    source_title,
)
from agrag.loaders.decode import decode_text
from agrag.loaders.errors import MalformedRecordError
from agrag.loaders.types import ReadOptions, SourceRef


_TURN_SEPARATOR = "\n\n"


def _normalize_field(text: str, opts: ReadOptions) -> str:
    """Apply the configured text normalization to one parsed message field."""
    normalization = opts.normalization
    if normalization.bom == "strip":
        text = text.removeprefix("\ufeff")
    if normalization.newline == "lf":
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalization.unicode_form != "none":
        text = unicodedata.normalize(normalization.unicode_form, text)
    return text


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
                f"Failed to parse line {line_no + 1} of {source.uri}: {exc}"
            ) from exc
    return messages


class ChatLoader(ProseLoader):
    """Reads a file of chat messages as one document with a section for each message.

    Each message is a JSON object with a ``role`` and a ``content`` string, and an
    optional ``id``. A ``.jsonl`` or ``.ndjson`` file has one message per line. A
    ``.json`` file holds an array of messages. The document text is one
    ``[role] content`` block per message, separated by a blank line. Each message is
    a section at depth 1 with the role as its heading and the message id as its
    ``source_id``.

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
    ) -> Iterator[Document]:
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
                string ``role`` and a string ``content``, an ``id`` repeats an
                earlier one, or the source is not valid JSON of the expected shape.
        """
        raw = read_within_limit(stream, source, opts)
        decoded = decode_text(raw, opts)
        messages = _messages(decoded.text, source)
        if not messages:
            return
        blocks: list[str] = []
        sections: list[DocumentSection] = []
        seen_ids: set[str] = set()
        position = 0
        for index, message in enumerate(messages):
            role, content, turn_id = self._fields(message, index, source)
            role = _normalize_field(role, opts)
            content = _normalize_field(content, opts)
            if not role:
                raise MalformedRecordError(
                    f"Message {index} of {source.uri} needs a non-empty string role"
                )
            if turn_id is not None:
                if turn_id in seen_ids:
                    raise MalformedRecordError(
                        f"Message {index} of {source.uri} repeats the id {turn_id!r}"
                    )
                seen_ids.add(turn_id)
            block = f"[{role}] {content}"
            sections.append(
                DocumentSection(
                    heading=role,
                    depth=1,
                    source_id=turn_id,
                    units=paragraph_units(block, position),
                )
            )
            blocks.append(block)
            position += len(block) + len(_TURN_SEPARATOR)
        text = _TURN_SEPARATOR.join(blocks)
        yield build_prose_document(
            source=source,
            text=text,
            encoding=decoded.encoding,
            source_format=(
                SourceFormat.JSON if source.extension == ".json" else SourceFormat.JSONL
            ),
            loader_name="chat",
            opts=opts,
            title=source_title(source),
            sections=sections,
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
