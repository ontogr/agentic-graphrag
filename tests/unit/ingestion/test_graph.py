"""Tests for the public Graph ingestion API (agrag.ingestion.Graph).

Graph.open and Graph.add are exercised against fake GraphStore, Embedder, and
Extractor implementations, so no real database or LLM calls are made. Covers
adding from a directory, raw text, and prebuilt documents; the mutually
exclusive input validation; progress callbacks; and that Graph.open closes the
store when connecting fails.
"""

import builtins
import hashlib
import logging
import unicodedata
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from math import ceil
from pathlib import Path
from typing import Any, Literal
from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import agrag.ingestion._ingest as ingest_module
import agrag.ingestion._job_cleanup as job_cleanup_module
import agrag.ingestion.extract as extract_module
import agrag.ingestion.graph as graph_module
from agrag.chunking import Chunker
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.community import (
    COMMUNITY_LABEL,
)
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
)
from agrag.common.data_models.normalization import Normalization
from agrag.common.data_models.presets import OPERATIONS
from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_LABEL,
)
from agrag.common.data_models.structure import version_id
from agrag.common.data_models.vector_record import Distance, VectorHit
from agrag.common.schema_fingerprint import RunRecord, run_record
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion.extract import (
    BAMLExtractor,
    ExtractionLLMSettings,
    Extractor,
    ExtractorMissingExtraError,
    GlinerExtractor,
    LLMExtractor,
)
from agrag.ingestion.settings import (
    EXTRACTION_PROMPT_ID,
    ExtractionSettings,
    effective_mode,
)
from agrag.llm.client_config import LLMClientConfig
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.prose import TextLoader
from agrag.loaders.types import ErrorPolicy, LoadStats, ReadOptions, SourceRef
from agrag.schema import SchemaLoadError, load_schema
from agrag.schema.loader import SchemaSource
from tests.unit.ingestion._index_fake import NoIndexesMixin
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


_FIXTURES = Path(__file__).parents[1] / "loaders" / "fixtures"


class _MockGraphStore(NoIndexesMixin, CutoverJobLeaseFake, GraphStore):
    """A no-op GraphStore for ingestion-only unit tests."""

    def __init__(self) -> None:
        """Create the store, tracking close() calls for cleanup assertions."""
        self.close_calls = 0

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        self.close_calls += 1

    def session(self) -> AbstractAsyncContextManager[Any]:
        class _MockSession:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

            async def execute_read(self, *a: Any, **kw: Any) -> list[dict[str, Any]]:
                return []

            async def execute_write(self, *a: Any, **kw: Any) -> list[dict[str, Any]]:
                return []

        return _MockSession()  # type: ignore[return-value]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        handled = self.handle_cutover_query(query, parameters)
        if handled is not None:
            return handled
        return []

    async def setup_constraints(self) -> None:
        return None

    async def setup_indexes(self) -> None:
        return None

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        return UpsertResult(written=len(relations))

    async def upsert_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Report every candidate written."""
        return UpsertResult(written=len(candidates))

    async def blocked_candidate_keys(self, keys: Sequence[str]) -> set[str]:
        """Return no reviewed candidate keys."""
        return set()

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        return None

    async def ensure_fulltext_index(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        return None

    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        return []

    async def register_labels(self, labels: Sequence[str]) -> None:
        return None

    async def register_relation_types(self, types: Sequence[str]) -> None:
        return None


class _MockEmbedder(Embedder):
    """A fake embedder returning zero vectors."""

    model = "fake"

    async def dimensions(self) -> int:
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0, 0.0] for _ in texts]


class _MockExtractor(Extractor):
    """A fake extractor returning no entities."""

    async def extract(self, chunk: Chunk, schema) -> ExtractionResult:  # type: ignore[no-untyped-def]
        return ExtractionResult(entities=[], relations=[], extractor_name="fake")


class _FailingExtractor(Extractor):
    """A fake extractor whose every extraction raises."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        raise RuntimeError("extraction unavailable")


class _SchemaRecordingExtractor(Extractor):
    """Records the schema of every extraction and extracts nothing."""

    def __init__(self) -> None:
        """Create the extractor with no recorded schemas."""
        self.received_schemas: list[GraphSchema] = []

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        self.received_schemas.append(schema)
        return ExtractionResult(entities=[], relations=[], extractor_name="fake")


async def _schema_seen_by_extractor(source: SchemaSource) -> GraphSchema:
    """Open a graph with source, add one note, and return the schema used."""
    extractor = _SchemaRecordingExtractor()
    graph = await Graph.open(
        schema=source,
        graph_store=_MockGraphStore(),
        embedder=_MockEmbedder(),
        extractor=extractor,
    )
    await graph.add(text="A short note.")
    return extractor.received_schemas[0]


async def _open_graph(store: _MockGraphStore | None = None) -> Graph:
    """Open a graph with fake dependencies for ingestion-only tests."""
    return await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=store if store is not None else _MockGraphStore(),
        embedder=_MockEmbedder(),
        extractor=_MockExtractor(),
    )


def _graph_record(graph: Graph) -> RunRecord:
    """Return the run record the graph stamps on the documents it writes.

    Every graph in these tests opens with DEFAULT_SCHEMA.
    """
    return run_record(
        DEFAULT_SCHEMA,
        graph.extraction_settings,
        effective_mode=graph.effective_mode,
        llm_model=graph.llm_model_name,
        prompt_id=EXTRACTION_PROMPT_ID,
    )


def _stored_version_id(graph: Graph, text: str) -> str:
    """Return the version id that an update with ``text`` writes under this graph."""
    normalized = unicodedata.normalize("NFKC", text)
    document = build_prose_document(
        source=SourceRef(uri="memory://doc", extension=".txt"),
        text=normalized,
        encoding="utf-8",
        source_format=SourceFormat.TXT,
        loader_name="inline",
        opts=ReadOptions(),
        title="inline",
        sections=text_sections(normalized),
    )
    return version_id(_graph_record(graph).stamp(document))


