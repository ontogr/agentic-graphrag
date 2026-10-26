"""Tests for fetch_relation_edges weight and pagination."""

from unittest.mock import AsyncMock

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.ingestion.community import fetch_relation_edges


def _schema() -> GraphSchema:
    """Return a schema for the relation types returned by these test pages."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label="Entity", description="test entity")],
        relations=[
            RelationType(
                label=relation_type,
                description="test relation",
                patterns=[("Entity", "Entity")],
            )
            for relation_type in ("KNOWS", "WORKS_WITH")
        ],
    )


class TestFetchRelationEdges:
    """fetch_relation_edges weight and pagination."""

    async def test_weight_attestation_and_fallback(self) -> None:
        """Weight is len(source_chunk_ids); an unattested relation weighs 0.0."""
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = [
            {
                "source_id": "a",
                "target_id": "b",
                "source_chunk_ids": ["x", "y"],
                "rel_type": "KNOWS",
                "rel_id": "r1",
            },
            {
                "source_id": "c",
                "target_id": "d",
                "source_chunk_ids": [],
                "rel_type": "KNOWS",
                "rel_id": "r2",
            },
        ]
        edges = await fetch_relation_edges(mock_store, schema=_schema(), page_size=10)
        assert edges[0][2] == 2.0
        assert edges[1][2] == 0.0

    async def test_pagination_resumes_past_shared_endpoint_group(self) -> None:
        """A page boundary inside a same-(a,b) group still yields every row.

        Regression test: the cursor used to advance only by
        (source_id, target_id), so a page ending mid-group silently
        excluded the remaining parallel relations between that pair.
        """
        mock_store = AsyncMock()
        mock_store.execute_read.side_effect = [
            [
                {
                    "source_id": "a",
                    "target_id": "b",
                    "source_chunk_ids": ["x"],
                    "rel_type": "KNOWS",
                    "rel_id": "r1",
                }
            ],
            [
                {
                    "source_id": "a",
                    "target_id": "b",
                    "source_chunk_ids": ["y"],
                    "rel_type": "WORKS_WITH",
                    "rel_id": "r2",
                }
            ],
            [],
        ]
        edges = await fetch_relation_edges(mock_store, schema=_schema(), page_size=1)
        assert len(edges) == 2
        second_call_params = mock_store.execute_read.call_args_list[1].args[1]
        assert second_call_params["last_a"] == "a"
        assert second_call_params["last_b"] == "b"
        assert second_call_params["last_type"] == "KNOWS"
        assert second_call_params["last_rel_id"] == "r1"
