"""Tests for the entity resolution pipeline."""

from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import (
    ExtractionLLMSettings,
    ExtractorMissingExtraError,
)
from agrag.ingestion.resolve import (
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    InBatchCandidateSource,
    LLMVerify,
    Resolver,
    _group_matches,
)


_DOC_ID = uuid4()


def _entity(
    text: str, label: str = "Person", chunk_id: UUID | None = None
) -> ExtractedEntity:  # noqa: B008
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


def _chunk(text: str = "context") -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


# ── ExactMatch ─────────────────────────────────────────────────────────


class TestExactMatch:
    """ExactMatch returns MATCH on identical normalized text."""

    async def test_match_on_same_text(self) -> None:
        """Same text returns MATCH."""
        matcher = ExactMatch()
        a = _entity("Ada Lovelace")
        b = _entity("Ada Lovelace")
        assert await matcher.compare(a, b) is ComparisonVerdict.MATCH

    async def test_match_case_insensitive(self) -> None:
        """Case differences are ignored."""
        matcher = ExactMatch()
        a = _entity("ada lovelace")
        b = _entity("Ada Lovelace")
        assert await matcher.compare(a, b) is ComparisonVerdict.MATCH

    async def test_match_with_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        matcher = ExactMatch()
        a = _entity("  Ada  ")
        b = _entity("Ada")
        assert await matcher.compare(a, b) is ComparisonVerdict.MATCH

    async def test_uncertain_on_different_text(self) -> None:
        """Different text returns UNCERTAIN, never NO_MATCH."""
        matcher = ExactMatch()
        a = _entity("Ada")
        b = _entity("Charles")
        assert await matcher.compare(a, b) is ComparisonVerdict.UNCERTAIN

    async def test_never_returns_no_match(self) -> None:
        """ExactMatch never returns NO_MATCH."""
        matcher = ExactMatch()
        pairs = [
            ("Ada", "Charles"),
            ("X", "Y"),
            ("", "something"),
        ]
        for text_a, text_b in pairs:
            verdict = await matcher.compare(_entity(text_a), _entity(text_b))
            assert verdict is not ComparisonVerdict.NO_MATCH


# ── FuzzyMatch ─────────────────────────────────────────────────────────


class TestFuzzyMatch:
    """FuzzyMatch has three verdict bands."""

    async def test_match_above_threshold(self) -> None:
        """High similarity returns MATCH."""
        matcher = FuzzyMatch(match_above=0.92, no_match_below=0.70)
        a = _entity("Apple Inc")
        b = _entity("Apple Inc.")
        assert await matcher.compare(a, b) is ComparisonVerdict.MATCH

    async def test_no_match_below_threshold(self) -> None:
        """Low similarity returns NO_MATCH."""
        matcher = FuzzyMatch(match_above=0.92, no_match_below=0.70)
        a = _entity("Apple")
        b = _entity("Banana")
        assert await matcher.compare(a, b) is ComparisonVerdict.NO_MATCH

    async def test_uncertain_in_band(self) -> None:
        """Medium similarity returns UNCERTAIN."""
        matcher = FuzzyMatch(match_above=0.98, no_match_below=0.50)
        a = _entity("Ada Lovelace")
        b = _entity("Ada Lovelace.")
        verdict = await matcher.compare(a, b)
        # 0.96 score falls between 0.50 and 0.98
        assert verdict is ComparisonVerdict.UNCERTAIN

    async def test_custom_thresholds(self) -> None:
        """Custom thresholds are respected."""
        strict = FuzzyMatch(match_above=0.99, no_match_below=0.98)
        a = _entity("Ada Lovelace")
        b = _entity("Ada Lovelace.")
        # 0.96 score is below 0.98 no_match_below → NO_MATCH
        verdict = await strict.compare(a, b)
        assert verdict is ComparisonVerdict.NO_MATCH


# ── LLMVerify ──────────────────────────────────────────────────────────


