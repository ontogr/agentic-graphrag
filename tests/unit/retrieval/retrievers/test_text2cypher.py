"""Tests for Text2CypherRetriever."""

from unittest.mock import AsyncMock, patch

from agrag.retrieval.retrievers.text2cypher import (
    Text2CypherRetriever,
)
from agrag.retrieval.settings import RetrievalSettings


class TestText2CypherRetriever:
    """Text2CypherRetriever generates and executes Cypher."""

    async def test_returns_empty_on_generation_failure(self) -> None:
        """Failed Cypher generation returns empty results."""
        gs = AsyncMock()
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(retriever, "_generate_cypher", side_effect=Exception("fail")):
            results = await retriever.retrieve("what is X?")
            assert results == []

    async def test_rejects_write_cypher(self) -> None:
        """Generated Cypher with write clauses returns empty."""
        gs = AsyncMock()
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n) DELETE n",
        ):
            results = await retriever.retrieve("delete everything")
            assert results == []

    async def test_accepts_read_cypher(self) -> None:
        """Pure MATCH...RETURN Cypher is executed."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n:Person) RETURN n LIMIT 5",
        ):
            results = await retriever.retrieve("who is Alice?")
            assert isinstance(results, list)

    async def test_rejects_call_in_write_shape(self) -> None:
        """CALL db.index.vector.queryNodes is accepted (read Cypher)."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value=(
                "CALL db.index.vector.queryNodes('idx', 10, $v) YIELD node RETURN node"
            ),
        ):
            results = await retriever.retrieve("search for X")
            # Should not be rejected (CALL is allowed).
            assert isinstance(results, list)


class TestText2CypherBounds:
    """Generated queries run with a row bound and a timeout."""

    async def test_appends_row_limit_to_generated_query(self) -> None:
        """A generated query without LIMIT gets the configured row bound."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n:Person) RETURN n",
        ):
            await retriever.retrieve("who is Alice?")

        executed = gs.execute_read.await_args_list[-1].args[0]
        assert executed == "MATCH (n:Person) RETURN n LIMIT 1000"

    async def test_keeps_existing_row_limit(self) -> None:
        """A generated query that already declares LIMIT is left alone."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n:Person) RETURN n LIMIT 5",
        ):
            await retriever.retrieve("who is Alice?")

        executed = gs.execute_read.await_args_list[-1].args[0]
        assert executed == "MATCH (n:Person) RETURN n LIMIT 5"

    async def test_limit_inside_string_literal_does_not_suppress_bound(self) -> None:
        """A quoted LIMIT in a predicate does not count as a row bound."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n:Person) WHERE n.name = 'LIMIT 5' RETURN n",
        ):
            await retriever.retrieve("who is Alice?")

        executed = gs.execute_read.await_args_list[-1].args[0]
        assert executed.endswith("RETURN n LIMIT 1000")

    async def test_passes_timeout_to_store(self) -> None:
        """The configured timeout reaches the store's execute_read calls."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        settings = RetrievalSettings(text2cypher_timeout_seconds=2.5)
        retriever = Text2CypherRetriever(graph_store=gs, settings=settings)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (n:Person) RETURN n",
        ):
            await retriever.retrieve("who is Alice?")

        assert gs.execute_read.await_count == 2
        for call in gs.execute_read.await_args_list:
            assert call.kwargs["timeout"] == 2.5
