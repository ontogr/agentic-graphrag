"""Exercise candidate review against the configured Neo4j service."""

import importlib.util
import json
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from agrag.candidates import (
    CandidateQuery,
    approve_candidates,
    list_candidates,
    prune_candidates,
    reject_candidates,
)
from agrag.candidates.errors import PatchNotAppliedError
from agrag.candidates.patch import read_patch
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import Extractor, Graph
from agrag.schema import load_schema


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCandidateReview:
    """Review transitions preserve candidate state and create a patch."""

    async def test_lists_approves_and_rejects_candidates(self) -> None:
        """Approval returns schema additions and rejection remains in the store."""
        store = build_graph_store("neo4j")
        await store.connect()
        chunk_id = str(uuid4())
        approve_record = CandidateRecord(
            kind="entity",
            label="ReviewNovelEntity",
            text="Review sample",
            confidence=0.7,
            reason="entity_band",
            chunk_id=uuid4(),
        )
        reject_record = CandidateRecord(
            kind="entity",
            label="ReviewRejectedEntity",
            text="Reject sample",
            confidence=0.6,
            reason="entity_band",
            chunk_id=uuid4(),
        )
        try:
            await store.execute_write(
                f"CREATE (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}})",
                {"id": chunk_id},
            )
            approved_candidate = approve_record.model_copy(
                update={"chunk_id": UUID(chunk_id)}
            )
            rejected_candidate = reject_record.model_copy(
                update={"chunk_id": UUID(chunk_id)}
            )
            await store.upsert_candidates([approved_candidate, rejected_candidate])

            groups = await list_candidates(
                store, CandidateQuery(label="ReviewNovelEntity")
            )
            assert len(groups) == 1
            assert groups[0].count == 1
            approval = await approve_candidates(
                store, DEFAULT_SCHEMA, ids=[approved_candidate.id]
            )
            rejection = await reject_candidates(store, keys=[rejected_candidate.key])

            assert approval.outcome.changed == [approved_candidate.key]
            assert approval.patch is not None
            assert approval.patch.additions["entities"] == [
                {"label": "ReviewNovelEntity", "description": ""}
            ]
            assert rejection.changed == [rejected_candidate.key]
            states = await store.execute_read(
                "MATCH (c:Candidate) WHERE c.id IN $ids "
                "RETURN c.id AS id, c.state AS state",
                {"ids": [str(approved_candidate.id), str(rejected_candidate.id)]},
            )
            assert {row["id"]: row["state"] for row in states} == {
                str(approved_candidate.id): "approved",
                str(rejected_candidate.id): "rejected",
            }
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [chunk_id, str(approve_record.id), str(reject_record.id)]},
            )
            await store.close()

    async def test_approval_writes_repeatable_patch_artifact(self, tmp_path) -> None:
        """Entity approval emits a patch file that can be read back exactly."""
        store = build_graph_store("neo4j")
        await store.connect()
        chunk_ids = [str(uuid4()), str(uuid4())]
        records = [
            CandidateRecord(
                kind="entity",
                label="ReviewArtifactEntity",
                text=text,
                confidence=0.8,
                reason="entity_band",
                chunk_id=UUID(chunk_id),
            )
            for text, chunk_id in zip(
                ("Artifact sample", "The Artifact sample"), chunk_ids, strict=True
            )
        ]
        path = tmp_path / "candidate-patch.json"
        try:
            await store.execute_write(
                f"UNWIND $ids AS id CREATE (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
                "{id: id})",
                {"ids": chunk_ids},
            )
            await store.upsert_candidates(records)
            result = await approve_candidates(
                store, DEFAULT_SCHEMA, ids=[records[0].id], output=path
            )

            assert result.patch is not None
            assert path.exists()
            assert read_patch(path) == result.patch
            assert json.loads(path.read_text())["candidate_ids"] == sorted(
                str(record.id) for record in records
            )
            assert result.patch.evidence["entity:ReviewArtifactEntity"] == 2
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": chunk_ids + [str(candidate.id) for candidate in records]},
            )
            await store.close()

    async def test_candidate_review_patch_conversion_and_pruning(  # noqa: PLR0915
        self, tmp_path
    ):
        """Review, schema activation, conversion and pruning work end to end."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_ReviewEmbedder(),
            extractor=_ReviewExtractor(),
        )
        ids = {
            name: uuid4()
            for name in (
                "ada",
                "beacon",
                "ambiguous",
                "ambiguous_org",
                "chunk_relation",
                "chunk_property",
                "chunk_rejected",
                "chunk_prunable",
                "relation",
                "property",
                "ambiguous_relation",
                "rejected",
                "prunable",
            )
        }
        patch_path = tmp_path / "review-patch.json"
        report_path = tmp_path / "conversion-report.json"
        records = [
            CandidateRecord(
                id=ids["relation"],
                kind="relation",
                label="MENTORS",
                source_text="Ada",
                target_text="Beacon Inc",
                confidence=0.8,
                reason="unresolved_endpoint",
                chunk_id=ids["chunk_relation"],
            ),
            CandidateRecord(
                id=ids["property"],
                kind="property",
                label="review_score",
                text="42",
                source_text="Ada",
                source_label="Person",
                confidence=0.7,
                reason="property",
                chunk_id=ids["chunk_property"],
            ),
            CandidateRecord(
                id=ids["ambiguous_relation"],
                kind="relation",
                label="MENTORS",
                source_text="Ada",
                target_text="Beacon",
                confidence=0.6,
                reason="unresolved_endpoint",
                chunk_id=ids["chunk_property"],
            ),
            CandidateRecord(
                id=ids["rejected"],
                kind="entity",
                label="ReviewRejected",
                text="Do not restore",
                confidence=0.4,
                reason="entity_band",
                chunk_id=ids["chunk_rejected"],
            ),
            CandidateRecord(
                id=ids["prunable"],
                kind="entity",
                label="ReviewDiscarded",
                text="Discard me",
                confidence=0.3,
                reason="entity_band",
                chunk_id=ids["chunk_prunable"],
            ),
        ]
        try:
            await store.execute_write(
                f"UNWIND $rows AS row CREATE (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
                "{id: row.id}), (e:_Node:Person {id: row.ada, name: 'Ada', "
                "merge_key: 'Person:ada', merge_count: 1, source_chunk_ids: []}), "
                "(o:_Node:Organization {id: row.beacon, name: 'Beacon Inc', "
                "merge_key: 'Organization:beacon inc', merge_count: 1, "
                "source_chunk_ids: []}), (amb:_Node:Person {id: row.ambiguous, "
                "name: 'Beacon', merge_key: 'Person:beacon', merge_count: 1, "
                "source_chunk_ids: []}), (amb_org:_Node:Organization "
                "{id: row.ambiguous_org, name: 'Beacon', merge_key: "
                "'Organization:beacon', merge_count: 1, source_chunk_ids: []}) "
                "WITH row MATCH (e:_Node {id: row.ada}), (o:_Node {id: row.beacon}), "
                "(amb:_Node {id: row.ambiguous}), "
                "(amb_org:_Node {id: row.ambiguous_org}) "
                "CREATE (a:_MergeAlias {merge_key: 'Person:ada', entity_id: row.ada}), "
                "(b:_MergeAlias {merge_key: 'Organization:beacon inc', "
                "entity_id: row.beacon}), "
                "(x:_MergeAlias {merge_key: 'Person:beacon', "
                "entity_id: row.ambiguous}), "
                "(y:_MergeAlias {merge_key: 'Organization:beacon', "
                "entity_id: row.ambiguous_org})",
                {
                    "rows": [
                        {
                            "id": str(ids["chunk_relation"]),
                            "ada": str(ids["ada"]),
                            "beacon": str(ids["beacon"]),
                            "ambiguous": str(ids["ambiguous"]),
                            "ambiguous_org": str(ids["ambiguous_org"]),
                        }
                    ]
                },
            )
            # Every candidate needs a stored evidence chunk.
            for chunk_name in ("chunk_property", "chunk_rejected", "chunk_prunable"):
                await store.execute_write(
                    f"CREATE (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}})",
                    {"id": str(ids[chunk_name])},
                )
            await store.upsert_candidates(records)

            rejected = await reject_candidates(store, keys=[records[3].key])
            assert rejected.changed == [records[3].key]
            await store.upsert_candidates([records[3]])
            rejected_again = await list_candidates(
                store, CandidateQuery(label="ReviewRejected", state="rejected")
            )
            assert len(rejected_again) == 1
            assert rejected_again[0].state == "rejected"
            approval = await approve_candidates(
                store,
                DEFAULT_SCHEMA,
                ids=[
                    ids["relation"],
                    ids["property"],
                    ids["ambiguous_relation"],
                    ids["rejected"],
                ],
                output=patch_path,
            )
            assert approval.outcome.changed == [records[0].key, records[1].key]
            assert (
                approval.outcome.skipped[str(ids["ambiguous_relation"])]
                == "endpoint_ambiguous"
            )
            assert approval.outcome.skipped[str(ids["rejected"])] == "state is rejected"
            patch = read_patch(patch_path)
            assert patch == approval.patch
            assert patch.additions["relations"] == [
                {
                    "label": "MENTORS",
                    "description": "",
                    "patterns": [["Person", "Organization"]],
                }
            ]
            assert [(item.entity, item.name) for item in patch.add_properties] == [
                ("Person", "review_score")
            ]

            dry_run = await prune_candidates(store, rejected=True)
            assert (dry_run.matched, dry_run.deleted, dry_run.applied) == (1, 0, False)
            applied = await prune_candidates(store, rejected=True, apply=True)
            assert (applied.matched, applied.deleted, applied.applied) == (1, 1, True)
            states = await store.execute_read(
                "MATCH (c:Candidate) WHERE c.id IN $ids "
                "RETURN c.id AS id, c.state AS state",
                {
                    "ids": [
                        str(ids[name]) for name in ("relation", "property", "rejected")
                    ]
                },
            )
            assert {row["id"]: row["state"] for row in states} == {
                str(ids["relation"]): "approved",
                str(ids["property"]): "approved",
            }

            with pytest.raises(PatchNotAppliedError):
                await graph.convert_candidates(patch)
            still_approved = await store.execute_read(
                "MATCH (c:Candidate) WHERE c.id IN $ids RETURN count(c) AS count",
                {"ids": [str(ids["relation"]), str(ids["property"])]},
            )
            assert still_approved == [{"count": 2}]

            overlay = {
                "entities": [
                    {
                        "label": "Person",
                        "override": True,
                        "properties": {"review_score": {"type": "integer"}},
                    }
                ],
                "relations": patch.additions["relations"],
            }
            updated_schema = load_schema(overlay, extends=DEFAULT_SCHEMA)
            assert {entity.label for entity in updated_schema.entities} >= {
                "Person",
                "Organization",
                "Location",
            }
            assert updated_schema.allows("MENTORS", "Person", "Organization")
            updated_graph = await Graph.open(
                schema=updated_schema,
                graph_store=store,
                embedder=_ReviewEmbedder(),
                extractor=_ReviewExtractor(),
            )
            converted = await updated_graph.convert_candidates(patch_path)
            assert (converted.created_relations, converted.set_properties) == (1, 1)
            report_path.write_text(
                converted.model_dump_json(indent=2), encoding="utf-8"
            )
            assert report_path.is_file()
            relation_rows = await store.execute_read(
                "MATCH (a:_Node {id: $ada})-[r:MENTORS]->(b:_Node {id: $beacon}) "
                "RETURN r.source_chunk_ids AS evidence",
                {"ada": str(ids["ada"]), "beacon": str(ids["beacon"])},
            )
            assert relation_rows == [{"evidence": [str(ids["chunk_relation"])]}]
            property_rows = await store.execute_read(
                "MATCH (e:_Node:Person {id: $ada}) RETURN e.review_score AS score",
                {"ada": str(ids["ada"])},
            )
            assert property_rows == [{"score": 42}]
            repeated = await updated_graph.convert_candidates(patch_path)
            assert (repeated.created_relations, repeated.set_properties) == (0, 0)
        finally:
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(value) for value in ids.values()]},
            )
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.entity_id IN $ids DELETE a",
                {
                    "ids": [
                        str(ids[name])
                        for name in ("ada", "beacon", "ambiguous", "ambiguous_org")
                    ]
                },
            )
            await store.close()


class _ReviewEmbedder(Embedder):
    """Provide deterministic vectors for Graph.open without external services."""

    model = "candidate-review-test"

    async def dimensions(self) -> int:
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class _ReviewExtractor(Extractor):
    """Provide the extractor slot required by Graph.open."""

    async def extract(self, chunk, schema: GraphSchema) -> ExtractionResult:
        return ExtractionResult(entities=[], relations=[], extractor_name="test")