def _matching_chunk_row(graph: Graph, text: str) -> dict[str, str | None]:
    """Return the stamps of an open chunk that an update with ``text`` wrote."""
    record = _graph_record(graph)
    return {
        "version_id": _stored_version_id(graph, text),
        "chunker_hash": graph.chunker.fingerprint,
        "schema_fingerprint": record.schema_fingerprint,
        "extraction_fingerprint": record.extraction_fingerprint,
    }


def _stored_version_reader(
    node_row: dict[str, str], chunk_rows: list[dict[str, str | None]]
) -> AsyncMock:
    """Return an execute_read fake that answers the two update lookups."""

    async def _read(query: str, *args: object, **kwargs: object) -> list[dict]:
        if "chunker_hash" in query:
            return chunk_rows
        if "current_content_hash" in query:
            return [node_row]
        return []

    return AsyncMock(side_effect=_read)


class _RecordingOpenStore(_MockGraphStore):
    """Records the Graph.open provisioning calls it receives."""

    def __init__(self) -> None:
        """Create the store with empty provisioning call logs."""
        super().__init__()
        self.labels_calls: list[list[str]] = []
        self.relation_calls: list[list[str]] = []
        self.vector_index_labels: list[str] = []

    async def register_labels(self, labels: Sequence[str]) -> None:
        self.labels_calls.append(list(labels))

    async def register_relation_types(self, types: Sequence[str]) -> None:
        self.relation_calls.append(list(types))

    async def ensure_vector_index(
        self, *, label: str, vector_property: str, dimensions: int, distance: Distance
    ) -> None:
        self.vector_index_labels.append(label)


class TestGraphOpenRegistration:
    """Graph.open provisions resolved-entity storage."""

    async def test_open_ensures_resolved_entity_vector_index(self) -> None:
        """Native vector search covers the derived label like Community's."""
        store = _RecordingOpenStore()
        await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )

        assert RESOLVED_ENTITY_LABEL in store.vector_index_labels
        assert COMMUNITY_LABEL in store.vector_index_labels


class _NeverBuiltGliner:
    """Fails if an LLM-only graph tries to build GLiNER."""

    def __init__(self, **_: object) -> None:
        raise AssertionError("GLiNER built in llm mode")


