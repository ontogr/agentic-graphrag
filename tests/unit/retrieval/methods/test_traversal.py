"""Tests for the traversal helpers in agrag.retrieval.methods.traversal.

Patches ``EntityRetriever``/``BFSRetriever``/``expand_with_communities`` in this
module's namespace, so no database, embedding, or model call is made.

Covers entity-id extraction for both entity and resolved-entity results (a
resolved entity seeds traversal with its members' raw ids, never its own id),
entity resolution's label/property projection, the relation-type allowlist and
its scope-denied refusal, document and label scope forwarding into BFS,
direction/depth/limit threading, community expansion, and relationship type
filtering.
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


class TestExtractEntityIds:
    """extract_entity_ids reads raw ids, not resolved-entity ids."""

    def test_extract_entity_ids_handles_entity(self) -> None:
        """A plain entity contributes its own id."""
        entity = _entity()
        assert extract_entity_ids([_result(entity)]) == [entity.id]

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


class TestFindEntity:
    """find_entity projects a scope onto one entity search."""

    async def test_find_entity_found(self) -> None:
        """A hit returns the whole SearchResult, not just its item."""
        entity = _entity()
        expected = _result(entity)
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[expected])
            found = await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
            )

        assert found is expected
        assert retriever_cls.return_value.retrieve.call_args.kwargs["limit"] == 1

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

    async def test_find_entity_entity_labels_reaches_entity_retriever_constructor(
        self,
    ) -> None:
        """entity_labels reaches EntityRetriever's own constructor argument."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization", "Person"],
            )

        assert retriever_cls.call_args.kwargs["entity_labels"] == [
            "Organization",
            "Person",
        ]
        assert retriever_cls.return_value.retrieve.call_args.kwargs["filters"] is None

    async def test_find_entity_filters_properties_reaches_projected_filter(
        self,
    ) -> None:
        """A properties scope is projected into the retrieve() filter."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
                filters=SearchFilters(properties={"tenant_id": "tenant-a"}),
            )

        projected = retriever_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert projected.properties == {"tenant_id": "tenant-a"}
        assert projected.labels == []

    async def test_find_entity_filters_labels_reach_projected_filter(
        self,
    ) -> None:
        """A filters.labels scope reaches retrieve() as the label override."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
                filters=SearchFilters(labels=["Company"]),
            )

        projected = retriever_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert projected.labels == ["Company"]

    async def test_find_entity_filters_none_reaches_projected_none(self) -> None:
        """No scope reaches retrieve() as None, never an empty SearchFilters."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
                filters=None,
            )

        assert retriever_cls.return_value.retrieve.call_args.kwargs["filters"] is None

    async def test_find_entity_preserves_document_scope(self) -> None:
        """A document_ids scope reaches entity resolution."""
        with patch(
            "agrag.retrieval.methods.traversal.EntityRetriever"
        ) as retriever_cls:
            retriever_cls.return_value.retrieve = AsyncMock(return_value=[])
            await find_entity(
                "Acme",
                graph_store=AsyncMock(),
                embedder=AsyncMock(),
                vector_store=None,
                settings=RetrievalSettings(),
                entity_labels=["Organization"],
                filters=SearchFilters(document_ids=["doc-1"]),
            )

        assert retriever_cls.return_value.retrieve.call_args.kwargs["filters"] == (
            SearchFilters(document_ids=["doc-1"])
        )


class TestIntersectRelationTypes:
    """_intersect_relation_types enforces the caller's allowlist."""

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


class TestTraverse:
    """traverse seeds BFS from a resolved entity under the caller's scope."""

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

    async def test_traverse_on_entity_seed(self) -> None:
        """An entity seed reaches BFS as its own raw id."""
        entity = _entity()
        _, bfs_cls = await self._traverse(_result(entity))

        seed_ids = bfs_cls.return_value.retrieve.call_args.kwargs["seed_ids"]
        assert seed_ids == [entity.id]

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

    async def test_traverse_relation_type_none_omits_filter(self) -> None:
        """No relation_type reaches BFS as an empty type list, not [None]."""
        _, bfs_cls = await self._traverse(_result(_entity()))

        filters = bfs_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert filters.relation_types == []

    async def test_traverse_relation_type_reaches_filter(self) -> None:
        """A relation_type reaches BFS as the type restriction."""
        _, bfs_cls = await self._traverse(_result(_entity()), relation_type="TREATS")

        filters = bfs_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert filters.relation_types == ["TREATS"]

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

    async def test_traverse_base_filters_are_forwarded_to_bfs(
        self,
    ) -> None:
        """Document and label scopes are enforced by BFS."""
        _, bfs_cls = await self._traverse(
            _result(_entity()),
            filters=SearchFilters(document_ids=["doc-1"], labels=["Drug"]),
        )

        filters = bfs_cls.return_value.retrieve.call_args.kwargs["filters"]
        assert filters.document_ids == ["doc-1"]
        assert filters.labels == ["Drug"]

    async def test_traverse_direction_and_depth_reach_bfs_retriever(self) -> None:
        """Direction and depth are threaded through to BFSRetriever."""
        _, bfs_cls = await self._traverse(
            _result(_entity()), direction="incoming", depth=3, limit=7
        )

        kwargs = bfs_cls.return_value.retrieve.call_args.kwargs
        assert kwargs["direction"] == "incoming"
        assert kwargs["depth"] == 3
        assert kwargs["limit"] == 7

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

    async def test_traverse_without_community_expand_skips_it(self) -> None:
        """With no community_expand, no community lookup happens at all."""
        with patch("agrag.retrieval.methods.traversal.BFSRetriever") as bfs_cls:
            bfs_cls.return_value.retrieve = AsyncMock(return_value=[])
            with patch(
                "agrag.retrieval.methods.traversal.expand_with_communities",
                AsyncMock(),
            ) as expand:
                await traverse(
                    _result(_entity()),
                    graph_store=AsyncMock(),
                    settings=RetrievalSettings(),
                )

        expand.assert_not_called()


class TestListRelationshipTypes:
    """list_relationship_types reports attached types, depth-1 only."""

    async def test_list_relationship_types_reaches_query_builder_with_seed_ids(
        self,
    ) -> None:
        """The seed's raw ids reach the query builder and the store."""
        entity = _entity()
        store = AsyncMock()
        store.execute_read.return_value = [
            {"rel_type": "TREATS"},
            {"rel_type": "WORKS_FOR"},
            {"rel_type": "TREATS"},
        ]

        types = await list_relationship_types(_result(entity), graph_store=store)

        assert types == ["TREATS", "WORKS_FOR"]
        query, params = store.execute_read.call_args.args
        assert "RETURN DISTINCT type(r) AS rel_type" in query
        assert params == {"seed_ids": [str(entity.id)]}

    async def test_list_relationship_types_on_resolved_entity_seed(self) -> None:
        """A resolved entity seed queries with its members' raw ids."""
        member_ids = [uuid4(), uuid4()]
        resolved = _resolved(member_ids)
        store = AsyncMock()
        store.execute_read.return_value = []

        await list_relationship_types(_result(resolved), graph_store=store)  # type: ignore[arg-type]

        _, params = store.execute_read.call_args.args
        assert params == {"seed_ids": [str(m) for m in member_ids]}

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
