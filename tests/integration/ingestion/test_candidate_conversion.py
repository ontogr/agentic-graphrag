"""Exercise approved-candidate conversion against a real Neo4j database."""

import importlib.util
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agrag.common.data_models.candidate_review import PatchBase, SchemaPatch
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.ingestion import Extractor, Graph
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCandidateConversionIntegration:
    """Conversion preserves graph identity and removes only handled candidates."""

    async def test_converts_once_and_folds_exact_name(self, tmp_path) -> None:  # noqa: PLR0915
        """Entity conversion and folding retain evidence and become no-ops."""
        store = build_test_store()
        await store.connect()
        suffix = uuid4().hex[:8]
        person = f"Person_{suffix}"
        schema = GraphSchema(
            name="conversion-test",
            version="2",
            entities=[
                EntityType(
                    label=person,
                    description="A person.",
                    properties={
                        "score": PropertySpec(type="integer"),
                        "description": PropertySpec(type="string"),
                    },
                )
            ],
            relations=[
                RelationType(
                    label="WORKS_FOR",
                    description="A relation.",
                    patterns=[(person, person)],
                )
            ],
        )
        (
            candidate_id,
            fold_id,
            relation_candidate_id,
            property_candidate_id,
            conflicting_property_id,
            description_candidate_id,
        ) = (uuid4() for _ in range(6))
        chunk_id, property_chunk_id, owner_id = uuid4(), uuid4(), uuid4()
        patch = SchemaPatch(
            patch_id=uuid4().hex[:16],
            created_at=datetime.now(UTC),
            base_schema=PatchBase(name=schema.name, version="1", fingerprint="old"),
            candidate_ids=[
                candidate_id,
                fold_id,
                relation_candidate_id,
                property_candidate_id,
                conflicting_property_id,
                description_candidate_id,
            ],
            additions={"entities": [], "relations": []},
        )
        try:
            await store.execute_write(
                f"CREATE (chunk:{NODE_IDENTITY_LABEL}:Chunk {{id: $chunk}}) "
                f"CREATE (owner:{NODE_IDENTITY_LABEL}:{person} {{id: $owner, "
                "name: 'Existing', merge_key: $merge_key, merge_count: 1, "
                "source_chunk_ids: []}) "
                "CREATE (a:_MergeAlias {merge_key: $merge_key, entity_id: $owner}) "
                f"CREATE (property_chunk:{NODE_IDENTITY_LABEL}:Chunk "
                "{id: $property_chunk})",
                {
                    "chunk": str(chunk_id),
                    "property_chunk": str(property_chunk_id),
                    "owner": str(owner_id),
                    "merge_key": f"{person}:existing",
                },
            )
            for candidate_id_value, name, key in (
                (candidate_id, "New Person", f"{person}:new person"),
                (fold_id, "Existing", f"{person}:existing"),
            ):
                await store.execute_write(
                    "CREATE (c:Candidate {id: $id, kind: 'entity', label: $label, "
                    "text: $name, key: $key, state: 'approved', count: 1, "
                    "confidence: 1.0, reason: 'entity_band', "
                    "schema_fingerprint: 'old', chunk_id: $chunk}) "
                    "WITH c MATCH (chunk:_Node {id: $chunk}) "
                    "CREATE (c)-[:EVIDENCED_BY]->(chunk)",
                    {
                        "id": str(candidate_id_value),
                        "label": person,
                        "name": name,
                        "key": key,
                        "chunk": str(chunk_id),
                    },
                )
            await store.execute_write(
                "CREATE (relation:Candidate {id: $relation_id, kind: 'relation', "
                "label: 'WORKS_FOR', text: '', source_text: 'Existing', "
                "target_text: 'Existing', source_entity_id: $owner, "
                "target_entity_id: $owner, source_label: $person, "
                "target_label: $person, state: 'approved', count: 1, "
                "confidence: 1.0, reason: 'off_pattern', schema_fingerprint: 'old', "
                "chunk_id: $chunk}), "
                "(property:Candidate {id: $property_id, kind: 'property', "
                "label: 'score', text: '42', source_text: 'Existing', "
                "source_entity_id: $owner, source_label: $person, state: 'approved', "
                "count: 1, confidence: 1.0, reason: 'property', "
                "schema_fingerprint: 'old', chunk_id: $chunk}) "
                "WITH relation, property MATCH (chunk:_Node {id: $chunk}) "
                "CREATE (relation)-[:EVIDENCED_BY]->(chunk) "
                "CREATE (property)-[:EVIDENCED_BY]->(chunk) "
                "WITH relation, property, chunk "
                "CREATE (conflict:Candidate {id: $conflict_id, kind: 'property', "
                "label: 'score', text: '43', source_text: 'Existing', "
                "source_entity_id: $owner, source_label: $person, state: 'approved', "
                "count: 1, confidence: 1.0, reason: 'property', "
                "schema_fingerprint: 'old', chunk_id: $chunk}) "
                "CREATE (conflict)-[:EVIDENCED_BY]->(chunk) "
                "WITH relation, property, chunk "
                "CREATE (description:Candidate {id: $description_id, kind: 'property', "
                "label: 'description', text: 'A useful person.', "
                "source_text: 'Existing', source_entity_id: $owner, "
                "source_label: $person, state: 'approved', count: 1, "
                "confidence: 1.0, reason: 'property', schema_fingerprint: 'old', "
                "chunk_id: $property_chunk}) "
                "WITH description MATCH (property_chunk:_Node {id: $property_chunk}) "
                "CREATE (description)-[:EVIDENCED_BY]->(property_chunk)",
                {
                    "relation_id": str(relation_candidate_id),
                    "property_id": str(property_candidate_id),
                    "conflict_id": str(conflicting_property_id),
                    "description_id": str(description_candidate_id),
                    "owner": str(owner_id),
                    "person": person,
                    "chunk": str(chunk_id),
                    "property_chunk": str(property_chunk_id),
                },
            )

            await store.ensure_fulltext_index(label=person, properties=["name"])
            graph = Graph(
                schema=schema,
                graph_store=store,
                embedder=_IntegrationEmbedder(),
                extractor=_IntegrationExtractor(),
            )
            report = await graph.convert_candidates(patch)
            assert report.converted_entities == 1
            assert report.folded == 1
            assert report.created_relations == 1
            assert report.set_properties == 1
            assert report.skipped[str(property_candidate_id)] == "property_conflict"
            assert report.skipped[str(conflicting_property_id)] == "property_conflict"
            artifact = tmp_path / "conversion-report.json"
            artifact.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            assert artifact.is_file()

            converted = await store.execute_read(
                f"MATCH (n:{NODE_IDENTITY_LABEL}:{person} {{id: $id}}) "
                "RETURN labels(n) AS labels, n.embedding AS embedding",
                {"id": str(candidate_id)},
            )
            assert len(converted) == 1
            assert person in converted[0]["labels"]
            assert converted[0]["embedding"] == [1.0, 0.0, 0.0, 0.0]
            call = await store.fulltext_search_call(label=person, properties=["name"])
            found = await store.execute_read(
                f"{call.text} RETURN node.id AS id",
                {**call.params, "fulltext_terms": "new person", "k": 5},
            )
            assert [row["id"] for row in found] == [str(candidate_id)]
            candidate_edges = await store.execute_read(
                "MATCH (entity:_Node {id: $id})-[edge:SOURCE|TARGET]-() "
                "RETURN count(edge) AS count",
                {"id": str(candidate_id)},
            )
            assert candidate_edges == [{"count": 0}]
            assert await store.execute_read(
                "MATCH (:Candidate {id: $id}) RETURN count(*) AS count",
                {"id": str(candidate_id)},
            ) == [{"count": 0}]
            mention = await store.execute_read(
                "MATCH (c:_Node {id: $chunk})-[:MENTIONED_IN]->"
                "(e:_Node {id: $entity}) RETURN count(*) AS count",
                {"chunk": str(chunk_id), "entity": str(candidate_id)},
            )
            assert mention[0]["count"] == 1
            folded_owner = await store.execute_read(
                f"MATCH (chunk:_Node {{id: $chunk}})-[:MENTIONED_IN]->"
                f"(owner:{person} {{id: $owner}}) "
                "RETURN owner.merge_count AS merge_count, "
                "owner.source_chunk_ids AS source_chunk_ids",
                {"chunk": str(chunk_id), "owner": str(owner_id)},
            )
            assert folded_owner[0]["merge_count"] == 2
            assert str(chunk_id) in folded_owner[0]["source_chunk_ids"]
            assert str(property_chunk_id) in folded_owner[0]["source_chunk_ids"]
            converted_relation = await store.execute_read(
                "MATCH (owner:_Node {id: $owner})-[edge:WORKS_FOR]->(owner) "
                "RETURN edge.source_chunk_ids AS chunks",
                {"owner": str(owner_id)},
            )
            assert converted_relation[0]["chunks"] == [str(chunk_id)]
            property_value = await store.execute_read(
                f"MATCH (owner:{person} {{id: $owner}}) RETURN owner.score AS score",
                {"owner": str(owner_id)},
            )
            assert property_value[0]["score"] is None
            retained_conflicts = await store.execute_read(
                "MATCH (c:Candidate) WHERE c.id IN $ids "
                "RETURN count(*) AS count, collect(DISTINCT c.state) AS states",
                {
                    "ids": [
                        str(property_candidate_id),
                        str(conflicting_property_id),
                    ]
                },
            )
            assert retained_conflicts == [{"count": 2, "states": ["approved"]}]
            property_provenance = await store.execute_read(
                f"MATCH (owner:{person} {{id: $owner}}) "
                "RETURN owner.description AS description, "
                "owner.source_chunk_ids AS source_chunk_ids",
                {"owner": str(owner_id)},
            )
            assert property_provenance[0]["description"] == "A useful person."
            assert set(property_provenance[0]["source_chunk_ids"]) == {
                str(chunk_id),
                str(property_chunk_id),
            }

            repeated = await graph.convert_candidates(patch)
            assert repeated.converted_entities == 0
            assert repeated.folded == 0
            assert repeated.skipped[str(candidate_id)] == "not approved"
            assert repeated.skipped[str(relation_candidate_id)] == "not approved"
            assert repeated.skipped[str(property_candidate_id)] == "property_conflict"
        finally:
            await store.close()
            cleanup_store = build_test_store()
            await cleanup_store.connect()
            try:
                await cleanup_store.execute_write(
                    "MATCH (n:_Node) WHERE n.id IN $ids DETACH DELETE n",
                    {
                        "ids": [
                            str(candidate_id),
                            str(fold_id),
                            str(relation_candidate_id),
                            str(property_candidate_id),
                            str(conflicting_property_id),
                            str(description_candidate_id),
                            str(chunk_id),
                            str(property_chunk_id),
                            str(owner_id),
                        ]
                    },
                )
                await cleanup_store.execute_write(
                    "MATCH (a:_MergeAlias) WHERE a.entity_id IN $ids DELETE a",
                    {"ids": [str(owner_id), str(candidate_id)]},
                )
                await cleanup_store.execute_write(
                    "MATCH (candidate:Candidate) WHERE candidate.id IN $ids "
                    "DETACH DELETE candidate",
                    {
                        "ids": [
                            str(candidate_id),
                            str(fold_id),
                            str(relation_candidate_id),
                            str(property_candidate_id),
                            str(conflicting_property_id),
                            str(description_candidate_id),
                        ]
                    },
                )
            finally:
                await cleanup_store.close()


class _IntegrationEmbedder(Embedder):
    """Supply deterministic vectors without an external embedding service."""

    model = "candidate-conversion-test"

    async def dimensions(self) -> int:
        return FAKE_EMBEDDING_DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, *([0.0] * (FAKE_EMBEDDING_DIMENSIONS - 1))] for _ in texts]


class _IntegrationExtractor(Extractor):
    """A placeholder extractor; conversion does not invoke extraction."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        return ExtractionResult(entities=[], relations=[], extractor_name="test")
