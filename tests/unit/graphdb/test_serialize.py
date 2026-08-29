"""Tests for graph-record serialization to driver params."""

from uuid import uuid4

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.graphdb.serialize import node_params, relation_params


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


def test_relation_params_converts_ids() -> None:
    """Start, end, and relation ids become strings."""
    rid = uuid4()
    start = uuid4()
    end = uuid4()
    rec = RelationRecord(
        id=rid,
        type="MENTIONS",
        start_id=start,
        end_id=end,
        properties={"w": 0.5},
    )
    params = relation_params(rec)
    assert params == {
        "id": str(rid),
        "start_id": str(start),
        "end_id": str(end),
        "properties": {"w": 0.5},
    }
