"""Import the supported OWL and RDFS Turtle subset."""

import re
from dataclasses import dataclass
from functools import partial
from importlib import import_module
from pathlib import Path
from typing import Any

from agrag.schema.formats.errors import (
    SchemaFormatError,
    SchemaFormatMissingExtraError,
)
from agrag.schema.formats.result import FormatWarning, ImportResult


_EXTRA = "schema-formats"
_SCALAR_TYPES = {
    "string": "string",
    "normalizedString": "string",
    "token": "string",
    "integer": "integer",
    "int": "integer",
    "long": "integer",
    "short": "integer",
    "decimal": "float",
    "double": "float",
    "float": "float",
    "boolean": "boolean",
    "date": "date",
}


def _rdflib() -> tuple[Any, ...]:
    try:
        rdf = import_module("rdflib")
        namespace = import_module("rdflib.namespace")
    except ImportError as exc:
        raise SchemaFormatMissingExtraError("OWL Turtle import", _EXTRA) from exc
    return (
        rdf.Graph,
        namespace.OWL,
        rdf.RDF,
        rdf.RDFS,
        rdf.URIRef,
        namespace.XSD,
    )


def _local(uri: Any) -> str:
    return (
        str(uri).rstrip("/#:").rsplit("/", 1)[-1].rsplit("#", 1)[-1].rsplit(":", 1)[-1]
    )


def _label(uri: Any) -> str | None:
    value = _local(uri)
    return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) else None


def _domains(graph: Any, prop: Any, rdfs: Any, owl: Any, rdf: Any) -> list[Any]:
    result: set[Any] = set()
    for node in graph.objects(prop, rdfs.domain):
        members = graph.value(node, owl.unionOf)
        if members is None:
            result.add(node)
        else:
            result.update(_rdf_list(graph, members, rdf))
    return sorted(result, key=str)


def _rdf_list(graph: Any, head: Any, rdf: Any) -> list[Any]:
    """Read an RDF list and reject cycles instead of hanging the import."""
    values = []
    seen = set()
    node = head
    while node != rdf.nil:
        if node in seen:
            raise SchemaFormatError("cyclic RDF list cannot be imported")
        seen.add(node)
        values.append(graph.value(node, rdf.first))
        node = graph.value(node, rdf.rest)
        if node is None:
            raise SchemaFormatError("malformed RDF list cannot be imported")
    return values


def _warn(warnings: list[FormatWarning], code: str, element: Any, message: str) -> None:
    warnings.append(FormatWarning(code, str(element), message))


def _property_description(
    graph: Any, prop: Any, rdfs: Any, warnings: list[FormatWarning]
) -> str:
    values = list(graph.objects(prop, rdfs.comment))
    comments = sorted(
        (value for value in values if not getattr(value, "language", None)),
        key=str,
    ) or sorted(values, key=str)
    comments = [str(value) for value in comments]
    if len(values) > 1:
        _warn(
            warnings,
            "comment_alternatives_dropped",
            prop,
            "Extra comments were dropped.",
        )
    if comments:
        _warn(
            warnings,
            "comment_ignored",
            prop,
            "Ontology comments are not used as schema descriptions.",
        )
        return _local(prop)
    _warn(
        warnings,
        "missing_description",
        prop,
        "The property name is used as its description.",
    )
    labels = sorted(map(str, graph.objects(prop, rdfs.label)))
    return labels[0] if labels else _local(prop)


