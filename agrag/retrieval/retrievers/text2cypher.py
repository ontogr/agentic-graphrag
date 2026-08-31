"""Text2Cypher retriever: generate Cypher from natural language."""

from __future__ import annotations

from uuid import UUID

from agrag.common.data_models.search_result import SearchResult
from agrag.cypher.safety import UnsafeCypherError, reject_write_cypher
from agrag.graphdb.base import GraphStore
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.retrievers.base import Retriever
from agrag.retrieval.settings import RetrievalSettings


class Text2CypherRetriever(Retriever):
    """Let the agent ask structured questions via generated Cypher.

    Calls a BAML function to generate a read-only Cypher query,
    runs reject_write_cypher as a safety pre-filter, then EXPLAIN
    and executes. Any entity id in the result is resolved through
    resolve_entity before becoming a SearchResult.
    """

    name = "text2cypher"

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        settings: RetrievalSettings | None = None,
    ) -> None:
        """Construct a Text2CypherRetriever.

        Args:
            graph_store: Where the generated query runs.
            settings: Retrieval configuration; defaults from
                environment.
        """
        self._graph_store = graph_store
        self._settings = settings or RetrievalSettings()

    async def retrieve(
        self,
        query: str,
        *,
        filters: None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Generate and execute a Cypher query for the question.

        Args:
            query: The natural-language question.
            filters: Ignored; text2cypher applies its own filters.
            limit: Maximum results to return.

        Returns:
            SearchResults from the generated query.
        """
        try:
            cypher_query = await self._generate_cypher(query)
        except Exception:
            return []

        # Safety gate.
        try:
            reject_write_cypher(cypher_query)
        except UnsafeCypherError:
            return []

        # EXPLAIN (read transaction, so a write would fail here too).
        try:
            await self._graph_store.execute_read(f"EXPLAIN {cypher_query}")
        except Exception:
            return []

        # Execute for real.
        try:
            rows = await self._graph_store.execute_read(cypher_query)
        except Exception:
            return []

        results: list[SearchResult] = []
        for row in rows[:limit]:
            # Try to find an entity id in the row.
            entity_id = self._extract_entity_id(row)
            if entity_id is not None:
                try:
                    entity = await resolve_entity(self._graph_store, entity_id)
                    results.append(
                        SearchResult(
                            item=entity,
                            score=1.0,
                            method=f"text2cypher: {cypher_query[:100]}",
                        )
                    )
                except (ValueError, Exception):
                    continue

        return results

    async def _generate_cypher(self, question: str) -> str:
        """Generate a Cypher query from a question.

        Args:
            question: The natural-language question.

        Returns:
            The generated Cypher query string.
        """
        try:
            from agrag.llm.baml_client import b as baml_client  # noqa: PLC0415

            return await baml_client.GenerateCypherQuery(
                question=question,
                schema_description="Generic schema with Person, "
                "Organization, Location, Event, Product entities "
                "and RELATED_TO, MENTIONED_IN relations.",
            )
        except ImportError:
            # BAML client not available; return a trivial query.
            return "MATCH (n) RETURN n LIMIT 1"

    @staticmethod
    def _extract_entity_id(row: dict) -> UUID | None:
        """Try to find a UUID entity id in a result row."""
        for key in ("id", "entity_id", "n"):
            val = row.get(key)
            if val is None:
                continue
            if isinstance(val, UUID):
                return val
            if isinstance(val, str):
                try:
                    return UUID(val)
                except ValueError:
                    continue
            if isinstance(val, dict):
                inner_id = val.get("id")
                if inner_id is not None:
                    try:
                        return UUID(str(inner_id))
                    except ValueError:
                        continue
        return None
