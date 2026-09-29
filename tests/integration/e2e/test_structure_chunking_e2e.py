"""E2E structure-aware chunking: chat turns and Markdown headings on Neo4j.

The scenario writes a chat file of 30 turns with one very long assistant turn, a
Markdown file with three heading levels and a plain-text file, then shows:

- ``ChatLoader`` and ``TurnWindowChunker`` cut only between turns, overlap by one
  turn, and label the pieces of the long turn ``turn-window:recursive``,
- ``HeadingChunker`` keeps each split-level section in its own chunk, and Markdown
  chunks carry their ``heading_path``,
- the plain-text file falls to the fallback chunker,
- ``AddResult.chunking`` counts chunks for each strategy.

The extractor and embedder are fake. Document keys are unique per run and cleanup
removes only what this run created. The test writes its outcome to
``reports/e2e/structure_chunking.json``.
"""

import importlib.util
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest

from agrag.chunking import (
    Chunking,
    ChunkingRule,
    HeadingChunker,
    RecursiveChunker,
    RuleMatch,
    TurnWindowChunker,
)
from agrag.common.data_models.document import SourceFormat
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.loaders.corpus.readers.chat import ChatLoader
from agrag.loaders.corpus.types import ReadOptions, SourceRef
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.e2e.test_chunking_e2e import _cleanup, _Env, _HashEmbedder


neo4j_missing = importlib.util.find_spec("neo4j") is None

_LONG = " ".join(f"detail{i}" for i in range(400))
_CHAT_SIZE = 200


def _write_chat(path: Path) -> None:
    messages = []
    for i in range(30):
        role = "user" if i % 2 == 0 else "assistant"
        content = _LONG if i == 7 else f"Message {i} about topic {i % 5} in short."
        messages.append({"role": role, "content": content, "id": i})
    path.write_text("\n".join(json.dumps(m) for m in messages) + "\n", encoding="utf-8")


def _write_markdown(path: Path) -> None:
    body = " ".join(f"sentence{i} of the section." for i in range(40))
    path.write_text(
        f"# Guide\n\nIntro line.\n\n## Setup\n\n{body}\n\n### Details\n\n{body}\n\n"
        f"## Usage\n\nShort usage text.\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestStructureChunkingE2E:
    """Turn windows and heading sections through the public Graph API."""

    @pytest.fixture
    async def env(self, tmp_path: Path) -> AsyncGenerator[_Env, None]:
        """Open a store and a folder unique to this test."""
        run = uuid4().hex[:8]
        label = validate_identifier(f"Topic_{run}")
        schema = GraphSchema(
            name="structure_chunking",
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

    async def test_turn_windows_and_heading_sections(  # noqa: PLR0915
        self, env: _Env
    ) -> None:
        """Chat chunks cut between turns; Markdown chunks follow the headings."""
        chat_dir = env.root / "chat"
        docs_dir = env.root / "docs"
        chat_dir.mkdir()
        docs_dir.mkdir()
        chat_path = chat_dir / "session.jsonl"
        _write_chat(chat_path)
        _write_markdown(docs_dir / "guide.md")
        (docs_dir / "notes.txt").write_text("Plain notes. " * 60, encoding="utf-8")
        chunking = Chunking(
            rules=[
                ChunkingRule(
                    match=RuleMatch(loader_names=["chat"]),
                    chunker=TurnWindowChunker(chunk_size=_CHAT_SIZE, turn_overlap=1),
                ),
                ChunkingRule(
                    match=RuleMatch(source_formats=[SourceFormat.MARKDOWN]),
                    chunker=HeadingChunker(chunk_size=_CHAT_SIZE),
                ),
            ],
            fallback=RecursiveChunker(chunk_size=_CHAT_SIZE),
        )
        graph = await env.open_graph(chunking)
        artifact: dict[str, object] = {}

        # Step 1: the chat file, read with ChatLoader.
        chat_added = await graph.add(source=chat_path, loader=ChatLoader())
        (parsed,) = ChatLoader().load(
            SourceRef(uri=str(chat_path), extension=".jsonl"),
            chat_path.open("rb"),
            ReadOptions(),
        )
        rows = await env.chunk_rows(str(chat_path))
        assert rows
        whole = [r for r in rows if r["chunker"] == "turn-window"]
        pieces = [r for r in rows if r["chunker"] == "turn-window:recursive"]
        assert whole
        assert len(pieces) > 1
        starts = {0} | {t.char_start for t in parsed.turns}
        ends = {t.char_end for t in parsed.turns} | {len(parsed.text)}
        for row in whole:
            span = TextProvenance(**json.loads(row["provenance"]))
            assert row["text"] == parsed.text[span.char_start : span.char_end]
            assert span.char_start in starts
            assert span.char_end in ends
        long_turn = parsed.turns[7]
        for row in pieces:
            span = TextProvenance(**json.loads(row["provenance"]))
            assert long_turn.char_start <= span.char_start < span.char_end
            assert span.char_end <= long_turn.char_end + 2
        # Overlap of one turn: the last two windows follow the long turn and share one.
        first, second = (
            TextProvenance(**json.loads(r["provenance"])) for r in whole[-2:]
        )
        assert second.char_start < first.char_end
        assert chat_added.chunking.documents_by_rule == {"rule 0": 1}
        assert chat_added.chunking.chunks_by_strategy == {
            "turn-window": len(whole),
            "turn-window:recursive": len(pieces),
        }
        artifact["chat"] = {
            "windows": len(whole),
            "long_turn_pieces": len(pieces),
            "chunking": chat_added.chunking.model_dump(
                mode="json", exclude={"matches"}
            ),
        }

        # Step 2: a Markdown file and a plain-text file.
        docs_added = await graph.add(source=docs_dir)
        md_key, txt_key = str(docs_dir / "guide.md"), str(docs_dir / "notes.txt")
        md_rows = await env.chunk_rows(md_key)
        txt_rows = await env.chunk_rows(txt_key)
        assert {r["chunker"] for r in txt_rows} == {"recursive"}
        assert {r["chunker"] for r in md_rows} <= {"heading", "heading:recursive"}
        md_paths = await env.store.execute_read(
            "MATCH (:Document {document_key: $key})-[r:PART_OF]->(c:Chunk) "
            "WHERE r.invalid_at IS NULL "
            "RETURN c.index AS index, c.heading_path AS path ORDER BY c.index",
            {"key": md_key},
        )
        paths = [list(r["path"]) for r in md_paths]
        assert paths[0] == ["Guide"]
        assert ["Guide", "Setup"] in paths
        assert ["Guide", "Setup", "Details"] in paths
        assert ["Guide", "Usage"] in paths
        guide_text = (docs_dir / "guide.md").read_text(encoding="utf-8")
        for row in md_rows:
            assert row["text"] in guide_text
            body = row["text"].split("\n", 1)[1] if "\n" in row["text"] else ""
            assert "\n## " not in "\n" + body and "\n# " not in "\n" + body
        counts = docs_added.chunking.chunks_by_strategy
        assert set(counts) <= {"heading", "heading:recursive", "recursive"}
        assert counts["recursive"] == len(txt_rows)
        assert docs_added.chunking.documents_by_rule == {"rule 1": 1, "fallback": 1}
        artifact["docs"] = {
            "heading_paths": paths,
            "text_file_chunks": len(txt_rows),
            "chunking": docs_added.chunking.model_dump(
                mode="json", exclude={"matches"}
            ),
        }

        write_artifact("structure_chunking", artifact)
