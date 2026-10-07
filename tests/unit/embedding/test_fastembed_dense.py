"""Tests for FastEmbedEmbedder in agrag.embedding.fastembed_dense.

A MockFastEmbedModel (records the thread each ``embed`` ran on, the texts and the
batch size it received) is injected through the ``model`` parameter, and a
_RecordingCache implements EmbeddingCache, so no model is downloaded and no network
is used. Covers output normalization, that ``embed`` runs off the event-loop thread,
lazy and shared model loading, cache reads and writes, and tracing spans through a
real SDK ``TracerProvider`` with an in-memory exporter. The granite registration
tests patch ``fastembed.TextEmbedding`` to check when the model is registered with
FastEmbed and how the model is built from ``EmbeddingSettings``.
"""

import asyncio
import threading
from collections.abc import Iterable
from unittest import mock

import numpy as np
import pytest
from fastembed.common.model_description import PoolingType
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.embedding.base import EmbeddingCache
from agrag.embedding.fastembed_dense import FastEmbedEmbedder
from agrag.embedding.settings import EmbeddingSettings


GRANITE = "ibm-granite/granite-embedding-small-english-r2"


class MockFastEmbedModel:
    """A stand-in for a FastEmbed ``TextEmbedding`` model in tests.

    Records the thread each ``embed`` runs on, the texts it received, and the
    batch size, so tests can assert off-loop execution and batching behavior.
    """

    def __init__(self, vector: tuple[float, ...] = (3.0, 4.0)) -> None:
        """Create the fake model.

        Args:
            vector: The raw vector returned for every text.
        """
        self._vector = vector
        self.embed_calls: list[list[str]] = []
        self.batch_sizes: list[int] = []
        self.embed_thread: threading.Thread | None = None

    @property
    def embedding_size(self) -> int:
        """Return the dimension of the fake vectors."""
        return len(self._vector)

    def embed(
        self, documents: list[str], batch_size: int = 256
    ) -> Iterable[np.ndarray]:
        """Record the call and yield one raw vector per text."""
        self.embed_thread = threading.current_thread()
        self.embed_calls.append(list(documents))
        self.batch_sizes.append(batch_size)
        for _ in documents:
            yield np.array(self._vector, dtype=np.float32)


class _RecordingCache(EmbeddingCache):
    """A cache that stores vectors in a dict."""

    def __init__(self) -> None:
        """Create an empty cache."""
        self.store: dict[tuple[str, str, bool], list[float]] = {}

    async def get(
        self, *, text: str, model: str, normalize: bool
    ) -> list[float] | None:
        """Return the stored vector, or None on a miss."""
        return self.store.get((text, model, normalize))

    async def set(
        self, *, text: str, model: str, normalize: bool, vector: list[float]
    ) -> None:
        """Store the vector."""
        self.store[(text, model, normalize)] = vector


def _tracing_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _supported(*names: str) -> list[dict[str, str]]:
    """Return the shape of ``TextEmbedding.list_supported_models()``."""
    return [{"model": name} for name in names]


class TestFastEmbedEmbedderOutput:
    """The embedder returns plain float lists, normalized when asked."""

    async def test_dimensions_come_from_the_model(self) -> None:
        """Dimensions reflects the loaded model's embedding size."""
        embedder = FastEmbedEmbedder(model=MockFastEmbedModel(vector=(1.0,) * 7))
        assert await embedder.dimensions() == 7

    async def test_normalize_scales_vectors_to_unit_length(self) -> None:
        """With normalize on, each vector has length 1."""
        embedder = FastEmbedEmbedder(
            model=MockFastEmbedModel(), settings=EmbeddingSettings(normalize=True)
        )
        (vector,) = await embedder.embed(["a"])
        assert vector == pytest.approx([0.6, 0.8])
        assert all(type(x) is float for x in vector)

    async def test_raw_vectors_are_unchanged_when_normalize_is_off(self) -> None:
        """With normalize off, the model's raw vector comes back as it is."""
        embedder = FastEmbedEmbedder(
            model=MockFastEmbedModel(), settings=EmbeddingSettings(normalize=False)
        )
        assert await embedder.embed(["a"]) == [[3.0, 4.0]]

    async def test_zero_vector_is_not_divided_by_zero(self) -> None:
        """A zero vector stays zero instead of becoming NaN."""
        embedder = FastEmbedEmbedder(
            model=MockFastEmbedModel(vector=(0.0, 0.0)),
            settings=EmbeddingSettings(normalize=True),
        )
        assert await embedder.embed(["a"]) == [[0.0, 0.0]]

    async def test_batch_size_setting_reaches_the_model(self) -> None:
        """The configured batch size is passed to the model's embed call."""
        model = MockFastEmbedModel()
        embedder = FastEmbedEmbedder(
            model=model, settings=EmbeddingSettings(batch_size=5)
        )
        await embedder.embed(["a", "b"])
        assert model.batch_sizes == [5]

    async def test_one_vector_per_text_in_order(self) -> None:
        """The result has one vector per input text."""
        embedder = FastEmbedEmbedder(model=MockFastEmbedModel())
        assert len(await embedder.embed(["a", "b", "c"])) == 3


