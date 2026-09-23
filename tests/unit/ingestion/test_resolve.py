"""Tests for the comparator, candidate source, and Resolver in ingestion.resolve.

Covers ExactMatch (case/whitespace-insensitive match, otherwise UNCERTAIN,
never NO_MATCH), FuzzyMatch's fast-path accept (MATCH at or above
threshold, otherwise UNCERTAIN, never NO_MATCH), and LLMVerify's fail-safe
NO_MATCH on a raising injected client, working without settings when a
client is injected directly, raising
ExtractorMissingExtraError when no client is available (simulated by
patching ``agrag.llm.baml_client`` out of ``sys.modules``), and
retry-with-backoff behavior driven by ExtractionLLMSettings.retry (sleep is
patched to record delays instead of actually sleeping).

Also covers GraphCandidateSource restricting in-batch candidates to
same-label, non-self entities; the union-find _group_matches helper
clustering transitively connected indices; and the zone-routed Resolver:
exact identity groups without evidence, fuzzy fast-path records
``fuzzy_fast_path`` evidence, embedding similarity hard-merges, discards,
or defers to a capped LLM tier, and uncertain LLM verdicts count as
ambiguous without merging.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.provenance import TextProvenance
from agrag.embedding.base import Embedder
from agrag.ingestion.extract import (
    ExtractionLLMSettings,
    ExtractorMissingExtraError,
)
from agrag.ingestion.resolve import (
    ComparisonVerdict,
    ExactMatch,
    FuzzyMatch,
    GraphCandidateSource,
    LLMVerify,
    PersistedCandidateSource,
    Resolver,
    _group_matches,
)
from agrag.llm.client_config import LLMClientConfig, RetryConfig


def _candidate_source() -> GraphCandidateSource:
    """Build a GraphCandidateSource for pure in-batch blocking tests.

    candidates_for never touches a store, so both dependencies are mocks.
    """
    return GraphCandidateSource(
        graph_store=AsyncMock(), embedder=MagicMock(), vector_store=None
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
        char_end=max(len(text), 1),
    )


def _chunk(text: str = "context") -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


@pytest.fixture
def _mock_match_client_cls() -> type:
    """Fixture providing a BAML client that always returns a match verdict."""

    class MockClient:
        async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
            return [
                {
                    "pair_id": pairs[0]["pair_id"],
                    "verdict": "match",
                    "reasoning": "fallback",
                }
            ]

    return MockClient


@pytest.fixture
def _fake_settings_no_config_cls() -> type:
    """Fixture providing an ExtractionLLMSettings that always fails to construct."""
    return type(
        "FakeSettings",
        (),
        {
            "__init__": lambda self, **_: (_ for _ in ()).throw(
                ValueError("no config")
            ),
            "from_openai_compatible_env": classmethod(
                lambda cls: (_ for _ in ()).throw(RuntimeError("no global"))
            ),
        },
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
    """FuzzyMatch fast-path accepts near-identical names, never rejects."""

    async def test_match_above_threshold(self) -> None:
        """Near-identical names return MATCH."""
        matcher = FuzzyMatch()
        a = _entity("Ada Lovelace")
        b = _entity("Lovelace Ada")
        assert await matcher.compare(a, b) is ComparisonVerdict.MATCH

    async def test_uncertain_below_threshold(self) -> None:
        """Dissimilar names defer to later tiers instead of NO_MATCH."""
        matcher = FuzzyMatch()
        a = _entity("Apple")
        b = _entity("Banana")
        assert await matcher.compare(a, b) is ComparisonVerdict.UNCERTAIN

    async def test_retains_similarity_score_as_match_evidence(self) -> None:
        """The resolver persists the score that produced a fuzzy match."""
        resolver = Resolver(
            comparators=[FuzzyMatch(match_above=0.80)],
            candidate_source=_candidate_source(),
        )

        result = await resolver.resolve(
            [_entity("Ada Lovelace"), _entity("Lovelace Ada")]
        )

        assert len(result.matches) == 1
        assert result.matches[0].score == 1.0

    async def test_custom_thresholds(self) -> None:
        """A stricter threshold defers pairs that score below it."""
        strict = FuzzyMatch(match_above=0.99)
        a = _entity("Ada Lovelace")
        b = _entity("Ada Lovelace.")
        verdict = await strict.compare(a, b)
        assert verdict is ComparisonVerdict.UNCERTAIN


# ── LLMVerify ──────────────────────────────────────────────────────────


class TestLLMVerify:
    """LLMVerify returns NO_MATCH on failure, raises on missing extra."""

    @pytest.mark.parametrize("max_pairs_per_batch", [0, -1])
    def test_rejects_non_positive_max_pairs_per_batch(
        self, max_pairs_per_batch: int
    ) -> None:
        """A zero or negative batch size cannot produce valid results."""
        chunk_id = uuid4()
        with pytest.raises(ValueError, match="must be positive"):
            LLMVerify(
                chunks_by_id={chunk_id: _chunk("context")},
                max_pairs_per_batch=max_pairs_per_batch,
            )

    async def test_returns_no_match_on_client_exception(self) -> None:
        """An injected client that raises produces NO_MATCH (fail-safe)."""

        class RaisingClient:
            async def VerifyEntityMatches(self, *args):  # noqa: N802
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

        class MockClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                return [
                    {
                        "pair_id": pairs[0]["pair_id"],
                        "verdict": "match",
                        "reasoning": "same",
                    }
                ]

        chunk = _chunk("context text")
        chunk_id = uuid4()
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Ada", chunk_id=chunk_id)
        verifier = LLMVerify(
            chunks_by_id={chunk_id: chunk},
            client=MockClient(),
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

    async def test_compare_retries_a_transient_failure_per_settings_retry(
        self, monkeypatch
    ) -> None:
        """settings.retry drives real retry-with-backoff around the LLM call."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        monkeypatch.setattr(
            "agrag.llm.client_registry.build_client_registry",
            lambda clients, *, strategy: object(),
        )

        call_count = 0

        class FlakyClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise RuntimeError("transient provider error")
                return [
                    {
                        "pair_id": pairs[0]["pair_id"],
                        "verdict": "match",
                        "reasoning": "same",
                    }
                ]

        chunk = _chunk("context text")
        chunk_id = uuid4()
        settings = ExtractionLLMSettings(
            clients=[LLMClientConfig(name="c", provider="openai", model="gpt-4o-mini")],
            retry=RetryConfig(max_retries=3, delay_ms=50, multiplier=2),
        )
        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings)
        monkeypatch.setattr(verifier, "_default_client", FlakyClient)
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Charles", chunk_id=chunk_id)

        verdict = await verifier.compare(a, b)

        assert call_count == 3
        assert sleeps == [0.05, 0.1]
        assert verdict is ComparisonVerdict.MATCH

    async def test_compare_with_non_default_env_retry_does_not_abort(
        self, monkeypatch
    ) -> None:
        """A non-default, env-backed RetryConfig works with a configured client."""
        monkeypatch.setenv(
            "EXTRACTION_LLM_CLIENTS",
            '[{"name": "c", "provider": "openai", "model": "gpt-4o-mini"}]',
        )
        monkeypatch.setenv("EXTRACTION_LLM_RETRY", '{"max_retries": 7}')
        settings = ExtractionLLMSettings()
        assert settings.retry.max_retries == 7

        class MockClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                return [
                    {
                        "pair_id": pairs[0]["pair_id"],
                        "verdict": "match",
                        "reasoning": "same",
                    }
                ]

        chunk = _chunk("context text")
        chunk_id = uuid4()
        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=settings)
        monkeypatch.setattr(verifier, "_default_client", MockClient)
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Charles", chunk_id=chunk_id)

        verdict = await verifier.compare(a, b)

        assert verdict is ComparisonVerdict.MATCH

    async def test_falls_back_to_global_llm_when_extraction_config_missing(
        self, monkeypatch, _mock_match_client_cls
    ) -> None:
        """No EXTRACTION_LLM_* falls back to LLM_* via from_openai_compatible_env."""
        monkeypatch.delenv("EXTRACTION_LLM_CLIENTS", raising=False)
        monkeypatch.delenv("EXTRACTION_LLM_BASE_URL", raising=False)
        monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL_ID", "test-model")
        # Ensure the fallback reads the monkeypatched env, not a stale .env
        monkeypatch.setattr(
            "agrag.llm.client_registry.build_client_registry",
            lambda clients, *, strategy: object(),
        )

        chunk = _chunk("context text")
        chunk_id = uuid4()
        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=None)
        monkeypatch.setattr(verifier, "_default_client", _mock_match_client_cls)
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Charles", chunk_id=chunk_id)

        verdict = await verifier.compare(a, b)

        assert verdict is ComparisonVerdict.MATCH

    async def test_returns_no_match_when_no_llm_config(
        self, monkeypatch, _fake_settings_no_config_cls
    ) -> None:
        """No EXTRACTION_LLM_* and no LLM_* returns NO_MATCH without calling LLM."""
        monkeypatch.delenv("EXTRACTION_LLM_CLIENTS", raising=False)
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_MODEL_ID", raising=False)
        monkeypatch.setenv("LLM_BASE_URL", "")
        monkeypatch.setenv("LLM_MODEL_ID", "")

        # Force both settings constructors to fail even if .env exists
        monkeypatch.setattr(
            "agrag.ingestion.resolve.resolver.ExtractionLLMSettings",
            _fake_settings_no_config_cls,
        )

        chunk = _chunk("context text")
        chunk_id = uuid4()
        verifier = LLMVerify(chunks_by_id={chunk_id: chunk}, settings=None)
        a = _entity("Ada", chunk_id=chunk_id)
        b = _entity("Charles", chunk_id=chunk_id)

        verdict = await verifier.compare(a, b)

        assert verdict is ComparisonVerdict.NO_MATCH


