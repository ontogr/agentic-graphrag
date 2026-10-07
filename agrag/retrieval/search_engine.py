"""Retrieval's public entry point, independent of Graph."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from opentelemetry.trace import Tracer

from agrag.common.data_models.community import Community
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.relations import TraversalDirection
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.observability import record_swallowed_exception
from agrag.retrieval.community_context import expand_with_communities
from agrag.retrieval.errors import (
    AllRetrievalMethodsFailedError,
    UnknownRecipeMethodError,
)
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.fusion import fuse
from agrag.retrieval.methods.traversal import (
    extract_entity_ids,
)
from agrag.retrieval.methods.traversal import (
    find_entity as _find_entity,
)
from agrag.retrieval.methods.traversal import (
    list_relationship_types as _list_relationship_types,
)
from agrag.retrieval.methods.traversal import (
    traverse as _traverse,
)
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.rerank.cross_encoder import cross_encoder_rerank
from agrag.retrieval.rerank.node_distance import node_distance_rerank
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.retrievers.bfs import BFSRetriever
from agrag.retrieval.retrievers.chunk import ChunkRetriever
from agrag.retrieval.retrievers.community import CommunityRetriever
from agrag.retrieval.retrievers.entity import EntityRetriever
from agrag.retrieval.retrievers.text2cypher import Text2CypherRetriever
from agrag.retrieval.settings import RetrievalSettings
from agrag.retrieval.tracing import record_results, retrieval_span
from agrag.vectordb.base import VectorStore


logger = logging.getLogger(__name__)


class SearchEngine:
    """Retrieval public entry point, independent of Graph.

    Fans a query out to every method a Recipe names, fuses the
    results, and optionally reranks them. Constructed from its own
    stores. It does not depend on a Graph instance existing.

    A ``tracer`` opens the retrieval spans and flows to every
    retriever and free function the engine calls. It is not pushed
    into ``graph_store``, ``embedder`` or ``vector_store``. Pass the
    same tracer to those when you build them, so their adapter spans
    nest under these retrieval spans.
    """

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        vector_store: VectorStore | None = None,
        settings: RetrievalSettings | None = None,
        entity_labels: Sequence[str] | None = None,
        graph_schema: GraphSchema | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Construct a SearchEngine.

        Args:
            graph_store: Always required. It backs entity and chunk search
                when vector_store is absent, and it always backs BFS.
            embedder: Produces query vectors for dense and hybrid
                search.
            vector_store: Optional. When set, entity, chunk, and
                community search run hybrid_search there instead of
                GraphStore's native search. ``Graph.open(vector_store=...)``
                provisions the collections and dual-writes every embedding
                this package ingests, so the two paths see the same data.
                Point it at a store that ``Graph.open`` provisioned: a
                missing collection makes each method that reads it fail, and
                ``search`` raises ``AllRetrievalMethodsFailedError`` when
                every method fails. Collections that exist but hold no
                records return no hits.
            settings: Retrieval configuration; defaults from
                environment.
            entity_labels: The entity labels native entity search runs
                against, one vector index each, as provisioned by
                ``Graph.open``. Retained as a checked input only: it must
                name exactly the labels graph_schema declares, since the
                schema is what native search and generated Cypher both
                read. Omit it and let the schema drive both. Ignored when
                a vector_store is configured.
            graph_schema: The graph's declared schema, ground truth for
                native entity labels and for generated Cypher. None uses
                ``GENERIC``.
            tracer: Opens the search span and flows to every retriever
                and free function the engine calls. None opens no
                recorded span.

        Raises:
            ValueError: entity_labels does not name exactly the labels
                graph_schema declares.
        """
        self._graph_store = graph_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings or RetrievalSettings()
        self._tracer = tracer
        self._graph_schema = graph_schema if graph_schema is not None else GENERIC
        schema_labels = [entity.label for entity in self._graph_schema.entities]
        if (
            graph_schema is not None
            and entity_labels is not None
            and set(entity_labels) != set(schema_labels)
        ):
            raise ValueError(
                "entity_labels must name exactly the graph_schema's entity "
                f"labels. Schema '{self._graph_schema.name}' declares "
                f"{schema_labels}, got {list(entity_labels)}. Drop "
                "entity_labels and let the schema drive native entity "
                "search, or pass the schema those labels belong to."
            )
        self._entity_labels = (
            schema_labels
            if graph_schema is not None
            else list(entity_labels or self._settings.entity_labels or schema_labels)
        )

    @property
    def graph_schema(self) -> GraphSchema:
        """The schema retrieval is grounded in, GENERIC when none was given."""
        return self._graph_schema

    async def find_entity(
        self, name: str, *, filters: SearchFilters | None = None
    ) -> SearchResult | None:
        """Resolve a named entity to its top search hit, or None.

        Searches this engine's configured entity_labels by default. A
        filters.labels value, when set, overrides which labels are
        searched rather than narrowing within entity_labels. This is the
        same EntityRetriever behavior that the entity search of
        search() already relies on.

        Args:
            name: The entity name (or description) to resolve.
            filters: Scope to resolve within. An entity that exists
                only outside it resolves to None, the same as one that
                does not exist.

        Returns:
            The top-ranked SearchResult, or None when nothing matched.
        """
        return await _find_entity(
            name,
            graph_store=self._graph_store,
            embedder=self._embedder,
            vector_store=self._vector_store,
            settings=self._settings,
            entity_labels=self._entity_labels,
            filters=filters,
            tracer=self._tracer,
        )

    async def traverse(
        self,
        seed: SearchResult,
        *,
        relation_type: str | None = None,
        direction: TraversalDirection = "both",
        depth: int = 1,
        limit: int = 10,
        community_expand: bool = False,
        community_top_k: int = 3,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        """Expand one resolved entity into its neighbours.

        Args:
            seed: The resolved entity to expand from, normally from
                ``find_entity``.
            relation_type: Restrict the traversal to this one
                relationship type.
            direction: Which way a hop walks each relationship,
                relative to the seed entity.
            depth: Maximum hops.
            limit: Maximum neighbours returned.
            community_expand: Also fuse in the reports of communities
                overlapping the seed.
            community_top_k: Maximum community reports to add when
                ``community_expand`` is set.
            filters: Scope for the traversal. Its ``relation_types`` is
                an allowlist. A ``relation_type`` argument cannot widen it.
                Its ``properties``, ``document_ids``, and ``labels``
                constrain returned neighbour nodes.

        Returns:
            The neighbouring entities, deduplicated, highest-ranked
            first, with any requested community reports fused in.

        Raises:
            ScopeDeniedError: relation_type names a type the caller's
                scope does not permit.
        """
        return await _traverse(
            seed,
            graph_store=self._graph_store,
            settings=self._settings,
            relation_type=relation_type,
            direction=direction,
            depth=depth,
            limit=limit,
            community_expand=community_expand,
            community_top_k=community_top_k,
            filters=filters,
            tracer=self._tracer,
        )

    async def list_relationship_types(
        self,
        seed: SearchResult,
        *,
        relation_type_filter: str | None = None,
        direction: TraversalDirection = "both",
        filters: SearchFilters | None = None,
    ) -> list[str]:
        """List the relationship types directly attached to an entity.

        Depth-1 only: it reports what is attached to the seed, never
        what lies past it.

        Args:
            seed: The resolved entity to read attached types from,
                normally from ``find_entity``.
            relation_type_filter: Only report this type, if present.
            direction: Which way to inspect relationships, relative to the
                seed entity.
            filters: Scope that limits visible relationship types.

        Returns:
            The distinct attached relationship type names.
        """
        return await _list_relationship_types(
            seed,
            graph_store=self._graph_store,
            relation_type_filter=relation_type_filter,
            direction=direction,
            filters=filters,
            tracer=self._tracer,
        )

    async def search(  # noqa: PLR0912, PLR0915
        self,
        query: str,
        recipe: Recipe,
        *,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        """Run recipe's methods, fuse, expand, and optionally rerank.

        Runs recipe.methods concurrently and fuses their output
        first. When recipe.bfs is set, BFS runs as a second,
        sequential step seeded from the fused entity results. BFS
        results are fused into the same list a second time before
        reranking.

        Args:
            query: The natural-language query text.
            recipe: Which methods to run, whether to expand via BFS
                afterward, and which reranker, if any, follows.
            filters: Constraints applied identically to every method.

        Returns:
            Up to recipe.limit results, ranked highest-relevance
            first.

        Raises:
            AllRetrievalMethodsFailedError: Every method the recipe
                names failed. A method failing while others succeed
                is logged and its results are absent.
            UnknownRecipeMethodError: The recipe names one or more
                methods that are not in the retriever registry. A
                misspelled method name is a configuration error. It
                is reported instead of silently returning no
                results.
        """
        retrievers = self._build_retrievers()
        self._validate_recipe_methods(recipe, retrievers)
        with retrieval_span(
            self._tracer,
            "agrag.retrieval.search",
            query=query,
            filters=filters,
            attributes={
                "agrag.recipe.methods": list(recipe.methods),
                "agrag.recipe.limit": recipe.limit,
                "agrag.recipe.bfs": recipe.bfs,
                "agrag.recipe.community_expand": recipe.community_expand,
                "agrag.recipe.reranker": recipe.reranker or "",
            },
        ) as span:
            return await self._run_search(query, recipe, filters, retrievers, span)

    async def _run_search(  # noqa: PLR0912, PLR0915
        self,
        query: str,
        recipe: Recipe,
        filters: SearchFilters | None,
        retrievers: dict[str, Retriever],
        span: Any,
    ) -> list[SearchResult]:
        """Run the search body inside the root span ``search`` opened.

        Args:
            query: The natural-language query text.
            recipe: Which methods to run and what follows them.
            filters: Constraints applied identically to every method.
            retrievers: The retriever registry ``search`` built.
            span: The open ``agrag.retrieval.search`` span.

        Returns:
            Up to recipe.limit results, ranked highest-relevance first.

        Raises:
            AllRetrievalMethodsFailedError: Every method the recipe
                names failed.
        """
        # Project SearchFilters per retriever: labels only go to entity
        # search, while document_ids and property filters apply to entity,
        # chunk, and community search.
        entity_filters = (
            SearchFilters(
                labels=filters.labels if filters else [],
                document_ids=filters.document_ids if filters else [],
                properties=filters.properties if filters else {},
            )
            if filters
            and (filters.labels or filters.document_ids or filters.properties)
            else None
        )
        chunk_filters = (
            SearchFilters(
                document_ids=filters.document_ids if filters else [],
                properties=filters.properties if filters else {},
            )
            if filters and (filters.document_ids or filters.properties)
            else None
        )
        community_filters = (
            SearchFilters(
                document_ids=filters.document_ids if filters else [],
                properties=filters.properties if filters else {},
            )
            if filters and (filters.document_ids or filters.properties)
            else None
        )
        retriever_filters: dict[str, SearchFilters | None] = {
            "entity": entity_filters,
            "chunk": chunk_filters,
            "community": community_filters,
        }

        # Fan out recipe.methods concurrently.
        tasks = []
        method_names = []
        for method_name in recipe.methods:
            if method_name in retrievers:
                tasks.append(
                    retrievers[method_name].retrieve(
                        query,
                        filters=retriever_filters.get(method_name, filters),
                        limit=recipe.limit,
                    )
                )
                method_names.append(method_name)

        method_results = await asyncio.gather(*tasks, return_exceptions=True)

        results_by_method: dict[str, list[SearchResult]] = {}
        failures: dict[str, BaseException] = {}
        for name, result in zip(method_names, method_results, strict=True):
            # Cancellation must propagate; only retriever errors are
            # tolerated here.
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                failures[name] = result
                continue
            results_by_method[name] = result

        if failures and not results_by_method:
            raise AllRetrievalMethodsFailedError(failures) from next(
                iter(failures.values())
            )
        if failures:
            logger.warning(
                "Retrieval methods %s failed; continuing with %s.",
                sorted(failures),
                sorted(results_by_method),
            )
            for failure in failures.values():
                if isinstance(failure, Exception):
                    record_swallowed_exception(failure)
            if span.is_recording():
                span.set_attribute("agrag.failed_methods", sorted(failures))

        # First fusion pass.
        fused = fuse(results_by_method, rrf_k=self._settings.rrf_k, tracer=self._tracer)

        # Entities the recipe's own methods found, before any BFS
        # expansion adds neighbours. These seed both BFS and the
        # node-distance reranker, which needs seeds that are not
        # themselves the candidates it is ordering.
        search_seed_ids = extract_entity_ids(fused)

        # BFS expansion as sequential follow-up.
        if recipe.bfs:
            bfs_retriever = BFSRetriever(
                graph_store=self._graph_store,
                settings=self._settings,
                tracer=self._tracer,
            )
            bfs_filters = (
                SearchFilters(
                    relation_types=filters.relation_types,
                    labels=filters.labels,
                    document_ids=filters.document_ids,
                    properties=filters.properties,
                )
                if filters
                and (
                    filters.relation_types
                    or filters.labels
                    or filters.document_ids
                    or filters.properties
                )
                else None
            )
            bfs_kwargs: dict[str, Any] = {
                "query": query,
                "filters": bfs_filters,
                "limit": recipe.limit,
                "seed_ids": search_seed_ids,
            }
            if recipe.bfs_depth is not None:
                bfs_kwargs["depth"] = recipe.bfs_depth
            bfs_results = await bfs_retriever.retrieve(**bfs_kwargs)
            if bfs_results:
                fused = fuse(
                    {"methods": fused, "bfs": bfs_results},
                    rrf_k=self._settings.rrf_k,
                    tracer=self._tracer,
                )

        if recipe.community_expand:
            fused = await expand_with_communities(
                fused,
                extract_entity_ids(fused),
                graph_store=self._graph_store,
                top_k=recipe.community_top_k,
                filters=community_filters,
                rrf_k=self._settings.rrf_k,
                tracer=self._tracer,
            )

        # Rerank.
        if recipe.reranker == "cross_encoder":
            community_items = [r for r in fused if isinstance(r.item, Community)]
            other_items = [r for r in fused if not isinstance(r.item, Community)]
            min_score = (
                recipe.min_score
                if recipe.min_score is not None
                else self._settings.reranker_min_score
            )
            reranked_other = await cross_encoder_rerank(
                query,
                other_items,
                model=self._settings.cross_encoder_model,
                min_score=min_score,
                tracer=self._tracer,
            )
            reserved = (
                min(len(community_items), recipe.community_top_k)
                if recipe.community_expand
                else 0
            )
            fused = (
                reranked_other[: max(0, recipe.limit - reserved)]
                + community_items[:reserved]
            )
        elif recipe.reranker == "node_distance":
            fused = await node_distance_rerank(
                fused,
                graph_store=self._graph_store,
                seed_ids=search_seed_ids[: self._settings.node_distance_seed_top_k],
                tracer=self._tracer,
            )

        final = fused[: recipe.limit]
        record_results(span, final)
        return final

    @staticmethod
    def _validate_recipe_methods(
        recipe: Recipe, retrievers: dict[str, Retriever]
    ) -> None:
        """Raise ``UnknownRecipeMethodError`` for any name not in the registry.

        A recipe that names only registered methods runs unchanged.
        A name that matches none is treated as a configuration error
        rather than silently dropped, so a typo is not hidden by an
        empty successful search.
        """
        known = list(retrievers)
        unknown = [name for name in recipe.methods if name not in retrievers]
        if unknown:
            raise UnknownRecipeMethodError(unknown, known)

    def _build_retrievers(self) -> dict:
        """Build the retriever map from current stores."""
        return {
            "entity": EntityRetriever(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                settings=self._settings,
                entity_labels=self._entity_labels,
                tracer=self._tracer,
            ),
            "chunk": ChunkRetriever(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                settings=self._settings,
                tracer=self._tracer,
            ),
            "community": CommunityRetriever(
                graph_store=self._graph_store,
                embedder=self._embedder,
                vector_store=self._vector_store,
                settings=self._settings,
                tracer=self._tracer,
            ),
            "text2cypher": Text2CypherRetriever(
                graph_store=self._graph_store,
                schema=self._graph_schema,
                settings=self._settings,
                tracer=self._tracer,
            ),
        }
