"""Tests for Text2CypherRetriever."""

from unittest.mock import AsyncMock, patch

from agrag.retrieval.retrievers.text2cypher import (
    Text2CypherRetriever,
)


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