class _MockLLMExtractor(LLMExtractor):
    """An LLM slot fake for graph configuration tests."""

    async def extract(
        self,
        chunk: Chunk,
        schema: GraphSchema,
        candidates: Sequence[ExtractedEntity] | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(entities=[], relations=[], extractor_name="llm-fake")


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hide LLM settings from the environment and any working-directory .env."""
    for name in (
        "EXTRACTION_LLM_CLIENTS",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extract_module, "load_dotenv", lambda *a, **k: False)


_PERSON_WITH_PROPERTIES = GraphSchema(
    name="people",
    version="1",
    entities=[
        EntityType(
            label="Person",
            description="A person named in the text.",
            properties={"role": PropertySpec(type="string")},
        )
    ],
    relations=[],
)


def _properties_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the captured log records whose message mentions properties."""
    return [record for record in caplog.records if "properties" in record.getMessage()]


class TestGraphExtractionSettings:
    """Graph exposes and resolves its extraction configuration."""

    async def test_defaults_to_extraction_settings_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-GLiNER extractor leaves the settings at their defaults."""
        monkeypatch.chdir(tmp_path)

        graph = await _open_graph()

        assert graph.extraction_settings == ExtractionSettings()

    async def test_explicit_settings_are_exposed(self) -> None:
        """Graph.open preserves the settings object passed by the caller."""
        settings = ExtractionSettings(entity_threshold=0.6)

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            extraction_settings=settings,
        )

        assert graph.extraction_settings is settings

    async def test_uses_settings_from_gliner_extractor(self) -> None:
        """Graph uses the local GLiNER slot settings when none are passed."""
        settings = ExtractionSettings(entity_threshold=0.6)

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=GlinerExtractor(settings=settings, model=object()),
        )

        assert graph.extraction_settings is settings

    async def test_rejects_settings_different_from_gliner_settings(self) -> None:
        """A graph cannot record settings that differ from its GLiNER slot."""
        extractor = GlinerExtractor(
            settings=ExtractionSettings(entity_threshold=0.6), model=object()
        )

        with pytest.raises(ValueError, match="same ExtractionSettings"):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=extractor,
                extraction_settings=ExtractionSettings(entity_threshold=0.9),
            )

    async def test_hybrid_without_llm_warns_and_degrades_to_gliner(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Hybrid mode warns once when no LLM slot is configured."""
        _clear_llm_env(monkeypatch, tmp_path)
        with caplog.at_level(logging.WARNING):
            graph = await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=GlinerExtractor(model=object()),
            )

        warnings = [
            record for record in caplog.records if record.levelno == logging.WARNING
        ]
        assert graph.effective_mode == "gliner"
        assert len(warnings) == 1
        for name in ("EXTRACTION_LLM_CLIENTS", "LLM_BASE_URL", "LLM_MODEL_ID"):
            assert name in warnings[0].getMessage()
        assert 'mode="gliner"' in warnings[0].getMessage()

    async def test_warns_when_gliner_mode_leaves_declared_properties_empty(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Gliner mode warns once, naming the types whose properties stay empty."""
        with caplog.at_level(logging.WARNING):
            await Graph.open(
                schema=_PERSON_WITH_PROPERTIES,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=GlinerExtractor(
                    settings=ExtractionSettings(mode="gliner"), model=object()
                ),
            )

        records = _properties_records(caplog)
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert "Person" in records[0].getMessage()

    async def test_gliner_mode_without_declared_properties_logs_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A schema without entity properties gives no properties warning."""
        with caplog.at_level(logging.WARNING):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=GlinerExtractor(
                    settings=ExtractionSettings(mode="gliner"), model=object()
                ),
            )

        assert _properties_records(caplog) == []

    async def test_hybrid_mode_with_an_llm_logs_no_properties_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An LLM slot can fill declared properties, so no warning is logged."""
        with caplog.at_level(logging.WARNING):
            graph = await Graph.open(
                schema=_PERSON_WITH_PROPERTIES,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=GlinerExtractor(
                    settings=ExtractionSettings(mode="hybrid"), model=object()
                ),
                llm_extractor=_MockLLMExtractor(),
            )

        assert graph.effective_mode == "hybrid"
        assert _properties_records(caplog) == []

    @pytest.mark.parametrize(
        ("mode", "llm_available", "expected"),
        [
            ("gliner", False, "gliner"),
            ("gliner", True, "gliner"),
            ("hybrid", True, "hybrid"),
            ("hybrid", False, "gliner"),
            ("llm", True, "llm"),
            ("llm", False, "llm"),
        ],
    )
    def test_effective_mode_only_degrades_hybrid_without_llm(
        self, mode: str, llm_available: bool, expected: str
    ) -> None:
        """Only hybrid mode changes when no LLM is available."""
        assert effective_mode(ExtractionSettings(mode=mode), llm_available) == expected

    async def test_gliner_mode_without_extra_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing GLiNER extra fails while opening a GLiNER graph."""
        monkeypatch.setattr(graph_module, "find_spec", lambda name: None)

        with pytest.raises(ExtractorMissingExtraError, match="extract.*extra"):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extraction_settings=ExtractionSettings(mode="gliner"),
            )

    async def test_invalid_extraction_client_does_not_use_shared_endpoint(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An invalid explicit client fails instead of selecting another model."""
        _clear_llm_env(monkeypatch, tmp_path)
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
        monkeypatch.setenv("LLM_MODEL_ID", "shared-model")
        monkeypatch.setenv(
            "EXTRACTION_LLM_CLIENTS",
            '[{"name":"extraction","provider":"openai-generic"}]',
        )

        with pytest.raises(ValidationError):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extraction_settings=ExtractionSettings(mode="llm"),
            )

    async def test_explicit_llm_keeps_hybrid_without_environment_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An LLM passed as llm_extractor is available without environment settings."""
        _clear_llm_env(monkeypatch, tmp_path)
        llm = _MockLLMExtractor()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            llm_extractor=llm,
        )

        assert graph.effective_mode == "hybrid"
        assert graph.llm_extractor is llm
        assert "no LLM is configured" not in caplog.text

    async def test_llm_mode_without_llm_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """LLM mode requires an LLM slot."""
        _clear_llm_env(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="EXTRACTION_LLM_CLIENTS"):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extraction_settings=ExtractionSettings(mode="llm"),
            )

    async def test_local_slot_is_rejected_in_llm_mode(self) -> None:
        """LLM mode does not accept an extractor in the local slot."""
        with pytest.raises(ValueError, match="extractor="):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
                llm_extractor=_MockLLMExtractor(),
                extraction_settings=ExtractionSettings(mode="llm"),
            )

    async def test_llm_extractor_is_rejected_in_local_slot(self) -> None:
        """An LLM role cannot be passed in the local extractor slot."""
        with pytest.raises(ValueError, match="llm_extractor="):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=_MockLLMExtractor(),  # type: ignore[arg-type]
                extraction_settings=ExtractionSettings(mode="hybrid"),
            )

    async def test_local_extractor_is_rejected_in_llm_slot(self) -> None:
        """A local role cannot be passed in the LLM extractor slot."""
        with pytest.raises(ValueError, match="extractor="):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
                llm_extractor=_MockExtractor(),  # type: ignore[arg-type]
                extraction_settings=ExtractionSettings(mode="hybrid"),
            )

    async def test_llm_slot_is_rejected_in_gliner_mode(self) -> None:
        """GLiNER mode does not accept an extractor in the LLM slot."""
        settings = ExtractionSettings(mode="gliner")

        with pytest.raises(ValueError, match="llm_extractor="):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=GlinerExtractor(settings=settings, model=object()),
                llm_extractor=_MockLLMExtractor(),
                extraction_settings=settings,
            )

    async def test_llm_mode_does_not_import_gliner2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM-only mode does not need the GLiNER extra."""
        real_import = builtins.__import__

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "gliner2" or name.startswith("gliner2."):
                raise AssertionError("gliner2 imported in llm mode")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", guarded_import)

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            llm_extractor=_MockLLMExtractor(),
            extraction_settings=ExtractionSettings(mode="llm"),
        )

        assert graph.effective_mode == "llm"

    async def test_hybrid_builds_default_llm_slot_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Configured LLM environment settings create the BAML slot."""
        _clear_llm_env(monkeypatch, tmp_path)
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
        monkeypatch.setenv("LLM_MODEL_ID", "test-model")

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
        )

        assert graph.effective_mode == "hybrid"
        assert isinstance(graph.llm_extractor, BAMLExtractor)

    async def test_llm_mode_builds_only_default_llm_slot(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """LLM mode builds BAML from environment without constructing GLiNER."""
        _clear_llm_env(monkeypatch, tmp_path)
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8000/v1")
        monkeypatch.setenv("LLM_MODEL_ID", "test-model")
        monkeypatch.setattr(graph_module, "GlinerExtractor", _NeverBuiltGliner)

        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extraction_settings=ExtractionSettings(mode="llm"),
        )

        assert graph.effective_mode == "llm"
        assert isinstance(graph.llm_extractor, BAMLExtractor)

    async def test_model_name_is_none_without_llm_slot(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A graph without an LLM slot reports no model name."""
        _clear_llm_env(monkeypatch, tmp_path)
        settings = ExtractionSettings(mode="gliner")
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=GlinerExtractor(settings=settings, model=object()),
            extraction_settings=settings,
        )

        assert graph.llm_model_name is None

    async def test_model_name_joins_baml_client_models(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A BAML slot reports its configured client model names."""
        _clear_llm_env(monkeypatch, tmp_path)
        settings = ExtractionLLMSettings(
            clients=[
                LLMClientConfig(
                    name="a", provider="openai-generic", model="m1", base_url="http://x"
                ),
                LLMClientConfig(
                    name="b", provider="openai-generic", model="m2", base_url="http://x"
                ),
            ]
        )
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            llm_extractor=BAMLExtractor(settings=settings),
            extraction_settings=ExtractionSettings(mode="llm"),
        )

        assert graph.llm_model_name == "m1,m2"

    async def test_custom_llm_extractor_uses_its_class_name_for_model(self) -> None:
        """A custom LLM slot reports its class name as the model name."""
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            llm_extractor=_MockLLMExtractor(),
            extraction_settings=ExtractionSettings(mode="llm"),
        )

        assert graph.llm_model_name == "_MockLLMExtractor"

    async def test_llm_only_graph_can_add_content(self) -> None:
        """LLM-only graphs still run through the existing ingestion pipeline."""
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            llm_extractor=_MockLLMExtractor(),
            extraction_settings=ExtractionSettings(mode="llm"),
        )

        result = await graph.add(text="A short note.")

        assert result.extraction.chunks_processed == 1
        assert result.extraction.entities_extracted == 0


