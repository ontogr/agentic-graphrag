"""Tests for identity resolution: resolve_entity."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from agrag.retrieval.identity import MAX_MERGE_HOPS, resolve_entity


def _row(entity_id: UUID, *, merged_into: UUID | None = None) -> dict:
    """Build a resolve_merged_into_query row for one node."""
    return {
        "node": {
            "id": str(entity_id),
            "labels": ["Person"],
            "properties": {
                "name": "Alice",
                "merge_key": "Person:alice",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
            },
        },
        "merged_into": str(merged_into) if merged_into else None,
    }


class TestResolveEntity:
    """resolve_entity follows merged_into chains."""

    async def test_raises_for_missing_entity(self) -> None:
        """Missing entity raises ValueError."""
        gs = AsyncMock()
        gs.execute_read.return_value = []

        with pytest.raises(ValueError, match="not found"):
            await resolve_entity(gs, uuid4())

    async def test_returns_live_entity_directly(self) -> None:
        """Live entity (no tombstone) is returned in one query."""
        ent_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.return_value = [_row(ent_id)]

        entity = await resolve_entity(gs, ent_id)

        assert entity.id == ent_id
        assert entity.name == "Alice"
        assert gs.execute_read.await_count == 1

    async def test_follows_merged_into_property_chain(self) -> None:
        """A multi-hop tombstone chain resolves to the survivor."""
        survivor_id = uuid4()
        middle_id = uuid4()
        tombstone_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_row(tombstone_id, merged_into=middle_id)],
            [_row(middle_id, merged_into=survivor_id)],
            [_row(survivor_id)],
        ]

        entity = await resolve_entity(gs, tombstone_id)

        assert entity.id == survivor_id

    async def test_raises_when_chain_target_is_missing(self) -> None:
        """A merged_into pointer to a missing node raises."""
        tombstone_id = uuid4()
        survivor_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_row(tombstone_id, merged_into=survivor_id)],
            [],
        ]

        with pytest.raises(ValueError, match="not found"):
            await resolve_entity(gs, tombstone_id)

    async def test_raises_on_cycle(self) -> None:
        """A merged_into cycle raises instead of looping forever."""
        first_id = uuid4()
        second_id = uuid4()
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_row(first_id, merged_into=second_id)],
            [_row(second_id, merged_into=first_id)],
        ]

        with pytest.raises(ValueError, match="cycles"):
            await resolve_entity(gs, first_id)

    async def test_raises_when_chain_exceeds_max_hops(self) -> None:
        """A chain longer than MAX_MERGE_HOPS raises."""
        ids = [uuid4() for _ in range(MAX_MERGE_HOPS + 2)]
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_row(current, merged_into=nxt)]
            for current, nxt in zip(ids, ids[1:], strict=False)
        ]

        with pytest.raises(ValueError, match="longer than"):
            await resolve_entity(gs, ids[0])
