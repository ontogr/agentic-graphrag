"""Tests for the traversal helpers in agrag.retrieval.methods.traversal.

Patches ``EntityRetriever``/``BFSRetriever``/``expand_with_communities`` in this
module's namespace, so no database, embedding, or model call is made.

Covers entity-id extraction for both entity and resolved-entity results (a
resolved entity seeds traversal with its members' raw ids, never its own id),
the relation-type allowlist and its scope-denied refusal, community expansion,
and relationship type filtering. Direction, relation-type narrowing, and scope
enforcement against a real graph run in the integration suite.
"""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.errors import ScopeDeniedError
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.traversal import (
    _intersect_relation_types,
    extract_entity_ids,
    find_entity,
    list_relationship_types,
    traverse,
)
from agrag.retrieval.settings import RetrievalSettings


def _entity(name: str = "Acme", label: str = "Organization") -> Entity:
    """Build a minimal Entity."""
    return Entity(id=uuid4(), label=label, name=name)


def _result(entity: Any) -> SearchResult:
    """Wrap an entity in a SearchResult as a retriever would."""
    return SearchResult(item=entity, score=1.0, method="entity")


def _resolved(member_ids: list) -> ResolvedEntity:
    """Build a ResolvedEntity carrying the given member ids."""
    return ResolvedEntity(
        id=uuid4(), label="Organization", name="Acme", member_ids=member_ids
    )


