"""Tests for node_params in agrag.graphdb.serialize.

Covers converting NodeRecord UUID fields (including a nested UUID inside a
node's properties) to strings for the Neo4j driver, while
leaving other scalar property values unchanged.
"""

from uuid import uuid4

from agrag.common.data_models.graph_record import NodeRecord
from agrag.graphdb.serialize import node_params


def test_node_params_converts_uuid_and_nested() -> None:
    """UUIDs and nested UUIDs become strings; scalars pass through."""
    rid = uuid4()
    rec = NodeRecord(
        id=rid,
        labels=["Chunk"],
        properties={"embedding_owner": uuid4(), "n": 1},
    )
    params = node_params(rec)
    assert params["id"] == str(rid)
    assert params["properties"]["embedding_owner"] == str(
        rec.properties["embedding_owner"]
    )
    assert params["properties"]["n"] == 1
