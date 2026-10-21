"""Tests for resolving mentions and persisted entities without a Graph."""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import PersistedCandidateSource
from agrag.ingestion.resolve.resolution import (
    _synthesize_mentions,
    find_exact_matches,
    resolve_among,
    resolve_batch,
)
from agrag.ingestion.resolve.resolver import FuzzyMatch, LLMVerify, Resolver
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
            [
                {"n": _node(exact_id, "Ada", "Person:ada")},
                {"n": _node(other_id, "Ada L.", "Person:ada l.")},
            ],
            [],
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


class TestBoundedVerification:
    """Batch completion order must not change merges or hide request failures."""

    async def test_reverse_completion_preserves_order_and_caps_requests(self) -> None:
        """Six independent batches reach the cap and retain selection order."""
        entities, chunks = _synthesize_mentions(
            [
                Entity(id=uuid4(), label="Person", name=name)
                for name in ("A", "B", "C", "D")
            ]
        )
        source = PersistedCandidateSource({0: [1, 2, 3], 1: [2, 3], 2: [3]})
        expected = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        for cap in (1, 3):
            active = peak = 0
            progress = []

            class Client:
                async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                    nonlocal active, peak
                    active += 1
                    peak = max(peak, active)
                    left, right = map(int, pairs[0]["pair_id"].split(":"))
                    await asyncio.sleep(0.03 - expected.index((left, right)) * 0.004)
                    active -= 1
                    return [{"pair_id": pairs[0]["pair_id"], "verdict": "match"}]

            verifier = LLMVerify(chunks_by_id=chunks, client=Client())
            resolver = Resolver(
                comparators=[FuzzyMatch(match_above=1.0), verifier],
                candidate_source=source,
                llm_batch_size=1,
                llm_concurrency=cap,
                on_progress=lambda done, total, elapsed, events=progress: events.append(
                    (done, total)
                ),
            )
            result = await resolver.resolve(entities)
            assert [(m.left_index, m.right_index) for m in result.matches] == expected
            assert peak == cap
            assert progress == [(done, 6) for done in range(7)]
            assert all(m.batch_id is not None for m in result.matches)

    async def test_failed_batch_keeps_other_matches(self) -> None:
        """A failed request is counted once while independent batches survive."""
        entities, chunks = _synthesize_mentions(
            [Entity(id=uuid4(), label="Person", name=name) for name in ("A", "B", "C")]
        )

        class Client:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                if pairs[0]["pair_id"] == "0:2":
                    raise RuntimeError("endpoint failed")
                return [{"pair_id": pairs[0]["pair_id"], "verdict": "match"}]

        resolver = Resolver(
            comparators=[LLMVerify(chunks_by_id=chunks, client=Client())],
            candidate_source=PersistedCandidateSource({0: [1, 2]}),
            llm_batch_size=1,
            llm_concurrency=2,
        )
        result = await resolver.resolve(entities)
        assert result.failed_llm_requests == 1
        assert result.unresolved_pairs == [(0, 2)]
        assert [(m.left_index, m.right_index) for m in result.matches] == [(0, 1)]

    async def test_rejected_pair_cannot_join_through_weaker_match(self) -> None:
        """A rejection constrains the whole group, independent of pair order."""
        entities, chunks = _synthesize_mentions(
            [
                Entity(id=uuid4(), label="Person", name=name)
                for name in ("A", "B", "C", "D")
            ]
        )

        class Client:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                return [
                    {
                        "pair_id": pair["pair_id"],
                        "verdict": "no_match" if pair["pair_id"] == "0:2" else "match",
                        "reasoning": "different"
                        if pair["pair_id"] == "0:2"
                        else "alias",
                    }
                    for pair in pairs
                ]

        for peers in ([1, 2], [2, 1]):
            resolver = Resolver(
                comparators=[LLMVerify(chunks_by_id=chunks, client=Client())],
                candidate_source=PersistedCandidateSource({0: peers, 1: [2]}),
                llm_batch_size=1,
            )
            result = await resolver.resolve(
                entities, similarity_by_pair={(0, 1): 0.94, (1, 2): 0.81}
            )
            assert [g.entity_indices for g in result.groups] == [[0, 1], [2], [3]]
            assert [(m.left_index, m.right_index) for m in result.matches] == [(0, 1)]

    async def test_name_gates_apply_before_fuzzy_and_embedding(self) -> None:
        """Near-identical sentences and conflicting numbers cannot merge."""
        for first, second, allowed in (
            (
                "must return " + "all records " * 20,
                "must retain " + "all records " * 20,
                False,
            ),
            ("clause 4.1", "clause 4.2", False),
            ("three (3) years", "2 years", False),
            ("3 years", "three (3) years", True),
            ("x" * 79 + "a", "x" * 79 + "b", True),
            ("x" * 80 + "a", "x" * 80 + "b", False),
            ("x" * 200, "x" * 200, True),
        ):
            resolver = Resolver(
                comparators=[],
                candidate_source=PersistedCandidateSource({0: [1]}),
                embedder=_Embedder(),
            )
            result = await resolver.resolve([_mention(first), _mention(second)])
            assert [g.entity_indices for g in result.groups] == (
                [[0, 1]] if allowed else [[0], [1]]
            )
            assert result.unresolved_pairs == ([] if allowed else [(0, 1)])
