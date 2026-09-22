"""Tests for node_params and relation_params in agrag.graphdb.serialize.

Covers converting NodeRecord/RelationRecord UUID fields (including a nested
UUID inside a node's properties) to strings for the Neo4j driver, while
leaving other scalar property values unchanged.
"""

from uuid import uuid4

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.graphdb.serialize import node_params, relation_params


def test_node_params_splits_out_the_pending_tag() -> None:
    """The Cutover Job tag rides its own key, out of the applied properties.

    It reaches the graph only through the upsert's ``ON CREATE SET``, so a
    job cannot tag a node it merely writes over.
    """
    rec = NodeRecord(
        id=uuid4(),
        labels=["Chunk"],
        properties={"text": "a", "_pending_job_id": "job-1"},
    )

    params = node_params(rec)

    assert params["properties"] == {"text": "a"}
    assert params["pending_job_id"] == "job-1"


def test_node_params_converts_a_uuid_pending_tag() -> None:
    """The separate Cutover Job tag is converted for the Neo4j driver."""
    job_id = uuid4()
    rec = NodeRecord(
        id=uuid4(),
        labels=["Chunk"],
        properties={"_pending_job_id": job_id},
    )

    assert node_params(rec)["pending_job_id"] == str(job_id)


def test_relation_params_splits_out_the_pending_tag() -> None:
    """An edge carries its tag on the same separate key."""
    rec = RelationRecord(
        id=uuid4(),
        type="MENTIONS",
        start_id=uuid4(),
        end_id=uuid4(),
        properties={"w": 0.5, "_pending_job_id": "job-1"},
    )

    params = relation_params(rec)

    assert params["properties"] == {"w": 0.5}
    assert params["pending_job_id"] == "job-1"


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
        "pending_job_id": None,
    }
