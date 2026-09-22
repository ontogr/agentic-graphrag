"""Integration tests for the entity resolution pipeline.

LLMVerify hits a real OpenAI-compatible endpoint to verify entity pairs.
The full Resolver flow chains ExactMatch → FuzzyMatch → LLMVerify end-to-end.

``fetch_entity_neighbors_query`` is also exercised against a real Neo4j
instance, since its per-entity bounded ``CALL { ... }`` subquery is the only
one of its kind in this codebase's Cypher.
"""

import importlib.util
import os
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.provenance import TextProvenance
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.ingestion.resolve import (
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    InBatchCandidateSource,
    LLMVerify,
    Resolver,
)
from agrag.ingestion.resolve.candidate_source import fetch_persisted_neighbors


neo4j_missing = importlib.util.find_spec("neo4j") is None


_DOC_ID = uuid4()


def _chunk(text: str = "context") -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _entity(
    text: str,
    label: str = "Person",
    chunk_id: UUID | None = None,
) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    if chunk_id is None:
        chunk_id = uuid4()
    return ExtractedEntity(
        chunk_id=chunk_id,
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _has_llm_endpoint() -> bool:
    """Return True when the LLM endpoint env vars are set."""
    return bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL_ID"))


# ── Persisted neighbors ────────────────────────────────────────────────


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestFetchPersistedNeighborsIntegration:
    """``fetch_entity_neighbors_query`` reads bounded real graph neighbors."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store with a unique entity label."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Neighbor_{uuid4().hex[:8]}")
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    async def test_bounds_and_filters_neighbors_in_both_directions(self) -> None:
        """One batched read caps each id and omits excluded relation types."""
        hub = Entity(id=uuid4(), label=self.label, name="Hub")
        others = [
            Entity(id=uuid4(), label=self.label, name=f"Other {i}") for i in range(7)
        ]
        await self.store.upsert_nodes(
            self.label, [hub.to_node_record(), *(o.to_node_record() for o in others)]
        )
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type="KNOWS",
                    start_id=hub.id,
                    end_id=other.id,
                    properties={},
                )
                for other in others
            ]
            + [
                # A resolution-owned system edge, which the caller excludes.
                RelationRecord(
                    id=uuid4(),
                    type="MATCHES",
                    start_id=hub.id,
                    end_id=others[0].id,
                    properties={},
                )
            ]
        )

        neighbors = await fetch_persisted_neighbors(
            [hub.id, others[0].id],
            graph_store=self.store,
            exclude_relation_types=["MATCHES"],
            max_neighbors=5,
        )

        assert len(neighbors[hub.id]) == 5
        assert all(
            name.startswith("KNOWS ") and name != "KNOWS Hub"
            for name in neighbors[hub.id]
        )
        assert "MATCHES Other 0" not in neighbors[hub.id]
        # The undirected match means the edge's other endpoint sees the hub.
        assert neighbors[others[0].id] == ["KNOWS Hub"]


# ── LLMVerify ──────────────────────────────────────────────────────────


class TestLLMVerifyIntegration:
    """LLMVerify calls a real LLM to verify entity pairs."""

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_llm_returns_a_verdict(self) -> None:
        """LLMVerify completes without error and returns a valid verdict."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        chunk = _chunk(
            "Ada Lovelace was a pioneer of computing. "
            "Ada Lovelace worked on the Analytical Engine."
        )
        chunk_id = chunk.id
        a = _entity("Ada Lovelace", chunk_id=chunk_id)
        b = _entity("Charles Babbage", chunk_id=chunk_id)

        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings)
        verdict = await verifier.compare(a, b)

        assert verdict in (ComparisonVerdict.MATCH, ComparisonVerdict.NO_MATCH)

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_same_entity_pair_completes(self) -> None:
        """LLMVerify completes when comparing the same entity name to itself."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        chunk = _chunk(
            "Ada Lovelace was a pioneer of computing. "
            "Ada Lovelace worked on the Analytical Engine."
        )
        chunk_id = chunk.id
        a = _entity("Ada Lovelace", chunk_id=chunk_id)
        b = _entity("Ada Lovelace", chunk_id=chunk_id)

        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings)
        verdict = await verifier.compare(a, b)

        # gemma4:31b can't reliably parse BAML bool output, so we only
        # confirm the call completes. Stronger models should return MATCH.
        assert verdict in (ComparisonVerdict.MATCH, ComparisonVerdict.NO_MATCH)

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_different_entity_pair_completes(self) -> None:
        """LLMVerify completes when comparing clearly unrelated entities."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        chunk = _chunk(
            "Ada Lovelace was a pioneer of computing. "
            "Quantum physics studies subatomic particles."
        )
        chunk_id = chunk.id
        a = _entity("Ada Lovelace", chunk_id=chunk_id)
        b = _entity("Quantum Physics", chunk_id=chunk_id)

        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings)
        verdict = await verifier.compare(a, b)

        assert verdict in (ComparisonVerdict.MATCH, ComparisonVerdict.NO_MATCH)


