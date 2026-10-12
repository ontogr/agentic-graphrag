"""Check the JSON-LD vocabulary emitted from loaded graph schemas."""

import json

from agrag.common.data_models.graph_schema import Cardinality, GraphSchema, RelationType
from agrag.schema import load_schema
from agrag.schema.formats import to_jsonld


def test_loaded_schema_exports_jsonld_vocabulary() -> None:
    """The export preserves class, property and relation declarations."""
    schema = load_schema(
        {
            "name": "odd schema",
            "entities": [
                {
                    "label": "ParentType",
                    "description": "The parent.",
                    "properties": {
                        "code": {"type": "string", "enum": ["a", "b"]},
                        "web address": {"type": "string"},
                    },
                },
                {
                    "label": "ChildType",
                    "description": "The child.",
                    "parents": ["ParentType"],
                    "properties": {"code": {"type": "integer", "required": True}},
                },
                {"label": "Target", "description": "A target."},
            ],
            "relations": [
                {
                    "label": "LINK_TYPE",
                    "description": "A link.",
                    "patterns": [["ChildType", "Target"], ["ParentType", "Target"]],
                    "cardinality": {"max_per_source": 1, "max_per_target": 1},
                },
            ],
        }
    )

    artifact = to_jsonld(schema)
    assert json.loads(json.dumps(artifact)) == artifact
    base = "urn:agrag:schema:odd%20schema:"
    graph = {item["@id"]: item for item in artifact["@graph"]}
    assert graph[base + "ChildType"]["rdfs:subClassOf"] == {"@id": base + "ParentType"}
    assert graph[base + "ParentType%2Fcode"]["rdfs:range"] == {"@id": "xsd:string"}
    assert graph[base + "ChildType%2Fcode"]["rdfs:range"] == {"@id": "xsd:integer"}
    assert graph[base + "ChildType%2Fcode"]["agrag:required"] == {
        "@value": True,
        "@type": "xsd:boolean",
    }
    assert graph[base + "ParentType%2Fcode"]["agrag:enum"] == [
        {"@value": "a"},
        {"@value": "b"},
    ]
    assert graph[base + "ParentType%2Fweb%20address"]["rdfs:label"] == {
        "@value": "web address"
    }
    relation = graph[base + "LINK_TYPE"]
    assert relation["@type"] == [
        "owl:ObjectProperty",
        "owl:FunctionalProperty",
        "owl:InverseFunctionalProperty",
    ]
    assert relation["agrag:patterns"] == [
        {"@value": '["ChildType","Target"]'},
        {"@value": '["ParentType","Target"]'},
    ]
    assert relation["rdfs:domain"] == {
        "@type": "owl:Class",
        "owl:unionOf": {
            "@list": [{"@id": base + "ChildType"}, {"@id": base + "ParentType"}]
        },
    }
    assert relation["rdfs:range"] == {"@id": base + "Target"}
    empty_schema = GraphSchema(
        name="empty",
        version="1",
        entities=schema.entities,
        relations=[
            RelationType(
                label="UNSPECIFIED",
                description="A relation without endpoint patterns.",
                patterns=[],
                symmetric=True,
                cardinality=Cardinality(max_per_source=2, max_per_target=2),
            )
        ],
    )
    unspecified = {item["@id"]: item for item in to_jsonld(empty_schema)["@graph"]}[
        "urn:agrag:schema:empty:UNSPECIFIED"
    ]
    assert "rdfs:domain" not in unspecified
    assert "rdfs:range" not in unspecified
    assert unspecified["@type"] == ["owl:ObjectProperty"]
    assert unspecified["agrag:symmetric"] == {
        "@value": True,
        "@type": "xsd:boolean",
    }
    assert unspecified["agrag:maxPerSource"] == {
        "@value": 2,
        "@type": "xsd:integer",
    }

    custom = to_jsonld(schema, base_iri="https://example.test/vocab/")
    assert custom["@graph"][0]["@id"] == "https://example.test/vocab/ParentType"
