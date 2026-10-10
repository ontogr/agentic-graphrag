"""Tests for FastEmbedBM25Embedder in agrag.embedding.fastembed_bm25.

Uses a MockSparseModel injected via ``_model`` so no real fastembed model is
downloaded. Covers that embed and query_embed delegate to distinct
model methods (a query must not use document-side term weighting), that
concurrent first-time embeds share one model build via
``mock.patch.object(..., autospec=True)`` and threading events rather than
racing to build it twice. Tracing tests use a real SDK ``TracerProvider`` with
an in-memory exporter: concurrent first use exports exactly one
``agrag.embedding.model_load`` span.
"""

import asyncio
import threading
from unittest import mock

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.embedding.fastembed_bm25 import DEFAULT_BM25_MODEL, FastEmbedBM25Embedder


class MockSparseModel:
    """A stand-in for a FastEmbed sparse model in tests."""

    model_name = DEFAULT_BM25_MODEL

    def embed(self, texts: list[str]):
        """Return one document sparse vector per text, weighted by index."""
        return [
            type("SV", (), {"indices": [i], "values": [1.0]})()
            for i, _ in enumerate(texts)
        ]

    def query_embed(self, texts: list[str]):
        """Return one query sparse vector per text, at a fixed index and weight.

        Distinct output from ``embed`` so tests can prove ``query_embed``
        delegates to this method, not the document-side ``embed``.
        """
        return [type("SV", (), {"indices": [9], "values": [1.0]})() for _ in texts]


def _tracing_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider wired to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestFastEmbedBM25Embed:
    """Embed delegates to FastEmbed in a worker thread."""

    async def test_query_embed_uses_query_side_weighting(self) -> None:
        """query_embed delegates to the model's query_embed, not its embed.

        Regression guard: BM25's document embedding applies term-frequency
        and length-normalization weighting meant for passages. Sending
        query text through that path instead of the model's query-side
        method would rank matches incorrectly.
        """
        embedder = FastEmbedBM25Embedder(model=MockSparseModel.model_name)
        model = MockSparseModel()
        embedder._model = model
        vectors = await embedder.query_embed(["a", "b"])
        assert len(vectors) == 2
        assert all(v.indices == [9] for v in vectors)


class TestFastEmbedBM25ConcurrentLoad:
    """Concurrent first-time embeds must share one model build, not race it."""

    async def test_concurrent_embeds_build_model_once(self) -> None:
        """A second concurrent embed waits for, and reuses, the first build.

        Regression guard: without locking, both calls would see ``self._model
        is None`` before either finishes building, and each would construct
        its own model.
        """
        build_calls = 0
        entered = threading.Event()
        release = threading.Event()

        def slow_build(_self: FastEmbedBM25Embedder) -> MockSparseModel:
            nonlocal build_calls
            build_calls += 1
            entered.set()
            release.wait(timeout=5)
            return MockSparseModel()

        embedder = FastEmbedBM25Embedder()
        with mock.patch.object(
            FastEmbedBM25Embedder,
            "_build_model",
            autospec=True,
            side_effect=slow_build,
        ):
            first = asyncio.create_task(embedder.embed(["a"]))
            await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(embedder.embed(["b"]))
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.gather(first, second)

        assert build_calls == 1


class TestFastEmbedBM25Tracing:
    """Tracing spans real model work."""

    async def test_concurrent_first_call_exports_single_model_load_span(
        self,
    ) -> None:
        """Two concurrent first embeds share one model_load span.

        Regression guard: a span opened before the lock (rather than inside
        the double-checked ``if self._model is None`` body) would export
        twice here, once per waiter.
        """
        provider, exporter = _tracing_provider()
        build_calls = 0
        entered = threading.Event()
        release = threading.Event()

        def slow_build(_self: FastEmbedBM25Embedder) -> MockSparseModel:
            nonlocal build_calls
            build_calls += 1
            entered.set()
            release.wait(timeout=5)
            return MockSparseModel()

        embedder = FastEmbedBM25Embedder(tracer=provider.get_tracer("test"))
        with mock.patch.object(
            FastEmbedBM25Embedder,
            "_build_model",
            autospec=True,
            side_effect=slow_build,
        ):
            first = asyncio.create_task(embedder.embed(["a"]))
            await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(embedder.embed(["b"]))
            await asyncio.sleep(0.05)
            release.set()
            await asyncio.gather(first, second)

        assert build_calls == 1
        spans = exporter.get_finished_spans()
        model_loads = [s for s in spans if s.name == "agrag.embedding.model_load"]
        assert len(model_loads) == 1
        assert (model_loads[0].attributes or {}).get("agrag.model") == (embedder.model)
        encodes = [s for s in spans if s.name == "agrag.embedding.encode"]
        assert len(encodes) == 2
        assert all((s.attributes or {}).get("agrag.text_count") == 1 for s in encodes)
