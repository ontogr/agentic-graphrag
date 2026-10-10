"""Tests for entity merge planning in agrag.ingestion.merge.

Covers canonical-name selection, per-property resolution strategies and
rules, LLM-assisted description resolution (mocked with ``AsyncMock``),
property merging, and full merge-plan computation.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.stage_failure import StageFailure
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    _resolve_property,
    compute_merge,
    mentioned_in_id,
    merge_properties,
    next_chunk_id,
    part_of_id,
    relation_id,
    resolve_description,
    select_canonical,
)
from agrag.llm.client_config import LLMClientConfig, RetryConfig


def _entity(
    *,
    label: str = "Person",
    name: str = "Ada",
    properties: dict[str, object] | None = None,
    entity_id: UUID | None = None,
    created_at: datetime | None = None,
    merge_count: int = 1,
    source_chunk_ids: list[UUID] | None = None,
) -> Entity:
    """Build a minimal Entity for tests."""
    return Entity(
        id=entity_id or uuid4(),
        created_at=created_at or datetime.now(UTC),
        label=label,
        name=name,
        properties=properties or {},
        merge_count=merge_count,
        source_chunk_ids=source_chunk_ids or [],
    )


def _mention(
    text: str = "Ada",
    label: str = "Person",
    chunk_id: UUID | None = None,
    properties: dict[str, object] | None = None,
) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    return ExtractedEntity(
        chunk_id=chunk_id or uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text) or 1,
        properties=properties or {},
    )


def _schema(
    label: str = "Person",
    properties: dict[str, str] | None = None,
) -> GraphSchema:
    """Build a schema with one entity type."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[
            EntityType(
                label=label,
                description="test",
                properties=properties or {},
            )
        ],
        relations=[],
    )


class TestSelectCanonical:
    """select_canonical tiebreaks."""

    def test_picks_fewest_missing_fields(self) -> None:
        """Most schema-complete entity wins."""
        schema_type = EntityType(
            label="Person",
            description="x",
            properties={"a": "str", "b": "str", "c": "str"},
        )
        # e1 missing 2, e2 missing 1, e3 missing 0
        e1 = _entity(name="e1", properties={"a": "1"})
        e2 = _entity(name="e2", properties={"a": "1", "b": "2"})
        e3 = _entity(name="e3", properties={"a": "1", "b": "2", "c": "3"})
        survivor, rest = select_canonical([e1, e2, e3], schema_type)
        assert survivor.id == e3.id
        assert {r.id for r in rest} == {e1.id, e2.id}

    def test_tiebreak_by_created_at(self) -> None:
        """Earlier created_at wins when completeness ties."""
        t1 = datetime(2020, 1, 1, tzinfo=UTC)
        t2 = datetime(2020, 1, 2, tzinfo=UTC)
        e1 = _entity(name="later", created_at=t2, properties={})
        e2 = _entity(name="earlier", created_at=t1, properties={})
        survivor, rest = select_canonical([e1, e2], None)
        assert survivor.id == e2.id
        assert rest[0].id == e1.id

    def test_tiebreak_by_lexicographic_id(self) -> None:
        """Lexicographically smallest id wins when time ties."""
        now = datetime(2020, 1, 1, tzinfo=UTC)
        id_a = UUID("00000000-0000-0000-0000-000000000001")
        id_b = UUID("00000000-0000-0000-0000-000000000002")
        e_a = _entity(entity_id=id_a, created_at=now, name="a")
        e_b = _entity(entity_id=id_b, created_at=now, name="b")
        survivor, rest = select_canonical([e_b, e_a], None)
        assert survivor.id == id_a
        assert rest[0].id == id_b


