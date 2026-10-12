"""Export GraphSchema declarations as a JSON-LD OWL vocabulary."""

import json
from typing import Any
from urllib.parse import quote

from agrag.common.data_models.graph_schema import (
    GraphSchema,
    PropertySpec,
    RelationType,
)


_XSD_TYPES = {
    "string": "xsd:string",
    "integer": "xsd:integer",
    "float": "xsd:double",
    "boolean": "xsd:boolean",
    "date": "xsd:date",
}


def _iri(base: str, name: str) -> str:
    return f"{base}{quote(name, safe='')}"


def _union(terms: list[str]) -> dict[str, Any]:
    if len(terms) == 1:
        return {"@id": terms[0]}
    return {
        "@type": "owl:Class",
        "owl:unionOf": {"@list": [{"@id": term} for term in terms]},
    }


def _property_node(
    base: str, label: str, name: str, spec: PropertySpec
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "@id": f"{base}{quote(label, safe='')}/{quote(name, safe='')}",
        "@type": "owl:DatatypeProperty",
        "rdfs:label": {"@value": name},
        "rdfs:domain": {"@id": _iri(base, label)},
        "rdfs:range": {"@id": _XSD_TYPES[spec.type]},
        "agrag:propertyName": {"@value": name},
        "agrag:required": {"@value": spec.required, "@type": "xsd:boolean"},
    }
    if spec.description:
        node["rdfs:comment"] = {"@value": spec.description}
    if spec.enum is not None:
        node["agrag:enum"] = [{"@value": value} for value in spec.enum]
    return node


def _relation_node(base: str, relation: RelationType) -> dict[str, Any]:
    node: dict[str, Any] = {
        "@id": _iri(base, relation.label),
        "@type": ["owl:ObjectProperty"],
        "rdfs:label": {"@value": relation.label},
        "agrag:patterns": [
            {"@value": json.dumps(pattern, ensure_ascii=False, separators=(",", ":"))}
            for pattern in relation.patterns
        ],
        "agrag:symmetric": {
            "@value": relation.symmetric,
            "@type": "xsd:boolean",
        },
    }
    if relation.description:
        node["rdfs:comment"] = {"@value": relation.description}
    if relation.patterns:
        source_labels = {source for source, _ in relation.patterns}
        target_labels = {target for _, target in relation.patterns}
        if relation.symmetric:
            source_labels.update(target_labels)
            target_labels.update(source for source, _ in relation.patterns)
        domains = sorted({_iri(base, label) for label in source_labels})
        ranges = sorted({_iri(base, label) for label in target_labels})
        node["rdfs:domain"] = _union(domains)
        node["rdfs:range"] = _union(ranges)
    for limit, annotation, owl_type in (
        (
            relation.cardinality.max_per_source,
            "agrag:maxPerSource",
            "owl:FunctionalProperty",
        ),
        (
            relation.cardinality.max_per_target,
            "agrag:maxPerTarget",
            "owl:InverseFunctionalProperty",
        ),
    ):
        if limit == 1:
            node["@type"].append(owl_type)
        elif limit is not None:
            node[annotation] = {"@value": limit, "@type": "xsd:integer"}
    return node


def to_jsonld(schema: GraphSchema, *, base_iri: str | None = None) -> dict[str, Any]:
    """Return a JSON-LD OWL vocabulary for a graph schema.

    Entity types become OWL classes. Entity properties use entity-qualified IRIs
    so declarations with the same property name on different types stay distinct.
    Relation endpoint sets use OWL union classes, preserving alternative domains
    and ranges instead of implying an intersection. Pattern pairs, symmetry,
    requiredness, enums and cardinality limits above one use ``agrag`` annotations.
    Empty relation patterns do not create domain or range axioms.

    Args:
        schema: The schema to export.
        base_iri: Replacement namespace, or None for the schema-name namespace.

    Returns:
        A plain JSON-serializable JSON-LD document.
    """
    base = (
        base_iri
        if base_iri is not None
        else f"urn:agrag:schema:{quote(schema.name, safe='')}:"
    )
    graph: list[dict[str, Any]] = []
    for entity in schema.entities:
        item: dict[str, Any] = {
            "@id": _iri(base, entity.label),
            "@type": "owl:Class",
            "rdfs:label": {"@value": entity.label},
        }
        if entity.description:
            item["rdfs:comment"] = {"@value": entity.description}
        if entity.parents:
            parents = [{"@id": _iri(base, parent)} for parent in entity.parents]
            item["rdfs:subClassOf"] = parents[0] if len(parents) == 1 else parents
        graph.append(item)
        for name, spec in entity.properties.items():
            graph.append(_property_node(base, entity.label, name, spec))

    for relation in schema.relations:
        graph.append(_relation_node(base, relation))

    return {
        "@context": {
            "owl": "http://www.w3.org/2002/07/owl#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "agrag": "https://ontogr.com/agrag/schema#",
        },
        "@graph": graph,
    }
