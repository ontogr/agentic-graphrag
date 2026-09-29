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