# ── GraphCandidateSource in-batch blocking ─────────────────────────────


class TestGraphCandidateSourceInBatch:
    """GraphCandidateSource only proposes same-label in-batch pairs."""

    async def test_never_proposes_cross_label(self) -> None:
        """Entities with different labels are never compared."""
        source = _candidate_source()
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
        source = _candidate_source()
        entities = [
            _entity("Ada", label="Person"),
            _entity("Charles", label="Person"),
            _entity("Grace", label="Person"),
        ]
        candidates = await source.candidates_for(0, entities)
        assert set(candidates) == {1, 2}

    async def test_excludes_self(self) -> None:
        """The entity's own index is never in the candidates."""
        source = _candidate_source()
        entities = [_entity("Ada", label="Person")]
        candidates = await source.candidates_for(0, entities)
        assert candidates == []


class TestPersistedCandidateSource:
    """Persisted candidates only originate from newly extracted mentions."""

    async def test_returns_configured_candidate_indices(self) -> None:
        """The source does not invent reverse or persisted-to-persisted pairs."""
        source = PersistedCandidateSource({0: [2, 3]})
        entities = [_entity("Ada"), _entity("Grace"), _entity("Ada L."), _entity("A.")]

        assert await source.candidates_for(0, entities) == [2, 3]
        assert await source.candidates_for(2, entities) == []


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
            candidate_source=_candidate_source(),
        )
        entities = [
            _entity("Ada Lovelace", label="Person"),
            _entity("Ada Lovelace", label="Person"),
            _entity("Charles Babbage", label="Person"),
        ]
        result = await resolver.resolve(entities)
        # Ada Lovelace pair should be in one group, Charles alone
        all_indices = [g.entity_indices for g in result.groups]
        pair_group = next(g for g in all_indices if 0 in g)
        assert set(pair_group) == {0, 1}
        charles_group = next(g for g in all_indices if 2 in g)
        assert charles_group == [2]

    async def test_separates_different_entities(self) -> None:
        """Different entities stay in separate groups."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=_candidate_source(),
        )
        entities = [
            _entity("Ada", label="Person"),
            _entity("Charles", label="Person"),
        ]
        result = await resolver.resolve(entities)
        assert len(result.groups) == 2

    async def test_respects_label_boundaries(self) -> None:
        """Same text but different labels are not compared."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=_candidate_source(),
        )
        entities = [
            _entity("Apple", label="Person"),
            _entity("Apple", label="Organization"),
        ]
        result = await resolver.resolve(entities)
        # Different labels → different groups
        assert len(result.groups) == 2

    async def test_records_non_exact_match_evidence(self) -> None:
        """A fuzzy match retains its exact input pair for graph persistence."""
        resolver = Resolver(
            comparators=[FuzzyMatch(match_above=0.80)],
            candidate_source=_candidate_source(),
        )
        result = await resolver.resolve([_entity("Apple Inc"), _entity("Apple Inc.")])
        assert len(result.matches) == 1
        assert result.matches[0].left_index == 0
        assert result.matches[0].right_index == 1
        assert result.matches[0].comparator == "fuzzy_fast_path"

    async def test_batches_uncertain_pairs_with_pair_id_verdicts(self) -> None:
        """Only a valid verdict for its requested pair can create a match."""
        chunk = _chunk()

        class BatchClient:
            """Return intentionally unordered and incomplete batch output."""

            async def VerifyEntityMatches(
                self, pairs: list[object], options: dict
            ) -> list[dict[str, str]]:
                """Return verdicts that prove pair identifiers control matching."""
                assert len(pairs) == 3
                assert options == {}
                return [
                    {"pair_id": "1:2", "verdict": "match", "reasoning": "same"},
                    {"pair_id": "0:1", "verdict": "invalid"},
                ]

        entities = [
            _entity("Ada", chunk_id=chunk.id),
            _entity("Charles", chunk_id=chunk.id),
            _entity("Charles Babbage", chunk_id=chunk.id),
        ]
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(match_above=1.0),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=BatchClient()),
            ],
            candidate_source=_candidate_source(),
        )

        result = await resolver.resolve(entities)

        assert sorted(group.entity_indices for group in result.groups) == [[0], [1, 2]]
        assert len(result.matches) == 1
        assert result.matches[0].left_index == 1
        assert result.matches[0].right_index == 2
        assert result.matches[0].reasoning == "same"


