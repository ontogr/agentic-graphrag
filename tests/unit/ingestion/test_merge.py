"""Tests for merge mechanics."""

from contextlib import asynccontextmanager
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
    relation_id,
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

    def test_dict_valued_candidates_do_not_raise(self) -> None:
        """A dict-valued candidate does not crash the hashable-only dedup path."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_LAST)
        value, conflicted = _resolve_property("meta", [{"a": 1}, {"b": 2}], rules)
        assert value == {"b": 2}
        assert conflicted is True

    def test_merge_all_result_merged_again_with_list_candidates(self) -> None:
        """A prior MERGE_ALL list result merging again does not raise.

        Simulates re-ingesting an already-merged entity whose property was
        previously resolved to a list by MERGE_ALL: that list becomes one of
        the candidates in a later merge, which must still resolve cleanly.
        """
        rules = PropertyRules(default=PropertyStrategy.MERGE_ALL)
        prior_result, _ = _resolve_property("tags", ["a", "b"], rules)
        assert prior_result == ["a", "b"]
        value, conflicted = _resolve_property("tags", [prior_result, ["c"]], rules)
        assert value == [["a", "b"], ["c"]]
        assert conflicted is True

    def test_list_valued_duplicate_candidates_deduped_by_equality(self) -> None:
        """Equal list candidates collapse to one, not raise or duplicate."""
        rules = PropertyRules(default=PropertyStrategy.KEEP_FIRST)
        value, conflicted = _resolve_property("tags", [["a"], ["a"]], rules)
        assert value == ["a"]
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

    async def test_accepted_merge_keys_includes_absorbed_entities_names(self) -> None:
        """Absorbed existing entities' own names are also accepted keys."""
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


def _transferred(
    *,
    other_id: UUID | None = None,
    rel_type: str = "KNOWS",
    new_relationship_id: UUID | None = None,
    source_chunk_ids: list[UUID] | None = None,
    properties: dict[str, object] | None = None,
) -> _TransferredRelationship:
    """Build a _TransferredRelationship for dedup tests."""
    return _TransferredRelationship(
        other_id=other_id or uuid4(),
        rel_type=rel_type,
        new_relationship_id=new_relationship_id or uuid4(),
        source_chunk_ids=source_chunk_ids or [],
        properties=properties or {},
    )


class TestPlanRelationshipDedup:
    """_plan_relationship_dedup grouping."""

    def test_group_of_one_returns_empty(self) -> None:
        """Single row in a group produces no updates."""
        r = _transferred(source_chunk_ids=[uuid4()])
        updates, delete_ids = _plan_relationship_dedup([r])
        assert updates == []
        assert delete_ids == []

    def test_group_of_two_merges_chunk_ids(self) -> None:
        """Two rows with same type and other merges chunk ids."""
        other = uuid4()
        c1, c2, c3 = uuid4(), uuid4(), uuid4()
        r1 = _transferred(other_id=other, source_chunk_ids=[c1, c2])
        r2 = _transferred(other_id=other, source_chunk_ids=[c2, c3])
        updates, deletes = _plan_relationship_dedup([r1, r2])
        assert len(updates) == 1
        assert updates[0]["id"] == str(r1.new_relationship_id)
        assert updates[0]["rel_type"] == "KNOWS"
        properties = updates[0]["properties"]
        assert isinstance(properties, dict)
        # deduped, order preserved: c1, c2, c3
        assert properties["source_chunk_ids"] == [
            str(c1),
            str(c2),
            str(c3),
        ]
        assert deletes == [{"id": str(r2.new_relationship_id), "rel_type": "KNOWS"}]

    def test_separate_groups_by_type(self) -> None:
        """Different rel_type creates separate groups."""
        other = uuid4()
        r1 = _transferred(other_id=other, rel_type="KNOWS")
        r2 = _transferred(other_id=other, rel_type="WORKS_AT")
        updates, delete_ids = _plan_relationship_dedup([r1, r2])
        assert updates == []
        assert delete_ids == []

    def test_separate_groups_by_other_id(self) -> None:
        """Different other_id creates separate groups."""
        r1 = _transferred()
        r2 = _transferred()
        updates, delete_ids = _plan_relationship_dedup([r1, r2])
        assert updates == []
        assert delete_ids == []

    def test_multiple_groups_mixed(self) -> None:
        """Multiple duplicate groups each produce an update."""
        other_a, other_b = uuid4(), uuid4()
        r1 = _transferred(other_id=other_a)
        r2 = _transferred(other_id=other_a)
        r3 = _transferred(other_id=other_b)
        r4 = _transferred(other_id=other_b)
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
        r_out1 = _transferred(other_id=other)
        r_out2 = _transferred(other_id=other)
        updates_out, _ = _plan_relationship_dedup([r_out1, r_out2])
        # Incoming group separately
        r_in1 = _transferred(other_id=other)
        updates_in, _ = _plan_relationship_dedup([r_in1])
        assert len(updates_out) == 1
        assert updates_in == []

    def test_merges_non_provenance_properties_from_duplicates(self) -> None:
        """A duplicate's distinct property is not lost when its edge is deleted.

        Regression test: fetch_node_relationships_query now returns each
        edge's full property map, and the dedup update carries the merged
        result, so a field only the deleted duplicate had survives onto the
        kept edge instead of disappearing.
        """
        other = uuid4()
        keeper = _transferred(other_id=other, properties={"confidence": "high"})
        extra = _transferred(
            other_id=other, properties={"confidence": None, "note": "from doc B"}
        )
        updates, deletes = _plan_relationship_dedup([keeper, extra])
        assert len(updates) == 1
        merged = updates[0]["properties"]
        assert isinstance(merged, dict)
        # Keeper's own value wins when it has one.
        assert merged["confidence"] == "high"
        # A field only the duplicate had is not dropped.
        assert merged["note"] == "from doc B"
        assert deletes == [{"id": str(extra.new_relationship_id), "rel_type": "KNOWS"}]


