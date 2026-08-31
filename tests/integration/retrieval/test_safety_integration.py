"""Integration tests for the Cypher safety gate against real Neo4j.

Tests that reject_write_cypher catches write clauses and that
read Cypher executes successfully through execute_read.
"""

import importlib.util
from collections.abc import AsyncGenerator, Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.graph_record import NodeRecord
from agrag.cypher.entities import validate_identifier
from agrag.cypher.safety import UnsafeCypherError, reject_write_cypher
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store


neo4j_missing = importlib.util.find_spec("neo4j") is None

if not neo4j_missing:
    from neo4j.exceptions import ClientError  # noqa: PLC0415


class _FixedEmbedder(Embedder):
    """Embedder returning deterministic vectors."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors."""
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


@pytest.mark.integration
@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestSafetyGateIntegration:
    """Safety gate behavior against real Neo4j."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Set up a fresh store."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        await self.store.close()

    def test_reject_delete_before_explain(self) -> None:
        """DELETE is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="DELETE"):
            reject_write_cypher("MATCH (n:Person) DELETE n")

    def test_reject_create_before_explain(self) -> None:
        """CREATE is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="CREATE"):
            reject_write_cypher("CREATE (n:Person {name: 'test'})")

    def test_reject_merge_before_explain(self) -> None:
        """MERGE is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="MERGE"):
            reject_write_cypher("MERGE (n:Person {name: 'test'})")

    def test_reject_set_before_explain(self) -> None:
        """SET is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="SET"):
            reject_write_cypher("MATCH (n) SET n.name = 'x'")

    def test_reject_remove_before_explain(self) -> None:
        """REMOVE is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="REMOVE"):
            reject_write_cypher("MATCH (n) REMOVE n.embedding")

    def test_reject_drop_before_explain(self) -> None:
        """DROP is rejected before any EXPLAIN reaches Neo4j."""
        with pytest.raises(UnsafeCypherError, match="DROP"):
            reject_write_cypher("DROP INDEX my_index")

    def test_accept_pure_match_return(self) -> None:
        """A pure MATCH...RETURN query is accepted."""
        reject_write_cypher("MATCH (n:Person) RETURN n LIMIT 5")

    def test_accept_call_vector_query(self) -> None:
        """CALL db.index.vector.queryNodes is accepted (read Cypher)."""
        reject_write_cypher(
            "CALL db.index.vector.queryNodes('idx', 10, $vector) "
            "YIELD node, score RETURN node, score"
        )

    def test_ignore_keywords_in_string_literals(self) -> None:
        """DELETE inside a string literal does not trigger rejection."""
        reject_write_cypher("RETURN 'This query will DELETE nothing'")

    def test_reject_write_inside_read_shape(self) -> None:
        """A DELETE inside a valid-looking read query is rejected."""
        with pytest.raises(UnsafeCypherError):
            reject_write_cypher(
                "MATCH (n:Person) WHERE n.name = $name DELETE n RETURN n"
            )

    async def test_read_cypher_executes_on_real_store(self) -> None:
        """A pure read query executes successfully on real Neo4j."""
        # Seed a node.
        node_id = uuid4()
        await self.store.upsert_nodes(
            self.label,
            [
                NodeRecord(
                    id=node_id,
                    labels=[self.label],
                    properties={"name": "Alice"},
                )
            ],
        )

        # Execute a read query.
        rows = await self.store.execute_read(
            f"MATCH (n:{self.label} {{id: $id}}) RETURN n.name AS name",
            {"id": str(node_id)},
        )

        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    async def test_write_cypher_rejected_by_read_transaction(
        self,
    ) -> None:
        """A write query fails in execute_read (read transaction).

        Neo4j's read transaction rejects write clauses, providing
        the ultimate safety boundary.
        """
        with pytest.raises(ClientError):
            await self.store.execute_read(
                f"CREATE (n:{self.label} {{name: 'test'}}) RETURN n"
            )

    async def test_explain_catches_syntax_error(self) -> None:
        """EXPLAIN catches malformed Cypher before execution."""
        with pytest.raises(ClientError):
            await self.store.execute_read("EXPLAIN INVALID CYPHER SYNTAX!!!")

    async def test_reject_cypher_with_hidden_merge(self) -> None:
        """MERGE hidden in a complex query is still rejected."""
        with pytest.raises(UnsafeCypherError, match="MERGE"):
            reject_write_cypher(
                "MATCH (a:Person) MERGE (b:Person {name: a.name}) RETURN a, b"
            )