class TestResolveProperty:
    """_resolve_property strategies."""

    def test_returns_single_distinct_no_conflict(self) -> None:
        """One distinct value is not a conflict."""
        value, conflicted = _resolve_property("title", ["a", "a", "a"], PropertyRules())
        assert value == "a"
        assert conflicted is False

    def test_returns_none_when_no_candidates(self) -> None:
        """Empty candidates returns None without conflict."""
        value, conflicted = _resolve_property("title", [], PropertyRules())
        assert value is None
        assert conflicted is False

    def test_dedupes_and_preserves_order(self) -> None:
        """Duplicate candidates are deduplicated before resolution."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("x", ["b", "a", "b", "a"], rules)
        # distinct is ["b", "a"] -> keep_first picks "b"
        assert value == "b"
        assert conflicted is True

    def test_keep_last(self) -> None:
        """KEEP_LAST picks the last distinct."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_LAST)
        value, conflicted = _resolve_property("f", ["first", "second"], rules)
        assert value == "second"
        assert conflicted is True

    def test_custom_rule_overrides_default(self) -> None:
        """Per-field custom rule is used instead of default."""

        def _upper(vals: list[object]) -> object:
            return "|".join(str(v).upper() for v in vals)

        rules = PropertyRules(rules={"f": _upper}, default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("f", ["a", "b"], rules)
        assert value == "A|B"
        assert conflicted is True

    def test_custom_rule_not_called_for_single_distinct(self) -> None:
        """Custom rule is not invoked when there is no conflict."""

        def _fail(vals: list[object]) -> object:
            raise AssertionError("should not be called")

        rules = PropertyRules(rules={"f": _fail})
        value, conflicted = _resolve_property("f", ["only", "only"], rules)
        assert value == "only"
        assert conflicted is False

    def test_list_valued_candidates_do_not_raise(self) -> None:
        """A list-valued candidate does not crash the hashable-only dedup path.

        Regression test: dict.fromkeys(candidates) raises TypeError for
        unhashable values such as a list, aborting the merge instead of
        resolving the field.
        """
        rules = PropertyRules(default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("tags", [["a", "b"], ["c"]], rules)
        assert value == ["a", "b"]
        assert conflicted is True

    def test_list_valued_duplicate_candidates_deduped_by_equality(self) -> None:
        """Equal list candidates collapse to one, not raise or duplicate."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("tags", [["a"], ["a"]], rules)
        assert value == ["a"]
        assert conflicted is False


class TestResolveDescription:
    """resolve_description LLM and fallback paths."""

    async def test_single_distinct_no_llm(self) -> None:
        """Single distinct candidate returns without LLM call."""

        class _FailClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise AssertionError("should not be called")

        value, conflicted, failure = await resolve_description(
            ["only one"], client=_FailClient()
        )
        assert value == "only one"
        assert conflicted is False
        assert failure is None

    async def test_multiple_distinct_with_mock_client_success(self) -> None:
        """Multiple distinct calls the mock client and returns its result."""

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                assert descriptions == ["d1", "d2"]
                assert baml_options == {}
                return "summarized"

        value, conflicted, failure = await resolve_description(
            ["d1", "d2"], client=MockClient()
        )
        assert value == "summarized"
        assert conflicted is True
        assert failure is None

    async def test_non_string_candidates_converted_before_summarization(self) -> None:
        """Non-string candidates are converted for the BAML string array."""

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                assert descriptions == ["42", "{'source': 'import'}"]
                assert all(isinstance(description, str) for description in descriptions)
                assert baml_options == {}
                return "summarized"

        value, conflicted, failure = await resolve_description(
            [42, {"source": "import"}], client=MockClient()
        )
        assert value == "summarized"
        assert conflicted is True
        assert failure is None

    async def test_multiple_distinct_with_failing_client_fallback(self) -> None:
        """Failing client falls back to concatenation and StageFailure."""

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("boom")

        value, conflicted, failure = await resolve_description(
            ["d1", "d2"], client=FailingClient()
        )
        assert value == "d1 | d2"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        assert failure.item_id == "description"
        assert failure.error_type == "RuntimeError"
        assert "boom" in failure.error_message

    async def test_dedupe_distinct_before_llm(self) -> None:
        """Duplicate descriptions are deduped before LLM call."""
        seen: list[list[object]] = []

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                seen.append(list(descriptions))
                return "ok"

        value, _, _ = await resolve_description(
            ["a", "b", "a", "b"], client=MockClient()
        )
        assert seen == [["a", "b"]]
        assert value == "ok"

    async def test_settings_path_success(self) -> None:
        """Settings path builds registry and calls default client."""
        settings = SimpleNamespace(
            clients=[LLMClientConfig(name="c", provider="openai", model="gpt-4o")],
            strategy="single",
            retry=RetryConfig(max_retries=0),
        )
        mock_registry = object()

        class MockDefaultClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                assert baml_options["client_registry"] is mock_registry
                return "via settings:" + "|".join(str(d) for d in descriptions)

        with (
            patch(
                "agrag.llm.client_registry.build_client_registry",
                return_value=mock_registry,
            ),
            patch("agrag.llm.baml_client.b", MockDefaultClient()),
        ):
            value, conflicted, failure = await resolve_description(
                ["a", "b"], client=None, settings=settings
            )
        assert value == "via settings:a|b"
        assert conflicted is True
        assert failure is None

    async def test_settings_path_baml_import_failure_fallback(self) -> None:
        """Missing baml extra falls back to concatenation."""
        settings = SimpleNamespace(
            clients=[LLMClientConfig(name="c", provider="openai", model="gpt-4o")],
            strategy="single",
            retry=RetryConfig(max_retries=0),
        )
        mock_registry = object()
        with (
            patch(
                "agrag.llm.client_registry.build_client_registry",
                return_value=mock_registry,
            ),
            patch.dict("sys.modules", {"agrag.llm.baml_client": None}),
        ):
            value, conflicted, failure = await resolve_description(
                ["x", "y"], client=None, settings=settings
            )
        assert value == "x | y"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        assert failure.error_type == "ImportError"


class TestResolveDescriptionSpans:
    """resolve_description opens a span only for multiple distinct candidates."""

    def _tracer(self, exporter: InMemorySpanExporter):
        """Build a tracer writing finished spans to exporter."""
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider.get_tracer("test")

    async def test_failing_client_links_failure_to_error_span(self) -> None:
        """The fallback join carries a StageFailure pointing at the ERROR span."""

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("boom")

        exporter = InMemorySpanExporter()
        value, conflicted, failure = await resolve_description(
            ["d1", "d2"],
            client=FailingClient(),
            tracer=self._tracer(exporter),
        )

        assert value == "d1 | d2"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        (span,) = [
            finished
            for finished in exporter.get_finished_spans()
            if finished.name == "agrag.merge.resolve_description"
        ]
        assert (span.attributes or {})["agrag.description_count"] == 2
        assert (span.attributes or {})["agrag.summarized"] is False
        assert span.status.status_code is StatusCode.ERROR
        assert failure.span_id == format(span.context.span_id, "016x")
        assert failure.trace_id == format(span.context.trace_id, "032x")

    async def test_single_candidate_opens_no_span(self) -> None:
        """One distinct candidate returns without opening the span."""
        exporter = InMemorySpanExporter()
        value, conflicted, failure = await resolve_description(
            ["only one"], client=AsyncMock(), tracer=self._tracer(exporter)
        )

        assert value == "only one"
        assert conflicted is False
        assert failure is None
        assert [
            finished
            for finished in exporter.get_finished_spans()
            if finished.name == "agrag.merge.resolve_description"
        ] == []

    async def test_success_marks_summarized(self) -> None:
        """A client summary marks the span summarized."""

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                return "summarized"

        exporter = InMemorySpanExporter()
        value, conflicted, failure = await resolve_description(
            ["d1", "d2"], client=MockClient(), tracer=self._tracer(exporter)
        )

        assert value == "summarized"
        assert conflicted is True
        assert failure is None
        (span,) = [
            finished
            for finished in exporter.get_finished_spans()
            if finished.name == "agrag.merge.resolve_description"
        ]
        assert (span.attributes or {})["agrag.description_count"] == 2
        assert (span.attributes or {})["agrag.summarized"] is True


class TestMergeProperties:
    """merge_properties with description and non-description fields."""

    async def test_description_field_uses_llm(self) -> None:
        """Description field is resolved via resolve_description."""

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions, baml_options
            ):
                return "merged desc"

        props, conflicts, failures = await merge_properties(
            [{"description": "d1"}, {"description": "d2"}],
            PropertyRules(),
            description_client=MockClient(),
        )
        assert props["description"] == "merged desc"
        assert len(conflicts) == 1
        assert conflicts[0].field == "description"
        assert failures == []

    async def test_non_description_conflict_recorded(self) -> None:
        """Non-description conflicts are recorded."""
        props, conflicts, failures = await merge_properties(
            [{"role": "a"}, {"role": "b"}],
            PropertyRules(default=PropertyStrategy.KEEP_LAST),
        )
        assert props["role"] == "b"
        assert len(conflicts) == 1
        assert conflicts[0].field == "role"
        assert conflicts[0].candidates == ["a", "b"]
        assert conflicts[0].resolved == "b"
        assert failures == []

    async def test_no_conflict_no_record(self) -> None:
        """Same value across sources is not a conflict."""
        props, conflicts, failures = await merge_properties(
            [{"role": "a"}, {"role": "a"}],
            PropertyRules(),
        )
        assert props["role"] == "a"
        assert conflicts == []
        assert failures == []

    async def test_conflict_with_description_failure(self) -> None:
        """Description LLM failure still records conflict and failure."""

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("fail")

        props, conflicts, failures = await merge_properties(
            [{"description": "d1"}, {"description": "d2"}],
            PropertyRules(),
            description_client=FailingClient(),
        )
        assert props["description"] == "d1 | d2"
        assert len(conflicts) == 1
        assert len(failures) == 1
        assert failures[0].item_id == "description"


class TestComputeMerge:
    """compute_merge behavior."""

    async def test_returns_new_id_when_no_existing(self) -> None:
        """Zero existing creates a new id."""
        mention = _mention(text="Ada")
        plan, failures = await compute_merge(
            existing_entities=[],
            mentions=[mention],
            schema=_schema(),
        )
        assert isinstance(plan.survivor.id, UUID)
        assert plan.survivor.name == "Ada"
        assert mention.chunk_id in plan.survivor.source_chunk_ids
        assert failures == []

    async def test_job_id_replays_same_survivor_id(self) -> None:
        """Same job id replays the same new-entity id."""
        job_id = uuid4()
        plan_a, _ = await compute_merge(
            existing_entities=[],
            mentions=[_mention(text="Ada")],
            schema=_schema(),
            job_id=job_id,
        )
        plan_b, _ = await compute_merge(
            existing_entities=[],
            mentions=[_mention(text="Ada")],
            schema=_schema(),
            job_id=job_id,
        )
        expected = uuid5(
            NAMESPACE_OID, f"CutoverJob:{job_id}:{plan_a.survivor.merge_key}"
        )
        assert plan_a.survivor.id == plan_b.survivor.id == expected

    async def test_different_job_ids_mint_different_ids(self) -> None:
        """Different job ids mint different new-entity ids."""
        plan_a, _ = await compute_merge(
            existing_entities=[],
            mentions=[_mention(text="Ada")],
            schema=_schema(),
            job_id=uuid4(),
        )
        plan_b, _ = await compute_merge(
            existing_entities=[],
            mentions=[_mention(text="Ada")],
            schema=_schema(),
            job_id=uuid4(),
        )
        assert plan_a.survivor.id != plan_b.survivor.id

    async def test_job_id_keeps_existing_id(self) -> None:
        """A job id never overrides an existing entity's id."""
        existing = _entity(name="Ada")
        plan, _ = await compute_merge(
            existing_entities=[existing],
            mentions=[_mention(text="Ada")],
            schema=_schema(),
            job_id=uuid4(),
        )
        assert plan.survivor.id == existing.id

    async def test_keeps_id_when_one_existing(self) -> None:
        """One existing keeps its id."""
        existing = _entity(name="Ada")
        mention = _mention(text="Ada")
        plan, _ = await compute_merge(
            existing_entities=[existing],
            mentions=[mention],
            schema=_schema(),
        )
        assert plan.survivor.id == existing.id
        # created_at preserved
        assert plan.survivor.created_at == existing.created_at

    async def test_mention_properties_reach_the_survivor(self) -> None:
        """A fresh mention's schema-declared properties reach the survivor.

        Regression test: field_sources used to build a mention's row from
        only its text, so a property an extractor reported on the mention
        itself (not on any existing entity) was silently dropped before
        field-level merge ever saw it.
        """
        mention = _mention(text="Ada", properties={"role": "engineer"})
        plan, _ = await compute_merge(
            existing_entities=[],
            mentions=[mention],
            schema=_schema(properties={"role": "str"}),
        )
        assert plan.survivor.properties["role"] == "engineer"

    async def test_mismatched_labels_raise(self) -> None:
        """Mismatched labels raise ValueError."""
        e = _entity(label="Person", name="Ada")
        m = _mention(label="Organization", text="Ada")
        with pytest.raises(ValueError, match="share one label"):
            await compute_merge(existing_entities=[e], mentions=[m], schema=_schema())

    async def test_existing_mismatched_labels_raise(self) -> None:
        """Two existing with different labels raise."""
        e1 = _entity(label="Person", name="Ada")
        e2 = _entity(label="Organization", name="Ada")
        with pytest.raises(ValueError, match="share one label"):
            await compute_merge(
                existing_entities=[e1, e2], mentions=[], schema=_schema()
            )

    async def test_both_empty_raise(self) -> None:
        """Both empty raises."""
        with pytest.raises(ValueError, match="at least one"):
            await compute_merge(existing_entities=[], mentions=[], schema=_schema())

    async def test_merge_all_default_keeps_canonical_name(self) -> None:
        """MERGE_ALL as default still resolves the name to the canonical name."""
        e1 = _entity(name="Ada")
        e2 = _entity(name="Bob")
        e1.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        e2.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        plan, _ = await compute_merge(
            existing_entities=[e2, e1],
            mentions=[],
            schema=_schema(),
            rules=PropertyRules(default=PropertyStrategy.MERGE_ALL),
        )
        assert plan.survivor.name == "Ada"

    async def test_merge_all_default_keeps_empty_canonical_name(self) -> None:
        """MERGE_ALL preserves an explicitly empty canonical name."""
        canonical = _entity(name="")
        other = _entity(name="Ada")
        canonical.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        other.created_at = datetime(2020, 1, 2, tzinfo=UTC)

        plan, _ = await compute_merge(
            existing_entities=[other, canonical],
            mentions=[],
            schema=_schema(),
            rules=PropertyRules(default=PropertyStrategy.MERGE_ALL),
        )

        assert plan.survivor.name == ""

    async def test_merge_count_at_least_one(self) -> None:
        """merge_count is at least 1 even with zero."""
        e = _entity(name="Ada", merge_count=0)
        plan, _ = await compute_merge(
            existing_entities=[e], mentions=[], schema=_schema()
        )
        assert plan.survivor.merge_count == 1

    async def test_source_chunk_ids_accumulation(self) -> None:
        """source_chunk_ids merges the existing entity's ids and mentions."""
        c1, c3 = uuid4(), uuid4()
        e1 = _entity(name="Ada", source_chunk_ids=[c1], merge_count=1)
        m = _mention(text="Ada", chunk_id=c3)
        plan, _ = await compute_merge(
            existing_entities=[e1], mentions=[m], schema=_schema()
        )
        assert plan.survivor.source_chunk_ids == [c1, c3]

    async def test_merge_all_property(self) -> None:
        """MERGE_ALL returns list for conflicting property."""
        e1 = _entity(name="Ada", properties={"role": "a"})
        e2 = _entity(name="Ada", properties={"role": "b"})
        plan, _ = await compute_merge(
            existing_entities=[e1, e2],
            mentions=[],
            schema=_schema(),
            rules=PropertyRules(default=PropertyStrategy.MERGE_ALL),
        )
        assert plan.survivor.properties["role"] == ["a", "b"]

    async def test_description_llm_path_failure_returned(self) -> None:
        """Description LLM failure is returned as StageFailure."""

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("llm fail")

        e1 = _entity(name="Ada", properties={"description": "d1"})
        e2 = _entity(name="Ada", properties={"description": "d2"})
        plan, failures = await compute_merge(
            existing_entities=[e1, e2],
            mentions=[],
            schema=_schema(),
            description_client=FailingClient(),
        )
        assert plan.survivor.properties["description"] == "d1 | d2"
        assert len(failures) == 1
        assert failures[0].error_type == "RuntimeError"

    async def test_schema_completeness_affects_survivor(self) -> None:
        """Schema completeness influences survivor choice."""
        schema = _schema(properties={"a": "str", "b": "str", "c": "str"})
        e_full = _entity(name="Ada", properties={"a": "1", "b": "2", "c": "3"})
        e_partial = _entity(name="Ada", properties={"a": "1"})
        # e_full is more complete, should be survivor even if later
        e_full.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        e_partial.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        plan, _ = await compute_merge(
            existing_entities=[e_partial, e_full],
            mentions=[],
            schema=schema,
        )
        assert plan.survivor.id == e_full.id

    async def test_accepted_merge_keys_includes_every_accepted_name(self) -> None:
        """accepted_merge_keys covers every name this merge folded in.

        Regression test: apply_merge only wrote an alias for the survivor's
        own chosen name. When resolution joins two different names (for
        example "Bob" and "Robert" fuzzy/LLM-matched into one group), a
        later mention of the non-canonical name found no alias and created
        a duplicate entity instead of resolving back to the same one.
        """
        mention = _mention(text="Bob")
        plan, _ = await compute_merge(
            existing_entities=[],
            mentions=[_mention(text="Robert"), mention],
            schema=_schema(),
        )
        assert "Person:robert" in plan.accepted_merge_keys
        assert "Person:bob" in plan.accepted_merge_keys

    async def test_accepted_merge_keys_includes_every_existing_name(self) -> None:
        """Every existing entity's own name is also an accepted key."""
        e1 = _entity(name="Ada")
        e2 = _entity(name="Ada Lovelace")
        plan, _ = await compute_merge(
            existing_entities=[e1, e2], mentions=[], schema=_schema()
        )
        assert e1.merge_key in plan.accepted_merge_keys
        assert e2.merge_key in plan.accepted_merge_keys

    async def test_new_source_chunk_ids_excludes_survivor_bases_own(self) -> None:
        """new_source_chunk_ids is this call's contribution, not the full union.

        apply_merge writes this atomically against whatever the survivor's
        node currently has, so it must not include the existing entity's own
        chunk ids -- those are already persisted and would be double-applied
        (harmlessly, since the DB union is idempotent, but the value should
        still reflect only what is new).
        """
        existing_cid = uuid4()
        new_cid = uuid4()
        existing = _entity(name="Ada", source_chunk_ids=[existing_cid])
        mention = _mention(text="Ada", chunk_id=new_cid)
        plan, _ = await compute_merge(
            existing_entities=[existing], mentions=[mention], schema=_schema()
        )
        assert plan.new_source_chunk_ids == [new_cid]
        assert existing_cid not in plan.new_source_chunk_ids
        # The survivor's own field still reports the full union, for reporting.
        assert existing_cid in plan.survivor.source_chunk_ids

    async def test_merge_count_delta_is_the_new_contribution_only(self) -> None:
        """merge_count_delta is what this call adds, not the resulting total."""
        existing = _entity(name="Ada", merge_count=5)
        plan, _ = await compute_merge(
            existing_entities=[existing],
            mentions=[_mention(text="Ada"), _mention(text="Ada")],
            schema=_schema(),
        )
        assert plan.merge_count_delta == 2
        # The survivor's own field still reports the full total, for reporting.
        assert plan.survivor.merge_count == 7


class TestRelationId:
    """relation_id deterministic ids.

    Regression coverage for concurrent ingestion of the same domain
    relation triple: two callers that both miss the existing-relation
    lookup must compute the same id here, or their upserts create two
    parallel edges instead of converging on one (see relation_id_constraint_query,
    which only enforces uniqueness of id within a type, not of the triple).
    """

    def test_deterministic(self) -> None:
        """Same triple returns same id, matching what a concurrent miss needs."""
        s, t = uuid4(), uuid4()
        assert relation_id(s, t, "KNOWS") == relation_id(s, t, "KNOWS")

    def test_different_types_differ(self) -> None:
        """Same endpoints, different type, differs."""
        s, t = uuid4(), uuid4()
        assert relation_id(s, t, "KNOWS") != relation_id(s, t, "WORKS_AT")

    def test_direction_matters(self) -> None:
        """Swapped source/target differs, since the relation is directed."""
        s, t = uuid4(), uuid4()
        assert relation_id(s, t, "KNOWS") != relation_id(t, s, "KNOWS")


class TestMentionedInId:
    """mentioned_in_id deterministic ids."""

    def test_deterministic(self) -> None:
        """Same pair returns same id."""
        c, e = uuid4(), uuid4()
        assert mentioned_in_id(c, e) == mentioned_in_id(c, e)

    def test_different_pairs(self) -> None:
        """Different pairs produce different ids."""
        c1, c2 = uuid4(), uuid4()
        e1, e2 = uuid4(), uuid4()
        assert mentioned_in_id(c1, e1) != mentioned_in_id(c1, e2)
        assert mentioned_in_id(c1, e1) != mentioned_in_id(c2, e1)
        assert mentioned_in_id(c1, e1) != mentioned_in_id(e2, c1)


class TestNextChunkId:
    """next_chunk_id deterministic ids."""

    def test_deterministic(self) -> None:
        """Same ordered pair always returns the same id."""
        a, b = uuid4(), uuid4()
        assert next_chunk_id(a, b) == next_chunk_id(a, b)


class TestPartOfId:
    """part_of_id versioned deterministic ids."""

    def test_deterministic_for_same_version(self) -> None:
        """Same triple always returns the same id."""
        d, c = uuid4(), uuid4()
        assert part_of_id(d, c, "v1") == part_of_id(d, c, "v1")

    def test_distinct_versions_differ(self) -> None:
        """Each document version gets a separate relationship id."""
        d, c = uuid4(), uuid4()
        assert part_of_id(d, c, "v1") != part_of_id(d, c, "v2")