def _store_with_transaction(execute_write: AsyncMock) -> AsyncMock:
    """Build a store AsyncMock whose transaction() yields a fake handle.

    The handle's execute_write is the given mock. Its upsert_nodes mock is
    exposed as store.txn_upsert_nodes, kept separate from the store's own
    upsert_nodes so a test can tell which one apply_merge actually used.
    """
    upsert_nodes = AsyncMock()
    handle = SimpleNamespace(execute_write=execute_write, upsert_nodes=upsert_nodes)

    @asynccontextmanager
    async def _transaction():
        yield handle

    store = AsyncMock()
    store.transaction = _transaction
    store.txn_upsert_nodes = upsert_nodes
    return store


class TestApplyMerge:
    """apply_merge writes to GraphStore."""

    async def test_zero_tombstones_upserts_survivor_and_alias(self) -> None:
        """No tombstones still runs in a transaction: upsert survivor + alias.

        The survivor write goes through upsert_survivor_query's atomic
        accumulation, not txn.upsert_nodes, so a concurrent writer's own
        contribution to the same node is never lost to a full overwrite.
        """
        survivor = _entity(name="Ada")
        plan = MergePlan(survivor=survivor, tombstone_ids=[], conflicts=[])
        execute_write = AsyncMock(return_value=[])
        store = _store_with_transaction(execute_write)

        await apply_merge(plan, graph_store=store, schema=_schema())

        store.upsert_nodes.assert_not_awaited()
        store.execute_write.assert_not_awaited()
        store.txn_upsert_nodes.assert_not_awaited()
        calls = execute_write.call_args_list
        survivor_calls = [c for c in calls if set(c.args[1]) == {"records"}]
        assert len(survivor_calls) == 1
        record = survivor_calls[0].args[1]["records"][0]
        assert record["id"] == str(survivor.id)
        assert "source_chunk_ids" not in record["properties"]
        assert "merged_from" not in record["properties"]
        assert "merge_count" not in record["properties"]
        alias_calls = [
            c for c in calls if set(c.args[1]) == {"merge_keys", "entity_id"}
        ]
        assert len(alias_calls) == 1
        assert alias_calls[0].args[1] == {
            "merge_keys": [survivor.merge_key],
            "entity_id": str(survivor.id),
        }

    async def test_two_plus_runs_in_one_transaction(self) -> None:
        """Two-plus tombstones, deletes internal edges, transfers, and re-fetches.

        Every write for the multi-entity path goes through the yielded
        transaction handle, never the store's own execute_write/upsert_nodes,
        since apply_merge must be able to roll the whole thing back as one
        unit.
        """
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        execute_write = AsyncMock(return_value=[])
        store = _store_with_transaction(execute_write)

        await apply_merge(plan, graph_store=store, schema=_schema())

        store.upsert_nodes.assert_not_awaited()
        store.execute_write.assert_not_awaited()
        store.txn_upsert_nodes.assert_not_awaited()

        calls = execute_write.call_args_list
        # merge_key is cleared from every tombstone before the survivor is
        # written, so a survivor whose resolved name matches a tombstone's
        # own name cannot collide with the per-label merge_key constraint.
        clear_calls = [
            c
            for c in calls
            if set(c.args[1]) == {"tombstone_ids"} and "REMOVE n.merge_key" in c.args[0]
        ]
        assert len(clear_calls) == 1
        assert clear_calls[0].args[1]["tombstone_ids"] == [str(tombstone)]
        # Survivor write, via upsert_survivor_query's atomic accumulation.
        survivor_calls = [c for c in calls if set(c.args[1]) == {"records"}]
        assert len(survivor_calls) == 1
        assert survivor_calls[0].args[1]["records"][0]["id"] == str(survivor.id)
        assert calls.index(clear_calls[0]) < calls.index(survivor_calls[0])
        # Merge-key alias for the survivor's own current name.
        alias_calls = [
            c for c in calls if set(c.args[1]) == {"merge_keys", "entity_id"}
        ]
        assert len(alias_calls) == 1
        assert alias_calls[0].args[1]["entity_id"] == str(survivor.id)
        # Tombstone: marks the absorbed id merged, distinguished from the
        # internal-edge delete below by query text since both take the same
        # {tombstone_ids, survivor_id} parameters.
        tombstone_calls = [
            c
            for c in calls
            if set(c.args[1]) == {"tombstone_ids", "survivor_id"}
            and "SET n.merged_into" in c.args[0]
        ]
        assert len(tombstone_calls) == 1
        assert tombstone_calls[0].args[1]["tombstone_ids"] == [str(tombstone)]
        # Internal/self-link edge cleanup, once, before any transfer.
        internal_delete_calls = [
            c
            for c in calls
            if set(c.args[1]) == {"tombstone_ids", "survivor_id"}
            and "DELETE r" in c.args[0]
        ]
        assert len(internal_delete_calls) == 1
        # Both transfer directions, once per tombstone.
        transfer_calls = [
            c for c in calls if set(c.args[1]) == {"tombstone_id", "survivor_id"}
        ]
        assert len(transfer_calls) == 2
        # Both post-transfer neighbourhood fetches.
        fetch_calls = [c for c in calls if set(c.args[1]) == {"node_id"}]
        assert len(fetch_calls) == 2

    async def test_handles_row_parsing_errors(self) -> None:
        """Malformed neighbourhood rows are skipped, and no dedup call follows."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])

        async def _exec_write(query, params=None):
            if params and "node_id" in params:
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
                        "properties": {"source_chunk_ids": ["not-a-uuid"]},
                    },
                ]
            return []

        execute_write = AsyncMock(side_effect=_exec_write)
        store = _store_with_transaction(execute_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        dedup_calls = [
            c
            for c in execute_write.call_args_list
            if "updates" in c.args[1] or "delete_ids" in c.args[1]
        ]
        assert dedup_calls == []

    async def test_transfer_handles_partial_bad_rows(self) -> None:
        """One good row and one bad row leave a single-row group: no dedup."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])
        other = uuid4()
        good_id = uuid4()
        c1 = uuid4()

        async def _exec_write(query, params=None):
            if params and "node_id" in params:
                return [
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(good_id),
                        "properties": {"source_chunk_ids": [str(c1)]},
                    },
                    {
                        "other_id": "bad",
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(uuid4()),
                        "properties": {"source_chunk_ids": []},
                    },
                ]
            return []

        execute_write = AsyncMock(side_effect=_exec_write)
        store = _store_with_transaction(execute_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        dedup_calls = [
            c
            for c in execute_write.call_args_list
            if "updates" in c.args[1] or "delete_ids" in c.args[1]
        ]
        assert dedup_calls == []

    async def test_dedup_update_and_delete_called(self) -> None:
        """Two duplicate neighbours trigger a type-scoped dedup update and delete."""
        survivor = _entity(name="Ada")
        tombstone = uuid4()
        other = uuid4()
        c1, c2 = uuid4(), uuid4()
        r1, r2 = uuid4(), uuid4()
        plan = MergePlan(survivor=survivor, tombstone_ids=[tombstone], conflicts=[])

        async def _exec_write(query, params=None):
            if params and "node_id" in params:
                return [
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(r1),
                        "properties": {"source_chunk_ids": [str(c1)]},
                    },
                    {
                        "other_id": str(other),
                        "rel_type": "KNOWS",
                        "new_relationship_id": str(r2),
                        "properties": {"source_chunk_ids": [str(c2)]},
                    },
                ]
            if params and "updates" in params:
                assert params["updates"][0]["id"] == str(r1)
                assert params["updates"][0]["rel_type"] == "KNOWS"
            if params and "delete_ids" in params:
                assert params["delete_ids"] == [{"id": str(r2), "rel_type": "KNOWS"}]
            return []

        execute_write = AsyncMock(side_effect=_exec_write)
        store = _store_with_transaction(execute_write)
        await apply_merge(plan, graph_store=store, schema=_schema())
        calls = execute_write.call_args_list
        update_calls = [c for c in calls if "updates" in c.args[1]]
        delete_calls = [c for c in calls if "delete_ids" in c.args[1]]
        assert update_calls
        assert delete_calls


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

    def test_known_value(self) -> None:
        """Known triple matches uuid5 with OID namespace."""
        s = UUID("11111111-1111-1111-1111-111111111111")
        t = UUID("22222222-2222-2222-2222-222222222222")
        expected = uuid5(NAMESPACE_OID, f"KNOWS:{s}:{t}")
        assert relation_id(s, t, "KNOWS") == expected


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
