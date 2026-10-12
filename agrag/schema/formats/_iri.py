"""IRI helpers shared by the SHACL and JSON-LD exporters."""

import re
from urllib.parse import quote

from agrag.common.data_models.graph_schema import GraphSchema


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Characters that would close a Turtle IRI reference or split the prefix
# line. The base is interpolated inside angle brackets, so anything here
# could inject extra triples into the export.
_BAD_BASE = re.compile(r'[<>\x00-\x20"{}|^`\\\x7f]')


def default_base(schema: GraphSchema) -> str:
    """Return the namespace IRI that a schema's terms live in."""
    return f"urn:agrag:schema:{quote(schema.name, safe='')}:"


def resolve_base(schema: GraphSchema, base_iri: str | None) -> str:
    """Return the namespace IRI for exported terms.

    Args:
        schema: The schema being exported.
        base_iri: A replacement namespace, or None for the default.

    Returns:
        The replacement, or the schema default when None is given.

    Raises:
        ValueError: If the replacement is not an absolute IRI without
            characters that would break the Turtle prefix line.
    """
    if base_iri is None:
        return default_base(schema)
    # Reject values that could close the angle brackets or add statements.
    if not base_iri or ":" not in base_iri or _BAD_BASE.search(base_iri):
        raise ValueError(
            f"Invalid base_iri {base_iri!r}; use an absolute IRI "
            'without spaces or <>"{}|^`\\ characters.'
        )
    return base_iri


def term_iri(name: str, base: str) -> str:
    """Return the Turtle term for a schema name.

    Names that fit a Turtle local name use the ``ex:`` prefix, so the
    SHACL and JSON-LD exports share one namespace. Anything else becomes
    a full IRI with the unsafe characters percent-encoded.

    Args:
        name: An entity, relation or property name.
        base: The namespace IRI that ``ex:`` stands for.

    Returns:
        ``ex:<name>`` for safe names, else a full IRI in brackets.
    """
    if _SAFE_NAME.match(name) is not None:
        return f"ex:{name}"
    return f"<{base}{quote(name, safe='')}>"


def _escape_literal(value: str) -> str:
    """Escape text for a double-quoted Turtle literal.

    Args:
        value: The raw text.

    Returns:
        The text with backslashes, quotes and controls escaped.
    """
    # Named escapes first, so the backslash they introduce is not re-escaped.
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )
    # Any other C0 control or DEL has no short form, so use a unicode escape.
    return re.sub(
        r"[\x00-\x08\x0b\x0e-\x1f\x7f]",
        lambda match: f"\\u{ord(match.group(0)):04X}",
        escaped,
    )