class TestLLMVerify:
    """LLMVerify returns NO_MATCH on failure, raises on missing extra."""

    async def test_returns_no_match_on_client_exception(self) -> None:
        """An injected client that raises produces NO_MATCH (fail-safe)."""

        class RaisingClient:
            async def VerifyEntityMatch(self, *args):  # noqa: N802
                raise RuntimeError("LLM call failed")

        chunk = _chunk("context text")
        chunk_id = uuid4()
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Charles", chunk_id=chunk_id)
        settings = ExtractionLLMSettings(clients=[])
        verifier = LLMVerify(
            chunks_by_id={chunk_id: chunk},
            settings=settings,
            client=RaisingClient(),
        )
        verdict = await verifier.compare(a, b)
        assert verdict is ComparisonVerdict.NO_MATCH

    async def test_injected_client_works_without_settings(self) -> None:
        """An injected client works without EXTRACTION_LLM_CLIENTS env vars."""

        class FakeClient:
            async def VerifyEntityMatch(self, *args):  # noqa: N802
                return True

        chunk = _chunk("context text")
        chunk_id = uuid4()
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Ada", chunk_id=chunk_id)
        verifier = LLMVerify(
            chunks_by_id={chunk_id: chunk},
            client=FakeClient(),
        )
        assert verifier.settings is None
        verdict = await verifier.compare(a, b)
        assert verdict is ComparisonVerdict.MATCH

    async def test_raises_when_no_client(self) -> None:
        """Missing llm extra raises ExtractorMissingExtraError."""
        from unittest.mock import patch  # noqa: PLC0415

        settings = ExtractionLLMSettings(clients=[])
        verifier = LLMVerify(chunks_by_id={}, settings=settings)
        verifier._client = None
        with patch.dict("sys.modules", {"agrag.llm.baml_client": None}):
            a = _entity("Ada")
            b = _entity("Charles")
            with pytest.raises(ExtractorMissingExtraError):
                await verifier.compare(a, b)


# ── InBatchCandidateSource ─────────────────────────────────────────────


class TestInBatchCandidateSource:
    """InBatchCandidateSource only proposes same-label pairs."""

    async def test_never_proposes_cross_label(self) -> None:
        """Entities with different labels are never compared."""
        source = InBatchCandidateSource()
        entities = [
            _entity("Ada", label="Person"),
            _entity("Apple", label="Organization"),
            _entity("Charles", label="Person"),
        ]
        candidates = await source.candidates_for(0, entities)
        # Only index 2 (Charles, same label Person) should be proposed
        assert candidates == [2]

    async def test_proposes_all_same_label(self) -> None:
        """All same-label entities are proposed."""
        source = InBatchCandidateSource()
        entities = [
            _entity("Ada", label="Person"),
            _entity("Charles", label="Person"),
            _entity("Grace", label="Person"),
        ]
        candidates = await source.candidates_for(0, entities)
        assert set(candidates) == {1, 2}

    async def test_excludes_self(self) -> None:
        """The entity's own index is never in the candidates."""
        source = InBatchCandidateSource()
        entities = [_entity("Ada", label="Person")]
        candidates = await source.candidates_for(0, entities)
        assert candidates == []


# ── _group_matches (union-find) ────────────────────────────────────────


class TestGroupMatches:
    """_group_matches clusters transitively connected indices."""

    def test_singletons(self) -> None:
        """No edges means every entity is its own group."""
        groups = _group_matches(3, [])
        assert sorted(groups) == [[0], [1], [2]]

    def test_direct_pair(self) -> None:
        """One edge connects two entities."""
        groups = _group_matches(3, [(0, 1)])
        # 0 and 1 in one group, 2 alone
        for group in groups:
            if 0 in group:
                assert 1 in group
            elif 2 in group:
                assert group == [2]

    def test_transitive_closure(self) -> None:
        """A~B and B~C implies one group of three, even without A~C edge."""
        groups = _group_matches(3, [(0, 1), (1, 2)])
        assert len(groups) == 1
        assert sorted(groups[0]) == [0, 1, 2]

    def test_two_clusters(self) -> None:
        """Disconnected subgraphs form separate groups."""
        groups = _group_matches(5, [(0, 1), (3, 4)])
        # Group containing 0,1 and group containing 3,4 and singleton 2
        assert len(groups) == 3
        group_sizes = sorted(len(g) for g in groups)
        assert group_sizes == [1, 2, 2]


# ── Resolver ───────────────────────────────────────────────────────────


class TestResolver:
    """Resolver groups exact-match entities together."""

    async def test_groups_exact_match(self) -> None:
        """Two entities with the same text are grouped."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=InBatchCandidateSource(),
        )
        entities = [
            _entity("Ada Lovelace", label="Person"),
            _entity("Ada Lovelace", label="Person"),
            _entity("Charles Babbage", label="Person"),
        ]
        groups = await resolver.resolve(entities)
        # Ada Lovelace pair should be in one group, Charles alone
        all_indices = [g.entity_indices for g in groups]
        pair_group = next(g for g in all_indices if 0 in g)
        assert set(pair_group) == {0, 1}
        charles_group = next(g for g in all_indices if 2 in g)
        assert charles_group == [2]

    async def test_separates_different_entities(self) -> None:
        """Different entities stay in separate groups."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=InBatchCandidateSource(),
        )
        entities = [
            _entity("Ada", label="Person"),
            _entity("Charles", label="Person"),
        ]
        groups = await resolver.resolve(entities)
        assert len(groups) == 2

    async def test_respects_label_boundaries(self) -> None:
        """Same text but different labels are not compared."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=InBatchCandidateSource(),
        )
        entities = [
            _entity("Apple", label="Person"),
            _entity("Apple", label="Organization"),
        ]
        groups = await resolver.resolve(entities)
        # Different labels → different groups
        assert len(groups) == 2
