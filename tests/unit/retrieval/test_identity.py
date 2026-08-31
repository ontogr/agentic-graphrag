"""Tests for identity resolution: resolve_entity."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.retrieval.identity import resolve_entity


class TestResolveEntity:
    """resolve_entity follows merged_into chains."""

    async def test_raises_for_missing_entity(self) -> None:
        """Missing entity raises ValueError."""
        gs = AsyncMock()
        gs.execute_read.return_value = []

        with pytest.raises(ValueError, match="not found"):
            await resolve_entity(gs, uuid4())

    async def test_returns_live_entity_directly(self) -> None:
        """Live entity (no tombstone) is returned directly."""
        ent_id = uuid4()
        gs = AsyncMock()
        # First call: resolve_merged_into_query returns no live node
        # (zero hops). Second call: direct fetch returns the entity.
        gs.execute_read.side_effect = [
            [],  # resolve_merged_into returns empty
            [
                {
                    "n": {
                        "id": str(ent_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Alice",
                            "merge_key": "Person:alice",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                        },
                    }
                }
            ],
        ]

        entity = await resolve_entity(gs, ent_id)
        assert entity.id == ent_id
        assert entity.name == "Alice"

    async def test_follows_merged_into_chain(self) -> None:
        """Tombstone chain is followed to the live survivor."""
        survivor_id = uuid4()
        tombstone_id = uuid4()
        gs = AsyncMock()

        # First call: resolve_merged_into_query finds the survivor.
        gs.execute_read.side_effect = [
            [
                {
                    "live": {
                        "id": str(survivor_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Alice",
                            "merge_key": "Person:alice",
                            "merged_from": [str(tombstone_id)],
                            "merge_count": 2,
                            "source_chunk_ids": [],
                        },
                    }
                }
            ],
        ]

        entity = await resolve_entity(gs, tombstone_id)
        assert entity.id == survivor_id
        assert entity.name == "Alice"
