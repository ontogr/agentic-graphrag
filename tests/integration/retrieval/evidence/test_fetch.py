"""Integration tests for exact evidence fetch over the authored corpus.

Each test builds span or chunk ids from authored text and offsets, then checks
what the store returns. Text is compared with slices of the authored strings,
so the expected values do not depend on the code under test.
"""

import json
from uuid import UUID, uuid4

from agrag.common.data_models.document import Document
from agrag.common.data_models.evidence import (
    EvidenceKind,
    EvidenceReference,
    FetchOutcome,
    FetchStatus,
    VersionStatus,
)
from agrag.evidence import fetch
from agrag.evidence.ids import encode_evidence_id
from tests.integration.retrieval.evidence._corpus import (
    GOLD_SENTENCE,
    HARBOR_SENTENCE,
    HARBOR_TEXT,
    HARBOR_TEXT_V2,
    HEADED_BODY,
    HEADED_TEXT,
    KEEP_TEXT,
    locate,
    make_headed_document,
    sha256_of,
    span_evidence_id,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_GOLD_START, _GOLD_END = locate(KEEP_TEXT, GOLD_SENTENCE)
_SALT_SENTENCE = (
    "Salt air had worn the iron railings on the gallery, so painters stripped them "
    "back to bare metal."
)


async def _open_chunk_ranges(
    env: EvidenceEnv, document_key: str
) -> list[tuple[int, int]]:
    """Return the text ranges of the open chunks of one document.

    Used only to check that a test range really crosses chunk boundaries.
    """
    rows = await env.store.execute_read(
        "MATCH (:Document {document_key: $key})-[r:HAS_PART]->(c:Chunk) "
        "WHERE r.invalid_at IS NULL "
        "RETURN c.provenance AS provenance",
        {"key": document_key},
    )
    ranges: list[tuple[int, int]] = []
    for row in rows:
        provenance = json.loads(row["provenance"])
        if provenance["kind"] == "text":
            ranges.append((provenance["char_start"], provenance["char_end"]))
    return ranges


async def _fetch_one(
    env: EvidenceEnv,
    evidence_id: str,
    *,
    scope_keys: frozenset[str] | None = None,
    max_chars: int = 8000,
) -> FetchOutcome:
    """Fetch one id with the given scope, defaulting to every corpus document."""
    scope = (
        scope_keys
        if scope_keys is not None
        else frozenset({env.keep, env.viber, env.harbor})
    )
    outcomes = await fetch(env.store, [evidence_id], scope=scope, max_chars=max_chars)
    assert len(outcomes) == 1
    return outcomes[0]


class TestExactFetch:
    """Span and chunk references return exact text with version status."""

    async def test_gold_span_returns_the_gold_sentence_exactly(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """The span over the gold sentence returns that sentence and nothing else."""
        evidence_id = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END
        )

        outcome = await _fetch_one(evidence_env, evidence_id)

        assert outcome.status is FetchStatus.OK
        assert outcome.text == GOLD_SENTENCE
        assert outcome.document_key == evidence_env.keep
        assert outcome.content_hash == sha256_of(KEEP_TEXT)
        assert outcome.covered_range == (_GOLD_START, _GOLD_END)
        assert outcome.partial is False
        assert outcome.status_of_version is VersionStatus.CURRENT

    async def test_span_across_chunk_boundaries_is_exact(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A range that crosses several chunks returns the exact authored slice."""
        start, _ = locate(HARBOR_TEXT, HARBOR_SENTENCE)
        _, end = locate(HARBOR_TEXT, _SALT_SENTENCE)
        ranges = await _open_chunk_ranges(evidence_env, evidence_env.harbor)
        crossed = [r for r in ranges if r[0] < end and start < r[1]]
        assert len(crossed) >= 2

        outcome = await _fetch_one(
            evidence_env, span_evidence_id(evidence_env.harbor, HARBOR_TEXT, start, end)
        )

        assert outcome.status is FetchStatus.OK
        assert outcome.text == HARBOR_TEXT[start:end]
        assert outcome.partial is False

    async def test_range_over_uncovered_tail_returns_the_covered_part(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Text past the last chunk is cut to the covered part and marked partial."""
        await evidence_env.graph.update(evidence_env.harbor, text=HARBOR_TEXT_V2)
        content_end = len(HARBOR_TEXT_V2.rstrip())
        start = content_end - 40

        outcome = await _fetch_one(
            evidence_env,
            span_evidence_id(
                evidence_env.harbor, HARBOR_TEXT_V2, start, len(HARBOR_TEXT_V2)
            ),
        )

        assert outcome.status is FetchStatus.PARTIAL
        assert outcome.text == HARBOR_TEXT_V2[start:content_end]
        assert outcome.covered_range == (start, content_end)
        assert outcome.partial is True

    async def test_range_starting_in_uncovered_lead_in_returns_the_covered_part(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Skip text no chunk holds at the start, and mark the range partial."""
        text = "\n\n" + HARBOR_TEXT
        await evidence_env.graph.update(evidence_env.harbor, text=text)
        lead = len(text) - len(text.lstrip())
        end = lead + 60

        outcome = await _fetch_one(
            evidence_env,
            span_evidence_id(evidence_env.harbor, text, 0, end),
        )

        assert outcome.status is FetchStatus.PARTIAL
        assert outcome.text == text[lead:end]
        assert outcome.covered_range == (lead, end)
        assert outcome.partial is True

    async def test_superseded_id_still_fetches_the_old_text(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """After an update the old id returns the old text marked superseded."""
        start, end = locate(HARBOR_TEXT, HARBOR_SENTENCE)
        old_id = span_evidence_id(evidence_env.harbor, HARBOR_TEXT, start, end)
        await evidence_env.graph.update(evidence_env.harbor, text=HARBOR_TEXT_V2)

        outcome = await _fetch_one(evidence_env, old_id)

        assert outcome.status is FetchStatus.OK
        assert outcome.text == HARBOR_TEXT[start:end]
        assert outcome.status_of_version is VersionStatus.SUPERSEDED
        assert outcome.content_hash == sha256_of(HARBOR_TEXT)

    async def test_current_id_after_update_is_current(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A range of the new text is fetched with the current status."""
        await evidence_env.graph.update(evidence_env.harbor, text=HARBOR_TEXT_V2)
        new_sentence = "The crew replaced the brass lantern gasket on the third landing"
        start = HARBOR_TEXT_V2.index(new_sentence)
        end = start + len(new_sentence)

        outcome = await _fetch_one(
            evidence_env,
            span_evidence_id(evidence_env.harbor, HARBOR_TEXT_V2, start, end),
        )

        assert outcome.status is FetchStatus.OK
        assert outcome.text == HARBOR_TEXT_V2[start:end]
        assert outcome.status_of_version is VersionStatus.CURRENT

    async def test_chunk_reference_returns_the_chunk_text(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A chunk reference returns the stored text of that chunk."""
        rows = await evidence_env.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:HAS_PART]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL RETURN c.id AS id, c.text AS text "
            "ORDER BY c.index LIMIT 1",
            {"key": evidence_env.keep},
        )
        chunk_id, chunk_text = rows[0]["id"], rows[0]["text"]
        reference = EvidenceReference(
            kind=EvidenceKind.CHUNK,
            document_node_id=Document.node_id_for(document_key=evidence_env.keep),
            content_hash_prefix=sha256_of(KEEP_TEXT)[:16],
            chunk_id=UUID(chunk_id),
        )

        outcome = await _fetch_one(evidence_env, encode_evidence_id(reference))

        assert outcome.status is FetchStatus.OK
        assert outcome.text == chunk_text
        assert outcome.status_of_version is VersionStatus.CURRENT

    async def test_wrong_content_hash_is_unavailable(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A reference whose hash matches no stored version is unavailable."""
        reference = EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=Document.node_id_for(document_key=evidence_env.keep),
            content_hash_prefix="0" * 16,
            char_start=_GOLD_START,
            char_end=_GOLD_END,
        )

        outcome = await _fetch_one(evidence_env, encode_evidence_id(reference))

        assert outcome.status is FetchStatus.UNAVAILABLE
        assert outcome.text is None


class TestCollidingPrefixes:
    """Two stored versions that share a 16-character hash prefix are not joined."""

    async def test_span_is_unavailable_when_two_hashes_share_the_prefix(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A second full hash under the same prefix makes the id unreadable."""
        await evidence_env.store.execute_write(
            "MATCH (:Document {document_key: $key})-[:HAS_PART]->(c:Chunk) "
            "WITH c ORDER BY c.index LIMIT 1 SET c.content_hash = $tampered",
            {
                "key": evidence_env.keep,
                "tampered": sha256_of(KEEP_TEXT)[:16] + "0" * 48,
            },
        )

        outcome = await _fetch_one(
            evidence_env,
            span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END),
        )

        assert outcome.status is FetchStatus.UNAVAILABLE
        assert outcome.text is None


class TestHeadedChunkSpans:
    """A span never joins a chunk whose text is longer than its offsets."""

    async def test_span_over_headed_body_is_unavailable(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Body text under a heading is reached through the chunk id, not a span."""
        key = evidence_env.key("headed")
        await evidence_env.graph.add(documents=[make_headed_document(key)])
        start = HEADED_TEXT.index(HEADED_BODY[0])
        end = start + len(HEADED_BODY[0])

        outcome = await _fetch_one(
            evidence_env,
            span_evidence_id(key, HEADED_TEXT, start, end),
            scope_keys=frozenset({key}),
        )

        assert outcome.status is FetchStatus.UNAVAILABLE
        assert outcome.text is None


class TestFetchScopeAndLimits:
    """Fetch hides out-of-scope evidence and states truncation."""

    async def test_out_of_scope_id_has_the_same_shape_as_a_missing_id(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """An out-of-scope id and a nonexistent id give the same unavailable outcome."""
        scope = frozenset({evidence_env.viber})
        real_id = span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)
        missing_reference = EvidenceReference(
            kind=EvidenceKind.SPAN,
            document_node_id=uuid4(),
            content_hash_prefix=sha256_of(KEEP_TEXT)[:16],
            char_start=_GOLD_START,
            char_end=_GOLD_END,
        )
        missing_id = encode_evidence_id(missing_reference)

        out_of_scope = await _fetch_one(evidence_env, real_id, scope_keys=scope)
        missing = await _fetch_one(evidence_env, missing_id, scope_keys=scope)

        assert out_of_scope.status is FetchStatus.UNAVAILABLE
        assert out_of_scope.model_dump(exclude={"evidence_id"}) == missing.model_dump(
            exclude={"evidence_id"}
        )

    async def test_empty_scope_makes_every_id_unavailable(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """An empty scope does not mean everything; every id is unavailable."""
        evidence_id = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END
        )

        outcome = await _fetch_one(evidence_env, evidence_id, scope_keys=frozenset())

        assert outcome.status is FetchStatus.UNAVAILABLE

    async def test_malformed_id_is_reported_as_malformed(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A string that does not decode gives the malformed status."""
        outcome = await _fetch_one(evidence_env, "ev1:s:not-an-id")

        assert outcome.status is FetchStatus.MALFORMED
        assert outcome.text is None

    async def test_text_over_max_chars_is_truncated_and_says_so(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Text longer than max_chars is cut, and the outcome says it was cut."""
        evidence_id = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END
        )

        outcome = await _fetch_one(evidence_env, evidence_id, max_chars=10)

        assert outcome.status is FetchStatus.TRUNCATED
        assert outcome.text == GOLD_SENTENCE[:10]
        assert outcome.covered_range == (_GOLD_START, _GOLD_START + 10)