class TestGraphAdd:
    """The Graph accepts sources, text, and documents."""

    async def test_add_directory_reads_all_sources(self) -> None:
        """Add directory reads all sources."""
        graph = await _open_graph()
        result = await graph.add(_FIXTURES)
        assert result.ingestion.documents > 0
        assert result.ingestion.sources > 0

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add requires exactly one input."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[])

    async def test_add_rejects_duplicate_document_keys(self) -> None:
        """An add call cannot join chunks from separate document versions."""
        graph = await _open_graph()
        first = Document(
            text="first",
            title="first",
            uri="memory://first",
            document_key="shared",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=hashlib.sha256(b"first").hexdigest(),
            loader_name="inline",
            char_count=5,
            line_count=1,
        )
        second = first.model_copy(
            update={
                "text": "second",
                "content_hash": hashlib.sha256(b"second").hexdigest(),
            }
        )

        with pytest.raises(ValueError, match="distinct document keys"):
            await graph.add(documents=[first, second])

    def test_chunks_use_distinct_ids_for_each_content_version(self) -> None:
        """Same-index chunks retain their separate version histories."""
        first = Document(
            text="first",
            title="first",
            uri="memory://doc",
            document_key="memory://doc",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=hashlib.sha256(b"first").hexdigest(),
            loader_name="text",
            char_count=5,
            line_count=1,
        )
        second = first.model_copy(
            update={
                "text": "second",
                "content_hash": hashlib.sha256(b"second").hexdigest(),
            }
        )
        chunker = Chunker()

        first_chunk = chunker.chunk(first).chunks[0]
        second_chunk = chunker.chunk(second).chunks[0]

        assert first_chunk.document_id == second_chunk.document_id
        assert first_chunk.id != second_chunk.id

    async def test_on_progress_receives_stats(self) -> None:
        """On progress receives stats."""
        graph = await _open_graph()
        seen: list[Any] = []
        await graph.add(_FIXTURES, on_progress=seen.append)
        assert seen

    async def test_loader_override_with_text_raises(self) -> None:
        """A loader override has no effect on ``text`` and must be rejected."""
        graph = await _open_graph()
        with pytest.raises(ValueError):
            await graph.add(text="x", loader=TextLoader())

    async def test_glob_pattern_skips_directory_matches(self, tmp_path: Path) -> None:
        """A glob pattern that also matches a directory does not choke on it."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_text("hello")
        graph = await _open_graph()
        result = await graph.add(str(tmp_path / "*"))
        assert result.ingestion.documents == 1
        assert result.ingestion.sources == 1


class _RecordingExtractor(Extractor):
    """Logs each extraction and fails on chunks whose first word is fail_on."""

    def __init__(self, events: list[str], fail_on: str | None = None) -> None:
        """Create the extractor that appends to events."""
        self.events = events
        self.fail_on = fail_on

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        first_word = chunk.text.split()[0]
        self.events.append(f"extract {first_word}")
        if first_word == self.fail_on:
            raise RuntimeError("extractor down")
        return ExtractionResult(entities=[], relations=[], extractor_name="rec")


def _named_documents(*names: str) -> list[Document]:
    """Return one short prose document per name, each starting with the name."""
    documents: list[Document] = []
    for name in names:
        text = f"{name} wrote some notes."
        documents.append(
            Document(
                text=text,
                title=name,
                uri=f"memory://{name}",
                document_key=f"memory://{name}",
                source_format=SourceFormat.TXT,
                family=DocumentFamily.PROSE,
                content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                loader_name="text",
                char_count=len(text),
                line_count=1,
            )
        )
    return documents


class TestGraphAddWritesEachBatch:
    """Graph.add writes each walk batch before it extracts the next batch."""

    async def test_first_batch_is_written_before_the_second_is_extracted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each document is written right after its own batch is extracted."""
        events: list[str] = []
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_RecordingExtractor(events),
        )
        docs = _named_documents("alpha", "beta")
        real_ingest = ingest_module.ingest_chunks

        async def _recording_ingest(*args: object, **kwargs: Any) -> Any:
            result = await real_ingest(*args, **kwargs)
            events.append("write")
            return result

        monkeypatch.setattr(ingest_module, "ingest_chunks", _recording_ingest)
        monkeypatch.setattr(
            ingest_module, "iter_document_batches", _one_document_per_batch(docs)
        )

        result = await graph.add(documents=docs)

        assert events == ["extract alpha", "write", "extract beta", "write"]
        assert result.extraction.chunks_processed == 2
        assert result.ingestion.documents == 2

    async def test_a_failure_in_the_second_batch_keeps_the_first_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A later batch that fails leaves the earlier batches written."""
        events: list[str] = []
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_RecordingExtractor(events, fail_on="beta"),
        )
        docs = _named_documents("alpha", "beta")
        real_ingest = ingest_module.ingest_chunks

        async def _recording_ingest(*args: object, **kwargs: Any) -> Any:
            result = await real_ingest(*args, **kwargs)
            events.append("write")
            return result

        monkeypatch.setattr(ingest_module, "ingest_chunks", _recording_ingest)
        monkeypatch.setattr(
            ingest_module, "iter_document_batches", _one_document_per_batch(docs)
        )

        with pytest.raises(RuntimeError, match="extractor down"):
            await graph.add(documents=docs)

        assert events == ["extract alpha", "write", "extract beta"]

    async def test_large_list_writes_first_batch_before_later_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pre-built documents are written in batches of 100 before the next one."""
        events: list[str] = []
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_RecordingExtractor(events, fail_on="doc100"),
        )
        docs = _named_documents(*(f"doc{index:03d}" for index in range(101)))
        real_ingest = ingest_module.ingest_chunks

        async def _recording_ingest(*args: object, **kwargs: Any) -> Any:
            result = await real_ingest(*args, **kwargs)
            events.append("write")
            return result

        monkeypatch.setattr(ingest_module, "ingest_chunks", _recording_ingest)

        with pytest.raises(RuntimeError, match="extractor down"):
            await graph.add(documents=docs)

        assert events == [
            *(f"extract doc{index:03d}" for index in range(100)),
            *["write"] * 100,
            "extract doc100",
        ]

    async def test_progress_counts_writes_from_batches_already_committed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each progress result counts the writes of the batches committed so far."""
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=_MockGraphStore(),
            embedder=_MockEmbedder(),
            extractor=_RecordingExtractor([]),
        )
        docs = _named_documents("alpha", "beta")
        monkeypatch.setattr(
            ingest_module, "iter_document_batches", _one_document_per_batch(docs)
        )
        progress: list[Any] = []

        await graph.add(documents=docs, on_progress=progress.append)

        after_first, after_second = progress[0], progress[1]
        assert after_first.storage.nodes_written == 2
        assert after_first.storage.relationships_written == 2
        assert after_second.storage.nodes_written == 4
        assert after_second.storage.relationships_written == 4


class TestGraphUpdate:
    """An update replaces one document version or deletes the document."""

    async def test_update_normalizes_text_before_comparing_content_hash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An NFKC-equivalent update does not replace the current version."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        node_row = {
            "id": str(uuid4()),
            "current_content_hash": hashlib.sha256(b"K").hexdigest(),
        }
        monkeypatch.setattr(
            store,
            "execute_read",
            _stored_version_reader(node_row, [_matching_chunk_row(graph, "Ｋ")]),
        )
        writes = AsyncMock(return_value=[])
        monkeypatch.setattr(store, "execute_write", writes)

        result = await graph.update("memory://doc", text="Ｋ")

        assert result.no_op is True
        writes.assert_not_awaited()

    async def test_update_rejects_multiple_inputs(self) -> None:
        """Update requires exactly one replacement source."""
        graph = await _open_graph()

        with pytest.raises(ValueError, match="exactly one"):
            await graph.update("memory://doc", text="new", source="other.txt")

    async def test_update_rejects_a_prebuilt_document_with_another_key(self) -> None:
        """A prebuilt document must carry the key that the update names."""
        graph = await _open_graph()
        other = "memory://other"
        note = "A short note."
        document = Document(
            text=note,
            title="note",
            uri=other,
            document_key=other,
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=hashlib.sha256(note.encode("utf-8")).hexdigest(),
            loader_name="inline",
            char_count=len(note),
            line_count=1,
        )

        with pytest.raises(ValueError, match="does not match the update key"):
            await graph.update("memory://doc", document=document)

    async def test_update_reads_a_single_file_source(self) -> None:
        """Update accepts a loader-backed single-file source."""
        graph = await _open_graph()

        result = await graph.update(
            "memory://doc",
            source=_FIXTURES / "sample.txt",
        )

        assert result.no_op is False
        assert result.add_result is not None

    async def test_update_rejects_source_with_multiple_documents(self) -> None:
        """Update rejects sources that do not resolve to exactly one document."""
        graph = await _open_graph()

        with pytest.raises(ValueError, match="exactly one document"):
            await graph.update("memory://doc", source=_FIXTURES / "sample.csv")

    async def test_delete_missing_document_is_a_no_op(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting an unknown document does not write graph state."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        monkeypatch.setattr(store, "execute_read", AsyncMock(return_value=[]))
        writes = AsyncMock(return_value=[{"closed": 1}])
        monkeypatch.setattr(store, "execute_write", writes)

        result = await graph.delete_document("memory://missing")

        assert result.no_op is True
        writes.assert_not_awaited()


class TestGraphFailurePolicies:
    """Skipped failures are counted in the result instead of stopping the call."""

    @pytest.mark.parametrize("verb", ["add", "update"])
    async def test_reports_rebuild_failures_in_storage_stats(
        self, monkeypatch: pytest.MonkeyPatch, verb: str
    ) -> None:
        """A skipped rebuild failure appears in the result storage stats."""
        store = _MockGraphStore()
        graph = await _open_graph(store)
        monkeypatch.setattr(store, "execute_read", AsyncMock(return_value=[]))
        member = Entity(
            id=uuid4(), label="Person", name="Alice", properties={}, source_chunk_ids=[]
        )
        real_ingest = ingest_module.ingest_chunks

        async def _ingest_with_component(*args: object, **kwargs: Any) -> Any:
            kwargs["rebuilt_components"].append(([], [member]))
            return await real_ingest(*args, **kwargs)

        monkeypatch.setattr(ingest_module, "ingest_chunks", _ingest_with_component)
        monkeypatch.setattr(
            job_cleanup_module,
            "rebuild_resolved_entities",
            AsyncMock(side_effect=RuntimeError("database unavailable")),
        )

        if verb == "add":
            result = await graph.add(text="a short note", error_policy=ErrorPolicy.SKIP)
        else:
            update = await graph.update(
                "memory://doc", text="brand new", error_policy=ErrorPolicy.SKIP
            )
            assert update.add_result is not None
            result = update.add_result

        assert result.storage.failures_total == 1
        assert result.storage.failures[0].item_id == str(member.id)
        assert result.storage.failures[0].error_message == "database unavailable"

    async def test_first_add_with_failed_chunk_is_extracted_by_next_update(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A first add with a failed chunk writes no stamp, so update re-extracts."""
        note = "A short note."
        key = "memory://failed-first-add"
        document = Document(
            text=note,
            title="note",
            uri=key,
            document_key=key,
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash=hashlib.sha256(note.encode("utf-8")).hexdigest(),
            loader_name="inline",
            char_count=len(note),
            line_count=1,
        )
        store = _MockGraphStore()
        failing_graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_FailingExtractor(),
        )
        upserts = AsyncMock(wraps=store.upsert_nodes)
        monkeypatch.setattr(store, "upsert_nodes", upserts)

        added = await failing_graph.add(
            documents=[document], error_policy=ErrorPolicy.SKIP
        )

        assert len(added.extraction.failures) == 1
        written = [
            node.properties
            for call in upserts.call_args_list
            if call.args[0] in {DOCUMENT_LABEL, CHUNK_LABEL}
            for node in call.args[1]
        ]
        assert written
        assert all("extraction_fingerprint" not in props for props in written)

        healthy = _SchemaRecordingExtractor()
        retry_graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=healthy,
        )
        stored_row = {
            "id": str(uuid4()),
            "current_content_hash": document.content_hash,
        }
        chunk_row = {
            **_matching_chunk_row(retry_graph, note),
            "extraction_fingerprint": None,
        }
        monkeypatch.setattr(
            store,
            "execute_read",
            _stored_version_reader(stored_row, [chunk_row]),
        )

        updated = await retry_graph.update(key, text=note)

        assert updated.no_op is False
        assert healthy.received_schemas


