"""Tests for linking and storing candidate records."""

from typing import Literal
from unittest.mock import AsyncMock
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

import pytest

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.ingestion._candidate_stage import candidate_stage
from agrag.ingestion._stage_context import StageContext
from agrag.loaders.types import ErrorPolicy
from agrag.observability import get_tracer


def _mention(chunk_id: UUID, text: str, label: str) -> ExtractedEntity:
    return ExtractedEntity(
        chunk_id=chunk_id,
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _candidate(
    chunk_id: UUID,
    *,
    kind: Literal["entity", "relation", "property"] = "entity",
    label: str = "Organization",
    text: str = "Acme",
    count: int = 1,
    confidence: float = 0.5,
    source_text: str | None = None,
    target_text: str | None = None,
    source_label: str | None = None,
    target_label: str | None = None,
) -> CandidateRecord:
    return CandidateRecord(
        kind=kind,
        label=label,
        text=text,
        confidence=confidence,
        reason="off_pattern",
        chunk_id=chunk_id,
        count=count,
        source_text=source_text,
        target_text=target_text,
        source_label=source_label,
        target_label=target_label,
    )


def _context(
    store: AsyncMock,
    *,
    error_policy: ErrorPolicy = ErrorPolicy.SKIP,
    job_id: UUID | None = None,
) -> StageContext:
    return StageContext(
        graph_store=store,
        embedder=AsyncMock(),
        error_policy=error_policy,
        tracer=get_tracer(None),
        job_id=job_id,
        deferred=None,
    )


class TestCandidateStage:
    """Verify candidates written through the graph-store boundary."""

    async def test_links_relation_and_property_by_normalized_text_and_label(
        self,
    ) -> None:
        """Link unambiguous labeled endpoints and leave ambiguous ones unresolved."""
        chunk_id = uuid4()
        organization_id, person_id, jordan_id = uuid4(), uuid4(), uuid4()
        entities = [
            _mention(chunk_id, "Acme, Inc.", "Organization"),
            _mention(chunk_id, "Acme, Inc.", "Person"),
            _mention(chunk_id, "Jordan", "Person"),
        ]
        candidates = [
            _candidate(
                chunk_id,
                kind="relation",
                label="WORKS_AT",
                text="",
                source_text="  ACME, INC.  ",
                target_text="Jordan",
                source_label="Organization",
                target_label="Person",
            ),
            _candidate(
                chunk_id,
                kind="property",
                label="industry",
                text="Finance",
                source_text="Acme, Inc.",
                source_label="Organization",
            ),
            _candidate(
                chunk_id,
                kind="relation",
                label="RELATED_TO",
                text="",
                source_text="acme, inc.",
                target_text="Jordan",
                source_label=None,
                target_label="Person",
            ),
            _candidate(
                chunk_id,
                kind="property",
                label="unlinked",
                text="Unknown",
                source_text="Missing mention",
            ),
        ]
        store = AsyncMock()
        store.blocked_candidate_keys.return_value = set()
        store.upsert_candidates.return_value = UpsertResult(written=4)

        result = await candidate_stage(
            candidates,
            entities,
            {0: organization_id, 1: person_id, 2: jordan_id},
            _context(store),
            schema_fingerprint="schema-v1",
            enabled=True,
        )

        stored = store.upsert_candidates.await_args.args[0]
        linked_relation = next(item for item in stored if item.label == "WORKS_AT")
        linked_property = next(item for item in stored if item.label == "industry")
        ambiguous_relation = next(item for item in stored if item.label == "RELATED_TO")
        unlinked_property = next(item for item in stored if item.label == "unlinked")
        assert linked_relation.source_entity_id == organization_id
        assert linked_relation.target_entity_id == jordan_id
        assert linked_property.source_entity_id == organization_id
        assert ambiguous_relation.source_entity_id is None
        assert ambiguous_relation.target_entity_id == jordan_id
        assert unlinked_property.source_entity_id is None
        assert result.written == 4

    async def test_aggregates_repeated_identity_with_deterministic_id_and_fingerprint(
        self,
    ) -> None:
        """Combine repeated sightings and assign stable identity metadata."""
        chunk_id, job_id = uuid4(), uuid4()
        first = _candidate(chunk_id, text="Acme", count=2, confidence=0.4)
        second = _candidate(chunk_id, text="ACME", count=3, confidence=0.9)
        store = AsyncMock()
        store.blocked_candidate_keys.return_value = set()
        store.upsert_candidates.return_value = UpsertResult(written=1)

        await candidate_stage(
            [first, second],
            [],
            {},
            _context(store, job_id=job_id),
            schema_fingerprint="fingerprint-7",
            enabled=True,
        )

        stored = store.upsert_candidates.await_args.args[0]
        assert len(stored) == 1
        assert stored[0].count == 5
        assert stored[0].confidence == 0.9
        assert stored[0].id == uuid5(
            NAMESPACE_OID, f"Candidate:{job_id}:{chunk_id}:{first.key}"
        )
        assert stored[0].schema_fingerprint == "fingerprint-7"

    async def test_blocked_keys_skip_all_occurrences_without_write(self) -> None:
        """A blocked key contributes its full occurrence count to skipped."""
        chunk_id = uuid4()
        candidate = _candidate(chunk_id, count=4)
        store = AsyncMock()
        store.blocked_candidate_keys.return_value = {candidate.key}

        result = await candidate_stage(
            [candidate],
            [],
            {},
            _context(store),
            schema_fingerprint="schema",
            enabled=True,
        )

        assert result.skipped == 4
        assert result.written == 0
        store.upsert_candidates.assert_not_awaited()

    async def test_merged_relation_self_loop_skips_occurrences(self) -> None:
        """A relation whose endpoints merge to one entity is not persisted."""
        chunk_id, entity_id = uuid4(), uuid4()
        relation = _candidate(
            chunk_id,
            kind="relation",
            label="KNOWS",
            text="",
            count=3,
            source_text="Alex",
            target_text="Alex",
            source_label="Person",
            target_label="Person",
        )
        store = AsyncMock()

        result = await candidate_stage(
            [relation],
            [
                _mention(chunk_id, "Alex", "Person"),
                _mention(chunk_id, "Alex", "Person"),
            ],
            {0: entity_id, 1: entity_id},
            _context(store),
            schema_fingerprint="schema",
            enabled=True,
        )

        assert result.skipped == 3
        assert result.written == 0
        store.blocked_candidate_keys.assert_not_awaited()

    @pytest.mark.parametrize(
        "enabled,candidates", [(False, [_candidate(uuid4())]), (True, [])]
    )
    async def test_disabled_or_empty_input_does_not_access_store(
        self, enabled: bool, candidates: list[CandidateRecord]
    ) -> None:
        """Disabled and empty stages return without graph-store access."""
        store = AsyncMock()

        result = await candidate_stage(
            candidates,
            [],
            {},
            _context(store),
            schema_fingerprint="schema",
            enabled=enabled,
        )

        assert result.written == result.skipped == 0
        store.blocked_candidate_keys.assert_not_awaited()

    @pytest.mark.parametrize(
        "failure_method", ["blocked_candidate_keys", "upsert_candidates"]
    )
    async def test_storage_exceptions_follow_job_and_error_policy(
        self, failure_method: str
    ) -> None:
        """Storage exceptions propagate for jobs or RAISE and report under SKIP."""
        candidate = _candidate(uuid4())
        for method, job_id, policy, raises in (
            ("blocked_candidate_keys", uuid4(), ErrorPolicy.SKIP, True),
            ("upsert_candidates", uuid4(), ErrorPolicy.SKIP, True),
            ("blocked_candidate_keys", None, ErrorPolicy.SKIP, False),
            ("upsert_candidates", None, ErrorPolicy.SKIP, False),
            ("blocked_candidate_keys", None, ErrorPolicy.RAISE, True),
            ("upsert_candidates", None, ErrorPolicy.RAISE, True),
        ):
            store = AsyncMock()
            store.blocked_candidate_keys.return_value = set()
            error = RuntimeError("storage unavailable")
            getattr(store, method).side_effect = error
            if method == "upsert_candidates":
                store.blocked_candidate_keys.return_value = set()
            if method != failure_method:
                continue

            if raises:
                with pytest.raises(RuntimeError, match="storage unavailable"):
                    await candidate_stage(
                        [candidate],
                        [],
                        {},
                        _context(store, job_id=job_id, error_policy=policy),
                        schema_fingerprint="schema",
                        enabled=True,
                    )
            else:
                result = await candidate_stage(
                    [candidate],
                    [],
                    {},
                    _context(store, error_policy=policy),
                    schema_fingerprint="schema",
                    enabled=True,
                )
                assert result.written == result.skipped == 0
                assert len(result.failures) == 1
                assert result.failures[0].item_id == "candidates"
                assert result.failures[0].error_message == "storage unavailable"

    async def test_record_failures_raise_for_job_and_are_reported_without_job(
        self,
    ) -> None:
        """Per-record write failures raise for jobs and return as stage failures."""
        candidate = _candidate(uuid4())
        failed_record = UpsertFailure(
            id=str(candidate.id), error_type="ConstraintError", error_message="rejected"
        )
        store = AsyncMock()
        store.blocked_candidate_keys.return_value = set()
        store.upsert_candidates.return_value = UpsertResult(
            written=0, failures=[failed_record]
        )

        with pytest.raises(RuntimeError, match="Candidate refresh failed: rejected"):
            await candidate_stage(
                [candidate],
                [],
                {},
                _context(store, job_id=uuid4()),
                schema_fingerprint="schema",
                enabled=True,
            )

        store.upsert_candidates.return_value = UpsertResult(
            written=0, failures=[failed_record]
        )
        result = await candidate_stage(
            [candidate],
            [],
            {},
            _context(store),
            schema_fingerprint="schema",
            enabled=True,
        )
        assert len(result.failures) == 1
        assert result.failures[0].item_id == str(candidate.id)
        assert result.failures[0].error_type == "ConstraintError"
        assert result.failures[0].error_message == "rejected"