class TestEmbedEventLoop:
    """Embed must run the blocking model off the event loop thread."""

    async def test_embed_runs_off_loop_thread(self) -> None:
        """The model runs in a worker thread, not on the event loop thread."""
        loop_thread = threading.current_thread()
        model = MockFastEmbedModel()
        embedder = FastEmbedEmbedder(model=model)
        await embedder.embed(["a", "b"])
        assert model.embed_thread is not None
        assert model.embed_thread is not loop_thread


class TestLazyModelLoad:
    """The model loads on first use, once, and a failed load can be retried."""

    async def test_construction_does_not_load_the_model(self) -> None:
        """Building the embedder never touches FastEmbed."""
        with mock.patch("fastembed.TextEmbedding") as text_embedding:
            FastEmbedEmbedder()
        text_embedding.assert_not_called()

    async def test_concurrent_first_calls_build_the_model_once(self) -> None:
        """A second concurrent call waits for the first build and reuses it."""
        build_calls = 0
        entered = threading.Event()
        release = threading.Event()

        def slow_build(_self: FastEmbedEmbedder) -> MockFastEmbedModel:
            nonlocal build_calls
            build_calls += 1
            entered.set()
            release.wait(timeout=5)
            return MockFastEmbedModel()

        embedder = FastEmbedEmbedder()
        with mock.patch.object(
            FastEmbedEmbedder, "_build_model", autospec=True, side_effect=slow_build
        ):
            first = asyncio.create_task(embedder.embed(["a"]))
            await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(embedder.dimensions())
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.gather(first, second)
        assert build_calls == 1

    async def test_failed_build_can_be_retried(self) -> None:
        """A build failure does not leave the embedder stuck."""
        embedder = FastEmbedEmbedder()
        with (
            mock.patch.object(
                FastEmbedEmbedder, "_build_model", side_effect=RuntimeError("boom")
            ),
            pytest.raises(RuntimeError),
        ):
            await embedder.embed(["a"])
        with mock.patch.object(
            FastEmbedEmbedder, "_build_model", return_value=MockFastEmbedModel()
        ):
            assert len(await embedder.embed(["a"])) == 1


class TestGraniteRegistration:
    """The granite model is registered only while FastEmbed lacks it."""

    async def test_registers_granite_when_fastembed_lacks_it(self) -> None:
        """A FastEmbed release without granite gets the model registered."""
        with mock.patch("fastembed.TextEmbedding") as text_embedding:
            text_embedding.list_supported_models.return_value = _supported(
                "BAAI/bge-small-en-v1.5"
            )
            text_embedding.return_value = MockFastEmbedModel()
            await FastEmbedEmbedder().dimensions()
        text_embedding.add_custom_model.assert_called_once()
        kwargs = text_embedding.add_custom_model.call_args.kwargs
        assert kwargs["model"] == GRANITE
        assert kwargs["pooling"] is PoolingType.CLS
        assert kwargs["normalization"] is False
        assert kwargs["dim"] == 384
        assert kwargs["sources"].hf == (
            "onnx-community/granite-embedding-small-english-r2-ONNX"
        )
        assert kwargs["model_file"] == "onnx/model.onnx"
        assert kwargs["additional_files"] == ["onnx/model.onnx_data"]

    async def test_skips_registration_when_fastembed_has_granite(self) -> None:
        """A FastEmbed release with granite is used as it is."""
        with mock.patch("fastembed.TextEmbedding") as text_embedding:
            text_embedding.list_supported_models.return_value = _supported(GRANITE)
            text_embedding.return_value = MockFastEmbedModel()
            await FastEmbedEmbedder().dimensions()
        text_embedding.add_custom_model.assert_not_called()

    async def test_other_models_are_not_registered(self) -> None:
        """Only the granite model needs registration."""
        with mock.patch("fastembed.TextEmbedding") as text_embedding:
            text_embedding.list_supported_models.return_value = _supported(
                "BAAI/bge-small-en-v1.5"
            )
            text_embedding.return_value = MockFastEmbedModel()
            await FastEmbedEmbedder(
                settings=EmbeddingSettings(model="BAAI/bge-small-en-v1.5")
            ).dimensions()
        text_embedding.add_custom_model.assert_not_called()

    async def test_model_is_built_from_the_settings(self) -> None:
        """The model name and the cache folder reach FastEmbed."""
        with mock.patch("fastembed.TextEmbedding") as text_embedding:
            text_embedding.list_supported_models.return_value = _supported(GRANITE)
            text_embedding.return_value = MockFastEmbedModel()
            settings = EmbeddingSettings(model=GRANITE, cache_folder="/tmp/models")
            await FastEmbedEmbedder(settings=settings).dimensions()
        text_embedding.assert_called_once_with(
            model_name=GRANITE, cache_dir="/tmp/models"
        )