class TestGraphOpen:
    """Graph.open provisioning failure handling."""

    async def test_connect_failure_closes_store(self) -> None:
        """A failure inside connect() itself still closes the store.

        Regression test: connect() can build and cache a driver before
        connectivity verification fails, so a failure here must still reach
        close() instead of leaking that driver's connection pool.
        """

        class _FailingStore(_MockGraphStore):
            async def connect(self) -> None:
                raise RuntimeError("boom")

        store = _FailingStore()
        with pytest.raises(RuntimeError, match="boom"):
            await Graph.open(
                schema=DEFAULT_SCHEMA,
                graph_store=store,
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )
        assert store.close_calls == 1


class TestGraphSchemaSources:
    """Graph accepts any source load_schema accepts and converts it once."""

    @staticmethod
    async def test_graph_schema_is_used_as_given() -> None:
        """A GraphSchema reaches the extractor unchanged."""
        custom = load_schema(["Ticket"])

        received = await _schema_seen_by_extractor(custom)

        assert received == custom

    @staticmethod
    async def test_shipped_name_gives_its_entity_labels() -> None:
        """A shipped schema name loads the default types plus its own."""
        received = await _schema_seen_by_extractor("operations")

        assert [entity.label for entity in received.entities] == [
            *[entity.label for entity in DEFAULT_SCHEMA.entities],
            "Facility",
            "Service",
            "Occupation",
        ]

    @pytest.mark.parametrize(
        ("source", "expected_labels"),
        [
            (["Person", "Machine"], ["Person", "Machine"]),
            (["Ticket"], ["Ticket"]),
        ],
    )
    async def test_label_list_gives_exactly_those_entity_labels(
        self, source: list[str], expected_labels: list[str]
    ) -> None:
        """A list of strings becomes the entity labels, in order."""
        received = await _schema_seen_by_extractor(source)

        assert [entity.label for entity in received.entities] == expected_labels

    @staticmethod
    async def test_yaml_file_path_matches_load_schema(tmp_path: Path) -> None:
        """A YAML file path gives the same schema as load_schema on that path."""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("entities:\n  Person: A person.\n", encoding="utf-8")

        received = await _schema_seen_by_extractor(schema_file)

        assert received == load_schema(schema_file)

    @staticmethod
    async def test_preset_matches_load_schema() -> None:
        """A Preset value gives the schema load_schema builds from it."""
        received = await _schema_seen_by_extractor(OPERATIONS)

        assert received == load_schema(OPERATIONS)

    async def test_open_rejects_invalid_dict_before_connecting(self) -> None:
        """An invalid dict raises SchemaLoadError and the store never connects."""

        class _ConnectTrackingStore(_MockGraphStore):
            def __init__(self) -> None:
                super().__init__()
                self.connect_calls = 0

            async def connect(self) -> None:
                self.connect_calls += 1

        store = _ConnectTrackingStore()
        with pytest.raises(SchemaLoadError):
            await Graph.open(
                schema={"entites": {"Person": "A person."}},
                graph_store=store,
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )
        assert store.connect_calls == 0

    @staticmethod
    def test_constructor_rejects_invalid_dict() -> None:
        """Graph(...) raises SchemaLoadError for an invalid dict schema."""
        with pytest.raises(SchemaLoadError):
            Graph(
                schema={"entites": {"Person": "A person."}},
                graph_store=_MockGraphStore(),
                embedder=_MockEmbedder(),
                extractor=_MockExtractor(),
            )