def _relation_limits(  # noqa: PLR0917
    graph: Any,
    domains: list[Any],
    prop: Any,
    owl: Any,
    rdfs: Any,
    warnings: list[FormatWarning],
) -> tuple[int | None, bool]:
    limits_by_domain: list[int | None] = []
    predicates = (
        owl.cardinality,
        owl.maxCardinality,
        owl.qualifiedCardinality,
        owl.maxQualifiedCardinality,
        owl.minCardinality,
        owl.minQualifiedCardinality,
    )
    for domain in domains:
        domain_limits: list[int] = []
        for restriction in graph.objects(domain, rdfs.subClassOf):
            if graph.value(restriction, owl.onProperty) != prop:
                continue
            for predicate in predicates:
                value = graph.value(restriction, predicate)
                if value is None:
                    continue
                if (
                    predicate in (owl.cardinality, owl.maxCardinality)
                    and int(value) >= 1
                ):
                    domain_limits.append(int(value))
                    if predicate in (owl.cardinality, owl.qualifiedCardinality):
                        _warn(
                            warnings,
                            "min_cardinality_dropped",
                            prop,
                            "The minimum implied by exact cardinality is not stored.",
                        )
                elif predicate in (
                    owl.minCardinality,
                    owl.minQualifiedCardinality,
                ):
                    _warn(
                        warnings,
                        "min_cardinality_dropped",
                        prop,
                        "Minimum relation cardinality is not represented.",
                    )
                else:
                    _warn(
                        warnings,
                        "restriction_ignored",
                        prop,
                        "Qualified or unsupported cardinality was ignored.",
                    )
        limits_by_domain.append(min(domain_limits) if domain_limits else None)
    unrestricted = any(limit is None for limit in limits_by_domain)
    scoped = len(set(limits_by_domain)) > 1
    return (
        None
        if unrestricted
        else max(
            (limit for limit in limits_by_domain if limit is not None), default=None
        ),
        scoped,
    )


@dataclass
class _Source:
    """An open RDF graph with the vocabularies and state one import shares."""

    graph: Any
    owl: Any
    rdf: Any
    rdfs: Any
    uri_ref: Any
    xsd: Any
    warnings: list[FormatWarning]
    declared: dict[Any, str]


def _declared_classes(src: _Source) -> dict[Any, str]:
    graph = src.graph
    owl = src.owl
    rdf = src.rdf
    rdfs = src.rdfs
    uri_ref = src.uri_ref
    declared = src.declared
    class_uris = sorted(
        set(graph.subjects(rdf.type, owl.Class))
        | set(graph.subjects(rdf.type, rdfs.Class)),
        key=str,
    )
    labels = {
        uri: _label(uri) if isinstance(uri, uri_ref) else None for uri in class_uris
    }
    invalid_classes = [uri for uri, label in labels.items() if label is None]
    if invalid_classes:
        raise SchemaFormatError(f"invalid class identifier: {invalid_classes[0]}")
    declared = {uri: label for uri, label in labels.items() if label is not None}
    if len(set(declared.values())) != len(declared):
        raise SchemaFormatError("colliding class identifiers map to the same label")
    return declared


def _read_entities(
    src: _Source,
) -> tuple[list[dict[str, Any]], dict[Any, list[Any]]]:
    graph = src.graph
    rdfs = src.rdfs
    uri_ref = src.uri_ref
    warnings = src.warnings
    declared = src.declared
    entities: list[dict[str, Any]] = []
    parent_uris: dict[Any, list[Any]] = {}
    for uri, label in sorted(declared.items(), key=lambda pair: pair[1]):
        comment_values = list(graph.objects(uri, rdfs.comment))
        comments = sorted(
            (value for value in comment_values if not getattr(value, "language", None)),
            key=str,
        ) or sorted(comment_values, key=str)
        comments = [str(value) for value in comments]
        if len(comment_values) > 1:
            _warn(
                warnings,
                "comment_alternatives_dropped",
                uri,
                "Extra comments were dropped.",
            )
        fallback = sorted(map(str, graph.objects(uri, rdfs.label)))
        description = label
        if comments or fallback:
            _warn(
                warnings,
                "description_ignored",
                uri,
                "Ontology text is not used as a schema description.",
            )
        if not comments and not fallback:
            _warn(
                warnings,
                "missing_description",
                uri,
                "The class name is used as its description.",
            )
        parent_uris[uri] = sorted(
            (
                parent
                for parent in graph.objects(uri, rdfs.subClassOf)
                if isinstance(parent, uri_ref)
            ),
            key=str,
        )
        if any(
            not isinstance(parent, uri_ref)
            for parent in graph.objects(uri, rdfs.subClassOf)
        ):
            _warn(
                warnings,
                "construct_ignored",
                uri,
                "Anonymous subclass expressions are not mapped.",
            )
        parents = []
        for parent in parent_uris[uri]:
            if parent in declared:
                parents.append(declared[parent])
            else:
                _warn(
                    warnings,
                    "unknown_parent",
                    uri,
                    f"Undeclared parent {_local(parent)!r} was ignored.",
                )
        props: dict[str, dict[str, Any]] = {}
        entities.append(
            {
                "label": label,
                "description": description,
                "parents": parents,
                "properties": props,
            }
        )
    return entities, parent_uris


