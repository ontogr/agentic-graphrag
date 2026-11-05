"""Cross-encoder loading is shared across loops and handles missing extras."""

import asyncio
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from importlib.machinery import ModuleSpec
from threading import Barrier, Event, Lock
from types import ModuleType
from uuid import uuid4

import pytest

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.evidence import rerank
from agrag.retrieval.settings import RetrievalSettings


def _install_cross_encoder(
    monkeypatch: pytest.MonkeyPatch, build: Callable[[str], object]
) -> None:
    """Provide a local CrossEncoder constructor for public reranker tests."""
    module = ModuleType("sentence_transformers")
    module.__dict__["CrossEncoder"] = build
    monkeypatch.setattr(
        rerank.importlib.util,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None),
    )
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)


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
        release_build = Event()
        builds = 0
        builds_lock = Lock()

        def build(_model: str) -> object:
            nonlocal builds
            with builds_lock:
                builds += 1
            first_build_started.set()
            if not release_build.wait(timeout=5):
                raise TimeoutError("model load was not released")
            return object()

        _install_cross_encoder(monkeypatch, build)
        reranker = rerank.CrossEncoderReranker(model)
        ready = [Event(), Event()]

        async def warm_up(index: int) -> None:
            task = asyncio.create_task(reranker.warm_up())
            await asyncio.sleep(0)
            ready[index].set()
            await task

        def load(index: int) -> None:
            start.wait(timeout=5)
            asyncio.run(warm_up(index))

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(load, index) for index in range(2)]
            start.wait(timeout=5)
            try:
                assert first_build_started.wait(timeout=5)
                assert all(event.wait(timeout=5) for event in ready)
            finally:
                release_build.set()
            for result in results:
                result.result(timeout=10)

        assert builds == 1

    def test_waiting_warm_up_does_not_occupy_executor_workers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pending model load leaves a worker for unrelated blocking work."""
        model = f"test-model-{uuid4()}"
        release_build = Event()
        build_started = Event()

        def build(_model: str) -> object:
            build_started.set()
            if not release_build.wait(timeout=5):
                raise TimeoutError("model load was not released")
            return object()

        async def exercise() -> bool:
            asyncio.get_running_loop().set_default_executor(
                ThreadPoolExecutor(max_workers=2)
            )
            _install_cross_encoder(monkeypatch, build)
            reranker = rerank.CrossEncoderReranker(model)
            first = asyncio.create_task(reranker.warm_up())
            assert await asyncio.wait_for(
                asyncio.to_thread(build_started.wait, 5), timeout=5
            )
            second = asyncio.create_task(reranker.warm_up())
            await asyncio.sleep(0)
            probe = asyncio.create_task(
                asyncio.to_thread(lambda: not release_build.is_set())
            )
            try:
                return await asyncio.wait_for(asyncio.shield(probe), timeout=1)
            except TimeoutError:
                return False
            finally:
                release_build.set()
                try:
                    await asyncio.gather(first, second)
                finally:
                    await probe

        assert asyncio.run(exercise())