class TestGraphChunking:
    """Graph chunks every document with its one chunker."""

    _TEXT = "The quick brown fox jumps over the lazy dog. " * 20

    async def _open(
        self, chunker: Chunker | None = None
    ) -> tuple[Graph, _MockGraphStore]:
        kwargs = {} if chunker is None else {"chunker": chunker}
        store = _MockGraphStore()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=store,
            embedder=_MockEmbedder(),
            extractor=_MockExtractor(),
            **kwargs,
        )
        return graph, store

    async def test_default_chunker_is_recorded_on_every_chunk(self) -> None:
        """Without a chunker argument, chunks carry the default settings hash."""
        graph, _ = await self._open()

        result = await graph.add(text=self._TEXT, return_chunks=True)

        assert result.chunks
        assert {c.chunker for c in result.chunks} == {"section"}
        assert {c.chunker_hash for c in result.chunks} == {Chunker().fingerprint}
        assert result.chunking.chunks == len(result.chunks)
        assert result.chunking.sections == 1

    async def test_the_chunker_argument_sets_the_chunk_size(self) -> None:
        """A smaller size gives more chunks and a different hash."""
        chunker = Chunker(size=40)
        graph, _ = await self._open(chunker)
        assert graph.chunker is chunker

        result = await graph.add(text=self._TEXT, return_chunks=True)
        default_graph, _ = await self._open()
        default = await default_graph.add(text=self._TEXT, return_chunks=True)

        assert len(result.chunks) > len(default.chunks)
        assert {c.chunker_hash for c in result.chunks} == {chunker.fingerprint}

    async def test_add_and_update_pass_read_options_to_the_loaders(self) -> None:
        """A none Unicode form keeps a ligature in the chunk text on both paths."""
        graph, _ = await self._open()
        options = ReadOptions(normalization=Normalization(unicode_form="none"))

        added = await graph.add(
            text="\ufb01 rst line", read_options=options, return_chunks=True
        )
        updated = await graph.update(
            "memory://doc", text="\ufb01 rst line", read_options=options
        )

        assert added.chunks[0].text == "\ufb01 rst line"
        assert (
            updated.new_content_hash
            == hashlib.sha256("\ufb01 rst line".encode()).hexdigest()
        )

    async def _update(
        self,
        graph: Graph,
        store: _MockGraphStore,
        *,
        chunk_rows: list[dict[str, str | None]],
    ) -> bool:
        node_row = {
            "id": str(uuid4()),
            "current_content_hash": hashlib.sha256(self._TEXT.encode()).hexdigest(),
        }
        reader = _stored_version_reader(node_row, chunk_rows)
        with mock.patch.object(store, "execute_read", new=reader):
            result = await graph.update("memory://doc", text=self._TEXT)
        return result.no_op

    async def test_update_is_a_no_op_when_every_stamp_is_unchanged(self) -> None:
        """Same content, chunker, schema and extraction setup: nothing runs."""
        graph, store = await self._open()

        assert (
            await self._update(
                graph, store, chunk_rows=[_matching_chunk_row(graph, self._TEXT)]
            )
            is True
        )

    @pytest.mark.parametrize(
        "stamp_overrides",
        [
            pytest.param({"chunker_hash": "0123456789abcdef"}, id="chunker"),
            pytest.param({"schema_fingerprint": "0123456789abcdef"}, id="schema"),
            pytest.param(
                {"extraction_fingerprint": "0123456789abcdef"}, id="extraction"
            ),
            pytest.param(
                {
                    "chunker_hash": None,
                    "schema_fingerprint": None,
                    "extraction_fingerprint": None,
                },
                id="chunks-without-run-record",
            ),
        ],
    )
    async def test_update_is_not_a_no_op_when_a_stamp_differs(
        self, stamp_overrides: dict[str, str | None]
    ) -> None:
        """A changed or missing stamp on the open chunk means the update runs."""
        graph, store = await self._open()
        chunk_row = {**_matching_chunk_row(graph, self._TEXT), **stamp_overrides}

        assert await self._update(graph, store, chunk_rows=[chunk_row]) is False

    async def test_update_after_delete_re_adds_the_document(self) -> None:
        """A document without an open chunk is not a no-op, even for the same text."""
        graph, store = await self._open()

        assert await self._update(graph, store, chunk_rows=[]) is False


