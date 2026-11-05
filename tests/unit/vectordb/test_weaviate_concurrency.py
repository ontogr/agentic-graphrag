"""Weaviate setup handles the same collection created by another loop."""

import asyncio
import contextlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError, Lock
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import Distance, VectorKind
from agrag.vectordb.errors import VectorStoreError
from agrag.vectordb.weaviate import WeaviateSettings, WeaviateVectorStore


class _CollectionState:
    def __init__(self) -> None:
        self.exists = False
        self.description = ""
        self.create_failure: Exception | None = None
        self.absent_checks = 0
        self.guard = Lock()
        self.absent_barrier = Barrier(2)


class _WeaviateBaseError(Exception):
    pass


class _UnexpectedStatusCodeError(_WeaviateBaseError):
    def __init__(self, status_code: int, error: object) -> None:
        self.status_code = status_code
        self.error = error
        super().__init__(str(error))


class _FakeCollection:
    def __init__(self, state: _CollectionState) -> None:
        self._state = state
        self.config = SimpleNamespace(get=self._config)
        self.aggregate = SimpleNamespace(over_all=self._count)

    async def _config(self) -> SimpleNamespace:
        return SimpleNamespace(
            description=self._state.description,
            vector_config={
                "vector": SimpleNamespace(
                    vector_index_config=SimpleNamespace(distance_metric="cosine")
                )
            },
        )

    async def _count(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(total_count=0)


class _FakeCollections:
    def __init__(self, state: _CollectionState) -> None:
        self._state = state

    async def exists(self, _name: str) -> bool:
        with self._state.guard:
            exists = self._state.exists
            wait_for_other_check = not exists and self._state.absent_checks < 2
            if wait_for_other_check:
                self._state.absent_checks += 1
        if wait_for_other_check:
            with contextlib.suppress(BrokenBarrierError):
                await asyncio.to_thread(self._state.absent_barrier.wait, 0.5)
        return exists

    async def create(self, *, name: str, description: str, **_kwargs: object) -> None:
        with self._state.guard:
            if self._state.exists:
                raise _UnexpectedStatusCodeError(
                    422,
                    {"error": [{"message": f"class name {name} already exists"}]},
                )
            self._state.exists = True
            self._state.description = description
            failure = self._state.create_failure
        if failure is not None:
            raise failure

    def use(self, _name: str) -> _FakeCollection:
        return _FakeCollection(self._state)


class _FakeClient:
    def __init__(self, state: _CollectionState) -> None:
        self.collections = _FakeCollections(state)

    async def connect(self) -> None:
        return None

    async def is_ready(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def _install_weaviate(monkeypatch: pytest.MonkeyPatch, state: _CollectionState) -> None:
    """Replace the optional SDK boundary with a shared test service."""
    weaviate = ModuleType("weaviate")
    weaviate.__path__ = []
    weaviate.__dict__.update(
        {
            "use_async_with_custom": lambda **_kwargs: _FakeClient(state),
            "use_async_with_weaviate_cloud": lambda **_kwargs: _FakeClient(state),
        }
    )
    classes = ModuleType("weaviate.classes")
    classes.__path__ = []
    config = ModuleType("weaviate.classes.config")
    config.__dict__.update(
        {
            "Configure": SimpleNamespace(
                Vectors=SimpleNamespace(self_provided=lambda **_kwargs: object()),
                VectorIndex=SimpleNamespace(hnsw=lambda **_kwargs: object()),
            ),
            "DataType": SimpleNamespace(TEXT_ARRAY="text_array", TEXT="text"),
            "Property": lambda **kwargs: kwargs,
            "Tokenization": SimpleNamespace(FIELD="field"),
            "VectorDistances": str,
        }
    )
    init = ModuleType("weaviate.classes.init")
    init.__dict__["Auth"] = object()
    exceptions = ModuleType("weaviate.exceptions")
    exceptions.__dict__.update(
        {
            "WeaviateBaseError": _WeaviateBaseError,
            "UnexpectedStatusCodeError": _UnexpectedStatusCodeError,
        }
    )
    weaviate.__dict__["classes"] = classes
    weaviate.__dict__["exceptions"] = exceptions
    for name, module in (
        ("weaviate", weaviate),
        ("weaviate.classes", classes),
        ("weaviate.classes.config", config),
        ("weaviate.classes.init", init),
        ("weaviate.exceptions", exceptions),
    ):
        monkeypatch.setitem(sys.modules, name, module)


def test_ensure_collection_accepts_a_concurrent_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both loops validate one collection when creation overlaps."""
    state = _CollectionState()
    _install_weaviate(monkeypatch, state)
    prefix = f"looprace_{uuid4().hex}"

    async def ensure_collection() -> tuple[int, Distance] | None:
        store = WeaviateVectorStore(
            settings=WeaviateSettings(_env_file=None, collection_prefix=prefix)
        )
        try:
            await store.ensure_collection(
                VectorKind.ENTITY, dimensions=3, distance=Distance.COSINE
            )
            info = await store.collection_info(VectorKind.ENTITY, exact_count=False)
            return None if info is None else (info.dimensions, info.distance)
        finally:
            await store.close()

    def run() -> tuple[int, Distance] | None:
        return asyncio.run(ensure_collection())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [executor.submit(run) for _ in range(2)]
        assert [result.result(timeout=10) for result in results] == [
            (3, Distance.COSINE),
            (3, Distance.COSINE),
        ]

    assert state.exists
    assert json.loads(state.description.split(":", maxsplit=1)[1]) == {
        "dimensions": 3,
        "prefix": prefix,
    }


@pytest.mark.parametrize(
    "failure",
    [
        _UnexpectedStatusCodeError(401, {"error": [{"message": "unauthorized"}]}),
        _UnexpectedStatusCodeError(422, {"error": [{"message": "invalid schema"}]}),
        _WeaviateBaseError("connection failed"),
    ],
)
def test_ensure_collection_propagates_non_duplicate_create_errors(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """Only a duplicate-class response is accepted as a concurrent create."""
    state = _CollectionState()
    state.create_failure = failure
    _install_weaviate(monkeypatch, state)
    store = WeaviateVectorStore(
        settings=WeaviateSettings(
            _env_file=None, collection_prefix=f"looprace_{uuid4().hex}"
        )
    )

    async def exercise() -> None:
        try:
            with pytest.raises(VectorStoreError):
                await store.ensure_collection(
                    VectorKind.ENTITY, dimensions=3, distance=Distance.COSINE
                )
        finally:
            await store.close()

    asyncio.run(exercise())
