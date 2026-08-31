"""Tests for merge mechanics."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_OID, UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.ingestion.merge import (
    MergePlan,
    PropertyRules,
    PropertyStrategy,
    _merge_properties,
    _plan_relationship_dedup,
    _resolve_description,
    _resolve_property,
    _select_canonical,
    _TransferredRelationship,
    apply_merge,
    compute_merge,
    mentioned_in_id,
)
from agrag.ingestion.types import StageFailure
from agrag.llm.client_config import LLMClientConfig, RetryConfig


def _entity(
    *,
    label: str = "Person",
    name: str = "Ada",
    properties: dict[str, object] | None = None,
    entity_id: UUID | None = None,
    created_at: datetime | None = None,
    merged_from: list[UUID] | None = None,
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
        merged_from=merged_from or [],
        merge_count=merge_count,
        source_chunk_ids=source_chunk_ids or [],
    )


def _mention(
    text: str = "Ada",
    label: str = "Person",
    chunk_id: UUID | None = None,
) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    return ExtractedEntity(
        chunk_id=chunk_id or uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text) or 1,
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


class TestPropertyStrategyAndRules:
    """PropertyStrategy and PropertyRules defaults."""

    def test_strategy_values(self) -> None:
        """Strategy enum values are stable strings."""
        assert PropertyStrategy.KEEP_FIRST == "keep_first"
        assert PropertyStrategy.KEEP_LAST == "keep_last"
        assert PropertyStrategy.MERGE_ALL == "merge_all"

    def test_rules_defaults(self) -> None:
        """Default rules are empty with keep_first."""
        rules = PropertyRules()
        assert rules.rules == {}
        assert rules.default is PropertyStrategy.KEEP_FIRST

    def test_custom_rules_store(self) -> None:
        """Custom rules store the resolver."""

        def _resolver(vals: list[object]) -> object:
            return vals[0]

        rules = PropertyRules(
            rules={"title": _resolver}, default=PropertyStrategy.MERGE_ALL
        )
        assert rules.rules["title"] is _resolver
        assert rules.default is PropertyStrategy.MERGE_ALL


class TestSelectCanonical:
    """_select_canonical tiebreaks."""

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
        survivor, rest = _select_canonical([e1, e2, e3], schema_type)
        assert survivor.id == e3.id
        assert {r.id for r in rest} == {e1.id, e2.id}

    def test_tiebreak_by_created_at(self) -> None:
        """Earlier created_at wins when completeness ties."""
        t1 = datetime(2020, 1, 1, tzinfo=UTC)
        t2 = datetime(2020, 1, 2, tzinfo=UTC)
        e1 = _entity(name="later", created_at=t2, properties={})
        e2 = _entity(name="earlier", created_at=t1, properties={})
        survivor, rest = _select_canonical([e1, e2], None)
        assert survivor.id == e2.id
        assert rest[0].id == e1.id

    def test_tiebreak_by_lexicographic_id(self) -> None:
        """Lexicographically smallest id wins when time ties."""
        now = datetime(2020, 1, 1, tzinfo=UTC)
        id_a = UUID("00000000-0000-0000-0000-000000000001")
        id_b = UUID("00000000-0000-0000-0000-000000000002")
        e_a = _entity(entity_id=id_a, created_at=now, name="a")
        e_b = _entity(entity_id=id_b, created_at=now, name="b")
        survivor, rest = _select_canonical([e_b, e_a], None)
        assert survivor.id == id_a
        assert rest[0].id == id_b

    def test_no_schema_uses_created_at_and_id(self) -> None:
        """With no entity_type, ranking falls back to time and id."""
        now = datetime(2020, 1, 1, tzinfo=UTC)
        e1 = _entity(created_at=now, name="x")
        e2 = _entity(created_at=now + timedelta(seconds=1), name="y")
        survivor, _ = _select_canonical([e2, e1], None)
        assert survivor.id == e1.id


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

    def test_keep_first(self) -> None:
        """KEEP_FIRST picks the first distinct."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("f", ["first", "second"], rules)
        assert value == "first"
        assert conflicted is True

    def test_keep_last(self) -> None:
        """KEEP_LAST picks the last distinct."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_LAST)
        value, conflicted = _resolve_property("f", ["first", "second"], rules)
        assert value == "second"
        assert conflicted is True

    def test_merge_all_returns_list(self) -> None:
        """MERGE_ALL returns the distinct list."""
        rules = PropertyRules(default=PropertyStrategy.MERGE_ALL)
        value, conflicted = _resolve_property("f", ["a", "b", "c"], rules)
        assert value == ["a", "b", "c"]
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

    def test_no_conflict_single_value(self) -> None:
        """Single candidate is returned without conflict."""
        value, conflicted = _resolve_property("f", ["x"], PropertyRules())
        assert value == "x"
        assert conflicted is False


class TestResolveDescription:
    """_resolve_description LLM and fallback paths."""

    async def test_single_distinct_no_llm(self) -> None:
        """Single distinct candidate returns without LLM call."""

        class _FailClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise AssertionError("should not be called")

        value, conflicted, failure = await _resolve_description(
            ["only one"], client=_FailClient()
        )
        assert value == "only one"
        assert conflicted is False
        assert failure is None

    async def test_single_distinct_empty_no_conflict(self) -> None:
        """Empty candidates returns None without conflict."""
        value, conflicted, failure = await _resolve_description([], client=AsyncMock())
        assert value is None
        assert conflicted is False
        assert failure is None

    async def test_multiple_distinct_with_mock_client_success(self) -> None:
        """Multiple distinct calls the mock client and returns its result."""

        class MockClient:
            async def SummarizeDescriptions(self, descs, baml_options):  # noqa: N802
                assert descs == ["d1", "d2"]
                assert baml_options == {}
                return "summarized"

        value, conflicted, failure = await _resolve_description(
            ["d1", "d2"], client=MockClient()
        )
        assert value == "summarized"
        assert conflicted is True
        assert failure is None

    async def test_multiple_distinct_success_via_keyword_fallback(self) -> None:
        """Positional TypeError falls back to keyword call."""

        class MockClient:
            async def SummarizeDescriptions(  # noqa: N802
                self, *, descriptions, baml_options
            ):
                return "kw:" + "|".join(descriptions)

        value, conflicted, failure = await _resolve_description(
            ["a", "b"], client=MockClient()
        )
        assert value == "kw:a|b"
        assert conflicted is True
        assert failure is None

    async def test_multiple_distinct_with_singular_method(self) -> None:
        """Fallback to SummarizeDescription when plural missing."""

        class MockClient:
            async def SummarizeDescription(self, descs, baml_options):  # noqa: N802
                return "singular:" + descs[0]

        value, conflicted, failure = await _resolve_description(
            ["x", "y"], client=MockClient()
        )
        assert value == "singular:x"
        assert conflicted is True
        assert failure is None

    async def test_multiple_distinct_with_failing_client_fallback(self) -> None:
        """Failing client falls back to concatenation and StageFailure."""

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("boom")

        value, conflicted, failure = await _resolve_description(
            ["d1", "d2"], client=FailingClient()
        )
        assert value == "d1 | d2"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        assert failure.item_id == "description"
        assert failure.error_type == "RuntimeError"
        assert "boom" in failure.error_message

    async def test_missing_baml_function_fallback(self) -> None:
        """No summarization function triggers fallback."""

        class EmptyClient:
            pass

        value, conflicted, failure = await _resolve_description(
            ["a", "b"], client=EmptyClient()
        )
        assert value == "a | b"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        assert failure.error_type == "AttributeError"

    async def test_settings_path_raises_validation_error_fallback(self) -> None:
        """Settings ValidationError falls back to concatenation."""
        with patch(
            "agrag.ingestion.extract.ExtractionLLMSettings",
            side_effect=ValidationError.from_exception_data(
                "ExtractionLLMSettings", []
            ),
        ):
            value, conflicted, failure = await _resolve_description(
                ["x", "y"], client=None, settings=None
            )
        assert value == "x | y"
        assert conflicted is True
        assert isinstance(failure, StageFailure)

    async def test_default_client_missing_summarize_fallback(self) -> None:
        """Default baml client without summarize falls back."""
        # b has no SummarizeDescriptions, so it should fallback
        value, conflicted, failure = await _resolve_description(
            ["a", "b"], client=None, settings=None
        )
        # Either ValidationError path or missing function path, both fallback
        assert value == "a | b"
        assert conflicted is True
        assert isinstance(failure, StageFailure)

    async def test_dedupe_distinct_before_llm(self) -> None:
        """Duplicate descriptions are deduped before LLM call."""
        seen: list[list[object]] = []

        class MockClient:
            async def SummarizeDescriptions(self, descs, baml_options):  # noqa: N802
                seen.append(list(descs))
                return "ok"

        value, _, _ = await _resolve_description(
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
            async def SummarizeDescriptions(self, descs, baml_options):  # noqa: N802
                assert baml_options["client_registry"] is mock_registry
                return "via settings:" + "|".join(str(d) for d in descs)

        with (
            patch(
                "agrag.llm.client_registry.build_client_registry",
                return_value=mock_registry,
            ),
            patch("agrag.llm.baml_client.b", MockDefaultClient()),
        ):
            value, conflicted, failure = await _resolve_description(
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
            value, conflicted, failure = await _resolve_description(
                ["x", "y"], client=None, settings=settings
            )
        assert value == "x | y"
        assert conflicted is True
        assert isinstance(failure, StageFailure)
        assert failure.error_type == "ImportError"

    async def test_fallback_stage_failure_import_error(self) -> None:
        """StageFailure import failure returns fallback without failure."""
        # patch sys.modules to make agrag.ingestion.types import fail

        class FailingClient:
            async def SummarizeDescriptions(self, *args, **kwargs):  # noqa: N802
                raise RuntimeError("boom")

        with patch.dict("sys.modules", {"agrag.ingestion.types": None}):
            value, conflicted, failure = await _resolve_description(
                ["a", "b"], client=FailingClient()
            )
        assert value == "a | b"
        assert conflicted is True
        assert failure is None


class TestMergeProperties:
    """_merge_properties with description and non-description fields."""

    async def test_description_field_uses_llm(self) -> None:
        """Description field is resolved via _resolve_description."""

        class MockClient:
            async def SummarizeDescriptions(self, descs, baml_options):  # noqa: N802
                return "merged desc"

        props, conflicts, failures = await _merge_properties(
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
        props, conflicts, failures = await _merge_properties(
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
        props, conflicts, failures = await _merge_properties(
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

        props, conflicts, failures = await _merge_properties(
            [{"description": "d1"}, {"description": "d2"}],
            PropertyRules(),
            description_client=FailingClient(),
        )
        assert props["description"] == "d1 | d2"
        assert len(conflicts) == 1
        assert len(failures) == 1
        assert failures[0].item_id == "description"

    async def test_multiple_fields_mixed(self) -> None:
        """Multiple fields with mixed conflict and non-conflict."""
        props, conflicts, _ = await _merge_properties(
            [
                {"name": "Ada", "role": "eng", "description": "d1"},
                {"name": "Ada", "role": "eng", "description": "d1"},
            ],
            PropertyRules(),
        )
        # name same, role same, description same -> no conflicts
        assert props["name"] == "Ada"
        assert conflicts == []


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
        assert plan.tombstone_ids == []
        assert plan.survivor.name == "Ada"
        assert mention.chunk_id in plan.survivor.source_chunk_ids
        assert failures == []

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
        assert plan.tombstone_ids == []
        # created_at preserved
        assert plan.survivor.created_at == existing.created_at

    async def test_picks_survivor_when_two_existing(self) -> None:
        """Two existing picks canonical survivor."""
        t1 = datetime(2020, 1, 1, tzinfo=UTC)
        t2 = datetime(2020, 1, 2, tzinfo=UTC)
        e1 = _entity(name="Ada", created_at=t2, properties={})
        e2 = _entity(name="Ada", created_at=t1, properties={})
        plan, _ = await compute_merge(
            existing_entities=[e1, e2],
            mentions=[],
            schema=_schema(),
        )
        assert plan.survivor.id == e2.id
        assert plan.tombstone_ids == [e1.id]

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

    async def test_name_not_str_raise(self) -> None:
        """Resolved name not str raises."""
        e1 = _entity(name="Ada")
        e2 = _entity(name="Bob")
        # MERGE_ALL will make name a list -> not str
        with pytest.raises(ValueError, match="Resolved name must be str"):
            await compute_merge(
                existing_entities=[e1, e2],
                mentions=[],
                schema=_schema(),
                rules=PropertyRules(default=PropertyStrategy.MERGE_ALL),
            )

    async def test_merge_count_accumulation(self) -> None:
        """merge_count accumulates from survivor, absorbed, and mentions."""
        e1 = _entity(name="Ada", merge_count=2)
        e2 = _entity(name="Ada", merge_count=3)
        mentions = [_mention(text="Ada"), _mention(text="Ada")]
        # Ensure e1 is survivor (earlier created_at)
        e1.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        e2.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        plan, _ = await compute_merge(
            existing_entities=[e1, e2],
            mentions=mentions,
            schema=_schema(),
        )
        # survivor base 2 + absorbed 3 + 2 mentions = 7
        assert plan.survivor.merge_count == 7

    async def test_merge_count_at_least_one(self) -> None:
        """merge_count is at least 1 even with zero."""
        e = _entity(name="Ada", merge_count=0)
        plan, _ = await compute_merge(
            existing_entities=[e], mentions=[], schema=_schema()
        )
        assert plan.survivor.merge_count == 1

    async def test_source_chunk_ids_accumulation(self) -> None:
        """source_chunk_ids merges survivor, absorbed, and mentions."""
        c1, c2, c3 = uuid4(), uuid4(), uuid4()
        e1 = _entity(name="Ada", source_chunk_ids=[c1], merge_count=1)
        e2 = _entity(name="Ada", source_chunk_ids=[c2], merge_count=1)
        # make e1 survivor
        e1.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        e2.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        m = _mention(text="Ada", chunk_id=c3)
        plan, _ = await compute_merge(
            existing_entities=[e1, e2], mentions=[m], schema=_schema()
        )
        assert plan.survivor.source_chunk_ids == [c1, c2, c3]

    async def test_merged_from_accumulation(self) -> None:
        """merged_from accumulates survivor merged_from plus absorbed ids."""
        absorbed_id = uuid4()
        survivor = _entity(
            name="Ada",
            merged_from=[uuid4()],
            merge_count=1,
        )
        absorbed = _entity(entity_id=absorbed_id, name="Ada", merge_count=1)
        survivor.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        absorbed.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        plan, _ = await compute_merge(
            existing_entities=[survivor, absorbed],
            mentions=[],
            schema=_schema(),
        )
        assert absorbed_id in plan.survivor.merged_from
        assert survivor.merged_from[0] in plan.survivor.merged_from

    async def test_merged_from_dedupes(self) -> None:
        """merged_from deduplicates while preserving order."""
        dup = uuid4()
        e1 = _entity(name="Ada", merged_from=[dup])
        e2 = _entity(entity_id=dup, name="Ada")
        e1.created_at = datetime(2020, 1, 1, tzinfo=UTC)
        e2.created_at = datetime(2020, 1, 2, tzinfo=UTC)
        plan, _ = await compute_merge(
            existing_entities=[e1, e2], mentions=[], schema=_schema()
        )
        # dup should appear only once
        assert plan.survivor.merged_from.count(dup) == 1

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

    async def test_description_llm_path_success(self) -> None:
        """Description LLM path succeeds via compute_merge."""

        class MockClient:
            async def SummarizeDescriptions(self, descs, baml_options):  # noqa: N802
                return "summarized desc"

        e1 = _entity(name="Ada", properties={"description": "d1"})
        e2 = _entity(name="Ada", properties={"description": "d2"})
        plan, failures = await compute_merge(
            existing_entities=[e1, e2],
            mentions=[],
            schema=_schema(),
            description_client=MockClient(),
        )
        assert plan.survivor.properties["description"] == "summarized desc"
        assert failures == []
        assert any(c.field == "description" for c in plan.conflicts)

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

    async def test_conflict_recording(self) -> None:
        """Conflicts are recorded for differing properties."""
        e1 = _entity(name="Ada", properties={"role": "a"})
        e2 = _entity(name="Ada", properties={"role": "b"})
        plan, _ = await compute_merge(
            existing_entities=[e1, e2],
            mentions=[],
            schema=_schema(),
        )
        assert len(plan.conflicts) == 1
        assert plan.conflicts[0].field == "role"

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


class TestPlanRelationshipDedup:
    """_plan_relationship_dedup grouping."""

    def test_group_of_one_returns_empty(self) -> None:
        """Single row in a group produces no updates."""
        r = _TransferredRelationship(
            other_id=uuid4(),
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates, delete_ids = _plan_relationship_dedup([r])
        assert updates == []
        assert delete_ids == []

    def test_group_of_two_merges_chunk_ids(self) -> None:
        """Two rows with same type and other merges chunk ids."""
        other = uuid4()
        c1, c2, c3 = uuid4(), uuid4(), uuid4()
        r1 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[c1, c2],
        )
        r2 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[c2, c3],
        )
        updates, delete_ids = _plan_relationship_dedup([r1, r2])
        assert len(updates) == 1
        assert updates[0]["id"] == str(r1.new_relationship_id)
        # deduped, order preserved: c1, c2, c3
        assert updates[0]["source_chunk_ids"] == [
            str(c1),
            str(c2),
            str(c3),
        ]
        assert delete_ids == [r2.new_relationship_id]

    def test_separate_groups_by_type(self) -> None:
        """Different rel_type creates separate groups."""
        other = uuid4()
        r1 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r2 = _TransferredRelationship(
            other_id=other,
            rel_type="WORKS_AT",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates, delete_ids = _plan_relationship_dedup([r1, r2])
        assert updates == []
        assert delete_ids == []

    def test_separate_groups_by_other_id(self) -> None:
        """Different other_id creates separate groups."""
        r1 = _TransferredRelationship(
            other_id=uuid4(),
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r2 = _TransferredRelationship(
            other_id=uuid4(),
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates, delete_ids = _plan_relationship_dedup([r1, r2])
        assert updates == []
        assert delete_ids == []

    def test_multiple_groups_mixed(self) -> None:
        """Multiple duplicate groups each produce an update."""
        other_a, other_b = uuid4(), uuid4()
        r1 = _TransferredRelationship(
            other_id=other_a,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r2 = _TransferredRelationship(
            other_id=other_a,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r3 = _TransferredRelationship(
            other_id=other_b,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r4 = _TransferredRelationship(
            other_id=other_b,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates, delete_ids = _plan_relationship_dedup([r1, r2, r3, r4])
        assert len(updates) == 2
        assert len(delete_ids) == 2

    def test_outgoing_vs_incoming_separate(self) -> None:
        """Caller separates outgoing and incoming; dedup does not mix them.

        Simulate two directions: the same other_id and type in different
        directions are handled in separate calls, so no cross-direction merge.
        """
        other = uuid4()
        # Outgoing group
        r_out1 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        r_out2 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates_out, _ = _plan_relationship_dedup([r_out1, r_out2])
        # Incoming group separately
        r_in1 = _TransferredRelationship(
            other_id=other,
            rel_type="KNOWS",
            new_relationship_id=uuid4(),
            source_chunk_ids=[uuid4()],
        )
        updates_in, _ = _plan_relationship_dedup([r_in1])
        assert len(updates_out) == 1
        assert updates_in == []


class TestApplyMerge:
    """apply_merge writes to GraphStore."""

    async def test_zero_tombstones_only_upserts(self) -> None:
        """No tombstones only upserts survivor."""
        survivor = _entity(name="Ada")
        plan = MergePlan(survivor=survivor, tombstone_ids=[], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()
        store.execute_write = AsyncMock()
        await apply_merge(plan, graph_store=store, schema=_schema())
        store.upsert_nodes.assert_awaited_once()
        args, _ = store.upsert_nodes.call_args
        assert args[0] == survivor.label
        store.execute_write.assert_not_awaited()

    async def test_one_existing_only_upserts(self) -> None:
        """Plan with no tombstones still only upserts."""
        survivor = _entity(name="Bob")
        plan = MergePlan(survivor=survivor, tombstone_ids=[], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()
        store.execute_write = AsyncMock()
        await apply_merge(plan, graph_store=store, schema=_schema())
        store.upsert_nodes.assert_awaited_once()
        store.execute_write.assert_not_awaited()

    async def test_two_plus_does_tombstone_and_transfer(self) -> None:
        """Two-plus performs tombstone, transfer, and dedup."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        other = uuid4()
        c1, c2 = uuid4(), uuid4()
        new_r1 = uuid4()
        new_r2 = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()

        async def _exec_write(query, params=None):
            # tombstone query
            if "merged_into" in query:
                return []
            # transfer queries
            if (
                ("CREATE (survivor)" in query or "CREATE (other)" in query)
                and params
                and params.get("tombstone_id") == str(tombstone)
            ):
                # Outgoing has "MATCH (tombstone" first
                if "MATCH (tombstone" in query:
                    return [
                        {
                            "other_id": str(other),
                            "rel_type": "KNOWS",
                            "new_relationship_id": str(new_r1),
                            "source_chunk_ids": [str(c1)],
                        },
                        {
                            "other_id": str(other),
                            "rel_type": "KNOWS",
                            "new_relationship_id": str(new_r2),
                            "source_chunk_ids": [str(c2)],
                        },
                    ]
                return []
            if "UNWIND $updates" in query:
                return []
            if "UNWIND $delete_ids" in query:
                return []
            return []

        store.execute_write = AsyncMock(side_effect=_exec_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        # upsert + tombstone + 2 transfers + dedup update + dedup delete
        assert store.upsert_nodes.await_count == 1
        # At least tombstone and one transfer should have been called
        assert store.execute_write.await_count >= 3
        # Check tombstone called with correct ids
        calls = [c.args[1] for c in store.execute_write.call_args_list]
        tombstone_call = next((p for p in calls if "tombstone_ids" in p), None)
        assert tombstone_call is not None
        assert tombstone_call["tombstone_ids"] == [str(tombstone)]

    async def test_handles_row_parsing_errors(self) -> None:
        """Malformed rows are skipped."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()

        async def _exec_write(query, params=None):
            if "merged_into" in query:
                return []
            if "MATCH (tombstone" in query or "MATCH (other)" in query:
                return [
                    {"bad": "row"},
                    {
                        "other_id": "not-a-uuid",
                        "rel_type": "X",
                        "new_relationship_id": "also-bad",
                    },
                    {
                        "other_id": str(uuid4()),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(uuid4()),
                        "source_chunk_ids": ["not-a-uuid"],
                    },
                ]
            if "UNWIND $updates" in query:
                return []
            if "UNWIND $delete_ids" in query:
                return []
            return []

        store.execute_write = AsyncMock(side_effect=_exec_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        # Should not raise, and no dedup updates because all rows bad
        assert store.upsert_nodes.await_count == 1

    async def test_transfer_handles_partial_bad_rows(self) -> None:
        """One good row and one bad row results in single-row group (no dedup)."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()
        other = uuid4()
        good_id = uuid4()
        c1 = uuid4()

        async def _exec_write(query, params=None):
            if "merged_into" in query:
                return []
            if "CREATE (survivor)" in query:
                return [
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(good_id),
                        "source_chunk_ids": [str(c1)],
                    },
                    {
                        "other_id": "bad",
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(uuid4()),
                        "source_chunk_ids": [],
                    },
                ]
            if "CREATE (other)" in query:
                return []
            if "UNWIND" in query:
                return []
            return []

        store.execute_write = AsyncMock(side_effect=_exec_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        # Only one good row -> no dedup
        dedup_calls = [
            c
            for c in store.execute_write.call_args_list
            if "UNWIND $updates" in c.args[0] or "UNWIND $delete_ids" in c.args[0]
        ]
        assert dedup_calls == []

    async def test_dedup_update_and_delete_called(self) -> None:
        """Dedup with two good rows triggers both update and delete."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        other = uuid4()
        c1, c2 = uuid4(), uuid4()
        r1, r2 = uuid4(), uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        store = AsyncMock()
        store.upsert_nodes = AsyncMock()

        async def _exec_write(query, params=None):
            if "merged_into" in query:
                return []
            if "MATCH (tombstone" in query:
                return [
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(r1),
                        "source_chunk_ids": [str(c1)],
                    },
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(r2),
                        "source_chunk_ids": [str(c2)],
                    },
                ]
            if "MATCH (other)" in query:
                return []
            if "UNWIND $updates" in query:
                assert params["updates"][0]["id"] == str(r1)
                return []
            if "UNWIND $delete_ids" in query:
                assert params["delete_ids"] == [str(r2)]
                return []
            return []

        store.execute_write = AsyncMock(side_effect=_exec_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        # Verify update and delete were called
        calls = [c.args[0] for c in store.execute_write.call_args_list]
        assert any("UNWIND $updates" in q for q in calls)
        assert any("UNWIND $delete_ids" in q for q in calls)


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

    def test_known_value(self) -> None:
        """Known pair matches uuid5 with OID namespace."""
        c = UUID("11111111-1111-1111-1111-111111111111")
        e = UUID("22222222-2222-2222-2222-222222222222")
        expected = uuid5(NAMESPACE_OID, f"MENTIONED_IN:{c}:{e}")
        assert mentioned_in_id(c, e) == expected

    def test_order_matters(self) -> None:
        """Swapped order yields different id."""
        c, e = uuid4(), uuid4()
        assert mentioned_in_id(c, e) != mentioned_in_id(e, c)