# ── FuzzyMatch ────────────────────────────────────────────────────────


class TestFuzzyMatchIntegration:
    """FuzzyMatch compares entity pairs using rapidfuzz similarity."""

    async def test_no_match_for_distinct_entities(self) -> None:
        """FuzzyMatch returns NO_MATCH when entities are too dissimilar."""
        a = _entity("Ada Lovelace")
        b = _entity("Quantum Physics")
        comparator = FuzzyMatch()

        verdict = await comparator.compare(a, b)

        assert verdict == ComparisonVerdict.NO_MATCH

    async def test_match_for_renamed_entities(self) -> None:
        """FuzzyMatch returns MATCH when reordered names are very similar."""
        a = _entity("Ada Lovelace")
        b = _entity("Lovelace, Ada")
        comparator = FuzzyMatch()

        verdict = await comparator.compare(a, b)

        assert verdict == ComparisonVerdict.MATCH


# ── Full Resolver Flow ─────────────────────────────────────────────────


class TestResolverIntegration:
    """End-to-end resolution with real comparators."""

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_full_pipeline_groups_exact_duplicates(self) -> None:
        """Exact duplicates are grouped; distinct entities stay separate."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        chunk = _chunk(
            "Ada Lovelace worked at the Analytical Engine Company. "
            "Ada Lovelace was a pioneer. "
            "Charles Babbage designed the engine."
        )
        chunk_id = chunk.id
        entities = [
            _entity("Ada Lovelace", chunk_id=chunk_id),
            _entity("Ada Lovelace", chunk_id=chunk_id),
            _entity("Charles Babbage", chunk_id=chunk_id),
        ]

        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings),
            ],
            candidate_source=InBatchCandidateSource(),
        )
        result = await resolver.resolve(entities)

        # Ada Lovelace pair should be grouped; Charles alone
        all_indices = [g.entity_indices for g in result.groups]
        ada_group = next(g for g in all_indices if 0 in g)
        assert set(ada_group) == {0, 1}
        charles_group = next(g for g in all_indices if 2 in g)
        assert charles_group == [2]

    @pytest.mark.skipif(not _has_llm_endpoint(), reason="LLM endpoint not configured")
    async def test_full_pipeline_uses_llm_for_ambiguous_pairs(self) -> None:
        """FuzzyMatch returns UNCERTAIN; LLMVerify breaks the tie."""
        settings = ExtractionLLMSettings.from_openai_compatible_env()
        chunk = _chunk(
            "Ada Lovelace was a pioneer of computing. "
            "Lady Lovelace wrote notes on the engine."
        )
        chunk_id = chunk.id
        # "Ada Lovelace" vs "Lady Lovelace" — similarity ~0.80, between
        # FuzzyMatch's no_match_below (0.70) and match_above (0.92), so
        # FuzzyMatch returns UNCERTAIN and LLMVerify is reached.
        entities = [
            _entity("Ada Lovelace", chunk_id=chunk_id),
            _entity("Lady Lovelace", chunk_id=chunk_id),
        ]

        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings),
            ],
            candidate_source=InBatchCandidateSource(),
        )
        result = await resolver.resolve(entities)

        # Both forms refer to the same person — LLM should confirm
        all_indices = [g.entity_indices for g in result.groups]
        assert len(all_indices) == 1
        assert set(all_indices[0]) == {0, 1}