class TestTraversal:
    """Tests scoped entity lookup and graph traversal helpers."""

    def test_extract_entity_ids_handles_resolved_entity_member_ids(self) -> None:
        """A resolved entity contributes its members' ids, never its own."""
        members = [uuid4(), uuid4()]
        resolved = _resolved(members)
        ids = extract_entity_ids([_result(resolved)])  # type: ignore[arg-type]
        assert ids == members
        assert resolved.id not in ids

    def test_extract_entity_ids_dedupes_and_skips_other_items(self) -> None:
        """Repeat ids are kept once and non-entity items are skipped."""
        entity = _entity()
        resolved = _resolved([entity.id, uuid4()])
        chunk = Chunk(
            document_id=uuid4(),
            text="text",
            provenance=TextProvenance(char_start=0, char_end=4),
        )
        ids = extract_entity_ids([_result(entity), _result(resolved), _result(chunk)])
        assert ids == [entity.id, resolved.member_ids[1]]

    async def test_find_entity_not_found(self) -> None:
        """No hit returns None."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            found = await find_entity(
                "Nope",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
            )

        assert found is None

    @pytest.mark.parametrize(
        ("base", "requested", "expected"),
        [
            ([], "TREATS", ["TREATS"]),
            ([], None, []),
            (["WORKS_FOR", "TREATS"], "TREATS", ["TREATS"]),
            (["WORKS_FOR"], None, ["WORKS_FOR"]),
        ],
    )
    def test_intersect_relation_types_allowlist_semantics(
        self, base: list[str], requested: str | None, expected: list[str]
    ) -> None:
        """The four allowlist cases resolve as documented."""
        assert _intersect_relation_types(base, requested) == expected

    def test_intersect_relation_types_non_member_is_empty(self) -> None:
        """A request outside a non-empty allowlist intersects to nothing."""
        assert _intersect_relation_types(["WORKS_FOR"], "FOUNDED") == []

    async def _traverse(self, seed: SearchResult, **kwargs) -> tuple:
        """Run traverse against a mocked BFSRetriever and return the mocks."""
        with patch("agrag.retrieval.methods.traversal.BFSRetriever") as bfs_cls:
            bfs_cls.return_value.retrieve = AsyncMock(return_value=[])
            results = await traverse(
                seed,
                graph_store=AsyncMock(),
                settings=RetrievalSettings(),
                **kwargs,
            )
        return results, bfs_cls

    async def test_traverse_on_resolved_entity_seed_with_multiple_members(self) -> None:
        """A resolved entity seed reaches BFS as its members' raw ids.

        Regression test: seeding with a ResolvedEntity's own id matches no
        _AgragNode, so traversal silently returned nothing for any
        already-clustered entity.
        """
        resolved = _resolved([uuid4(), uuid4()])
        _, bfs_cls = await self._traverse(_result(resolved))  # type: ignore[arg-type]

        seed_ids = bfs_cls.return_value.retrieve.call_args.kwargs["seed_ids"]
        assert seed_ids == resolved.member_ids
        assert resolved.id not in seed_ids

    async def test_traverse_relation_type_and_base_filters_combine(self) -> None:
        """A relation_type and a caller-set property scope both reach BFS."""
        _, bfs_cls = await self._traverse(
            _result(_entity()),
            relation_type="TREATS",
            filters=SearchFilters(
                relation_types=["TREATS", "CAUSES"],
                properties={"tenant_id": "tenant-a"},
            ),
        )

        filters = bfs_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert filters.relation_types == ["TREATS"]
        assert filters.properties == {"tenant_id": "tenant-a"}

    async def test_traverse_denied_relation_type_returns_scope_denied_without_querying(
        self,
    ) -> None:
        """A relation type outside the allowlist refuses before querying."""
        with (
            patch("agrag.retrieval.methods.traversal.BFSRetriever") as bfs_cls,
            pytest.raises(ScopeDeniedError),
        ):
            await traverse(
                _result(_entity()),
                graph_store=AsyncMock(),
                settings=RetrievalSettings(),
                relation_type="FOUNDED",
                filters=SearchFilters(relation_types=["WORKS_FOR"]),
            )

        bfs_cls.assert_not_called()

    async def test_traverse_community_expand_calls_expand_with_communities(
        self,
    ) -> None:
        """community_expand fuses community results through the shared helper."""
        entity = _entity()
        scope = SearchFilters(properties={"tenant_id": "tenant-a"})
        with patch("agrag.retrieval.methods.traversal.BFSRetriever") as bfs_cls:
            bfs_cls.return_value.retrieve = AsyncMock(return_value=[])
            with patch(
                "agrag.retrieval.methods.traversal.expand_with_communities",
                AsyncMock(return_value=[]),
            ) as expand:
                await traverse(
                    _result(entity),
                    graph_store=AsyncMock(),
                    settings=RetrievalSettings(),
                    community_expand=True,
                    community_top_k=2,
                    filters=scope,
                )

        kwargs = expand.call_args.kwargs
        assert kwargs["top_k"] == 2
        assert kwargs["filters"] is scope
        assert kwargs["rrf_k"] == RetrievalSettings().rrf_k
        assert expand.call_args.args[1] == [entity.id]

    async def test_list_relationship_types_on_resolved_entity_seed(self) -> None:
        """A resolved entity seed queries with its members' raw ids."""
        member_ids = [uuid4(), uuid4()]
        resolved = _resolved(member_ids)
        store = AsyncMock()
        store.execute_read.return_value = []

        await list_relationship_types(_result(resolved), graph_store=store)  # type: ignore[arg-type]

        _, params = store.execute_read.call_args.args
        assert params == {"seed_ids": [str(m) for m in member_ids], "job_id": None}

    async def test_list_relationship_types_filter_reaches_query(self) -> None:
        """relation_type_filter restricts the generated pattern."""
        store = AsyncMock()
        store.execute_read.return_value = []

        await list_relationship_types(
            _result(_entity()),
            graph_store=store,
            relation_type_filter="TREATS",
        )

        query, _ = store.execute_read.call_args.args
        assert "[r:TREATS]" in query

    async def test_list_relationship_types_applies_relation_scope(self) -> None:
        """A relation allowlist reaches the relationship type query."""
        store = AsyncMock()
        store.execute_read.return_value = []

        await list_relationship_types(
            _result(_entity()),
            graph_store=store,
            filters=SearchFilters(relation_types=["TREATS"]),
        )

        query, _ = store.execute_read.call_args.args
        assert "[r:TREATS]" in query
