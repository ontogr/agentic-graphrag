"""Tests for entity-resolution support primitives."""

from uuid import uuid4

import numpy as np
import pytest

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.cypher.resolution_read import (
    fetch_matches_for_component_query,
    fetch_resolved_entity_members_query,
)
from agrag.cypher.resolution_write import (
    deactivate_match_query,
    delete_resolved_as_query,
    upsert_matches_query,
    upsert_resolved_as_query,
)
from agrag.ingestion._clustering import average_linkage_clusters
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.resolve.zone_classifier import ComparisonZone, classify_zone


class TestResolutionSupport:
    """Small pure resolution support units."""

    @pytest.mark.parametrize(
        ("fuzzy_score", "embedding_similarity", "expected"),
        [
            (0.97, None, ComparisonZone.HARD_MERGE),
            (None, 0.95, ComparisonZone.HARD_MERGE),
            (None, 0.80, ComparisonZone.AMBIGUOUS),
            (None, 0.79, ComparisonZone.DISCARD),
        ],
    )
    def test_classifies_similarity_zones(
        self, fuzzy_score, embedding_similarity, expected
    ) -> None:
        """Thresholds select the documented resolution zone."""
        assert (
            classify_zone(
                fuzzy_score=fuzzy_score, embedding_similarity=embedding_similarity
            )
            == expected
        )

    def test_requires_embedding_without_fast_path(self) -> None:
        """A non-fast-path comparison needs an embedding score."""
        with pytest.raises(ValueError):
            classify_zone()

    def test_clusters_tight_members(self) -> None:
        """Average linkage joins a tight cluster."""
        ids = [uuid4(), uuid4()]
        assert average_linkage_clusters(
            ids, np.array([[0.0, 0.1], [0.1, 0.0]]), cut_distance=0.2
        ) == [ids]

    def test_rejects_invalid_cluster_matrix(self) -> None:
        """Clustering rejects dimensions that do not match member ids."""
        with pytest.raises(ValueError):
            average_linkage_clusters(
                [uuid4(), uuid4()], np.zeros((1, 1)), cut_distance=0.2
            )

    async def test_blocks_candidates_by_label(self) -> None:
        """In-batch candidates only include mentions with the same label."""
        source = GraphCandidateSource(graph_store=None, embedder=None)  # type: ignore[arg-type]
        chunk_id = uuid4()
        mentions = [
            ExtractedEntity(
                chunk_id=chunk_id, label="Person", text="Ada", char_start=0, char_end=3
            ),
            ExtractedEntity(
                chunk_id=chunk_id,
                label="Place",
                text="London",
                char_start=0,
                char_end=6,
            ),
            ExtractedEntity(
                chunk_id=chunk_id,
                label="Person",
                text="Grace",
                char_start=0,
                char_end=5,
            ),
        ]
        assert await source.candidates_for(0, mentions) == [2]

    def test_builds_resolution_queries(self) -> None:
        """Resolution query builders produce the required relationship operations."""
        queries = [
            upsert_matches_query(),
            deactivate_match_query(),
            upsert_resolved_as_query(),
            delete_resolved_as_query(),
            fetch_matches_for_component_query(),
            fetch_resolved_entity_members_query(),
        ]
        assert all("MATCH" in query for query in queries)

    def test_serializes_resolved_entity(self) -> None:
        """Resolved entities retain member ids in graph records."""
        member_id = uuid4()
        entity = ResolvedEntity(
            id=uuid4(), label="Person", name="Ada", member_ids=[member_id]
        )
        assert entity.to_node_record().properties["member_ids"] == [str(member_id)]
