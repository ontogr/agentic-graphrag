"""Tests for the public Graph ingestion API."""

from pathlib import Path

import pytest

from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.ingestion import Graph
from agrag.loaders.corpus.errors import UnsupportedFormatError
from agrag.loaders.corpus.types import ErrorPolicy


_FIXTURES = Path(__file__).parents[1] / "loaders" / "corpus" / "fixtures"


class TestGraphAdd:
    """The Graph accepts sources, text, and documents."""

    async def test_open_returns_a_graph(self) -> None:
        """Open returns a graph."""
        graph = await Graph.open()
        assert isinstance(graph, Graph)

    async def test_add_directory_reads_all_sources(self) -> None:
        """Add directory reads all sources."""
        graph = await Graph.open()
        result = await graph.add(_FIXTURES)
        assert result.documents > 0
        assert result.sources > 0

    async def test_add_single_text(self) -> None:
        """Add single text."""
        graph = await Graph.open()
        result = await graph.add(text="a short note")
        assert result.documents == 1
        assert result.sources == 1

    async def test_add_prebuilt_documents(self) -> None:
        """Add prebuilt documents."""
        graph = await Graph.open()
        doc = Document(
            text="prebuilt",
            title="t",
            uri="u",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="h",
            loader_name="text",
            char_count=8,
            line_count=1,
        )
        result = await graph.add(documents=[doc])
        assert result.documents == 1

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add requires exactly one input."""
        graph = await Graph.open()
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[])

    async def test_on_progress_receives_stats(self) -> None:
        """On progress receives stats."""
        graph = await Graph.open()
        seen = []
        await graph.add(_FIXTURES, on_progress=seen.append)
        assert seen

    async def test_raise_policy_stops_on_unsupported_format(
        self, tmp_path: Path
    ) -> None:
        """Raise policy stops on unsupported format."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await Graph.open()
        with pytest.raises(UnsupportedFormatError):
            await graph.add(bad)

    async def test_skip_policy_counts_skipped_source(self, tmp_path: Path) -> None:
        """Skip policy counts skipped source."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await Graph.open()
        result = await graph.add(bad, error_policy=ErrorPolicy.SKIP)
        assert result.skipped == 1
        assert result.documents == 0

    async def test_quarantine_policy_counts_quarantined(self, tmp_path: Path) -> None:
        """Quarantine policy counts quarantined."""
        bad = tmp_path / "file.unknown"
        bad.write_text("x")
        graph = await Graph.open()
        result = await graph.add(bad, error_policy=ErrorPolicy.QUARANTINE)
        assert result.quarantined == 1
        assert result.quarantined_items