def _expand_unions(src: _Source, nodes: list[Any]) -> list[Any]:
    members: list[Any] = []
    for node in nodes:
        union = src.graph.value(node, src.owl.unionOf)
        members.extend(
            _rdf_list(src.graph, union, src.rdf) if union is not None else [node]
        )
    return members


def _scalar_type(src: _Source, node: Any) -> str | None:
    if not str(node).startswith(str(src.xsd)):
        return None
    return _SCALAR_TYPES.get(_local(node))


def _enum_kind(src: _Source, item: Any) -> str | None:
    if item.datatype is None:
        return "string"
    return _scalar_type(src, item.datatype)


def _enum_values(
    src: _Source, prop: Any, enum_node: Any, value_type: str
) -> tuple[str, list[str]]:
    literals = _rdf_list(src.graph, src.graph.value(enum_node, src.owl.oneOf), src.rdf)
    kinds = {_enum_kind(src, item) for item in literals}
    if len(kinds) == 1 and None not in kinds:
        value_type = str(next(iter(kinds)))
    elif len(kinds) > 1 or None in kinds:
        _warn(
            src.warnings,
            "enum_types_widened",
            prop,
            "Mixed or unsupported enum types were widened to string.",
        )
    values = sorted(
        re.sub(r"(?:Z|[+-]\d{2}:\d{2})$", "", str(item))
        if value_type == "date"
        else str(item)
        for item in literals
    )
    return value_type, values


def _datatype_and_enum(src: _Source, prop: Any) -> tuple[str, list[str] | None]:
    graph = src.graph
    owl = src.owl
    rdfs = src.rdfs
    warnings = src.warnings
    range_nodes = _expand_unions(src, sorted(graph.objects(prop, rdfs.range), key=str))
    value_type = next(
        (kind for kind in map(partial(_scalar_type, src), range_nodes) if kind), None
    )
    if value_type is None:
        value_type = "string"
        _warn(
            warnings,
            "datatype_widened",
            prop,
            "The missing or unsupported datatype range was widened to string.",
        )
    enum_node = next(
        (
            node
            for node in graph.objects(prop, rdfs.range)
            if (node, owl.oneOf, None) in graph
        ),
        None,
    )
    if enum_node is not None:
        return _enum_values(src, prop, enum_node, value_type)
    mixed = len(set(range_nodes)) > 1
    if mixed and len({_scalar_type(src, node) for node in range_nodes}) > 1:
        _warn(
            warnings,
            "multiple_ranges_narrowed",
            prop,
            "Multiple datatype ranges cannot be represented as alternatives.",
        )
        value_type = "string"
    return value_type, None


def _required_by_restrictions(src: _Source, domain: Any, prop: Any) -> bool:
    graph = src.graph
    owl = src.owl
    rdfs = src.rdfs
    warnings = src.warnings
    required = False
    for restriction in graph.objects(domain, rdfs.subClassOf):
        if graph.value(restriction, owl.onProperty) != prop:
            continue
        for predicate in (owl.minCardinality, owl.cardinality):
            value = graph.value(restriction, predicate)
            if value is not None and int(value) > 0:
                required = True
        for predicate in (owl.maxCardinality, owl.cardinality):
            value = graph.value(restriction, predicate)
            if value is not None and int(value) == 0:
                _warn(
                    warnings,
                    "zero_max_cardinality_dropped",
                    prop,
                    "Zero maximum cardinality cannot be represented.",
                )
            if value is not None and int(value) > 1:
                _warn(
                    warnings,
                    "max_cardinality_dropped",
                    prop,
                    "A scalar property cannot store a maximum above one.",
                )
    return required


