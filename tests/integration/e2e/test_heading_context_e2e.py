"""E2E heading context: the heading path reaches extraction and embedding, not storage.

The scenario ingests a Markdown file (and a PDF) with a heading-aware chunker and the
real ``BAMLExtractor`` with a fake BAML client, against a real Neo4j. It runs the flag
combinations and shows that:

- with ``include_heading_path`` the client gets a ``section`` argument, and without it
  the client gets none,
- with ``embed_heading_path`` the embedder gets the heading path above each chunk text,
  and without it the embedder gets the raw text,
- the stored chunk text is always the raw source slice, and extraction offsets index it,
- a PDF chunk reaches the client with a section string too.

Document keys are unique per run and cleanup removes only what this run created. The
test writes its outcome to ``reports/e2e/heading_context.json``.
"""

import importlib.util
import json
import shutil
from collections.abc import AsyncGenerator, Sequence
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from agrag.chunking import (
    Chunking,
    ChunkingRule,
    DoclingChunker,
    HeadingChunker,
    RecursiveChunker,
    RuleMatch,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import BAMLExtractor
from agrag.ingestion.graph import Graph
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.e2e.test_chunking_e2e import _cleanup, _Env, _HashEmbedder


neo4j_missing = importlib.util.find_spec("neo4j") is None
docling_missing = importlib.util.find_spec("docling") is None

_PDF = Path(__file__).parents[1] / "loaders" / "corpus" / "fixtures" / "multi_page.pdf"
_CHUNKING = Chunking(
    rules=[
        ChunkingRule(
            match=RuleMatch(loader_names=["docling"]),
            chunker=DoclingChunker(max_tokens=200),
        )
    ],
    fallback=HeadingChunker(
        chunk_size=200,
        fallback=RecursiveChunker(chunk_size=200),
    ),
)


class _RecordingEmbedder(_HashEmbedder):
    """Hash embedder that records the texts it embeds."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Record and embed the texts."""
        self.texts.extend(texts)
        return await super().embed(texts)


class _RecordingClient:
    """Fake BAML client that records its arguments and finds the word ``alpha``."""

    def __init__(self, label: str) -> None:
        self._label = label
        self.calls: list[tuple[str, str | None]] = []

    async def ExtractEntitiesAndRelations(self, text, section, options):  # noqa: N802
        """Record the call; report ``alpha`` with offsets into ``text``."""
        self.calls.append((text, section))
        start = text.find("alpha")
        entities = []
        if start >= 0:
            entities.append(
                SimpleNamespace(
                    label=self._label,
                    text="alpha",
                    char_start=start,
                    char_end=start + 5,
                    properties={},
                )
            )
        return SimpleNamespace(entities=entities, relations=[])


def _write_markdown(path: Path) -> None:
    body = " ".join(f"Sentence {i} about alpha topics." for i in range(12))
    path.write_text(
        f"# Guide\n\nIntro alpha line.\n\n## Setup\n\n{body}\n\n## Usage\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestHeadingContextE2E:
    """Extraction and embedding context through the public Graph API."""

    @pytest.fixture
    async def env(self, tmp_path: Path) -> AsyncGenerator[_Env, None]:
        """Open a store and a folder unique to this test."""
        run = uuid4().hex[:8]
        label = validate_identifier(f"Topic_{run}")
        schema = GraphSchema(
            name="heading_context",
            version="1",
            entities=[EntityType(label=label, description="A topic.")],
            relations=[],
        )
        store = build_graph_store("neo4j")
        root = tmp_path / f"corpus_{run}"
        root.mkdir()
        env = _Env(run, store, schema, _HashEmbedder(), root)
        try:
            yield env
        finally:
            try:
                await _cleanup(env)
                await drop_schema_for(store, label)
            finally:
                await store.close()

    async def _ingest(
        self, env: _Env, folder: Path, *, extraction: bool, embedding: bool
    ) -> tuple[_RecordingClient, _RecordingEmbedder]:
        client = _RecordingClient(env.schema.entities[0].label)
        embedder = _RecordingEmbedder()
        graph = await Graph.open(
            schema=env.schema,
            graph_store=env.store,
            embedder=embedder,
            extractor=BAMLExtractor(client=client, include_heading_path=extraction),
            chunking=_CHUNKING,
            embed_heading_path=embedding,
        )
        await graph.add(source=folder)
        return client, embedder

    async def test_flags_control_extraction_and_embedding_context(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Each flag changes only its own stage, and storage stays raw."""
        artifact: dict[str, object] = {}
        for name, extraction, embedding in [
            ("both_on", True, True),
            ("both_off", False, False),
            ("extraction_only", True, False),
            ("embedding_only", False, True),
        ]:
            folder = env.root / name
            folder.mkdir()
            _write_markdown(folder / "guide.md")
            source = (folder / "guide.md").read_text(encoding="utf-8")

            client, embedder = await self._ingest(
                env, folder, extraction=extraction, embedding=embedding
            )

            rows = await env.store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
                "WHERE r.invalid_at IS NULL RETURN c.text AS text, "
                "c.provenance AS provenance, c.heading_path AS path",
                {"key": str(folder / "guide.md")},
            )
            assert rows
            for row in rows:
                span = TextProvenance(**json.loads(row["provenance"]))
                assert row["text"] == source[span.char_start : span.char_end]
            paths = {row["text"]: list(row["path"]) for row in rows}
            with_path = [t for t, p in paths.items() if p]
            assert with_path

            sections = dict(client.calls)
            if extraction:
                assert all(sections[t] == " > ".join(paths[t]) for t in with_path), (
                    sections
                )
            else:
                assert set(sections.values()) == {None}
            for text, _ in client.calls:
                assert text in paths

            expected = {
                (" > ".join(p) + "\n\n" + t) if (embedding and p) else t
                for t, p in paths.items()
            }
            # The embedder also embeds the entity name that the fake client returns.
            assert set(embedder.texts) - {"alpha"} == expected
            artifact[name] = {
                "chunks": len(rows),
                "chunks_with_heading_path": len(with_path),
                "sections_sent": sum(s is not None for s in sections.values()),
                "embedded_with_context": sum(
                    t not in paths for t in set(embedder.texts) - {"alpha"}
                ),
            }

        write_artifact("heading_context", artifact)

    @pytest.mark.skipif(docling_missing, reason="docling extra not installed")
    async def test_pdf_chunks_reach_the_client_with_a_section(self, env: _Env) -> None:
        """A PDF chunk with a heading gets a section string."""
        folder = env.root / "pdf"
        folder.mkdir()
        shutil.copy(_PDF, folder / "report.pdf")

        client, _ = await self._ingest(env, folder, extraction=True, embedding=True)

        assert client.calls
        assert any(section for _, section in client.calls)
        assert any(
            section and "Word Processors" in section for _, section in client.calls
        )
