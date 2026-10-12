"""Export a GraphSchema as SHACL shapes in Turtle syntax."""

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.schema.formats._iri import _escape_literal, resolve_base, term_iri


_DATATYPES = {
    "string": "xsd:string",
    "integer": "xsd:integer",
    "float": "xsd:double",
    "boolean": "xsd:boolean",
    "date": "xsd:date",
}


def _literal(value: str) -> str:
    """Wrap text as a double-quoted Turtle literal."""
    return f'"{_escape_literal(value)}"'


def _typed(value: str, datatype: str) -> str:
    """Render an enum value as a typed Turtle literal."""
    return f"{_literal(value)}^^{datatype}"


def _property_shape(name: str, spec: PropertySpec, base: str) -> str:
    """Render one entity property as an inline SHACL property shape."""
    datatype = _DATATYPES[spec.type]
    parts = [
        f"sh:path {term_iri(name, base)}",
        f"sh:datatype {datatype}",
        f"sh:minCount {1 if spec.required else 0}",
    ]
    if spec.enum is not None:
        values = " ".join(_typed(value, datatype) for value in spec.enum)
        parts.append(f"sh:in ( {values} )")
    if spec.description:
        parts.append(f"rdfs:comment {_literal(spec.description)}")
    return f"sh:property [ {' ; '.join(parts)} ]"


def _class_constraint(targets: list[str], base: str) -> str:
    """Render one sh:class or an sh:or over several classes."""
    if len(targets) == 1:
        return f"sh:class {term_iri(targets[0], base)}"
    members = " ".join(f"[ sh:class {term_iri(label, base)} ]" for label in targets)
    return f"sh:or ( {members} )"


def _forward_shape(relation: RelationType, targets: list[str], base: str) -> str:
    """Render the outgoing-edge shape a source node shape carries."""
    parts = [
        f"sh:path {term_iri(relation.label, base)}",
        _class_constraint(targets, base),
    ]
    if relation.cardinality.max_per_source is not None:
        parts.append(f"sh:maxCount {relation.cardinality.max_per_source}")
    return f"sh:property [ {' ; '.join(parts)} ]"


def _inverse_shape(relation: RelationType, sources: list[str], base: str) -> str:
    """Render the incoming-edge shape a target node shape carries."""
    path = term_iri(relation.label, base)
    parts = [
        f"sh:path [ sh:inversePath {path} ]",
        _class_constraint(sources, base),
    ]
    if relation.cardinality.max_per_target is not None:
        parts.append(f"sh:maxCount {relation.cardinality.max_per_target}")
    return f"sh:property [ {' ; '.join(parts)} ]"


def _declared_pairs(relation: RelationType) -> list[tuple[str, str]]:
    """Return the declared patterns without repeated pairs."""
    pairs: list[tuple[str, str]] = []
    for source, target in relation.patterns:
        # One annotation line per pair; repeats carry no extra meaning.
        if (source, target) not in pairs:
            pairs.append((source, target))
    return pairs


def _entity_block(
    entity: EntityType,
    outgoing: list[str],
    incoming: list[str],
    base: str,
) -> str:
    """Render one entity type as a SHACL node shape."""
    subject = term_iri(entity.label, base)
    lines = [
        f"{subject} a rdfs:Class, sh:NodeShape",
        f"    sh:targetClass {subject}",
        f"    rdfs:label {_literal(entity.label)}",
    ]
    if entity.description:
        lines.append(f"    rdfs:comment {_literal(entity.description)}")
    if entity.parents:
        members = ", ".join(term_iri(parent, base) for parent in entity.parents)
        lines.append(f"    rdfs:subClassOf {members}")
    for name in sorted(entity.properties):
        lines.append(f"    {_property_shape(name, entity.properties[name], base)}")
    for shape in outgoing:
        lines.append(f"    {shape}")
    for shape in incoming:
        lines.append(f"    {shape}")
    return " ;\n".join(lines) + " ."


def _relation_block(relation: RelationType, base: str) -> str:
    """Render one relation type as an annotated RDF property."""
    lines = [f"{term_iri(relation.label, base)} a rdf:Property"]
    for source, target in _declared_pairs(relation):
        start = term_iri(source, base)
        end = term_iri(target, base)
        lines.append(f"    x-agrag:pattern ( {start} {end} )")
    if relation.cardinality.max_per_source is not None:
        lines.append(f"    x-agrag:maxPerSource {relation.cardinality.max_per_source}")
    if relation.cardinality.max_per_target is not None:
        lines.append(f"    x-agrag:maxPerTarget {relation.cardinality.max_per_target}")
    if relation.symmetric:
        lines.append("    x-agrag:symmetric true")
    return " ;\n".join(lines) + " ."


def to_shacl(schema: GraphSchema, *, base_iri: str | None = None) -> str:
    """Export a schema as SHACL shapes in Turtle syntax.

    Each entity type becomes a ``sh:NodeShape`` with a
    ``sh:targetClass``, its description as ``rdfs:comment`` and each
    parent as ``rdfs:subClassOf``. Each declared property becomes an
    inline ``sh:property`` shape with ``sh:path``, ``sh:datatype``,
    ``sh:minCount`` and, for enums, ``sh:in``. Each relation type
    becomes an ``rdf:Property`` annotated with its declared patterns and
    limits, plus one ``sh:property`` shape on each endpoint's node shape
    naming the allowed classes (``sh:inversePath`` on the target side).
    Cardinality limits and symmetry have no SHACL form, so they appear
    as ``x-agrag:`` annotations that validators ignore.

    Args:
        schema: The schema to export.
        base_iri: A namespace IRI for the ``ex:`` prefix. Defaults to
            the schema namespace shared with the JSON-LD export.

    Returns:
        Turtle text describing the schema, written without dependencies.
    """
    base = resolve_base(schema, base_iri)
    header = "\n".join(
        [
            f"@prefix ex: <{base}> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix sh: <http://www.w3.org/ns/shacl#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "@prefix x-agrag: <urn:agrag:> .",
        ]
    )
    relations = sorted(schema.relations, key=lambda item: item.label)
    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    for relation in relations:
        by_source: dict[str, set[str]] = {}
        by_target: dict[str, set[str]] = {}
        for source, target in relation.patterns:
            by_source.setdefault(source, set()).add(target)
            by_target.setdefault(target, set()).add(source)
        for source in sorted(by_source):
            shape = _forward_shape(relation, sorted(by_source[source]), base)
            outgoing.setdefault(source, []).append(shape)
        for target in sorted(by_target):
            shape = _inverse_shape(relation, sorted(by_target[target]), base)
            incoming.setdefault(target, []).append(shape)
    chunks = [header]
    for entity in schema.entities:
        chunks.append(
            _entity_block(
                entity,
                outgoing.get(entity.label, []),
                incoming.get(entity.label, []),
                base,
            )
        )
    for relation in relations:
        chunks.append(_relation_block(relation, base))
    return "\n\n".join(chunks) + "\n"
