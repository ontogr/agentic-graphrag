"""IRI helpers shared by the SHACL and JSON-LD exporters."""

from urllib.parse import quote

from agrag.common.data_models.graph_schema import GraphSchema


def default_base(schema: GraphSchema) -> str:
    """Return the namespace IRI that a schema's terms live in."""
    return f"urn:agrag:schema:{quote(schema.name, safe='')}:"
