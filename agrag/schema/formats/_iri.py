"""IRI helpers shared by the SHACL and JSON-LD exporters."""

import re
from urllib.parse import quote

from agrag.common.data_models.graph_schema import GraphSchema


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    """
    if base_iri is None:
        return default_base(schema)
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
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