def _read_datatype_property(
    src: _Source, entity_by_uri: dict[Any, dict[str, Any]], prop: Any
) -> None:
    graph = src.graph
    owl = src.owl
    rdf = src.rdf
    rdfs = src.rdfs
    warnings = src.warnings
    declared = src.declared
    domains = _domains(graph, prop, rdfs, owl, rdf)
    class_domains = [domain for domain in domains if domain in declared]
    for domain in domains:
        if domain not in declared:
            _warn(
                warnings,
                "unknown_class_ignored",
                prop,
                f"Undeclared domain {_local(domain)!r} was ignored.",
            )
    if len(class_domains) > 1:
        _warn(
            warnings,
            "multiple_domains_unioned",
            prop,
            "Multiple domains are mapped as a union.",
        )
    if not class_domains:
        _warn(
            warnings,
            "property_without_domain",
            prop,
            "The datatype property has no declared class domain and was dropped.",
        )
        return
    prop_label = _label(prop)
    if prop_label is None:
        _warn(
            warnings,
            "construct_ignored",
            prop,
            "The property name is not a valid schema property name.",
        )
        return
    value_type, enum_values = _datatype_and_enum(src, prop)
    description = _property_description(graph, prop, rdfs, warnings)
    for domain in class_domains:
        required = _required_by_restrictions(src, domain, prop)
        properties = entity_by_uri[domain]["properties"]
        if prop_label in properties:
            _warn(
                warnings,
                "property_name_collision",
                prop,
                f"Property {prop_label!r} collides with an earlier property; "
                "it was ignored.",
            )
            continue
        properties[prop_label] = {
            "type": value_type,
            "required": required,
            "enum": enum_values,
            "description": description,
        }


def _inherit_properties(
    declared: dict[Any, str],
    parent_uris: dict[Any, list[Any]],
    entity_by_uri: dict[Any, dict[str, Any]],
) -> None:
    for uri in declared:
        inherited = {}
        ancestors = list(parent_uris[uri])
        seen_ancestors = set()
        while ancestors:
            parent = ancestors.pop()
            if parent in seen_ancestors:
                continue
            seen_ancestors.add(parent)
            ancestors.extend(parent_uris.get(parent, []))
            if parent in entity_by_uri:
                inherited.update(entity_by_uri[parent]["properties"])
        for prop_label, specification in inherited.items():
            properties = entity_by_uri[uri]["properties"]
            if prop_label not in properties:
                properties[prop_label] = specification


def _relation_endpoints(src: _Source, prop: Any) -> tuple[list[str], list[str]] | None:
    graph = src.graph
    rdfs = src.rdfs
    warnings = src.warnings
    declared = src.declared
    domain_statements = list(graph.objects(prop, rdfs.domain))
    range_statements = list(graph.objects(prop, rdfs.range))
    if len(domain_statements) > 1 or len(range_statements) > 1:
        _warn(
            warnings,
            "conjunctive_endpoints_unsupported",
            prop,
            "Multiple domain or range axioms are conjunctive and were dropped.",
        )
        return None
    domains = _domains(graph, prop, rdfs, src.owl, src.rdf)
    ranges = sorted(set(_expand_unions(src, range_statements)), key=str)
    sources = [declared[node] for node in domains if node in declared]
    targets = [declared[node] for node in ranges if node in declared]
    for node in [*domains, *ranges]:
        if node not in declared:
            _warn(
                warnings,
                "unknown_class_ignored",
                prop,
                f"Undeclared endpoint {_local(node)!r} was ignored.",
            )
    if len(domains) > 1 or len(ranges) > 1:
        _warn(
            warnings,
            "multiple_domains_unioned",
            prop,
            "Multiple endpoints are mapped as a union.",
        )
    if not sources or not targets:
        _warn(
            warnings,
            "relation_dropped",
            prop,
            "The object property needs a declared class domain and range.",
        )
        return None
    return sources, targets


