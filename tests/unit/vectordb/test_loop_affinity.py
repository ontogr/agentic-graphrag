"""Vector-store clients reject use outside their initializing event loop."""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import ModuleType

import pytest

from agrag.vectordb.errors import VectorStoreError
from agrag.vectordb.qdrant import QdrantSettings, QdrantVectorStore


def test_store_rejects_concurrent_initialization_from_another_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second loop cannot contend on the first loop's SDK lifecycle lock."""
    startup_started = Event()
    release_startup = Event()
    client_creations = 0
    client_closes = 0

    class FakeQdrantClient:
        def __init__(self, **_kwargs: object) -> None:
            nonlocal client_creations
            client_creations += 1

        async def get_collections(self) -> None:
            startup_started.set()
            if not await asyncio.to_thread(release_startup.wait, 5):
                raise TimeoutError("startup was not released")

        async def close(self) -> None:
            nonlocal client_closes
            client_closes += 1

    qdrant_client = ModuleType("qdrant_client")
    qdrant_client.__path__ = []
    qdrant_client.__dict__["AsyncQdrantClient"] = FakeQdrantClient
    http = ModuleType("qdrant_client.http")
    http.__path__ = []
    exceptions = ModuleType("qdrant_client.http.exceptions")

    class UnexpectedResponseError(Exception):
        pass

    exceptions.__dict__["UnexpectedResponse"] = UnexpectedResponseError
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http)
    monkeypatch.setitem(sys.modules, "qdrant_client.http.exceptions", exceptions)
    store = QdrantVectorStore(
        settings=QdrantSettings(_env_file=None, collection_prefix="unit")
    )
    asyncio.run(store.close())

    def initialize_and_close() -> None:
        async def run() -> None:
            await store.initialize()
            await store.close()

        asyncio.run(run())

    def reject_other_loop() -> None:
        async def run() -> None:
            with pytest.raises(VectorStoreError, match="event loop"):
                await asyncio.wait_for(store.initialize(), timeout=1)

        asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_loop = executor.submit(initialize_and_close)
        assert startup_started.wait(timeout=5)
        second_loop = executor.submit(reject_other_loop)
        try:
            second_loop.result(timeout=5)
        finally:
            release_startup.set()
        first_loop.result(timeout=10)

    assert client_creations == 1
    assert client_closes == 1