# ── Zone routing ─────────────────────────────────────────────────────


def _cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity for asserting test vectors land in the right zone."""
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    return dot / (left_norm * right_norm)


class _ScriptedEmbedder(Embedder):
    """Embedder returning fixed vectors per text, recording batch calls."""

    model = "scripted"

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        """Serve one fixed vector per known text."""
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def dimensions(self) -> int:
        """Return the scripted vector dimension."""
        return len(next(iter(self.vectors.values())))

    async def embed(self, texts) -> list[list[float]]:  # type: ignore[no-untyped-def]
        """Return the scripted vector per text, recording the batch."""
        self.calls.append(list(texts))
        return [self.vectors[text] for text in texts]


class _CountingClient:
    """Batch client replying one verdict to every pair, counting requests."""

    def __init__(self, verdict: str) -> None:
        """Reply with verdict to every requested pair."""
        self.verdict = verdict
        self.calls = 0

    async def VerifyEntityMatches(self, pairs: list, options: dict) -> list:  # noqa: N802
        """Count the request and reply the fixed verdict per pair."""
        self.calls += 1
        return [
            {"pair_id": pair["pair_id"], "verdict": self.verdict, "reasoning": "test"}
            for pair in pairs
        ]


def _llm_chunk() -> Chunk:
    """Build a shared context chunk for LLM-tier tests."""
    return _chunk("shared context")


def _llm_entity(text: str, chunk: Chunk, label: str = "Person") -> ExtractedEntity:
    """Build a mention carrying the shared LLM context chunk."""
    return _entity(text, label=label, chunk_id=chunk.id)


class TestZoneRouting:
    """Resolver routes pairs through exact, fuzzy, embedding, and LLM zones."""

    async def test_exact_match_groups_without_evidence(self) -> None:
        """Exact identity merges with no match record and no ambiguity."""
        resolver = Resolver(
            comparators=[ExactMatch()],
            candidate_source=_candidate_source(),
        )
        result = await resolver.resolve(
            [_entity("Ada Lovelace"), _entity("Ada Lovelace")]
        )

        assert sorted(group.entity_indices for group in result.groups) == [[0, 1]]
        assert result.matches == []
        assert result.ambiguous_count == 0

    async def test_embedding_hard_merge_records_evidence(self) -> None:
        """A high cosine similarity merges with embedding evidence."""
        resolver = Resolver(
            comparators=[ExactMatch(), FuzzyMatch()],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder({"Apple": [1.0, 0.0], "Banana": [1.0, 0.0]}),
        )
        result = await resolver.resolve([_entity("Apple"), _entity("Banana")])

        assert sorted(group.entity_indices for group in result.groups) == [[0, 1]]
        assert len(result.matches) == 1
        assert result.matches[0].comparator == "embedding"
        assert result.matches[0].score == pytest.approx(1.0)

    async def test_embedding_discard_drops_without_llm(self) -> None:
        """A low cosine similarity drops the pair before any LLM call."""
        client = _CountingClient("no_match")
        chunk = _llm_chunk()
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=client),
            ],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder({"Apple": [1.0, 0.0], "Banana": [0.0, 1.0]}),
        )
        result = await resolver.resolve([_entity("Apple"), _entity("Banana")])

        assert sorted(group.entity_indices for group in result.groups) == [[0], [1]]
        assert result.matches == []
        assert client.calls == 0
        assert result.ambiguous_count == 0

    async def test_ambiguous_pair_reaches_llm(self) -> None:
        """A mid-band similarity goes to the LLM and merges on MATCH."""
        low = [1.0, 0.0]
        mid = [4.0, 3.0]
        assert 0.80 <= _cosine(low, mid) < 0.95
        chunk = _llm_chunk()
        client = _CountingClient("match")
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=client),
            ],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder({"Jon Smith": low, "John Smith": mid}),
        )
        result = await resolver.resolve(
            [_llm_entity("Jon Smith", chunk), _llm_entity("John Smith", chunk)]
        )

        assert sorted(group.entity_indices for group in result.groups) == [[0, 1]]
        assert [match.comparator for match in result.matches] == ["llm"]
        assert client.calls == 1
        assert result.ambiguous_count == 0

    async def test_uncertain_llm_verdict_counts_ambiguous(self) -> None:
        """An uncertain LLM verdict never merges but counts as ambiguous."""
        chunk = _llm_chunk()
        client = _CountingClient("uncertain")
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=client),
            ],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder(
                {"Jon Smith": [1.0, 0.0], "John Smith": [4.0, 3.0]}
            ),
        )
        result = await resolver.resolve(
            [_llm_entity("Jon Smith", chunk), _llm_entity("John Smith", chunk)]
        )

        assert sorted(group.entity_indices for group in result.groups) == [[0], [1]]
        assert result.matches == []
        assert result.ambiguous_count == 1

    async def test_precluster_auto_merges_without_llm(self) -> None:
        """An ambiguous pair inside a tight cluster merges with no LLM call."""
        vectors = {
            "Alpha": [1.0, 0.0],
            "Beta": [0.99, 0.141067],
            "Gamma": [0.94, 0.34117],
        }
        assert _cosine(vectors["Alpha"], vectors["Beta"]) >= 0.95
        assert _cosine(vectors["Beta"], vectors["Gamma"]) >= 0.95
        assert 0.80 <= _cosine(vectors["Alpha"], vectors["Gamma"]) < 0.95
        chunk = _llm_chunk()
        client = _CountingClient("match")
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=client),
            ],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder(vectors),
        )
        result = await resolver.resolve([_llm_entity(text, chunk) for text in vectors])

        assert sorted(group.entity_indices for group in result.groups) == [[0, 1, 2]]
        assert {match.comparator for match in result.matches} == {"embedding"}
        assert len(result.matches) == 3
        assert client.calls == 0
        assert result.ambiguous_count == 0

    async def test_missing_llm_tier_drops_boundary_pairs(self) -> None:
        """Without an LLMVerify comparator, boundary pairs never merge."""
        resolver = Resolver(
            comparators=[ExactMatch(), FuzzyMatch()],
            candidate_source=_candidate_source(),
            embedder=_ScriptedEmbedder(
                {"Jon Smith": [1.0, 0.0], "John Smith": [4.0, 3.0]}
            ),
        )
        result = await resolver.resolve([_entity("Jon Smith"), _entity("John Smith")])

        assert sorted(group.entity_indices for group in result.groups) == [[0], [1]]
        assert result.matches == []
        assert result.ambiguous_count == 0

    async def test_llm_calls_stay_within_budget(self) -> None:
        """LLM requests never exceed ceil(L * max_llm_pairs / llm_batch_size)."""
        chunk = _llm_chunk()
        client = _CountingClient("no_match")
        labels = ["Person", "Organization"]
        entities = [
            _llm_entity(f"name-{label}-{index}", chunk, label=label)
            for label in labels
            for index in range(6)
        ]
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=client),
            ],
            candidate_source=_candidate_source(),
            max_llm_pairs=2,
            llm_batch_size=2,
        )
        result = await resolver.resolve(entities)

        assert client.calls <= 2
        assert result.ambiguous_count == 0

    async def test_neighbors_reach_the_llm_verify_tier(self) -> None:
        """Neighbor context passed to resolve() arrives in the LLM request."""
        chunk = _chunk()
        seen: list[dict] = []

        class RecordingClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                seen.extend(pairs)
                return []

        entities = [
            _entity("Ada Lovelace", chunk_id=chunk.id),
            _entity("Lady Lovelace", chunk_id=chunk.id),
        ]
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(match_above=1.0),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=RecordingClient()),
            ],
            candidate_source=_candidate_source(),
        )

        await resolver.resolve(entities, neighbors_by_index={0: ["KNOWS Ada"]})

        assert seen[0]["neighbors_a"] == ["KNOWS Ada"]
        assert seen[0]["neighbors_b"] == []

    async def test_compare_batch_forwards_context_to_every_chunk(self) -> None:
        """Chunked requests each carry the global context maps, unsliced."""
        chunk = _chunk("context text")
        seen: list[dict] = []

        class RecordingClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                seen.extend(pairs)
                return []

        a = _entity("Ada", chunk_id=chunk.id)
        b = _entity("Ada L.", chunk_id=chunk.id)
        c = _entity("Ada Lovelace", chunk_id=chunk.id)
        verifier = LLMVerify(
            chunks_by_id={chunk.id: chunk},
            client=RecordingClient(),
            max_pairs_per_batch=1,
        )

        await verifier.compare_batch(
            [(0, 1, a, b), (1, 2, b, c)],
            neighbors_by_index={
                0: ["KNOWS Acme"],
                1: ["KNOWS Acme"],
                2: ["KNOWS Acme"],
            },
            similarities={(0, 1): 0.83, (1, 2): 0.61},
        )

        assert len(seen) == 2
        assert [payload["pair_id"] for payload in seen] == ["0:1", "1:2"]
        assert seen[0]["similarity"] == 0.83
        assert seen[1]["similarity"] == 0.61
        assert all(payload["neighbors_a"] == ["KNOWS Acme"] for payload in seen)
        assert all(payload["neighbors_b"] == ["KNOWS Acme"] for payload in seen)

    async def test_fuzzy_score_reaches_the_llm_verify_tier(self) -> None:
        """A pair that stays UNCERTAIN carries its FuzzyMatch score to the LLM.

        Driven the existing way -- resolve() with no context arguments --
        which also proves the new parameters are additive: neighbor context
        stays empty while the pair still gains FuzzyMatch's score.
        """
        chunk = _chunk()
        seen: list[dict] = []

        class RecordingClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                seen.extend(pairs)
                return []

        a = _entity("Ada Lovelace", chunk_id=chunk.id)
        b = _entity("Lady Lovelace", chunk_id=chunk.id)
        fuzzy = FuzzyMatch(match_above=1.0)
        expected_score = (await fuzzy.compare_with_evidence(a, b)).score
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                fuzzy,
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=RecordingClient()),
            ],
            candidate_source=_candidate_source(),
        )

        await resolver.resolve([a, b])

        assert expected_score is not None and expected_score > 0.0
        assert seen[0]["similarity"] == expected_score
        assert seen[0]["neighbors_a"] == []
        assert seen[0]["neighbors_b"] == []

    async def test_seeded_similarity_wins_over_a_later_fuzzy_score(self) -> None:
        """A caller-seeded real score, not FuzzyMatch's, reaches the LLM.

        Seeded at 0.85: inside the ambiguous band, so the pair reaches the
        LLM tier instead of being routed by zone alone.
        """
        chunk = _chunk()
        seen: list[dict] = []

        class RecordingClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                seen.extend(pairs)
                return []

        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(match_above=1.0),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=RecordingClient()),
            ],
            candidate_source=_candidate_source(),
        )
        entities = [
            _entity("Ada Lovelace", chunk_id=chunk.id),
            _entity("Lady Lovelace", chunk_id=chunk.id),
        ]

        await resolver.resolve(entities, similarity_by_pair={(0, 1): 0.85})

        assert seen[0]["similarity"] == 0.85

    async def test_resolve_does_not_mutate_the_callers_similarity_map(self) -> None:
        """Resolving never writes into the caller's seed dict."""
        chunk = _chunk()
        seed: dict[tuple[int, int], float] = {}

        class RecordingClient:
            async def VerifyEntityMatches(self, pairs, options):  # noqa: N802
                return []

        entities = [
            _entity("Ada Lovelace", chunk_id=chunk.id),
            _entity("Lady Lovelace", chunk_id=chunk.id),
        ]
        resolver = Resolver(
            comparators=[
                ExactMatch(),
                FuzzyMatch(match_above=1.0),
                LLMVerify(chunks_by_id={chunk.id: chunk}, client=RecordingClient()),
            ],
            candidate_source=_candidate_source(),
        )

        await resolver.resolve(entities, similarity_by_pair=seed)
        await resolver.resolve(entities, similarity_by_pair=seed)

        assert seed == {}

    def test_llm_batch_size_must_be_positive(self) -> None:
        """A non-positive batch size cannot bound LLM requests."""
        with pytest.raises(ValueError, match="must be positive"):
            Resolver(
                comparators=[ExactMatch()],
                candidate_source=_candidate_source(),
                llm_batch_size=0,
            )

    def test_llm_batch_size_must_fit_comparator_batches(self) -> None:
        """A batch larger than max_pairs_per_batch cannot stay in one request."""
        with pytest.raises(ValueError, match="must fit"):
            Resolver(
                comparators=[
                    LLMVerify(chunks_by_id={}, max_pairs_per_batch=5),
                ],
                candidate_source=_candidate_source(),
                llm_batch_size=10,
            )