def _relation_label(src: _Source, prop: Any) -> str | None:
    raw_label = _local(prop)
    rel_label = re.sub(r"(?<!^)(?=[A-Z])", "_", raw_label).upper()
    if rel_label != raw_label.upper():
        _warn(
            src.warnings,
            "relation_label_normalized",
            prop,
            f"Relation label was normalized to {rel_label}.",
        )
    if _label(prop) is None:
        _warn(
            src.warnings,
            "construct_ignored",
            prop,
            "The relation name is not a valid label.",
        )
        return None
    return rel_label


def _relation_patterns_and_limits(
    src: _Source, prop: Any, sources: list[str], targets: list[str]
) -> tuple[list[list[str]], int | None, int | None]:
    graph = src.graph
    owl = src.owl
    rdf = src.rdf
    functional = (prop, rdf.type, owl.FunctionalProperty) in graph
    inverse = (prop, rdf.type, owl.InverseFunctionalProperty) in graph
    symmetric = (prop, rdf.type, owl.SymmetricProperty) in graph
    restricted_limit, scoped = _relation_limits(
        graph,
        [uri for uri in src.declared if src.declared[uri] in sources],
        prop,
        owl,
        src.rdfs,
        src.warnings,
    )
    max_per_source = 1 if functional else restricted_limit
    if scoped:
        _warn(
            src.warnings,
            "cardinality_scope_lost",
            prop,
            "Class-specific relation cardinality applies to the imported relation.",
        )
    max_per_target = 1 if inverse else None
    patterns = [[source, target] for source in sources for target in targets]
    if symmetric:
        symmetric_limit = max_per_source or max_per_target
        max_per_source = symmetric_limit
        max_per_target = symmetric_limit
        reverse_patterns = sorted(
            {
                (source, target)
                for source in sources
                for target in targets
                for source, target in ((source, target), (target, source))
            }
        )
        patterns = [[source, target] for source, target in reverse_patterns]
    return patterns, max_per_source, max_per_target


def _read_relation(src: _Source, prop: Any) -> dict[str, Any] | None:
    endpoints = _relation_endpoints(src, prop)
    if endpoints is None:
        return None
    sources, targets = endpoints
    rel_label = _relation_label(src, prop)
    if rel_label is None:
        return None
    description = _property_description(src.graph, prop, src.rdfs, src.warnings)
    patterns, max_per_source, max_per_target = _relation_patterns_and_limits(
        src, prop, sources, targets
    )
    return {
        "label": rel_label,
        "description": description,
        "patterns": patterns,
        "cardinality": {
            "max_per_source": max_per_source,
            "max_per_target": max_per_target,
        },
        "symmetric": False,
    }


def _construct_message(src: _Source, predicate: Any) -> str | None:
    owl = src.owl
    fixed = {
        owl.imports: "owl:imports is not followed.",
        owl.equivalentClass: "owl:equivalentClass is not mapped.",
    }
    if predicate in fixed:
        return fixed[predicate]
    unmapped = {
        owl.disjointWith,
        owl.inverseOf,
        owl.equivalentProperty,
        owl.propertyChainAxiom,
        src.rdfs.subPropertyOf,
    }
    if predicate in unmapped:
        return f"Unsupported construct {_local(predicate)} was ignored."
    if str(predicate).endswith("altLabel"):
        return "Alternative labels are not stored by the schema model."
    return None


def _report_restriction(src: _Source, restriction: Any) -> None:
    graph = src.graph
    owl = src.owl
    cardinality_terms = (owl.cardinality, owl.maxCardinality, owl.minCardinality)
    owners = list(graph.subjects(src.rdfs.subClassOf, restriction))
    prop = graph.value(restriction, owl.onProperty)
    mapped_property = any(
        (prop, src.rdf.type, kind) in graph
        for kind in (owl.ObjectProperty, owl.DatatypeProperty)
    )
    if (
        owners
        and mapped_property
        and any(
            owner in _domains(graph, prop, src.rdfs, owl, src.rdf) for owner in owners
        )
        and any(
            graph.value(restriction, term) is not None for term in cardinality_terms
        )
    ):
        return
    _warn(
        src.warnings,
        "restriction_ignored",
        prop or restriction,
        "The restriction cannot map to a declared property constraint.",
    )


