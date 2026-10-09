"""Tests for resolving mentions and persisted entities without a Graph."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.resolution import (
    _synthesize_mentions,
    find_exact_matches,
    resolve_among,
    resolve_batch,
)
from agrag.loaders.types import ErrorPolicy


class _Embedder:
    """Embedder double that gives every text the same vector."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a fixed vector."""
        return [0.1, 0.2]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one fixed vector per text."""
        return [[0.1, 0.2] for _ in texts]


def _mention(text: str, label: str = "Person") -> ExtractedEntity:
    """Build a mention for resolution tests."""
    return ExtractedEntity(
        chunk_id=uuid4(), label=label, text=text, char_start=0, char_end=len(text)
    )


def _node(entity_id: object, name: str, merge_key: str) -> dict[str, object]:
    """Build the node payload a merge-key read returns."""
    return {
        "id": str(entity_id),
        "name": name,
        "merge_key": merge_key,
        "merge_count": 1,
        "source_chunk_ids": [],
        "created_at": "2020-01-01T00:00:00+00:00",
    }


class TestFindExactMatches:
    """Persisted exact matches map back to mention indices."""

    async def test_empty_mentions_do_not_read(self) -> None:
        """No mentions means no store read."""
        store = AsyncMock()

        assert await find_exact_matches([], graph_store=store) == {}
        store.execute_read.assert_not_called()

    async def test_groups_by_label_and_dedups(self) -> None:
        """One query per distinct label, deduped keys."""
        store = AsyncMock()
        entity_id = uuid4()
        store.execute_read.side_effect = [
            [{"n": _node(entity_id, "Alice", "Person:alice")}],
            [],
        ]

        result = await find_exact_matches(
            [_mention("Alice"), _mention("alice"), _mention("Acme", "Organization")],
            graph_store=store,
        )

        assert result[0].id == entity_id
        assert result[1].id == entity_id
        assert 2 not in result
        assert store.execute_read.call_count == 2

    async def test_accepted_alias_with_different_name_resolves_to_entity(self) -> None:
        """A mention resolves through the merge key its alias was queried on.

        An alias for "Person:bob" can point at an entity now named "Robert".
        Re-deriving the key from that name would not map "Bob" back.
        """
        store = AsyncMock()
        entity_id = uuid4()
        store.execute_read.side_effect = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": _node(entity_id, "Robert", "Person:robert"),
                }
            ]
        ]

        result = await find_exact_matches([_mention("Bob")], graph_store=store)

        assert result[0].id == entity_id
        assert result[0].name == "Robert"

    async def test_skips_unparsable_rows(self) -> None:
        """A row whose node is not a valid entity is skipped."""
        store = AsyncMock()
        entity_id = uuid4()
        store.execute_read.side_effect = [
            [
                {"n": _node(entity_id, "Bob", "Person:bob")},
                {"n": {"id": "bad"}},
            ]
        ]

        result = await find_exact_matches([_mention("Bob")], graph_store=store)

        assert set(result) == {0}


class TestSynthesizeMentions:
    """Persisted entities get independent mention context."""

    def test_shared_source_chunk_does_not_cross_contaminate_context(self) -> None:
        """Two entities sharing a first source chunk keep their own context."""
        shared_chunk_id = uuid4()
        alice = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[shared_chunk_id],
        )
        bob = Entity(
            id=uuid4(),
            label="Person",
            name="Bob",
            properties={},
            source_chunk_ids=[shared_chunk_id],
        )

        mentions, chunks_by_id = _synthesize_mentions([alice, bob])

        assert mentions[0].chunk_id != mentions[1].chunk_id
        assert chunks_by_id[mentions[0].chunk_id].text == "Alice"
        assert chunks_by_id[mentions[1].chunk_id].text == "Bob"


class TestResolveAmong:
    """A fixed entity set resolves without reading the store."""

    async def test_matches_same_label_names_only(self) -> None:
        """Names that differ only by case match; other labels never pair."""
        ada = Entity(id=uuid4(), label="Person", name="Ada")
        ada_lower = Entity(id=uuid4(), label="Person", name="ada")
        org = Entity(id=uuid4(), label="Organization", name="Ada")

        result = await resolve_among(
            [ada, ada_lower, org], embedder=_Embedder(), tracer=None, max_llm_pairs=0
        )

        groups = [set(group.entity_indices) for group in result.groups]
        assert {0, 1} in groups
        assert {2} in groups


class TestResolveBatch:
    """A batch resolves against its own mentions and persisted candidates."""

    async def test_empty_batch_has_no_resolver_result(self) -> None:
        """No mentions yields no groups and no resolver pass."""
        store = AsyncMock()

        batch = await resolve_batch(
            [],
            [],
            {},
            graph_store=store,
            embedder=_Embedder(),
            vector_store=None,
            vector_collection="",
            entity_labels=["Person"],
            tracer=None,
            max_llm_pairs=0,
            error_policy=ErrorPolicy.RAISE,
        )

        assert batch.result is None
        assert batch.groups == []
        store.execute_read.assert_not_called()

    async def test_exact_match_is_not_a_synthetic_candidate(self) -> None:
        """The persisted entity a mention matches exactly is not re-compared."""
        store = AsyncMock()
        exact_id, other_id = uuid4(), uuid4()
        store.execute_read.side_effect = [
            [{"n": _node(exact_id, "Ada", "Person:ada")}],
            [],
        ]
        hits = [
            VectorHit(
                id=exact_id,
                score=0.99,
                payload={"id": str(exact_id), "label": "Person", "name": "Ada"},
            ),
            VectorHit(
                id=other_id,
                score=0.8,
                payload={"id": str(other_id), "label": "Person", "name": "Ada L."},
            ),
        ]

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new=AsyncMock(return_value=hits),
        ):
            batch = await resolve_batch(
                [_mention("Ada")],
                [],
                {},
                graph_store=store,
                embedder=_Embedder(),
                vector_store=None,
                vector_collection="",
                entity_labels=["Person"],
                tracer=None,
                max_llm_pairs=0,
                error_policy=ErrorPolicy.RAISE,
            )

        assert batch.exact_matches[0].id == exact_id
        assert list(batch.persisted_ids.values()) == [other_id]
        assert set(batch.candidate_entities) == {other_id}

    async def test_failed_candidate_read_leaves_the_mention_unresolved(self) -> None:
        """A mention whose read failed is reported and compared with no peer."""
        store = AsyncMock()
        store.execute_read.return_value = []
        mentions = [_mention("Ada"), _mention("Ada L.")]

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new=AsyncMock(side_effect=[RuntimeError("vector store down"), []]),
        ):
            batch = await resolve_batch(
                mentions,
                [],
                {},
                graph_store=store,
                embedder=_Embedder(),
                vector_store=None,
                vector_collection="",
                entity_labels=["Person"],
                tracer=None,
                max_llm_pairs=0,
                error_policy=ErrorPolicy.SKIP,
            )

        assert batch.unresolved_indices == {0}
        assert len(batch.failures) == 1
        assert batch.result is not None
        assert all(
            0 not in group.entity_indices or len(group.entity_indices) == 1
            for group in batch.result.groups
        )
