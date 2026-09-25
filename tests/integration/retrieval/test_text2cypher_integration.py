"""Integration tests for Text2CypherRetriever against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). Every test seeds
a freshly and randomly labelled graph under a custom, non-``GENERIC``
:class:`GraphSchema`, then deletes only its own labels, so the suite can run
alongside other tests against one database.

The query-execution and retry tests stub the generated client's ``b`` object,
so they exercise the real EXPLAIN, execution, and row-parsing path against
the database without a model. The tests that assert on generated query text
call a real model instead; they skip unless ``LLM_BASE_URL`` and
``LLM_MODEL_ID`` name an endpoint to call.
"""

import importlib.util
import os
import re
import types
from collections.abc import AsyncGenerator, Sequence
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from dotenv import load_dotenv

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.recipes import TEXT2CYPHER
from agrag.retrieval.retrievers.text2cypher import Text2CypherRetriever
from agrag.retrieval.search_engine import SearchEngine


neo4j_missing = importlib.util.find_spec("neo4j") is None
baml_missing = importlib.util.find_spec("baml_py") is None


def _llm_endpoint_configured() -> bool:
    """Return True when the shared OpenAI-compatible endpoint is configured."""
    load_dotenv()
    return bool(os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL_ID"))


class _FixedEmbedder(Embedder):
    """Embedder returning a deterministic vector.

    The text2cypher path never embeds, but SearchEngine requires an embedder
    to construct.
    """

    model = "fixed"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one deterministic vector per text."""
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _entity_node(node_id: UUID, label: str, name: str) -> NodeRecord:
    """Build an entity node record carrying the properties retrieval parses."""
    return NodeRecord(
        id=node_id,
        labels=[label],
        properties={
            "name": name,
            "merge_key": f"{label}:{name.lower()}",
            "merged_from": [],
            "merge_count": 1,
            "source_chunk_ids": [],
            "created_at": "2024-01-01T00:00:00",
        },
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(baml_missing, reason="baml-py extra not installed")
class TestText2CypherIntegration:
    """Schema-grounded generation and retry against real Neo4j."""

    @pytest.fixture(autouse=True)
    async def setup_store(self) -> AsyncGenerator[None, None]:
        """Connect, build a custom schema, and seed this test's own graph."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        suffix = uuid4().hex[:8]
        self.person_label = validate_identifier(f"Person_{suffix}")
        self.org_label = validate_identifier(f"Organization_{suffix}")
        self.location_label = validate_identifier(f"Location_{suffix}")
        self.founded_type = validate_identifier(f"FOUNDED_{suffix.upper()}")
        self.located_type = validate_identifier(f"LOCATED_IN_{suffix.upper()}")
        self.schema = GraphSchema(
            name=f"integration_{suffix}",
            version="1",
            entities=[
                EntityType(label=self.person_label, description="A person."),
                EntityType(label=self.org_label, description="An organization."),
                EntityType(label=self.location_label, description="A place."),
            ],
            relations=[
                RelationType(
                    label=self.founded_type,
                    description="A person founded an organization.",
                    patterns=[(self.person_label, self.org_label)],
                ),
                RelationType(
                    label=self.located_type,
                    description="An organization is located in a place.",
                    patterns=[(self.org_label, self.location_label)],
                ),
            ],
        )
        await self._seed()
        yield
        for label in (self.person_label, self.org_label, self.location_label):
            await self.store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
        await self.store.close()

    async def _seed(self) -> None:
        """Write one person, the organization they founded, and its location."""
        self.person_id, self.org_id, self.location_id = uuid4(), uuid4(), uuid4()
        await self.store.upsert_nodes(
            self.person_label,
            [_entity_node(self.person_id, self.person_label, "Ada")],
        )
        await self.store.upsert_nodes(
            self.org_label,
            [_entity_node(self.org_id, self.org_label, "Acme")],
        )
        await self.store.upsert_nodes(
            self.location_label,
            [_entity_node(self.location_id, self.location_label, "Cambridge")],
        )
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type=self.founded_type,
                    start_id=self.person_id,
                    end_id=self.org_id,
                    properties={},
                ),
                RelationRecord(
                    id=uuid4(),
                    type=self.located_type,
                    start_id=self.org_id,
                    end_id=self.location_id,
                    properties={},
                ),
            ]
        )

    async def _retrieve_with_stubbed_generation(
        self, question: str, *queries: str
    ) -> tuple[list, list[str | None]]:
        """Run ``retrieve`` with generation stubbed to return ``queries``.

        Args:
            question: The natural-language question to ask.
            *queries: One generated query per generation call. The last one is
                reused for any further calls.

        Returns:
            The retrieved results and the ``failure_context`` of every
            generation call, in call order.
        """
        contexts: list[str | None] = []

        async def generate(**kwargs: object) -> str:
            contexts.append(kwargs.get("failure_context"))
            index = min(len(contexts) - 1, len(queries) - 1)
            return queries[index]

        retriever = Text2CypherRetriever(graph_store=self.store, schema=self.schema)
        with patch(
            "agrag.llm.baml_client.b",
            types.SimpleNamespace(GenerateCypherQuery=generate),
        ):
            results = await retriever.retrieve(question)
        return results, contexts

    async def test_retrieve_executes_a_generated_query_against_the_real_graph(
        self,
    ) -> None:
        """A generated query runs on Neo4j and its rows become entities."""
        results, contexts = await self._retrieve_with_stubbed_generation(
            "Who is in the graph?",
            f"MATCH (n:{self.person_label}) RETURN n",
        )

        assert contexts == [None]
        assert [result.item.id for result in results] == [self.person_id]
        assert isinstance(results[0].item, Entity)
        assert results[0].method.startswith("text2cypher: ")

    async def test_an_arbitrary_node_alias_still_returns_entities(self) -> None:
        """A query naming its returned node freely still yields entities."""
        results, contexts = await self._retrieve_with_stubbed_generation(
            "Who is in the graph?",
            f"MATCH (p:{self.person_label}) RETURN p",
        )

        assert contexts == [None]
        assert [result.item.id for result in results] == [self.person_id]

    async def test_retrieve_retries_a_query_neo4j_cannot_plan(self) -> None:
        """A real EXPLAIN failure is retried once, then executes for real."""
        results, contexts = await self._retrieve_with_stubbed_generation(
            "Who is in the graph?",
            "MATCH (n RETURN n",
            f"MATCH (n:{self.person_label}) RETURN n",
        )

        assert len(contexts) == 2
        assert contexts[0] is None
        # A real Neo4j syntax error, scrubbed of the offending query text.
        assert contexts[1]
        assert "MATCH" not in contexts[1]
        assert "ClientError" in contexts[1]
        assert [result.item.id for result in results] == [self.person_id]

    async def test_both_attempts_failing_returns_no_results(self) -> None:
        """Two unplannable queries name no results and stop at one retry."""
        results, contexts = await self._retrieve_with_stubbed_generation(
            "Who is in the graph?",
            "MATCH (n RETURN n",
        )

        assert results == []
        assert len(contexts) == 2

    async def test_search_engine_grounds_text2cypher_in_its_schema(self) -> None:
        """The TEXT2CYPHER recipe reaches a retriever holding engine's schema."""
        engine = SearchEngine(
            graph_store=self.store,
            embedder=_FixedEmbedder(),
            graph_schema=self.schema,
        )
        prompts: list[str] = []

        async def generate(**kwargs: object) -> str:
            prompts.append(str(kwargs["schema_description"]))
            return f"MATCH (n:{self.person_label}) RETURN n"

        with patch(
            "agrag.llm.baml_client.b",
            types.SimpleNamespace(GenerateCypherQuery=generate),
        ):
            results = await engine.search("Who is in the graph?", TEXT2CYPHER)

        assert prompts == [self.schema.to_prompt_description()]
        assert [result.item.id for result in results] == [self.person_id]
        assert results[0].method.startswith("text2cypher: ")

    @pytest.mark.skipif(
        not _llm_endpoint_configured(), reason="LLM endpoint not configured"
    )
    async def test_generated_cypher_uses_only_the_passed_schema(self) -> None:
        """Generation names the custom schema's labels, not the old default."""
        retriever = Text2CypherRetriever(graph_store=self.store, schema=self.schema)

        cypher = await retriever._generate_cypher(
            f"Which {self.org_label} was founded by a {self.person_label}?"
        )

        assert self.person_label in cypher
        assert self.org_label in cypher
        assert "RELATED_TO" not in cypher
        assert "MENTIONED_IN" not in cypher

    @pytest.mark.skipif(
        not _llm_endpoint_configured(), reason="LLM endpoint not configured"
    )
    async def test_multi_hop_question_generates_a_multi_hop_query(self) -> None:
        """A question needing two relationships does not collapse to one."""
        retriever = Text2CypherRetriever(graph_store=self.store, schema=self.schema)

        cypher = await retriever._generate_cypher(
            f"Which {self.location_label} is the {self.org_label} named Acme "
            f"located in, counting the {self.person_label} who founded it?"
        )

        assert len(re.findall(r"-\s*\[", cypher)) >= 2
