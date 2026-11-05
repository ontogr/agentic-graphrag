"""Cross-encoder loading is shared across loops and handles missing extras."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.evidence import rerank
from agrag.retrieval.settings import RetrievalSettings


class TestCrossEncoderReranker:
    """Model loading is shared across loops and reports missing extras."""

    def test_direct_construction_names_the_missing_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct construction identifies the extra and its install command."""

        def missing_module(_module_name: str) -> None:
            return None

        monkeypatch.setattr(rerank.importlib.util, "find_spec", missing_module)

        with pytest.raises(
            EmbeddingMissingExtraError,
            match=r"agentic-graphrag\[embed-local\]",
        ) as error:
            rerank.CrossEncoderReranker("cross-encoder/model")

        assert error.value.extra == "embed-local"

    def test_settings_factory_keeps_rerank_optional(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Configured rerank falls back to no reranker when the extra is absent."""

        def missing_module(_module_name: str) -> None:
            return None

        monkeypatch.setattr(rerank.importlib.util, "find_spec", missing_module)
        settings = RetrievalSettings(rerank_enabled=True, _env_file=None)

        assert rerank.reranker_from_settings(settings) is None

    def test_concurrent_loads_share_one_model_across_event_loops(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Concurrent loops build one shared model instance."""
        model = f"test-model-{uuid4()}"
        start = Barrier(3)
        first_build_started = Event()
        duplicate_build_started = Event()
        release_build = Event()
        builds = 0
        builds_lock = Lock()
        instance = object()

        def build(_model: str) -> object:
            nonlocal builds
            with builds_lock:
                builds += 1
                if builds > 1:
                    duplicate_build_started.set()
            first_build_started.set()
            if not release_build.wait(timeout=5):
                raise TimeoutError("model load was not released")
            return instance

        monkeypatch.setattr(rerank, "_build_cross_encoder", build)

        def load() -> object:
            start.wait(timeout=5)
            return asyncio.run(rerank._load_cross_encoder(model))

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(load) for _ in range(2)]
            start.wait(timeout=5)
            try:
                assert first_build_started.wait(timeout=5)
                duplicate_build_started.wait(timeout=1)
            finally:
                release_build.set()
            instances = [result.result(timeout=10) for result in results]

        assert builds == 1
        assert instances == [instance, instance]