def _report_unsupported(src: _Source) -> None:
    owl = src.owl
    supported = {
        owl.Class,
        src.rdfs.Class,
        owl.DatatypeProperty,
        owl.ObjectProperty,
        owl.FunctionalProperty,
        owl.InverseFunctionalProperty,
        owl.SymmetricProperty,
    }
    for subject, predicate, obj in sorted(
        src.graph, key=lambda triple: tuple(map(str, triple))
    ):
        message = _construct_message(src, predicate)
        if message is not None:
            _warn(src.warnings, "construct_ignored", subject, message)
        elif predicate != src.rdf.type or obj in supported:
            continue
        elif obj == owl.NamedIndividual:
            _warn(
                src.warnings,
                "individuals_ignored",
                subject,
                "Named individuals are not imported.",
            )
        elif obj == owl.Restriction:
            _report_restriction(src, subject)
        else:
            _warn(
                src.warnings,
                "construct_ignored",
                subject,
                f"Unsupported type {_local(obj)} was ignored.",
            )


def _read(text: str, *, name: str | None, version: str | None) -> ImportResult:
    graph_type, owl, rdf, rdfs, uri_ref, xsd = _rdflib()
    graph = graph_type()
    try:
        graph.parse(data=text, format="turtle", publicID="urn:agrag:input:")
        graph = import_module("rdflib.compare").to_canonical_graph(graph)
    except Exception as exc:
        raise SchemaFormatError(f"invalid Turtle document: {exc}") from exc

    src = _Source(graph, owl, rdf, rdfs, uri_ref, xsd, [], {})
    src.declared = _declared_classes(src)
    entities, parent_uris = _read_entities(src)
    by_label = {entity["label"]: entity for entity in entities}
    entity_by_uri = {uri: by_label[label] for uri, label in src.declared.items()}
    for prop in sorted(set(graph.subjects(rdf.type, owl.DatatypeProperty)), key=str):
        _read_datatype_property(src, entity_by_uri, prop)
    _inherit_properties(src.declared, parent_uris, entity_by_uri)
    relations = [
        relation
        for prop in sorted(set(graph.subjects(rdf.type, owl.ObjectProperty)), key=str)
        if (relation := _read_relation(src, prop)) is not None
    ]
    _report_unsupported(src)

    data = {
        "name": name or "custom",
        "version": version or "1",
        "entities": entities,
        "relations": relations,
    }
    from agrag.schema import load_schema  # noqa: PLC0415

    return ImportResult(load_schema(data), src.warnings)


def loads_owl(
    text: str, *, name: str | None = None, version: str | None = None
) -> ImportResult:
    """Load the supported OWL/RDFS subset from Turtle text.

    Only declared types are imported. No reasoning or remote imports run.
    Unsupported constructs and lossy mappings appear in the warnings list.
    Name and version default to ``custom`` and ``1``.

    Raises:
        SchemaFormatError: Turtle or term identifiers cannot be read.
        SchemaFormatMissingExtraError: Install the ``schema-formats`` extra.
        SchemaLoadError: The mapped data fails schema validation.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _read(text, name=name, version=version)


def load_owl(
    source: str | Path, *, name: str | None = None, version: str | None = None
) -> ImportResult:
    """Load the supported OWL/RDFS subset from a local UTF-8 Turtle file.

    The name defaults to the file stem and version to ``1``. Import warnings
    are returned, not logged. Remote paths and ontology imports are not fetched.

    Raises:
        SchemaFormatError: The file or Turtle document cannot be read.
        SchemaFormatMissingExtraError: Install the ``schema-formats`` extra.
        SchemaLoadError: The mapped data fails schema validation.
    """
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SchemaFormatError(
            f"cannot read Turtle file {str(path)!r}: {exc}"
        ) from exc
    return _read(text, name=name or path.stem, version=version)