class _ScoreByChunk(Extractor):
    """First extractor: every chunk gets one weak entity (score 0.4)."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Person",
                    text=f"p{chunk.index}",
                    char_start=0,
                    char_end=2,
                    confidence=0.4,
                )
            ],
            relations=[],
            extractor_name="first",
        )


class _CountingLlm(LLMExtractor):
    """Escalation extractor that counts its calls."""

    def __init__(self) -> None:
        """Create the extractor with an empty call count."""
        self.calls = 0

    async def extract(
        self,
        chunk: Chunk,
        schema: GraphSchema,
        candidates: Sequence[ExtractedEntity] | None = None,
    ) -> ExtractionResult:
        self.calls += 1
        return ExtractionResult(entities=[], relations=[], extractor_name="llm")


_MANY_PARAGRAPHS = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(12))
_SHORT_TEXT = "Ada Lovelace wrote notes."


async def _open_escalating_graph(
    llm: LLMExtractor | None,
    *,
    budget: float | str = 0.25,
    mode: Literal["gliner", "hybrid"] = "hybrid",
) -> Graph:
    """Open a graph with a weak first extractor and small chunks.

    The first extractor's 0.4 entities sit below the default entity threshold,
    so the threshold is lowered to keep them as spans that can be ranked.
    """
    return await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=_MockGraphStore(),
        embedder=_MockEmbedder(),
        extractor=_ScoreByChunk(),
        llm_extractor=llm,
        extraction_settings=ExtractionSettings(
            mode=mode, escalation_budget=budget, entity_threshold=0.3
        ),
        chunker=Chunker(size=40, min_size=10),
    )


def _one_document_per_batch(
    docs: list[Document],
) -> Callable[..., AsyncIterator[tuple[list[Document], LoadStats]]]:
    """Return a stand-in for iter_document_batches that yields one batch each."""

    async def _batches(**_: object) -> AsyncIterator[tuple[list[Document], LoadStats]]:
        stats = LoadStats()
        for document in docs:
            stats.documents += 1
            stats.sources += 1
            yield [document], stats

    return _batches


class TestGraphEscalation:
    """Graph.add and Graph.update apply the budget and report it."""

    async def test_add_returns_the_escalation_report(self) -> None:
        """AddResult.escalation counts the chunks of the whole call."""
        llm = _CountingLlm()
        graph = await _open_escalating_graph(llm)

        result = await graph.add(text=_MANY_PARAGRAPHS)

        report = result.escalation
        assert report.total == result.extraction.chunks_processed > 4
        assert report.eligible == report.total
        assert report.escalated == ceil(report.total * 0.25) == llm.calls
        assert report.left_for_gliner == report.eligible - report.escalated
        assert report.lowest_score_left == 0.4
        assert report.budget_needed == 1.0

    async def test_add_logs_the_report_lines(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Graph.add logs the three report lines at the end of the call."""
        graph = await _open_escalating_graph(_CountingLlm())

        with caplog.at_level(logging.INFO, logger="agrag.ingestion.graph"):
            result = await graph.add(text=_MANY_PARAGRAPHS)

        report = result.escalation
        messages = [r.getMessage() for r in caplog.records]
        assert messages[:3] == [
            f"mode hybrid | chunks {report.total:,} | "
            f"eligible {report.eligible:,} (100%) | "
            f"escalated {report.escalated:,} (budget 25%)",
            f"left for GLiNER only {report.left_for_gliner:,} | lowest score left 0.40",
            "budget needed 100% to escalate all eligible chunks",
        ]
        assert messages[3] == (
            f"escalation failed on {report.failed:,} chunks | first result kept"
        )

    async def test_add_logs_nothing_without_an_llm_extractor(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A graph with one extractor does not log escalation lines."""
        graph = await _open_escalating_graph(None, mode="gliner")

        with caplog.at_level(logging.INFO, logger="agrag.ingestion.graph"):
            result = await graph.add(text=_MANY_PARAGRAPHS)

        assert caplog.records == []
        assert result.escalation.escalated == 0

    async def test_budget_all_escalates_every_eligible_chunk(self) -> None:
        """Budget all has no ceiling."""
        llm = _CountingLlm()
        graph = await _open_escalating_graph(llm, budget="all")

        result = await graph.add(text=_MANY_PARAGRAPHS)

        assert llm.calls == result.escalation.total

    async def test_budget_zero_never_calls_the_llm_extractor(self) -> None:
        """Budget 0 means the first extractor only."""
        llm = _CountingLlm()
        graph = await _open_escalating_graph(llm, budget=0.0)

        result = await graph.add(text=_MANY_PARAGRAPHS)

        assert llm.calls == 0
        assert result.escalation.left_for_gliner == result.escalation.eligible

    async def test_update_applies_the_budget_to_its_one_document(self) -> None:
        """update() ranks and caps the chunks of the one document it extracts."""
        llm = _CountingLlm()
        graph = await _open_escalating_graph(llm)

        result = await graph.update("memory://doc", text=_MANY_PARAGRAPHS)

        assert result.add_result is not None
        report = result.add_result.escalation
        assert report.total == result.add_result.extraction.chunks_processed
        assert report.escalated == ceil(report.total * 0.25) == llm.calls

    async def test_each_walk_batch_gets_its_own_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two one-chunk batches escalate one chunk each, not a pooled share.

        At 20% a pooled budget of two chunks rounds up to one call. A budget
        per batch rounds each batch up, so both chunks escalate.
        """
        llm = _CountingLlm()
        graph = await _open_escalating_graph(llm, budget=0.2)
        docs = [
            Document(
                text=_SHORT_TEXT,
                title="t",
                uri=f"memory://{name}",
                document_key=f"memory://{name}",
                source_format=SourceFormat.TXT,
                family=DocumentFamily.PROSE,
                content_hash=hashlib.sha256(_SHORT_TEXT.encode("utf-8")).hexdigest(),
                loader_name="text",
                char_count=len(_SHORT_TEXT),
                line_count=1,
            )
            for name in ("a", "b")
        ]
        monkeypatch.setattr(
            ingest_module, "iter_document_batches", _one_document_per_batch(docs)
        )

        result = await graph.add(documents=docs)

        assert llm.calls == 2
        assert (result.escalation.total, result.escalation.escalated) == (2, 2)
        assert result.escalation.budget_needed == 1.0
