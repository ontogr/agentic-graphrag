"""Helpers shared by the chunking tests."""

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    HeadingRef,
    SourceFormat,
)


def make_document(
    text: str,
    *,
    uri: str = "u",
    source_format: SourceFormat = SourceFormat.TXT,
    loader_name: str = "text",
    family: DocumentFamily = DocumentFamily.PROSE,
    outline: list[HeadingRef] | None = None,
    content_hash: str = "h",
) -> Document:
    """Build a prose document around text."""
    return Document(
        text=text,
        title="t",
        uri=uri,
        source_format=source_format,
        family=family,
        content_hash=content_hash,
        loader_name=loader_name,
        char_count=len(text),
        line_count=text.count("\n") + 1,
        heading_outline=outline or [],
    )


def make_chat_document(
    contents: list[str], *, header: str = "", separator: str = "\n\n", trailer: str = ""
) -> Document:
    """Build a chat document with one ``[role] content`` block per content."""
    from agrag.common.data_models.document import TurnRef  # noqa: PLC0415

    text = header
    turns = []
    for index, content in enumerate(contents):
        role = "user" if index % 2 == 0 else "assistant"
        block = f"[{role}] {content}"
        if index > 0 or header:
            text += separator
        turns.append(
            TurnRef(role=role, char_start=len(text), char_end=len(text) + len(block))
        )
        text += block
    text += trailer
    document = make_document(text, loader_name="chat")
    return document.model_copy(update={"turns": turns})


def content_for(index: int, block_length: int) -> str:
    """Return chat content that makes turn ``index`` a block of the given length."""
    role = "user" if index % 2 == 0 else "assistant"
    return "a" * (block_length - len(f"[{role}] "))
