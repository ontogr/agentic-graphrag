"""Tests for the entity merge stage of one ingestion batch."""

from collections.abc import Iterator
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_schema import GENERIC
from agrag.ingestion import _merge_stage
from agrag.ingestion._merge_stage import merge_stage
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion.merge import ConflictRecord
from agrag.ingestion.merge import relation_id as domain_relation_id
from agrag.ingestion.resolve.resolution import BatchResolution
from agrag.ingestion.resolve.resolver import ResolutionGroup
from agrag.loaders.types import ErrorPolicy
from agrag.observability import get_tracer


def _mention(text: str, *, chunk_id: UUID | None = None) -> ExtractedEntity:
    return ExtractedEntity(
        chunk_id=chunk_id or uuid4(),
        label="Organization",
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _existing(name: str, *, entity_id: UUID | None = None) -> Entity:
    return Entity(id=entity_id or uuid4(), label="Organization", name=name)


def _batch(
    groups: list[list[int]], *, exact_matches: dict[int, Entity] | None = None
) -> BatchResolution:
    return BatchResolution(
        exact_matches=exact_matches or {},
        groups=[ResolutionGroup(entity_indices=indices) for indices in groups],
        result=None,
    )


def _store(relation_rows: list[dict[str, Any]] | None = None) -> AsyncMock:
    """Build a store whose relation lookup returns rows for WORKS_AT only."""
    rows = relation_rows or []
    store = AsyncMock()
    store.execute_read.side_effect = lambda query, _params: (
        rows if "WORKS_AT" in query else []
    )
    return store


def _failing_relation_store(error: Exception) -> AsyncMock:
    """Build a store whose relation read raises for WORKS_AT and returns no rows."""
    store = AsyncMock()

    async def _read(query: str, _params: Any) -> list[dict[str, Any]]:
        if "WORKS_AT" in query:
            raise error
        return []

    store.execute_read.side_effect = _read
    return store


async def _merge(
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    batch: BatchResolution,
    store: AsyncMock,
    *,
    error_policy: ErrorPolicy = ErrorPolicy.SKIP,
) -> Any:
    ctx = StageContext(
        graph_store=store,
        embedder=AsyncMock(),
        vector_store=None,
        error_policy=error_policy,
        tracer=get_tracer(None),
        job_id=None,
    )
    return await merge_stage(
        entities,
        relations,
        batch,
        ctx,
        graph_schema=GENERIC,
        resolved_entity_collection="resolved_entities",
        rebuilt_components=None,
    )


def _compute_merge_with_conflict() -> Any:
    real_compute = _merge_stage.compute_merge

    async def _compute(**kwargs: Any) -> Any:
        plan, failures = await real_compute(**kwargs)
        conflict = ConflictRecord(field="name", candidates=["A", "B"], resolved="A")
        return plan.model_copy(update={"conflicts": [conflict]}), failures

    return mock.patch.object(_merge_stage, "compute_merge", side_effect=_compute)


@pytest.fixture
def _no_writes() -> Iterator[AsyncMock]:
    with mock.patch.object(_merge_stage, "apply_merge", new_callable=AsyncMock) as fake:
        yield fake


def _compute_merge_failing_on(text: str) -> Any:
    real_compute = _merge_stage.compute_merge

    async def _compute(**kwargs: Any) -> Any:
        if kwargs["mentions"][0].text == text:
            raise RuntimeError(f"merge of {text} failed")
        return await real_compute(**kwargs)

    return mock.patch.object(_merge_stage, "compute_merge", side_effect=_compute)


@pytest.mark.usefixtures("_no_writes")
class TestMergeStage:
    """Merging resolved mentions into survivors and relation records."""

    async def test_counts_groups_that_create_or_update_an_entity(self) -> None:
        """A group with no persisted match creates an entity, else it updates one."""
        entities = [_mention("Alice"), _mention("Acme")]
        batch = _batch([[0], [1]], exact_matches={1: _existing("Acme")})

        result = await _merge(entities, [], batch, _store())

        assert result.stats.nodes_created == 1
        assert result.stats.nodes_updated == 1
        assert {entity.name for entity in result.survivors.values()} == {
            "Alice",
            "Acme",
        }

    async def test_records_failed_group_and_merges_the_rest_under_skip(self) -> None:
        """A failed group is recorded by its mention text and the rest merge."""
        entities = [_mention("Alice"), _mention("Acme")]
        batch = _batch([[0], [1]])

        with _compute_merge_failing_on("Acme"):
            result = await _merge(entities, [], batch, _store())

        assert [failure.item_id for failure in result.stats.failures] == ["Acme"]
        assert [failure.error_type for failure in result.stats.failures] == [
            "RuntimeError"
        ]
        assert [entity.name for entity in result.survivors.values()] == ["Alice"]
        assert result.stats.nodes_created == 1

    async def test_raises_group_failure_under_raise(self) -> None:
        """Under ErrorPolicy.RAISE a failed group merge propagates."""
        entities = [_mention("Alice"), _mention("Acme")]
        batch = _batch([[0], [1]])

        with (
            _compute_merge_failing_on("Acme"),
            pytest.raises(RuntimeError, match="Acme"),
        ):
            await _merge(entities, [], batch, _store(), error_policy=ErrorPolicy.RAISE)

    async def test_unions_chunk_ids_into_existing_relation_and_keeps_its_id(
        self,
    ) -> None:
        """A relation already in the graph keeps its id and gains the new chunk."""
        earlier_chunk, later_chunk = uuid4(), uuid4()
        alice, acme = _existing("Alice"), _existing("Acme")
        relation_id = uuid4()
        store = _store(
            [
                {
                    "id": str(relation_id),
                    "source_id": str(alice.id),
                    "target_id": str(acme.id),
                    "source_chunk_ids": [str(earlier_chunk)],
                }
            ]
        )
        entities = [_mention("Alice"), _mention("Acme")]
        relations = [
            ExtractedRelation(
                chunk_id=later_chunk,
                label="WORKS_AT",
                source_index=0,
                target_index=1,
            )
        ]
        batch = _batch([[0], [1]], exact_matches={0: alice, 1: acme})

        result = await _merge(entities, relations, batch, store)

        [record] = result.relation_records
        assert record.id == relation_id
        assert record.start_id == alice.id
        assert record.end_id == acme.id
        assert record.properties["source_chunk_ids"] == [
            str(earlier_chunk),
            str(later_chunk),
        ]

    async def test_treats_failed_relation_lookup_as_new_under_skip(self) -> None:
        """A failed relation read is recorded and the relation is written as new."""
        chunk_id = uuid4()
        alice, acme = _existing("Alice"), _existing("Acme")
        entities = [_mention("Alice"), _mention("Acme")]
        relations = [
            ExtractedRelation(
                chunk_id=chunk_id, label="WORKS_AT", source_index=0, target_index=1
            )
        ]
        batch = _batch([[0], [1]], exact_matches={0: alice, 1: acme})
        store = _failing_relation_store(RuntimeError("read unavailable"))

        result = await _merge(entities, relations, batch, store)

        [record] = result.relation_records
        assert record.id == domain_relation_id(alice.id, acme.id, "WORKS_AT")
        assert record.properties["source_chunk_ids"] == [str(chunk_id)]
        assert [(f.item_id, f.error_type) for f in result.stats.failures] == [
            ("WORKS_AT", "RuntimeError")
        ]

    async def test_raises_failed_relation_lookup_under_raise(self) -> None:
        """Under ErrorPolicy.RAISE a failed relation read propagates."""
        alice, acme = _existing("Alice"), _existing("Acme")
        entities = [_mention("Alice"), _mention("Acme")]
        relations = [
            ExtractedRelation(
                chunk_id=uuid4(), label="WORKS_AT", source_index=0, target_index=1
            )
        ]
        batch = _batch([[0], [1]], exact_matches={0: alice, 1: acme})
        store = _failing_relation_store(RuntimeError("read unavailable"))

        with pytest.raises(RuntimeError, match="read unavailable"):
            await _merge(
                entities,
                relations,
                batch,
                store,
                error_policy=ErrorPolicy.RAISE,
            )

    async def test_failed_apply_merge_counts_no_merged_entity_or_conflict(
        self, _no_writes: AsyncMock
    ) -> None:
        """A group whose transaction fails is recorded but not counted as merged."""
        entities = [_mention("Acme")]
        batch = _batch([[0]])
        _no_writes.side_effect = RuntimeError("commit failed")

        with _compute_merge_with_conflict():
            result = await _merge(entities, [], batch, _store())

        assert result.stats.nodes_created == 0
        assert result.stats.nodes_updated == 0
        assert result.stats.conflicts_resolved == 0
        assert result.survivors == {}
        assert [failure.error_type for failure in result.stats.failures] == [
            "RuntimeError"
        ]

    async def test_drops_relation_whose_endpoints_merge_into_one_entity(self) -> None:
        """A relation between two mentions of one entity is dropped as a self-loop."""
        entities = [_mention("Alice"), _mention("Alice")]
        relations = [
            ExtractedRelation(
                chunk_id=uuid4(), label="KNOWS", source_index=0, target_index=1
            )
        ]
        batch = _batch([[0, 1]])

        result = await _merge(entities, relations, batch, _store())

        assert result.relation_records == []
        assert len(result.mentioned_in_records) == 2
