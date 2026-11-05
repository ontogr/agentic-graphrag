"""Loop-local locks must serialize work without crossing event loops."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from weakref import WeakKeyDictionary

from agrag.common._asyncio_locks import _get_loop_lock, _LoopLockRegistry


def test_loop_lock_keeps_same_loop_serialization_during_other_loop_use(  # noqa: PLR0915
) -> None:
    """An intervening loop must not replace a lock used by active callers."""
    registry: _LoopLockRegistry = WeakKeyDictionary()
    key = "collection"
    loop_ready = Event()
    first_loop_ref: list[asyncio.AbstractEventLoop] = []
    second_loop_ref: list[asyncio.AbstractEventLoop] = []
    first_loop_ready: list[asyncio.Event] = []
    second_loop_release: list[asyncio.Event] = []
    active_calls = 0
    active_counts: list[int] = []

    async def first_loop() -> None:
        loop = asyncio.get_running_loop()
        ready = asyncio.Event()
        second_call_attempted = asyncio.Event()
        first_loop_ref.append(loop)
        first_loop_ready.append(ready)
        loop_ready.set()

        async def first_call() -> None:
            nonlocal active_calls
            async with _get_loop_lock(registry, key):
                active_calls += 1
                active_counts.append(active_calls)
                await asyncio.wait_for(second_call_attempted.wait(), timeout=5)
                active_calls -= 1

        async def second_call() -> None:
            nonlocal active_calls
            await asyncio.wait_for(ready.wait(), timeout=5)
            lock = _get_loop_lock(registry, key)
            acquire = asyncio.create_task(lock.acquire())
            await asyncio.sleep(0)
            second_call_attempted.set()
            second_loop_ref[0].call_soon_threadsafe(second_loop_release[0].set)
            await asyncio.wait_for(acquire, timeout=5)
            try:
                active_calls += 1
                active_counts.append(active_calls)
                active_calls -= 1
            finally:
                lock.release()

        await asyncio.gather(first_call(), second_call())

    async def second_loop() -> None:
        loop = first_loop_ref[0]
        ready = first_loop_ready[0]
        release = asyncio.Event()
        second_loop_ref.append(asyncio.get_running_loop())
        second_loop_release.append(release)
        first_call_entered = asyncio.Event()

        async def first_call() -> None:
            async with _get_loop_lock(registry, key):
                first_call_entered.set()
                await asyncio.wait_for(release.wait(), timeout=5)

        async def second_call() -> None:
            await asyncio.wait_for(first_call_entered.wait(), timeout=5)
            lock = _get_loop_lock(registry, key)
            acquire = asyncio.create_task(lock.acquire())
            await asyncio.sleep(0)
            loop.call_soon_threadsafe(ready.set)
            await asyncio.wait_for(acquire, timeout=5)
            lock.release()

        await asyncio.gather(first_call(), second_call())

    def run_second_loop() -> None:
        loop_ready.wait(timeout=5)
        asyncio.run(second_loop())

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_result = executor.submit(asyncio.run, first_loop())
        second_result = executor.submit(run_second_loop)
        first_result.result(timeout=10)
        second_result.result(timeout=10)

    assert active_counts == [1, 1]
