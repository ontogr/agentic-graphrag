"""Tests for Text2CypherRetriever."""

import json
import logging
import sys
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.relation import Relation
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

    async def test_returns_empty_without_baml_client(self) -> None:
        """A missing BAML client yields no results and no query."""
        gs = AsyncMock()
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.dict(sys.modules, {"agrag.llm.baml_client": None}):
            results = await retriever.retrieve("what is X?")

        assert results == []
        gs.execute_read.assert_not_awaited()

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

    async def test_accepts_vector_query_call(self) -> None:
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


class TestText2CypherRowShapes:
    """Structured rows are surfaced as Entity/Relation/Chunk results."""

    async def test_relation_row_becomes_search_result(self) -> None:
        """A relationship row is wrapped in a Relation, not dropped."""
        gs = AsyncMock()
        rel_id = uuid4()
        src_id = uuid4()
        tgt_id = uuid4()
        rel = {
            "id": str(rel_id),
            "type": "KNOWS",
            "start_id": str(src_id),
            "end_id": str(tgt_id),
            "source_chunk_ids": [],
        }
        gs.execute_read.return_value = [{"r": rel}]
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH ()-[r:KNOWS]->() RETURN r",
        ):
            results = await retriever.retrieve("who knows who?")

        assert len(results) == 1
        assert isinstance(results[0].item, Relation)
        assert results[0].item.id == rel_id
        assert results[0].item.type == "KNOWS"
        assert results[0].item.source_id == src_id
        assert results[0].item.target_id == tgt_id

    async def test_chunk_row_becomes_search_result(self) -> None:
        """A chunk node row is wrapped in a Chunk, not dropped."""
        gs = AsyncMock()
        chunk_id = uuid4()
        doc_id = uuid4()
        provenance = {
            "kind": "text",
            "char_start": 0,
            "char_end": 9,
        }
        chunk = {
            "id": str(chunk_id),
            "document_id": str(doc_id),
            "index": 0,
            "text": "Hello world",
            "provenance": json.dumps(provenance),
            "heading_path": [],
            "content_kind": "text",
        }
        gs.execute_read.return_value = [{"c": chunk}]
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH (c:Chunk) RETURN c LIMIT 5",
        ):
            results = await retriever.retrieve("hello world")

        assert len(results) == 1
        assert isinstance(results[0].item, Chunk)
        assert results[0].item.id == chunk_id
        assert results[0].item.text == "Hello world"

    async def test_scalar_row_is_logged_not_dropped_silently(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A scalar row is logged as a warning, not silently dropped.

        A query like ``RETURN count(p)`` cannot become a SearchResult
        (count is not an Entity, Relation, or Chunk). The retriever
        must not pretend there were no results; it must log the row
        so the caller can see a structured answer was returned.
        """
        gs = AsyncMock()
        gs.execute_read.return_value = [{"count(p)": 42}]
        retriever = Text2CypherRetriever(graph_store=gs)

        with (
            patch.object(
                retriever,
                "_generate_cypher",
                return_value="MATCH (p:Person) RETURN count(p)",
            ),
            caplog.at_level(
                logging.WARNING, logger="agrag.retrieval.retrievers.text2cypher"
            ),
        ):
            results = await retriever.retrieve("how many people?")

        assert results == []
        assert any("count(p)" in record.message for record in caplog.records)

    async def test_relation_with_embedded_start_end(self) -> None:
        """A relationship row carrying embedded start/end nodes is parsed."""
        gs = AsyncMock()
        rel_id = uuid4()
        src_id = uuid4()
        tgt_id = uuid4()
        rel = {
            "id": str(rel_id),
            "type": "MENTIONED_IN",
            "start": {"id": str(src_id)},
            "end": {"id": str(tgt_id)},
        }
        gs.execute_read.return_value = [{"r": rel}]
        retriever = Text2CypherRetriever(graph_store=gs)

        with patch.object(
            retriever,
            "_generate_cypher",
            return_value="MATCH ()-[r]->() RETURN r",
        ):
            results = await retriever.retrieve("edges")

        assert len(results) == 1
        assert isinstance(results[0].item, Relation)
        assert results[0].item.source_id == src_id
        assert results[0].item.target_id == tgt_id