class TestEmbedCaching:
    """Embed reads the cache and writes new vectors in one batched call."""

    async def test_miss_then_hit_uses_cache(self) -> None:
        """A second identical embed hits the cache and encodes nothing."""
        model = MockFastEmbedModel()
        embedder = FastEmbedEmbedder(model=model, cache=_RecordingCache())
        first = await embedder.embed(["a", "b"])
        assert model.embed_calls == [["a", "b"]]
        assert await embedder.embed(["a", "b"]) == first
        assert model.embed_calls == [["a", "b"]]

    async def test_partial_miss_batches_only_misses(self) -> None:
        """A partial miss encodes only the missing texts in one call."""
        model = MockFastEmbedModel()
        embedder = FastEmbedEmbedder(model=model, cache=_RecordingCache())
        await embedder.embed(["a", "b"])
        await embedder.embed(["a", "c"])
        assert model.embed_calls == [["a", "b"], ["c"]]

    async def test_opposite_normalize_settings_do_not_share_cache_entries(
        self,
    ) -> None:
        """Embedders that differ only in normalize stay apart in one cache."""
        model = MockFastEmbedModel()
        cache = _RecordingCache()
        normalized = FastEmbedEmbedder(
            model=model, cache=cache, settings=EmbeddingSettings(normalize=True)
        )
        raw = FastEmbedEmbedder(
            model=model, cache=cache, settings=EmbeddingSettings(normalize=False)
        )
        assert await normalized.embed_one("a") == pytest.approx([0.6, 0.8])
        assert await raw.embed_one("a") == [3.0, 4.0]
        assert await normalized.embed_one("a") == pytest.approx([0.6, 0.8])
        assert await raw.embed_one("a") == [3.0, 4.0]
        assert model.embed_calls == [["a"], ["a"]]


class TestFastEmbedTracing:
    """Tracing spans real model work without touching a host span."""

    async def test_tracer_none_leaves_host_span_untouched(self) -> None:
        """Embed with tracer=None keeps the host span unset and event-free."""
        host_provider, host_exporter = _tracing_provider()
        with host_provider.get_tracer("host").start_as_current_span("host.request"):
            await FastEmbedEmbedder(model=MockFastEmbedModel(), tracer=None).embed(
                ["a"]
            )
        (host_span,) = host_exporter.get_finished_spans()
        assert host_span.name == "host.request"
        assert host_span.status.status_code is StatusCode.UNSET
        assert list(host_span.events) == []

    async def test_concurrent_first_call_exports_one_model_load_span(self) -> None:
        """Two concurrent first embeds share one model_load span."""
        provider, exporter = _tracing_provider()
        entered = threading.Event()
        release = threading.Event()

        def slow_build(_self: FastEmbedEmbedder) -> MockFastEmbedModel:
            entered.set()
            release.wait(timeout=5)
            return MockFastEmbedModel()

        embedder = FastEmbedEmbedder(tracer=provider.get_tracer("test"))
        with mock.patch.object(
            FastEmbedEmbedder, "_build_model", autospec=True, side_effect=slow_build
        ):
            first = asyncio.create_task(embedder.embed(["a"]))
            await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(embedder.embed(["b"]))
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.gather(first, second)
        spans = exporter.get_finished_spans()
        loads = [s for s in spans if s.name == "agrag.embedding.model_load"]
        assert len(loads) == 1
        assert (loads[0].attributes or {}).get("agrag.model") == embedder.model
        encodes = [s for s in spans if s.name == "agrag.embedding.encode"]
        assert len(encodes) == 2

    async def test_full_cache_hit_exports_no_encode_span(self) -> None:
        """A fully cached embed opens no encode span."""
        provider, exporter = _tracing_provider()
        embedder = FastEmbedEmbedder(
            model=MockFastEmbedModel(),
            cache=_RecordingCache(),
            tracer=provider.get_tracer("test"),
        )
        await embedder.embed(["a", "b"])
        exporter.clear()
        await embedder.embed(["a", "b"])
        assert [
            s
            for s in exporter.get_finished_spans()
            if s.name == "agrag.embedding.encode"
        ] == []
